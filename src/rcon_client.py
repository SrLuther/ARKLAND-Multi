"""
Cliente RCON (Source RCON Protocol) para servidores ARK: Survival Evolved.

Protocolo:
  Cada pacote: size(4) + id(4) + type(4) + body(null-term) + empty(null-term)
  Tipos: AUTH=3, AUTH_RESPONSE=2, EXECCOMMAND=2, RESPONSE_VALUE=0

Características:
  - Thread-safe via Lock
  - Auto-reconexão em send_command
  - Retry configurable via send_command_with_retry()
  - Ping leve para keep-alive
  - Rastreamento de idle time e estatísticas
"""
from __future__ import annotations

import socket
import struct
import threading
import time
from typing import Callable, Optional

_PACKET_TYPE_AUTH          = 3
_PACKET_TYPE_AUTH_RESPONSE = 2
_PACKET_TYPE_EXECCOMMAND   = 2
_PACKET_TYPE_RESPONSE      = 0

_MAX_PACKET_SIZE   = 4096
_RESPONSE_TIMEOUT  = 10.0   # timeout geral de leitura do socket
_CONNECT_TIMEOUT   = 5.0    # timeout de TCP connect
_EXEC_TIMEOUT      = 5.0    # timeout aguardando resposta de comando
_PING_TIMEOUT      = 3.0    # timeout para ping de keep-alive
_MAX_RETRIES       = 3      # tentativas padrão em send_command_with_retry
_RETRY_DELAY       = 1.0    # segundos entre tentativas


class RconError(Exception):
    pass


class RconAuthError(RconError):
    pass


class RconConnectionError(RconError):
    pass


class RconClient:
    """Cliente RCON thread-safe para servidores ARK: Survival Evolved.

    Uso básico::
        client = RconClient("127.0.0.1", 27020, "senha")
        client.connect()
        ok, resp = client.send_command_safe("ListPlayers")
        client.disconnect()

    Com retry automático::
        ok, resp = client.send_command_with_retry("SaveWorld", retries=3)
    """

    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        on_log: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        if not host or not host.strip():
            raise ValueError("Host RCON não pode ser vazio.")
        if not (1 <= port <= 65535):
            raise ValueError(f"Porta RCON inválida: {port}. Use um valor entre 1 e 65535.")
        from .rcon_util import sanitize_rcon_password
        password = sanitize_rcon_password(password)
        if not password:
            raise ValueError("Senha RCON não pode ser vazia.")

        self._host     = host.strip()
        self._port     = port
        self._password = password
        self._on_log   = on_log or (lambda m, lvl: None)

        self._sock: Optional[socket.socket] = None
        self._connected = False
        self._lock      = threading.Lock()
        self._pkt_id    = 0

        # Rastreamento de estatísticas
        self._connected_at:         Optional[float] = None   # monotonic timestamp
        self._last_used_at:         Optional[float] = None   # monotonic timestamp
        self._total_commands_sent:  int = 0
        self._consecutive_failures: int = 0

    # ── Interface pública ─────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def connected_since(self) -> Optional[float]:
        """Timestamp monotônico de quando a conexão foi estabelecida, ou None."""
        return self._connected_at

    @property
    def connected_seconds(self) -> float:
        """Segundos desde a última conexão bem-sucedida (0 se desconectado)."""
        if self._connected_at is None:
            return 0.0
        return time.monotonic() - self._connected_at

    @property
    def idle_seconds(self) -> float:
        """Segundos desde o último comando enviado (∞ se nunca usado)."""
        if self._last_used_at is None:
            return float("inf")
        return time.monotonic() - self._last_used_at

    def connect(self) -> None:
        """Conecta e autentica. Lança RconAuthError ou RconConnectionError."""
        with self._lock:
            self._connect_locked()

    def disconnect(self) -> None:
        """Fecha a conexão com segurança. Nunca lança exceção."""
        with self._lock:
            self._disconnect_locked()

    def ping(self) -> bool:
        """Verifica se a conexão está viva enviando um pacote vazio.

        Retorna True se respondeu, False se a conexão falhou.
        Nunca lança exceções. Ideal para keep-alive.
        """
        try:
            with self._lock:
                if not self._connected or self._sock is None:
                    return False
                old_to = self._sock.gettimeout()
                self._sock.settimeout(_PING_TIMEOUT)
                try:
                    cmd_id = self._next_id()
                    self._send_packet(cmd_id, _PACKET_TYPE_EXECCOMMAND, "")
                    deadline = time.monotonic() + _PING_TIMEOUT
                    while time.monotonic() < deadline:
                        try:
                            pkt_id, _, _ = self._recv_packet()
                            if pkt_id == cmd_id:
                                self._last_used_at = time.monotonic()
                                return True
                        except socket.timeout:
                            break
                    return False
                except (OSError, struct.error, RconError):
                    self._disconnect_locked()
                    return False
                finally:
                    if self._sock:
                        try:
                            self._sock.settimeout(old_to)
                        except OSError:
                            pass
        except Exception:
            return False

    def send_command(self, command: str) -> str:
        """Envia um comando RCON e retorna a resposta.
        Reconecta automaticamente se a conexão caiu. Lança RconError em falha."""
        with self._lock:
            if not self._connected:
                self._connect_locked()
            return self._exec_locked(command)

    def send_command_safe(self, command: str) -> tuple[bool, str]:
        """Versão segura de send_command — nunca lança exceção.

        Retorna (True, resposta) em sucesso ou (False, mensagem_de_erro) em falha.
        """
        try:
            result = self.send_command(command)
            self._consecutive_failures = 0
            return True, result
        except RconError as e:
            self._connected = False
            self._consecutive_failures += 1
            return False, str(e)
        except Exception as e:
            self._connected = False
            self._consecutive_failures += 1
            return False, f"Erro inesperado: {e}"

    def send_command_with_retry(
        self,
        command: str,
        retries: int = _MAX_RETRIES,
        retry_delay: float = _RETRY_DELAY,
    ) -> tuple[bool, str]:
        """Envia comando com múltiplas tentativas e reconexão entre elas.

        Args:
            command: Comando RCON a enviar.
            retries: Número máximo de tentativas (≥1).
            retry_delay: Segundos de espera entre tentativas.

        Returns:
            (True, resposta) se alguma tentativa teve sucesso.
            (False, último_erro) se todas falharam.
        """
        retries = max(1, retries)
        last_error = "Nenhuma tentativa executada."

        for attempt in range(1, retries + 1):
            ok, result = self.send_command_safe(command)
            if ok:
                self._consecutive_failures = 0
                return True, result

            last_error = result
            self._on_log(
                f"[RCON] Tentativa {attempt}/{retries} falhou: {result}", "warning"
            )

            if attempt < retries:
                # Espera e tenta reconectar antes da próxima tentativa
                if retry_delay > 0:
                    time.sleep(retry_delay)
                try:
                    with self._lock:
                        self._connect_locked()
                    self._on_log(
                        f"[RCON] Reconectado — tentando novamente ({attempt + 1}/{retries})",
                        "info",
                    )
                except RconError as e:
                    last_error = str(e)

        self._consecutive_failures += 1
        return False, f"Falhou após {retries} tentativa(s). Último erro: {last_error}"

    # ── Internals ─────────────────────────────────────────────────────────────

    def _next_id(self) -> int:
        self._pkt_id = (self._pkt_id % 2_147_483_647) + 1
        return self._pkt_id

    def _connect_locked(self) -> None:
        self._disconnect_locked()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(_CONNECT_TIMEOUT)
            sock.connect((self._host, self._port))
            sock.settimeout(_RESPONSE_TIMEOUT)
            self._sock = sock
        except OSError as exc:
            raise RconConnectionError(
                f"Não foi possível conectar a {self._host}:{self._port} — {exc}"
            ) from exc

        # Autenticação
        auth_id = self._next_id()
        self._send_packet(auth_id, _PACKET_TYPE_AUTH, self._password)
        resp_id, resp_type, _ = self._recv_packet()

        # O ARK pode mandar um RESPONSE_VALUE vazio antes da AUTH_RESPONSE
        if resp_type == _PACKET_TYPE_RESPONSE:
            resp_id, resp_type, _ = self._recv_packet()

        if resp_id == -1 or resp_id != auth_id:
            self._disconnect_locked()
            raise RconAuthError("Falha na autenticação RCON. Verifique a senha.")

        now = time.monotonic()
        self._connected    = True
        self._connected_at = now
        self._last_used_at = now
        self._consecutive_failures = 0
        self._on_log(f"RCON conectado a {self._host}:{self._port}", "info")

    def _disconnect_locked(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        self._connected    = False
        self._connected_at = None

    def _exec_locked(self, command: str) -> str:
        cmd_id = self._next_id()
        self._total_commands_sent += 1
        self._send_packet(cmd_id, _PACKET_TYPE_EXECCOMMAND, command)
        self._last_used_at = time.monotonic()

        # ARK envia resposta em pacote único por comando.
        # Pacotes com IDs diferentes (respostas orfãs de comandos anteriores) são descartados.
        # Comandos sem resposta (SaveWorld, Broadcast, DoExit…) retornam vazio após o timeout.
        response_parts: list[str] = []
        self._sock.settimeout(_EXEC_TIMEOUT)  # type: ignore[union-attr]
        try:
            deadline = time.monotonic() + _EXEC_TIMEOUT
            while time.monotonic() < deadline:
                try:
                    pkt_id, _pkt_type, body = self._recv_packet()
                except socket.timeout:
                    break
                except (OSError, struct.error) as exc:
                    self._disconnect_locked()
                    raise RconConnectionError(f"Erro ao receber resposta RCON: {exc}") from exc
                if pkt_id == cmd_id:
                    response_parts.append(body)
                    break  # ARK: uma resposta por comando (ASE)
                # descarta pacote com ID inesperado (resposta orfã) e continua
        finally:
            if self._sock:
                try:
                    self._sock.settimeout(_RESPONSE_TIMEOUT)
                except OSError:
                    pass

        return "".join(response_parts).strip()

    def _send_packet(self, pkt_id: int, pkt_type: int, body: str) -> None:
        encoded = body.encode("utf-8", errors="replace")
        # size = id(4) + type(4) + body + null-terminator + empty-string null
        size   = 4 + 4 + len(encoded) + 2
        packet = struct.pack("<iii", size, pkt_id, pkt_type) + encoded + b"\x00\x00"
        try:
            self._sock.sendall(packet)  # type: ignore[union-attr]
        except OSError as exc:
            self._disconnect_locked()
            raise RconConnectionError(f"Erro ao enviar pacote RCON: {exc}") from exc

    def _recv_packet(self) -> tuple[int, int, str]:
        size_data = self._recv_exact(4)
        (size,)   = struct.unpack("<i", size_data)
        if size < 10 or size > _MAX_PACKET_SIZE * 16:
            raise RconConnectionError(f"Tamanho de pacote inválido: {size}")
        payload  = self._recv_exact(size)
        pkt_id, pkt_type = struct.unpack("<ii", payload[:8])
        body = payload[8:-2].decode("utf-8", errors="replace")
        return pkt_id, pkt_type, body

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))  # type: ignore[union-attr]
            if not chunk:
                raise RconConnectionError("Conexão encerrada pelo servidor.")
            buf += chunk
        return buf
