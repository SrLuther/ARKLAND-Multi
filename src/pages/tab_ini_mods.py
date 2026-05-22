from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import (
    _GREEN_DARK, _GREEN_HOVER, _BLUE, _BLUE_HOVER,
    _SIDEBAR_BG, _CARD_BG, _BG,
)

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig


def build_tab_ini_mods(app: "ARKServerManagerApp", parent, srv: "ServerConfig") -> None:  # noqa: C901
    """Aba de edição estruturada das seções INI (Mods + Personalizadas)."""
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=1)
    w = app._server_widgets[srv.id]

    sub = ctk.CTkTabview(parent, fg_color=_BG, segmented_button_fg_color=_SIDEBAR_BG,
                         segmented_button_selected_color=_GREEN_DARK,
                         segmented_button_selected_hover_color=_GREEN_HOVER,
                         segmented_button_unselected_color=_SIDEBAR_BG,
                         segmented_button_unselected_hover_color=_CARD_BG)
    sub.grid(row=0, column=0, sticky="nsew", padx=4, pady=(4, 4))
    sub.add("GameUserSettings.ini")
    sub.add("Game.ini")

    for file_key, tab_name in [("gus", "GameUserSettings.ini"), ("game", "Game.ini")]:
        t = sub.tab(tab_name)
        t.grid_columnconfigure(0, weight=0)
        t.grid_columnconfigure(1, weight=1)
        t.grid_rowconfigure(1, weight=1)

        # ── Barra de ações ────────────────────────────────────────────────
        bar = ctk.CTkFrame(t, fg_color="transparent")
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(4, 2))

        ctk.CTkLabel(bar, text="Seções INI personalizadas",
                     text_color="gray55",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(8, 16))

        ctk.CTkButton(bar, text="+ Seção", width=90, height=28,
                      fg_color=_BLUE, hover_color=_BLUE_HOVER,
                      font=ctk.CTkFont(size=11),
                      command=lambda fk=file_key, sid=srv.id:
                          app._ini_add_section(sid, fk)).pack(side="left", padx=(0, 4))

        ctk.CTkButton(bar, text="� Colar Seção", width=115, height=28,
                      fg_color="#3a2a5a", hover_color="#4e3a7a",
                      font=ctk.CTkFont(size=11),
                      command=lambda fk=file_key, sid=srv.id:
                          app._ini_paste_section(sid, fk)).pack(side="left", padx=(0, 4))

        ctk.CTkButton(bar, text="�🔁 Atualizar", width=100, height=28,
                      fg_color="#2a2a2a", hover_color="#404040",
                      font=ctk.CTkFont(size=11),
                      command=lambda fk=file_key, sid=srv.id:
                          app._ini_reload(sid, fk)).pack(side="left", padx=(0, 4))

        ctk.CTkButton(bar, text="💾 Salvar INI", width=110, height=28,
                      fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                      font=ctk.CTkFont(size=11),
                      command=lambda sid=srv.id:
                          app._ini_save(sid)).pack(side="right", padx=8)

        # ── Painel esquerdo: lista de seções ──────────────────────────────
        sec_outer = ctk.CTkFrame(t, fg_color=_CARD_BG, corner_radius=8, width=230)
        sec_outer.grid(row=1, column=0, sticky="nsew", padx=(4, 2), pady=(2, 4))
        sec_outer.grid_columnconfigure(0, weight=1)
        sec_outer.grid_rowconfigure(1, weight=1)
        sec_outer.grid_propagate(False)

        ctk.CTkLabel(sec_outer, text="Seções", text_color="gray45",
                     font=ctk.CTkFont(size=10, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=(6, 2))

        sec_scroll = ctk.CTkScrollableFrame(sec_outer, fg_color="transparent",
                                            corner_radius=0)
        sec_scroll.grid(row=1, column=0, sticky="nsew", padx=2, pady=(0, 4))
        sec_scroll.grid_columnconfigure(0, weight=1)
        w[f"_ini_{file_key}_secscroll"] = sec_scroll

        # ── Painel direito: entradas da seção ─────────────────────────────
        kv_outer = ctk.CTkFrame(t, fg_color=_CARD_BG, corner_radius=8)
        kv_outer.grid(row=1, column=1, sticky="nsew", padx=(2, 4), pady=(2, 4))
        kv_outer.grid_columnconfigure(0, weight=1)
        kv_outer.grid_rowconfigure(2, weight=1)

        # Nome da seção selecionada
        sec_name_var = tk.StringVar()
        w[f"_ini_{file_key}_sec_name_var"] = sec_name_var

        kv_hdr = ctk.CTkFrame(kv_outer, fg_color="transparent")
        kv_hdr.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        kv_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkEntry(kv_hdr, textvariable=sec_name_var, height=32,
                     font=ctk.CTkFont(size=12, weight="bold"),
                     placeholder_text="(nenhuma seção selecionada)").grid(
            row=0, column=0, sticky="ew")

        # Cabeçalho das colunas Chave / Valor
        col_hdr = ctk.CTkFrame(kv_outer, fg_color="transparent")
        col_hdr.grid(row=1, column=0, sticky="ew", padx=12, pady=(4, 0))
        col_hdr.grid_columnconfigure(0, weight=1)
        col_hdr.grid_columnconfigure(1, weight=2)
        ctk.CTkLabel(col_hdr, text="Chave", text_color="gray45",
                     font=ctk.CTkFont(size=10)).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(col_hdr, text="Valor", text_color="gray45",
                     font=ctk.CTkFont(size=10)).grid(row=0, column=1, sticky="w", padx=(8, 0))

        kv_scroll = ctk.CTkScrollableFrame(kv_outer, fg_color="transparent",
                                           corner_radius=0)
        kv_scroll.grid(row=2, column=0, sticky="nsew", padx=4, pady=2)
        kv_scroll.grid_columnconfigure(0, weight=1)
        kv_scroll.grid_columnconfigure(1, weight=2)
        w[f"_ini_{file_key}_kvscroll"] = kv_scroll

        kv_footer = ctk.CTkFrame(kv_outer, fg_color="transparent")
        kv_footer.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 8))
        ctk.CTkButton(kv_footer, text="+ Entrada", width=90, height=26,
                      fg_color=_BLUE, hover_color=_BLUE_HOVER,
                      font=ctk.CTkFont(size=11),
                      command=lambda fk=file_key, sid=srv.id:
                          app._ini_add_entry(sid, fk)).pack(side="left")

        # ── Estado da aba ─────────────────────────────────────────────────
        w[f"_ini_{file_key}_sel_section"] = None
        # Dados: lista de seção-dicts já descritos acima
        w[f"_ini_{file_key}_data"] = []

    # Carregamento inicial na sub-aba ativa
    app._ini_reload(srv.id, "gus")
    app._ini_reload(srv.id, "game")

