from __future__ import annotations
import threading
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def scan_running_servers(app: "ARKServerManagerApp") -> None:
    """Detecta servidores ARK já em execução e reconecta ao iniciar o app.
    Útil após restart automático pelo updater — os servidores continuam rodando
    enquanto o app é atualizado e relançado.
    """
    def _do() -> None:
        count = app.server_manager.scan_running_servers()
        if count:
            app._global_log(
                f"{count} servidor(es) já em execução detectado(s) e reconectado(s).",
                "info",
            )
    threading.Thread(target=_do, daemon=True, name="ScanRunningServers").start()

