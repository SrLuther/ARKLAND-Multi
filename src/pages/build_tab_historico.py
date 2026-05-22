from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _RED_DARK, _RED_HOVER, _CARD_BG, _BG
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig


def build_tab_historico(app: "ARKServerManagerApp", parent, srv: "ServerConfig") -> None:
    """Exibe o histórico de alterações de configuração do servidor."""
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(1, weight=1)

    # ── Barra de controles ────────────────────────────────────────────────
    bar = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=8)
    bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))

    ctk.CTkLabel(bar, text="📋 Histórico de alterações",
                 font=ctk.CTkFont(size=13, weight="bold"),
                 text_color="#c0c0d8").pack(side="left", padx=12, pady=8)

    filter_var = tk.StringVar(value="Todas as abas")
    tabs_filter = ["Todas as abas", "Geral", "Jogo", "Avançado"]
    filter_menu = ctk.CTkOptionMenu(bar, variable=filter_var, values=tabs_filter,
                                    width=140, height=28,
                                    fg_color="#2a2a2a", button_color="#3a3a3a",
                                    font=ctk.CTkFont(size=11),
                                    command=lambda _: app._historico_refresh(srv.id, filter_var))
    filter_menu.pack(side="left", padx=(0, 8), pady=8)

    ctk.CTkButton(bar, text="🔁 Atualizar", width=100, height=28,
                  fg_color="#2a2a2a", hover_color="#404040",
                  font=ctk.CTkFont(size=11),
                  command=lambda: app._historico_refresh(srv.id, filter_var)
                  ).pack(side="left", pady=8)

    ctk.CTkButton(bar, text="🗑 Limpar histórico", width=140, height=28,
                  fg_color=_RED_DARK, hover_color=_RED_HOVER,
                  font=ctk.CTkFont(size=11),
                  command=lambda: app._historico_clear(srv.id, filter_var)
                  ).pack(side="right", padx=8, pady=8)

    # ── Textbox de exibição ───────────────────────────────────────────────
    tw = ctk.CTkTextbox(parent, state="disabled", font=ctk.CTkFont(family="Consolas", size=11),
                        fg_color=_BG, text_color="#d0d0e0", corner_radius=8,
                        wrap="none")
    tw.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

    # Tags de formatação
    tw.tag_config("ts",    foreground="#7070a0")
    tw.tag_config("tab",   foreground="#5080c0")
    tw.tag_config("label", foreground="#c0c0d8")
    tw.tag_config("arrow", foreground="#606060")
    tw.tag_config("old",   foreground="#c07070")
    tw.tag_config("new",   foreground="#70c070")
    tw.tag_config("empty", foreground="#404050")

    app._server_widgets[srv.id]["_historico_tw"] = tw
    app._server_widgets[srv.id]["_historico_filter_var"] = filter_var
    app._historico_refresh(srv.id, filter_var)

