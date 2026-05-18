"""
Agente HTTP do ARKLAND - Server Manager.

Quando habilitado, sobe um servidor HTTP leve na porta configurada.
Permite que outra instância do app controle este motor de sync remotamente.

Endpoints (todos exigem header  Authorization: Bearer <token>):
  GET  /status        → JSON com stats e status do sync
  GET  /logs          → JSON com as últimas 200 linhas de log
  POST /sync/start    → Inicia a sincronização
  POST /sync/stop     → Para  a sincronização
  POST /sync/force    → Força um ciclo imediato
"""
import json
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .sync_engine import SyncEngine

_MAX_LOG_LINES = 200


class RemoteAgent:
    def __init__(
        self,
        sync_engine: "SyncEngine",
        port: int = 32440,
        token: str = "",
    ) -> None:
        self._engine = sync_engine
        self._port = port
        self._token = token
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
            def log_message(self, format: str, *args: object) -> None:  # silencia log padrão do httpserver
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

            def do_GET(self) -> None:
                if not self._auth():
                    self._json(401, {"error": "Não autorizado"})
                    return
                if self.path == "/status":
                    self._json(200, {
                        "running": agent._engine.is_running,
                        "stats": agent._engine.stats,
                    })
                elif self.path == "/logs":
                    self._json(200, {"logs": list(agent._log_buffer)})
                else:
                    self._json(404, {"error": "Endpoint não encontrado"})

            def do_POST(self) -> None:
                if not self._auth():
                    self._json(401, {"error": "Não autorizado"})
                    return
                if self.path == "/sync/start":
                    agent._engine.start()
                    self._json(200, {"ok": True, "action": "start"})
                elif self.path == "/sync/stop":
                    agent._engine.stop()
                    self._json(200, {"ok": True, "action": "stop"})
                elif self.path == "/sync/force":
                    agent._engine.sync_once()
                    self._json(200, {"ok": True, "action": "force"})
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
