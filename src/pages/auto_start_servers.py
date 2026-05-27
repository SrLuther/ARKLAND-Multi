from __future__ import annotations
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def auto_start_servers(app: "ARKServerManagerApp") -> None:
    """Inicia automaticamente os servidores com auto_start_on_launch=True."""
    servers = [s for s in app.config_manager.servers if s.auto_start_on_launch]
    if not servers:
        return

    def _do() -> None:
        for srv in servers:
            app._global_log(f"[Auto-Start] Iniciando servidor '{srv.name}'...", "info")
            app.after(0, lambda sid=srv.id: app._start_server(sid))

    threading.Thread(target=_do, daemon=True, name="AutoStartServers").start()
