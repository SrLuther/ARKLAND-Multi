"""
Cliente RCON (Source RCON Protocol) para servidores ARK: Survival Evolved.

Protocolo:
  Cada pacote: size(4) + id(4) + type(4) + body(null-term) + empty(null-term)
  Tipos: AUTH=3, AUTH_RESPONSE=2, EXECCOMMAND=2, RESPONSE_VALUE=0
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

_MAX_PACKET_SIZE = 4096
_RESPONSE_TIMEOUT = 10.0
_CONNECT_TIMEOUT  = 5.0


class RconError(Exception):
    pass


class RconAuthError(RconError):
    pass


class RconConnectionError(RconError):
    pass


class RconClient:
    """Cliente RCON thread-safe para servidores ARK."""

    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        on_log: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self._host = host
        self._port = port
        self._password = password
        self._on_log = on_log or (lambda m, lvl: None)
        self._sock: Optional[socket.socket] = None
        self._connected = False
        self._lock = threading.Lock()
        self._pkt_id = 0

    # ── Interface pública ─────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        """Conecta e autentica. Lança RconAuthError ou RconConnectionError."""
        with self._lock:
            self._connect_locked()

    def disconnect(self) -> None:
        with self._lock:
            self._disconnect_locked()

    def send_command(self, command: str) -> str:
        """Envia um comando RCON e retorna a resposta."""
        with self._lock:
            if not self._connected:
                self._connect_locked()
            return self._exec_locked(command)

    def send_command_safe(self, command: str) -> tuple[bool, str]:
        """Versão segura — retorna (ok, resposta_ou_erro)."""
        try:
            return True, self.send_command(command)
        except RconError as e:
            self._connected = False
            return False, str(e)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _next_id(self) -> int:
        self._pkt_id = (self._pkt_id % 2147483647) + 1
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
            raise RconConnectionError(f"Não foi possível conectar a {self._host}:{self._port} — {exc}") from exc

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

        self._connected = True
        self._on_log(f"RCON conectado a {self._host}:{self._port}", "info")

    def _disconnect_locked(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        self._connected = False

    def _exec_locked(self, command: str) -> str:
        cmd_id = self._next_id()
        self._send_packet(cmd_id, _PACKET_TYPE_EXECCOMMAND, command)

        # Enviar um segundo pacote "vazio" como sentinel para detectar fim da resposta
        sentinel_id = self._next_id()
        self._send_packet(sentinel_id, _PACKET_TYPE_RESPONSE, "")

        response_parts: list[str] = []
        deadline = time.monotonic() + _RESPONSE_TIMEOUT
        while time.monotonic() < deadline:
            try:
                pkt_id, pkt_type, body = self._recv_packet()
            except (OSError, struct.error) as exc:
                self._disconnect_locked()
                raise RconConnectionError(f"Erro ao receber resposta RCON: {exc}") from exc

            if pkt_id == sentinel_id:
                break
            if pkt_id == cmd_id:
                response_parts.append(body)

        return "".join(response_parts).strip()

    def _send_packet(self, pkt_id: int, pkt_type: int, body: str) -> None:
        encoded = body.encode("utf-8", errors="replace")
        # size = id(4) + type(4) + body + null + null
        size = 4 + 4 + len(encoded) + 2
        packet = struct.pack("<iii", size, pkt_id, pkt_type) + encoded + b"\x00\x00"
        try:
            self._sock.sendall(packet)  # type: ignore[union-attr]
        except OSError as exc:
            self._disconnect_locked()
            raise RconConnectionError(f"Erro ao enviar pacote RCON: {exc}") from exc

    def _recv_packet(self) -> tuple[int, int, str]:
        size_data = self._recv_exact(4)
        (size,) = struct.unpack("<i", size_data)
        if size < 10 or size > _MAX_PACKET_SIZE * 16:
            raise RconConnectionError(f"Tamanho de pacote inválido: {size}")
        payload = self._recv_exact(size)
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
