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
    app.mod_manager.steamcmd_path = app.config_manager.config.steamcmd_path
    app.mod_manager.download_mods(
        srv.mods, srv.install_dir,
        on_done=lambda ok: app.after(0, lambda: app._refresh_mods_list(server_id)),  # type: ignore[arg-type]
    )

