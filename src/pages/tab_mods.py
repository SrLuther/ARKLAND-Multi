from __future__ import annotations

import threading
import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import (
    _BLUE,
    _BLUE_HOVER,
    _CARD_BG,
    _GREEN_DARK,
    _GREEN_HOVER,
    _RED_DARK,
    _RED_HOVER,
)

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig


def build_tab_mods(app: "ARKServerManagerApp", parent, srv: "ServerConfig") -> None:
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(1, weight=1)

    w = app._server_widgets[srv.id]
    w["_mods_page"] = 0   # estado de paginação

    add_card = ctk.CTkFrame(parent, corner_radius=10, fg_color=_CARD_BG)
    add_card.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
    add_card.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(add_card, text="🔧  Steam Workshop Mod ID:",
                 text_color="gray60").grid(row=0, column=0, padx=16, pady=(14, 4))
    w["new_mod_id"] = tk.StringVar()
    ctk.CTkEntry(add_card, textvariable=w["new_mod_id"], height=34,
                 placeholder_text="Ex: 731604991").grid(
        row=0, column=1, padx=(0, 8), pady=(14, 4), sticky="ew")
    ctk.CTkButton(
        add_card, text="➕ Adicionar", width=110, height=34,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=lambda: app._add_mod(srv.id),
    ).grid(row=0, column=2, padx=(0, 8), pady=(14, 4))
    ctk.CTkButton(
        add_card, text="🔍 Buscar Workshop", width=150, height=34,
        fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=lambda: app._open_mod_search_dialog(srv.id),
    ).grid(row=0, column=3, padx=(0, 16), pady=(14, 4))

    ctk.CTkLabel(
        add_card,
        text="💡  Cole o ID do mod (número) ou use 🔍 para buscar pelo nome. Você pode encontrar o ID na URL da página do Workshop.",
        text_color="gray45", font=ctk.CTkFont(size=10), wraplength=700, justify="left",
    ).grid(row=1, column=0, columnspan=4, padx=16, pady=(0, 10), sticky="w")

    if not app.mod_manager.is_steamcmd_available():
        ctk.CTkLabel(
            add_card,
            text="⚠️  SteamCMD não configurado. Configure o caminho nas Configurações Globais.",
            text_color="#ffaa44", font=ctk.CTkFont(size=11),
        ).grid(row=2, column=0, columnspan=4, padx=16, pady=(0, 10), sticky="w")

    mods_card = ctk.CTkScrollableFrame(parent, corner_radius=10, fg_color=_CARD_BG)
    mods_card.grid(row=1, column=0, padx=12, pady=(6, 0), sticky="nsew")
    mods_card.grid_columnconfigure(0, weight=1)
    w["_mods_list_frame"] = mods_card

    # Barra de navegação de páginas (mods)
    mods_nav = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=6, height=34)
    mods_nav.grid(row=2, column=0, padx=12, pady=(2, 4), sticky="ew")
    mods_nav.grid_columnconfigure(1, weight=1)
    mods_nav.grid_propagate(False)
    sv_mods_nav = tk.StringVar(value="")
    btn_mods_prev = ctk.CTkButton(
        mods_nav, text="◀", width=36, height=26,
        fg_color="#2a2a4a", hover_color="#3a3a5a",
        command=lambda: app._refresh_mods_list(srv.id, w["_mods_page"] - 1),
    )
    btn_mods_prev.grid(row=0, column=0, padx=(6, 2), pady=4)
    ctk.CTkLabel(mods_nav, textvariable=sv_mods_nav,
                 text_color="gray60", font=ctk.CTkFont(size=11)
                 ).grid(row=0, column=1)
    btn_mods_next = ctk.CTkButton(
        mods_nav, text="▶", width=36, height=26,
        fg_color="#2a2a4a", hover_color="#3a3a5a",
        command=lambda: app._refresh_mods_list(srv.id, w["_mods_page"] + 1),
    )
    btn_mods_next.grid(row=0, column=2, padx=(2, 6), pady=4)
    w["_mods_sv_nav"] = sv_mods_nav
    w["_mods_btn_prev"] = btn_mods_prev
    w["_mods_btn_next"] = btn_mods_next

    actions = ctk.CTkFrame(parent, fg_color="transparent")
    actions.grid(row=3, column=0, padx=12, pady=(4, 12), sticky="ew")

    ctk.CTkButton(
        actions, text="⬇️  Baixar / Atualizar Todos os Mods",
        height=38, fg_color=_BLUE, hover_color=_BLUE_HOVER,
        font=ctk.CTkFont(size=13, weight="bold"),
        command=lambda: app._download_all_mods(srv.id),
    ).pack(side="left", padx=(0, 8))

    ctk.CTkButton(
        actions, text="💾  Salvar Lista de Mods",
        height=38, fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=lambda: app._save_server_config(srv.id),
    ).pack(side="left", padx=(0, 8))

    ctk.CTkButton(
        actions, text="🗑️  Apagar Todos os Mods",
        height=38, fg_color="#8B1A1A", hover_color="#B22222",
        command=lambda: app._clear_all_mods(srv.id),
    ).pack(side="left")

    app._refresh_mods_list(srv.id)
    app._build_auto_update_panel(parent, srv)

