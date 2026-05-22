from __future__ import annotations
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def player_kick(app: "ARKServerManagerApp", server_id: str, steam_id: str, name: str) -> None:
    if not messagebox.askyesno(
        "Confirmar Kick",
        f"Kickar o jogador '{name}'?\n\nSteam ID: {steam_id}",
        parent=app,
    ):
        return
    app._rcon_exec(server_id, f"KickPlayer {steam_id}")
    app.after(1500, lambda: app._refresh_players(server_id))

