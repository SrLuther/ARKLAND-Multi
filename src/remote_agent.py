"""
Agente HTTP do ARKLAND - Server Manager.

Quando habilitado, sobe um servidor HTTP leve na porta configurada.
Permite que outra instância do app controle este motor remotamente.

Endpoints (todos exigem header  Authorization: Bearer <token>):
  GET  /info                    → Informações da instância (nome, versão, servidores)
  GET  /servers                 → Lista detalhada de servidores com status
  POST /server/{id}/start       → Inicia o servidor
  POST /server/{id}/stop        → Para o servidor graciosamente
  POST /server/{id}/stop/force  → Para forçado (taskkill)
  POST /server/{id}/restart     → Reinicia o servidor
  GET  /server/{id}/logs        → Últimas N linhas de log (?n=200)
  POST /server/{id}/rcon        → Executa comando RCON (body: {"command": "..."})
  GET  /logs                    → Últimas 200 linhas do log do agente (legado)
  GET  /status                  → Status do sync engine (legado)
  POST /sync/start              → Inicia sincronização
  POST /sync/stop               → Para sincronização
  POST /sync/force              → Força ciclo de sincronização

  Filesystem remoto (sync entre máquinas):
  GET  /fs/list?root=<path>          → Lista arquivos [{rel, mtime, size}]
  GET  /fs/read?root=<path>&rel=<r>  → Lê arquivo (bytes)
  POST /fs/write?root=<path>&rel=<r> → Grava arquivo (body = bytes brutos)
"""
import base64
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from .sync_engine import SyncEngine
    from .server_manager import ServerManager

_MAX_LOG_LINES = 200


# ── Helpers de código de identidade ──────────────────────────────────────────

def local_ip() -> str:
    """Retorna o IP local da máquina (melhor esforço)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def make_identity_code(name: str, host: str, port: int, token: str) -> str:
    """Gera o código de identidade desta instância para compartilhar com outra máquina."""
    payload = json.dumps(
        {"n": name, "h": host, "p": port, "t": token},
        separators=(",", ":"),
    )
    return base64.urlsafe_b64encode(payload.encode()).decode()


def parse_identity_code(code: str) -> Dict[str, Any]:
    """Decodifica um código de identidade. Retorna dict com chaves n, h, p, t."""
    try:
        data = json.loads(base64.urlsafe_b64decode(code.strip().encode()).decode())
    except Exception as exc:
        raise ValueError("Código de identidade inválido") from exc
    if not all(k in data for k in ("n", "h", "p", "t")):
        raise ValueError("Código de identidade incompleto — chaves ausentes")
    if not isinstance(data["p"], int):
        raise ValueError("Porta inválida no código de identidade")
    return data


# ═════════════════════════════════════════════════════════════════════════════
class RemoteAgent:
    """Servidor HTTP leve que expõe controle total desta instância do app."""

    def __init__(
        self,
        server_manager: "ServerManager",
        sync_engine: Optional["SyncEngine"] = None,
        port: int = 32440,
        token: str = "",
        name: str = "",
    ) -> None:
        self._server_manager = server_manager
        self._engine = sync_engine
        self._port = port
        self._token = token
        self._name = name
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._log_buffer: deque[dict] = deque(maxlen=_MAX_LOG_LINES)
        self._running = False
        self._pending_pairs: dict = {}  # {req_id: {name, host, approved, token, ts}}
        self.pair_request_callback = None  # callable(req_id, name, host)

    # ── Interface pública ─────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running and (self._thread is not None and self._thread.is_alive())

    def approve_pair(self, req_id: str) -> None:
        """Aprova uma solicitação de pareamento pendente."""
        if req_id in self._pending_pairs:
            self._pending_pairs[req_id]["approved"] = True
            self._pending_pairs[req_id]["token"] = self._token

    def deny_pair(self, req_id: str) -> None:
        """Nega uma solicitação de pareamento pendente."""
        if req_id in self._pending_pairs:
            self._pending_pairs[req_id]["approved"] = False

    def push_log(self, message: str, level: str = "info") -> None:
        """Chamado pelo app para alimentar o buffer de logs remoto."""
        from datetime import datetime
        self._log_buffer.append({
            "time": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "level": level,
            "message": message,
        })

    def start(self) -> None:
        if self._running:
            return
        agent = self

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # silencia log padrão
                pass

            def _auth(self) -> bool:
                if not agent._token:
                    return False
                header = self.headers.get("Authorization", "")
                return header == f"Bearer {agent._token}"

            def _json(self, code: int, data: object) -> None:
                body = json.dumps(data, ensure_ascii=False).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _read_body(self) -> dict:
                length = int(self.headers.get("Content-Length", 0))
                if length > 0:
                    raw = self.rfile.read(length)
                    try:
                        return json.loads(raw.decode())
                    except Exception:
                        pass
                return {}

            def _inst_info(self, inst: Any) -> dict:
                return {
                    "id":     inst.config.id,
                    "name":   inst.config.name,
                    "map":    inst.config.map,
                    "port":   inst.config.port,
                    "status": inst.status,
                    "uptime": inst.uptime,
                    "pid":    inst.pid,
                }

            def do_GET(self) -> None:
                path = self.path.split("?")[0]  # strip query string

                # Endpoints públicos — não exigem autenticação
                if path == "/ping":
                    self._json(200, {"ok": True})
                    return

                if path == "/pair/status":
                    qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                    req_id = qs.get("id", [None])[0]
                    if req_id and req_id in agent._pending_pairs:
                        pair = agent._pending_pairs[req_id]
                        # Expira após 120 s sem resposta
                        if time.time() - pair.get("ts", 0) > 120:
                            del agent._pending_pairs[req_id]
                            self._json(200, {"status": "expired"})
                            return
                        if pair["approved"] is True:
                            self._json(200, {"status": "approved", "token": pair["token"]})
                            del agent._pending_pairs[req_id]
                        elif pair["approved"] is False:
                            self._json(200, {"status": "denied"})
                            del agent._pending_pairs[req_id]
                        else:
                            self._json(200, {"status": "pending"})
                    else:
                        self._json(200, {"status": "not_found"})
                    return

                if not self._auth():
                    self._json(401, {"error": "Não autorizado"})
                    return

                if path == "/info":
                    from .version import APP_VERSION
                    instances = agent._server_manager.get_all_instances()
                    self._json(200, {
                        "name":    agent._name,
                        "version": APP_VERSION,
                        "servers": [self._inst_info(i) for i in instances],
                    })

                elif path == "/servers":
                    instances = agent._server_manager.get_all_instances()
                    self._json(200, {"servers": [self._inst_info(i) for i in instances]})

                elif path.startswith("/server/") and path.endswith("/logs"):
                    parts = path.split("/")  # ['', 'server', '{id}', 'logs']
                    if len(parts) == 4:
                        sid = parts[2]
                        inst = agent._server_manager.get_instance(sid)
                        if inst:
                            try:
                                n = int(self.path.split("?n=")[1])
                            except Exception:
                                n = 200
                            self._json(200, {"logs": inst.log_buffer[-n:]})
                        else:
                            self._json(404, {"error": "Servidor não encontrado"})
                    else:
                        self._json(404, {"error": "Endpoint não encontrado"})

                elif path == "/logs":
                    self._json(200, {"logs": list(agent._log_buffer)})

                elif path == "/status":
                    info: dict = {"remote_agent": True, "name": agent._name}
                    if agent._engine:
                        info["sync_running"] = agent._engine.is_running
                        info["sync_stats"]   = agent._engine.stats
                    self._json(200, info)

                elif path == "/fs/list":
                    qs   = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                    root = urllib.parse.unquote(qs.get("root", [""])[0]).strip()
                    if not root or not os.path.isdir(root):
                        self._json(400, {"error": "Pasta inválida ou não encontrada"})
                        return
                    root_path = Path(root).resolve()
                    files: list = []
                    try:
                        for f in root_path.rglob("*"):
                            if f.is_file():
                                rel = f.relative_to(root_path).as_posix()
                                st  = f.stat()
                                files.append({"rel": rel, "mtime": st.st_mtime, "size": st.st_size})
                    except (PermissionError, OSError) as exc:
                        self._json(500, {"error": str(exc)})
                        return
                    self._json(200, {"files": files})

                elif path == "/fs/read":
                    qs   = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                    root = urllib.parse.unquote(qs.get("root", [""])[0]).strip()
                    rel  = urllib.parse.unquote(qs.get("rel",  [""])[0]).strip()
                    if not root or not rel:
                        self._json(400, {"error": "Parâmetros 'root' e 'rel' são obrigatórios"})
                        return
                    try:
                        root_resolved = Path(root).resolve()
                        target = (root_resolved / rel).resolve()
                        target.relative_to(root_resolved)  # garante sem path traversal
                    except (ValueError, OSError):
                        self._json(403, {"error": "Acesso negado"})
                        return
                    if not target.is_file():
                        self._json(404, {"error": "Arquivo não encontrado"})
                        return
                    try:
                        data = target.read_bytes()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/octet-stream")
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                    except (OSError, IOError) as exc:
                        self._json(500, {"error": str(exc)})

                else:
                    self._json(404, {"error": "Endpoint não encontrado"})

            def do_POST(self) -> None:
                path = self.path.split("?")[0]

                # Endpoint público — solicitação de pareamento LAN
                if path == "/pair/request":
                    body = self._read_body()
                    name = str(body.get("name", "Desconhecido"))[:64]
                    host = self.client_address[0]
                    req_id = uuid.uuid4().hex[:8]
                    agent._pending_pairs[req_id] = {
                        "name": name, "host": host,
                        "approved": None, "token": None,
                        "ts": time.time(),
                    }
                    if agent.pair_request_callback:
                        agent.pair_request_callback(req_id, name, host)
                    self._json(200, {"request_id": req_id})
                    return

                if not self._auth():
                    self._json(401, {"error": "Não autorizado"})
                    return

                # ── /server/{id}/… ────────────────────────────────────────────
                if path.startswith("/server/"):
                    parts = path.split("/")  # ['', 'server', '{id}', 'action', ...]
                    if len(parts) >= 4:
                        sid    = parts[2]
                        action = "/".join(parts[3:])
                        inst   = agent._server_manager.get_instance(sid)
                        if not inst:
                            self._json(404, {"error": "Servidor não encontrado"})
                            return

                        if action == "start":
                            ok = agent._server_manager.start_server(sid)
                            self._json(200, {"ok": ok})

                        elif action == "stop":
                            ok = agent._server_manager.stop_server(sid, force=False)
                            self._json(200, {"ok": ok})

                        elif action == "stop/force":
                            ok = agent._server_manager.stop_server(sid, force=True)
                            self._json(200, {"ok": ok})

                        elif action == "restart":
                            agent._server_manager.restart_server(sid)
                            self._json(200, {"ok": True})

                        elif action == "rcon":
                            body = self._read_body()
                            cmd  = body.get("command", "").strip()
                            if not cmd:
                                self._json(400, {"error": "Campo 'command' obrigatório"})
                                return
                            if inst.status != "running":
                                self._json(409, {"error": "Servidor não está rodando"})
                                return
                            try:
                                from .rcon_client import RconClient
                                client = RconClient(
                                    host="127.0.0.1",
                                    port=inst.config.rcon_port,
                                    password=inst.config.admin_password,
                                )
                                with client:
                                    resp = client.send(cmd)
                                self._json(200, {"ok": True, "response": resp})
                            except Exception as exc:
                                self._json(500, {"error": str(exc)})
                        else:
                            self._json(404, {"error": "Ação não reconhecida"})
                    else:
                        self._json(400, {"error": "Path inválido"})
                    return

                # ── /fs/write ─────────────────────────────────────────────────
                elif path == "/fs/write":
                    qs   = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                    root = urllib.parse.unquote(qs.get("root", [""])[0]).strip()
                    rel  = urllib.parse.unquote(qs.get("rel",  [""])[0]).strip()
                    if not root or not rel:
                        self._json(400, {"error": "Parâmetros 'root' e 'rel' são obrigatórios"})
                        return
                    try:
                        root_resolved = Path(root).resolve()
                        target = (root_resolved / rel).resolve()
                        target.relative_to(root_resolved)  # garante sem path traversal
                    except (ValueError, OSError):
                        self._json(403, {"error": "Acesso negado"})
                        return
                    length = int(self.headers.get("Content-Length", 0))
                    if length <= 0:
                        self._json(400, {"error": "Body vazio"})
                        return
                    raw = self.rfile.read(length)
                    try:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(raw)
                        self._json(200, {"ok": True})
                    except (OSError, IOError) as exc:
                        self._json(500, {"error": str(exc)})
                    return

                # ── Sync legado ───────────────────────────────────────────────
                if agent._engine:
                    if path == "/sync/start":
                        agent._engine.start()
                        self._json(200, {"ok": True, "action": "start"})
                    elif path == "/sync/stop":
                        agent._engine.stop()
                        self._json(200, {"ok": True, "action": "stop"})
                    elif path == "/sync/force":
                        agent._engine.sync_once()
                        self._json(200, {"ok": True, "action": "force"})
                    else:
                        self._json(404, {"error": "Endpoint não encontrado"})
                else:
                    self._json(404, {"error": "Endpoint não encontrado"})

        try:
            self._server = HTTPServer(("0.0.0.0", self._port), _Handler)
            self._running = True
            self._thread = threading.Thread(
                target=self._server.serve_forever,
                daemon=True,
                name="ArkRemoteAgent",
            )
            self._thread.start()
        except OSError:
            self._running = False
            raise

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None
        self._running = False


# ═════════════════════════════════════════════════════════════════════════════
class RemoteClient:
    """Cliente HTTP para controlar uma instância remota do ARKLAND."""

    def __init__(self, host: str, port: int, token: str, timeout: float = 8.0) -> None:
        self._base    = f"http://{host}:{port}"
        self._token   = token
        self._timeout = timeout

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        url  = self._base + path
        data = json.dumps(body).encode() if body else None
        req  = urllib.request.Request(
            url, data=data, method=method,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type":  "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            try:
                return json.loads(exc.read().decode())
            except Exception:
                return {"error": f"HTTP {exc.code}"}
        except Exception as exc:
            return {"error": str(exc)}

    # ── API ───────────────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Verifica alcance sem autenticação. Retorna True se o agente responder."""
        url = self._base + "/ping"
        try:
            with urllib.request.urlopen(url, timeout=3.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def get_info(self) -> dict:
        return self._request("GET", "/info")

    def get_servers(self) -> dict:
        return self._request("GET", "/servers")

    def start_server(self, sid: str) -> dict:
        return self._request("POST", f"/server/{sid}/start")

    def stop_server(self, sid: str, force: bool = False) -> dict:
        path = f"/server/{sid}/stop/force" if force else f"/server/{sid}/stop"
        return self._request("POST", path)

    def restart_server(self, sid: str) -> dict:
        return self._request("POST", f"/server/{sid}/restart")

    def get_server_logs(self, sid: str, n: int = 200) -> dict:
        return self._request("GET", f"/server/{sid}/logs?n={n}")

    def send_rcon(self, sid: str, command: str) -> dict:
        return self._request("POST", f"/server/{sid}/rcon", {"command": command})

    # ── Pareamento LAN (endpoints públicos, sem auth) ─────────────────────────

    def pair_request(self, name: str) -> dict:
        """Envia solicitação de pareamento para a máquina remota. Não requer token."""
        url = self._base + "/pair/request"
        data = json.dumps({"name": name}).encode()
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            try:
                return json.loads(exc.read().decode())
            except Exception:
                return {"error": f"HTTP {exc.code}"}
        except Exception as exc:
            return {"error": str(exc)}

    def pair_status(self, request_id: str) -> dict:
        """Consulta status de uma solicitação de pareamento. Não requer token."""
        url = self._base + f"/pair/status?id={urllib.parse.quote(request_id)}"
        try:
            with urllib.request.urlopen(url, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:
            return {"error": str(exc)}

    # ── Filesystem remoto (sync entre máquinas) ───────────────────────────────

    def fs_list(self, root: str) -> list:
        """Lista arquivos de uma pasta remota. Retorna [{rel, mtime, size}]."""
        path = "/fs/list?root=" + urllib.parse.quote(root, safe="")
        result = self._request("GET", path)
        if isinstance(result, dict) and "error" in result:
            raise OSError(result["error"])  # propaga 401, 400, 500 etc.
        return result.get("files", []) if isinstance(result, dict) else []

    def fs_read(self, root: str, rel: str) -> bytes:
        """Baixa o conteúdo de um arquivo remoto."""
        url = (self._base + "/fs/read?root=" +
               urllib.parse.quote(root, safe="") + "&rel=" +
               urllib.parse.quote(rel, safe=""))
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self._token}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=60.0) as resp:
            return resp.read()

    def fs_write(self, root: str, rel: str, data: bytes) -> dict:
        """Grava um arquivo em uma pasta remota."""
        url = (self._base + "/fs/write?root=" +
               urllib.parse.quote(root, safe="") + "&rel=" +
               urllib.parse.quote(rel, safe=""))
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={
                "Authorization":  f"Bearer {self._token}",
                "Content-Type":   "application/octet-stream",
                "Content-Length": str(len(data)),
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            try:
                return json.loads(exc.read().decode())
            except Exception:
                return {"error": f"HTTP {exc.code}"}
        except Exception as exc:
            return {"error": str(exc)}


# ═════════════════════════════════════════════════════════════════════════════
# Descoberta automática na rede local via UDP broadcast
# ═════════════════════════════════════════════════════════════════════════════

_UDP_DISCOVERY_PORT    = 32441   # porta UDP usada para anúncios LAN
_UDP_ANNOUNCE_INTERVAL = 30      # segundos entre broadcasts
_UDP_PEER_TTL          = 90      # segundos sem resposta → remove peer


class UdpDiscovery:
    """
    Descobre automaticamente outras instâncias ARKLAND na mesma rede local.

    Cada instância com o RemoteAgent ativo faz broadcast UDP a cada
    _UDP_ANNOUNCE_INTERVAL segundos anunciando seu nome, IP e porta.
    O token *não* é incluído no broadcast — só é exigido na hora de conectar.
    """

    def __init__(self, name: str, host: str, agent_port: int,
                 disc_port: int = _UDP_DISCOVERY_PORT) -> None:
        self._name  = name
        self._host  = host
        self._port  = agent_port
        self._dport = disc_port
        self._peers: Dict[str, Any] = {}   # "host:port" → {name, host, port, seen_at}
        self._lock    = threading.Lock()
        self._running = False

    # ── Interface pública ─────────────────────────────────────────────────────

    @property
    def peers(self) -> list:
        """Retorna instâncias vistas nos últimos _UDP_PEER_TTL segundos."""
        cutoff = time.time() - _UDP_PEER_TTL
        with self._lock:
            return [dict(p) for p in self._peers.values() if p["seen_at"] >= cutoff]

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        threading.Thread(target=self._broadcast_loop, daemon=True,
                         name="UdpAnnounce").start()
        threading.Thread(target=self._listen_loop, daemon=True,
                         name="UdpListener").start()

    def stop(self) -> None:
        self._running = False

    # ── Loops internos ────────────────────────────────────────────────────────

    def _payload(self) -> bytes:
        return json.dumps(
            {"n": self._name, "h": self._host, "p": self._port},
            separators=(",", ":"),
        ).encode()

    def _broadcast_loop(self) -> None:
        import socket as _socket
        while self._running:
            try:
                sock = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
                sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_BROADCAST, 1)
                sock.settimeout(2.0)
                sock.sendto(self._payload(), ("255.255.255.255", self._dport))
                sock.close()
            except Exception:
                pass
            # Aguarda o intervalo em fatias de 0.5 s para responder ao stop()
            for _ in range(_UDP_ANNOUNCE_INTERVAL * 2):
                if not self._running:
                    return
                time.sleep(0.5)

    def _listen_loop(self) -> None:
        import socket as _socket
        try:
            sock = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
            sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
            sock.settimeout(1.0)
            sock.bind(("", self._dport))
        except Exception:
            return
        try:
            while self._running:
                try:
                    raw, addr = sock.recvfrom(512)
                    peer = json.loads(raw.decode())
                    name = str(peer.get("n", addr[0]))
                    host = str(peer.get("h", addr[0]))
                    port = int(peer.get("p", _UDP_DISCOVERY_PORT))
                    # Ignora announce da própria instância
                    if host == self._host and port == self._port:
                        continue
                    key = f"{host}:{port}"
                    with self._lock:
                        self._peers[key] = {
                            "name": name, "host": host,
                            "port": port, "seen_at": time.time(),
                        }
                except _socket.timeout:
                    pass
                except Exception:
                    pass
        finally:
            sock.close()

