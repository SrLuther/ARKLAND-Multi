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
"""
import base64
import json
import socket
import threading
import urllib.error
import urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer
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

    # ── Interface pública ─────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

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
                if not self._auth():
                    self._json(401, {"error": "Não autorizado"})
                    return

                path = self.path.split("?")[0]  # strip query string

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

                else:
                    self._json(404, {"error": "Endpoint não encontrado"})

            def do_POST(self) -> None:
                if not self._auth():
                    self._json(401, {"error": "Não autorizado"})
                    return

                path = self.path.split("?")[0]

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
