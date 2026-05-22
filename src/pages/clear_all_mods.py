from __future__ import annotations
from tkinter import messagebox
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def clear_all_mods(app: "ARKServerManagerApp", server_id: str) -> None:
    srv = app.config_manager.get_server(server_id)
    if not srv or not srv.mods:
        return
    count = len(srv.mods)
    if not messagebox.askyesno(
        "Apagar todos os mods",
        f"Remover todos os {count} mod(s) da lista do servidor?\n\nEsta ação não desinstala os arquivos do disco.",
    ):
        return
    srv.mods.clear()
    srv.mod_names.clear()
    srv.mod_ini_configs.clear()
    app.config_manager.update_server(srv)
    app._refresh_mods_list(server_id)

