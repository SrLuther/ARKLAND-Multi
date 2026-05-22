from __future__ import annotations
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def player_ban(app: "ARKServerManagerApp", server_id: str, steam_id: str, name: str) -> None:
    if not messagebox.askyesno(
        "Confirmar Ban",
        f"Banir permanentemente '{name}'?\n\nSteam ID: {steam_id}\n\nPara desfazer use o console: UnbanPlayer {steam_id}",
        parent=app,
    ):
        return
    app._rcon_exec(server_id, f"BanPlayer {steam_id}")
    app.after(1500, lambda: app._refresh_players(server_id))

