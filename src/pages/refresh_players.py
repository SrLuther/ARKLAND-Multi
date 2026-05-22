from __future__ import annotations
import threading
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def refresh_players(app: "ARKServerManagerApp", server_id: str) -> None:
    client = app._rcon_clients.get(server_id)
    w = app._server_widgets.get(server_id, {})
    frame = w.get("_players_list_frame")
    count_var: Optional[tk.StringVar] = w.get("_players_count_var")
    if not frame:
        return
    if not client or not client.is_connected:
        for child in frame.winfo_children():
            child.destroy()
        ctk.CTkLabel(
            frame,
            text="⚠️  RCON não conectado.\nVá até a aba 'Console RCON' e clique em 'Conectar' primeiro.",
            text_color="#f87171",
        ).pack(pady=20)
        if count_var:
            count_var.set("— Sem conexão RCON")
        return
    if count_var:
        count_var.set("⏳ Buscando jogadores...")

    def _do():
        ok, result = client.send_command_safe("ListPlayers")
        app.after(0, lambda: app._update_players_list(server_id, ok, result or ""))

    threading.Thread(target=_do, daemon=True).start()

