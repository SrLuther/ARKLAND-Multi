from __future__ import annotations
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def download_all_mods(app: "ARKServerManagerApp", server_id: str) -> None:
    srv = app.config_manager.get_server(server_id)
    if not srv or not srv.mods:
        messagebox.showinfo("Mods", "Nenhum mod para baixar.", parent=app)
        return
    from ..dialogs.mod_download_dialog import open_mod_download_dialog
    open_mod_download_dialog(app, server_id, list(srv.mods))

