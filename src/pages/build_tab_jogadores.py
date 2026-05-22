from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import (
    _BLUE,
    _BLUE_HOVER,
    _CARD_BG,
    _GREEN_DARK,
    _GREEN_HOVER,
)
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig


def build_tab_jogadores(app: "ARKServerManagerApp", parent, srv: "ServerConfig") -> None:
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(1, weight=1)

    w = app._server_widgets[srv.id]

    # Header card
    hdr = ctk.CTkFrame(parent, corner_radius=10, fg_color=_CARD_BG)
    hdr.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
    hdr.grid_columnconfigure(1, weight=1)

    w["_players_count_var"] = tk.StringVar(value="— Jogadores online")
    ctk.CTkLabel(
        hdr, textvariable=w["_players_count_var"],
        font=ctk.CTkFont(size=14, weight="bold"),
    ).grid(row=0, column=0, padx=16, pady=12, sticky="w")

    btn_row = ctk.CTkFrame(hdr, fg_color="transparent")
    btn_row.grid(row=0, column=1, padx=8, pady=8, sticky="e")

    w["_players_auto_var"] = tk.BooleanVar(value=False)
    w["_players_auto_job"] = None
    ctk.CTkCheckBox(
        btn_row, text="Auto (30s)", variable=w["_players_auto_var"],
        command=lambda: app._toggle_players_auto(srv.id),
    ).pack(side="left", padx=(0, 12))
    ctk.CTkButton(
        btn_row, text="🔄  Atualizar", width=120, height=32,
        fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=lambda: app._refresh_players(srv.id),
    ).pack(side="left", padx=(0, 16))

    ctk.CTkLabel(
        hdr,
        text="⚡  Requer conexão RCON ativa (aba Console RCON). Ações: Kick, Ban, Adicionar como Admin.",
        text_color="gray45", font=ctk.CTkFont(size=10), wraplength=700, justify="left",
    ).grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 10), sticky="w")

    # Lista de jogadores
    players_frame = ctk.CTkScrollableFrame(parent, corner_radius=10, fg_color=_CARD_BG)
    players_frame.grid(row=1, column=0, padx=12, pady=6, sticky="nsew")
    players_frame.grid_columnconfigure(0, weight=1)
    w["_players_list_frame"] = players_frame

    ctk.CTkLabel(
        players_frame,
        text="Clique em 'Atualizar' para listar os jogadores conectados.",
        text_color="gray50",
    ).pack(pady=20)

