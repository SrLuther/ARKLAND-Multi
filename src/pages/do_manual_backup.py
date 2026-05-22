from __future__ import annotations
import threading
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def do_manual_backup(app: "ARKServerManagerApp", server_id: str) -> None:
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return
    bm = app._backup_manager
    if not bm:
        return

    def _run() -> None:
        result = bm.do_backup(srv)
        def _done() -> None:
            if result:
                app._refresh_backup_list(server_id)
            else:
                messagebox.showerror(
                    "Backup falhou",
                    "Não foi possível realizar o backup. Verifique o diretório de instalação.",
                    parent=app,
                )
        app.after(0, _done)

    threading.Thread(target=_run, daemon=True).start()

