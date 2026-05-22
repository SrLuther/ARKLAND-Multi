from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _GREEN_DARK, _GREEN_HOVER, _BLUE, _BLUE_HOVER, _CARD_BG

import sys
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig


def build_tab_rcon(app: "ARKServerManagerApp", parent, srv: "ServerConfig") -> None:
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(1, weight=1)

    w = app._server_widgets[srv.id]

    conn_bar = ctk.CTkFrame(parent, corner_radius=10, fg_color=_CARD_BG)
    conn_bar.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="ew")
    conn_bar.grid_columnconfigure(4, weight=1)

    ctk.CTkLabel(conn_bar, text="Host:", text_color="gray60").grid(
        row=0, column=0, padx=(14, 4), pady=10)
    w["rcon_host"] = tk.StringVar(value="127.0.0.1")
    ctk.CTkEntry(conn_bar, textvariable=w["rcon_host"], width=120, height=30).grid(
        row=0, column=1, padx=(0, 12), pady=10)

    ctk.CTkLabel(conn_bar, text="Porta:", text_color="gray60").grid(
        row=0, column=2, padx=(0, 4), pady=10)
    w["rcon_port_entry"] = tk.StringVar(value=str(srv.rcon_port))
    ctk.CTkEntry(conn_bar, textvariable=w["rcon_port_entry"], width=70, height=30).grid(
        row=0, column=3, padx=(0, 12), pady=10)

    w["rcon_status_var"] = tk.StringVar(value="⬛ Desconectado")
    ctk.CTkLabel(conn_bar, textvariable=w["rcon_status_var"],
                 text_color="gray50", font=ctk.CTkFont(size=12)).grid(
        row=0, column=4, padx=8, pady=10, sticky="w")

    w["rcon_connect_btn"] = ctk.CTkButton(
        conn_bar, text="🔌 Conectar", width=110, height=30,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=lambda: app._rcon_connect(srv.id),
    )
    w["rcon_connect_btn"].grid(row=0, column=5, padx=(0, 14), pady=10)

    w["rcon_output"] = ctk.CTkTextbox(
        parent, font=ctk.CTkFont(family="Courier New", size=12),
        wrap="word", state="disabled", fg_color="#0a0a14",
    )
    w["rcon_output"].grid(row=1, column=0, padx=12, pady=4, sticky="nsew")
    tw = w["rcon_output"]._textbox
    tw.tag_config("cmd",  foreground="#88d4a0")
    tw.tag_config("resp", foreground="#d0d0e0")
    tw.tag_config("err",  foreground="#ff6666")
    tw.tag_config("sys",  foreground="#888899")

    # Atalhos de comando
    shortcuts_frame = ctk.CTkFrame(parent, corner_radius=8, fg_color=_CARD_BG)
    shortcuts_frame.grid(row=2, column=0, padx=12, pady=(2, 2), sticky="ew")

    common_cmds = [
        ("SaveWorld",        "SaveWorld"),
        ("ListPlayers",      "ListPlayers"),
        ("GetChat",          "GetChat"),
        ("Broadcast",        "Broadcast Olá Sobreviventes!"),
        ("DoExit",           "DoExit"),
        ("DestroyWildDinos", "DestroyWildDinos"),
    ]
    for ci, (lbl, cmd) in enumerate(common_cmds):
        ctk.CTkButton(
            shortcuts_frame, text=lbl, width=130, height=28,
            fg_color="#2a2a44", hover_color="#3a3a5a",
            font=ctk.CTkFont(size=11),
            command=lambda c=cmd, sid=srv.id: app._rcon_exec(sid, c),
        ).grid(row=0, column=ci, padx=4, pady=6)

    input_row = ctk.CTkFrame(parent, fg_color="transparent")
    input_row.grid(row=3, column=0, padx=12, pady=(2, 12), sticky="ew")
    input_row.grid_columnconfigure(0, weight=1)

    w["rcon_input"] = tk.StringVar()
    input_entry = ctk.CTkEntry(
        input_row, textvariable=w["rcon_input"], height=36,
        placeholder_text="Digite um comando RCON e pressione Enter...",
    )
    input_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
    input_entry.bind("<Return>", lambda e, sid=srv.id: app._rcon_send(sid))

    ctk.CTkButton(
        input_row, text="Enviar ▶", width=90, height=36,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=lambda: app._rcon_send(srv.id),
    ).grid(row=0, column=1)

