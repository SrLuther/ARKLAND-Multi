from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..ui_constants import _parse_listplayers


def update_players_list(app: "ARKServerManagerApp", server_id: str, ok: bool, response: str) -> None:
    w = app._server_widgets.get(server_id, {})
    frame = w.get("_players_list_frame")
    count_var: Optional[tk.StringVar] = w.get("_players_count_var")
    if not frame:
        return
    for child in frame.winfo_children():
        child.destroy()
    if not ok:
        ctk.CTkLabel(frame, text=f"Erro RCON: {response}", text_color="#f87171").pack(pady=20)
        if count_var:
            count_var.set("Erro ao listar jogadores")
        return
    players = _parse_listplayers(response)
    if not players:
        ctk.CTkLabel(
            frame, text="Nenhum jogador conectado no momento.", text_color="gray50",
        ).pack(pady=20)
        if count_var:
            count_var.set("0 jogadores online")
        return
    n = len(players)
    if count_var:
        count_var.set(f"{n} jogador{'es' if n != 1 else ''} online")
    for p in players:
        app._build_player_row(frame, server_id, p["name"], p["steam_id"])

