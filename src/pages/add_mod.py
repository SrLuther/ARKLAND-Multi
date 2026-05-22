from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def add_mod(app: "ARKServerManagerApp", server_id: str, mod_name: str = "") -> None:
    w = app._server_widgets.get(server_id, {})
    mod_id = w.get("new_mod_id", tk.StringVar()).get().strip()
    if not mod_id or not mod_id.isdigit():
        messagebox.showwarning("Mod inválido", "Informe um ID numérico válido.", parent=app)
        return
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return
    if mod_id not in srv.mods:
        srv.mods.append(mod_id)
    if mod_name:
        srv.mod_names[mod_id] = mod_name
    app.config_manager.update_server(srv)
    w["new_mod_id"].set("")
    app._refresh_mods_list(server_id)
    if not mod_name and mod_id not in srv.mod_names:
        app._fetch_mod_names_async(server_id, [mod_id])

