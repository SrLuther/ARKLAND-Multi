"""Servidor HTTP local para servir configurações dinâmicas do ARK via DynamicConfigURL.

O ARK Server suporta o parâmetro de startup ``-DynamicConfigURL=<url>``, que faz
o servidor buscar periodicamente um arquivo INI dessa URL e aplicar as configurações
sem necessidade de reinicialização (ex: multiplicadores de XP, taming, breeding...).

Uso básico::

    server = DynamicConfigServer(port=8765)
    server.start()
    server.update("server-uuid", ini_content_string)
    url = server.get_url("server-uuid")   # → http://127.0.0.1:8765/server-uuid
    server.stop()
"""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Optional


class DynamicConfigServer:
    """Servidor HTTP local que serve configurações dinâmicas por servidor ARK.

    Cada servidor ARK é identificado pelo seu UUID e acessado em::

        GET http://127.0.0.1:<port>/<server_id>

    O conteúdo é atualizado em memória via :meth:`update`; o ARK poll a URL
    periodicamente (a cada ~2 min) e aplica as mudanças sem reiniciar.
    """

    DEFAULT_PORT = 8765

    def __init__(self, port: int = DEFAULT_PORT) -> None:
        self._port = port
        self._contents: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._httpd: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Inicia o servidor HTTP em background.

        Returns:
            ``True`` se iniciado com sucesso; ``False`` se a porta já estiver em uso.
        """
        if self._thread and self._thread.is_alive():
            return True

        try:
            _self = self

            class _Handler(BaseHTTPRequestHandler):
                def do_GET(self) -> None:  # noqa: N802
                    key = self.path.lstrip("/")
                    with _self._lock:
                        content = _self._contents.get(key)
                    if content is None:
                        self.send_response(404)
                        self.end_headers()
                        return
                    data = content.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)

                def log_message(self, *args) -> None:  # silencia logs de acesso
                    pass

            self._httpd = HTTPServer(("127.0.0.1", self._port), _Handler)
            self._thread = threading.Thread(
                target=self._httpd.serve_forever,
                daemon=True,
                name="ARKDynamicConfigHTTP",
            )
            self._thread.start()
            return True
        except OSError:
            return False

    def stop(self) -> None:
        """Para o servidor HTTP."""
        if self._httpd:
            self._httpd.shutdown()
            self._httpd = None
        self._thread = None

    @property
    def is_running(self) -> bool:
        """``True`` se o servidor HTTP está ativo."""
        return self._thread is not None and self._thread.is_alive()

    # ── Gestão de conteúdo ────────────────────────────────────────────────────

    def update(self, server_id: str, content: str) -> None:
        """Atualiza o conteúdo INI servido para um servidor específico.

        A próxima poll do ARK receberá o novo conteúdo automaticamente.
        """
        with self._lock:
            self._contents[server_id] = content

    def remove(self, server_id: str) -> None:
        """Remove o conteúdo de um servidor do cache (responde 404)."""
        with self._lock:
            self._contents.pop(server_id, None)

    def get_url(self, server_id: str) -> str:
        """Retorna a URL completa para uso no parâmetro ``-DynamicConfigURL``."""
        return f"http://127.0.0.1:{self._port}/{server_id}"

    @property
    def port(self) -> int:
        return self._port
