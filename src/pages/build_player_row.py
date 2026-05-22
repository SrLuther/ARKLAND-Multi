from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _RED_DARK, _RED_HOVER
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_player_row(app: "ARKServerManagerApp", parent, server_id: str, name: str, steam_id: str) -> None:
    srv = app.config_manager.get_server(server_id)
    row_fr = ctk.CTkFrame(parent, corner_radius=8, fg_color="#252535")
    row_fr.pack(fill="x", padx=8, pady=3)
    row_fr.grid_columnconfigure(0, weight=1)

    info = ctk.CTkFrame(row_fr, fg_color="transparent")
    info.grid(row=0, column=0, padx=12, pady=6, sticky="w")
    ctk.CTkLabel(
        info, text=f"🧑  {name}",
        font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
    ).pack(anchor="w")
    ctk.CTkLabel(
        info, text=steam_id,
        font=ctk.CTkFont(size=10), text_color="gray55", anchor="w",
    ).pack(anchor="w")

    btns = ctk.CTkFrame(row_fr, fg_color="transparent")
    btns.grid(row=0, column=1, padx=(0, 8), pady=4, sticky="e")

    is_admin = srv and steam_id in srv.admin_ids
    if not is_admin:
        ctk.CTkButton(
            btns, text="⭐ Admin", width=82, height=28,
            fg_color="#2d4a2d", hover_color="#3d6a3d",
            command=lambda: app._player_add_admin(server_id, steam_id, name),
        ).pack(side="left", padx=3)
    ctk.CTkButton(
        btns, text="👢 Kick", width=74, height=28,
        fg_color="#4a3a1a", hover_color="#6a5020",
        command=lambda: app._player_kick(server_id, steam_id, name),
    ).pack(side="left", padx=3)
    ctk.CTkButton(
        btns, text="🔨 Ban", width=74, height=28,
        fg_color=_RED_DARK, hover_color=_RED_HOVER,
        command=lambda: app._player_ban(server_id, steam_id, name),
    ).pack(side="left", padx=3)

