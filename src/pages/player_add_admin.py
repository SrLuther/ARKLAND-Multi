from __future__ import annotations
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def player_add_admin(app: "ARKServerManagerApp", server_id: str, steam_id: str, name: str) -> None:
    srv = app.config_manager.get_server(server_id)
    if not srv or steam_id in srv.admin_ids:
        return
    srv.admin_ids.append(steam_id)
    if name:
        srv.admin_names[steam_id] = name
    app.config_manager.update_server(srv)
    app._refresh_admins_list(server_id)
    app._refresh_players(server_id)
    messagebox.showinfo(
        "Admin adicionado",
        f"'{name}' foi adicionado à lista de admins.\nLembre-se de salvar as configurações.",
        parent=app,
    )

