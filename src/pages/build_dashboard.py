from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _GREEN_DARK, _GREEN_HOVER
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

_LEGEND_ITEMS = [
    ("⬛ PARADO",      "#ff6666",  "Servidor encerrado"),
    ("🟡 INICIANDO",   "#ffaa44",  "Aguardando startup do ARK"),
    ("🟢 RODANDO",     "#4CAF50",   "Online e acessível"),
    ("🟡 PARANDO",     "#ffaa44",  "Encerrando servidor"),
    ("🔴 TRAVADO",     "#ff3333",  "Processo travado — use 💀 Forçar Enc."),
    ("🟡 ATUALIZANDO", "#ffaa44",  "SteamCMD em execução"),
]


def build_dashboard(app: "ARKServerManagerApp", parent: "ctk.CTkFrame") -> None:
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(2, weight=1)

    hdr = ctk.CTkFrame(parent, fg_color="transparent")
    hdr.grid(row=0, column=0, padx=24, pady=(24, 4), sticky="ew")
    hdr.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(hdr, text="Dashboard",
                 font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, sticky="w")
    ctk.CTkLabel(hdr, text="Gerencie todos os seus servidores ARK em um só lugar.",
                 text_color="gray60").grid(row=1, column=0, sticky="w")

    ctk.CTkButton(
        hdr, text="＋  Novo Servidor", width=160, height=36,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        font=ctk.CTkFont(size=13, weight="bold"),
        command=app._dialog_add_server,
    ).grid(row=0, column=1, rowspan=2, sticky="e")

    ctk.CTkFrame(parent, height=1, fg_color="#2a2a44").grid(
        row=1, column=0, padx=20, pady=(8, 0), sticky="ew")

    app._dashboard_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
    app._dashboard_scroll.grid(row=2, column=0, padx=12, pady=(12, 0), sticky="nsew")
    app._dashboard_scroll.grid_columnconfigure((0, 1), weight=1)

    # ── Footer de legenda (fixo, não rola com os cards) ───────────────────────
    legend = ctk.CTkFrame(parent, fg_color="#13131e", corner_radius=0, height=32)
    legend.grid(row=3, column=0, sticky="ew", padx=0, pady=0)
    legend.grid_propagate(False)
    ctk.CTkLabel(legend, text="Legenda:",
                 text_color="gray50", font=ctk.CTkFont(size=11, weight="bold")
                 ).pack(side="left", padx=(16, 10))
    for lbl, color, tip in _LEGEND_ITEMS:
        ctk.CTkLabel(legend, text=lbl, text_color=color,
                     font=ctk.CTkFont(size=11, weight="bold")
                     ).pack(side="left", padx=(0, 2))
        ctk.CTkLabel(legend, text=f"= {tip}",
                     text_color="gray55", font=ctk.CTkFont(size=11)
                     ).pack(side="left", padx=(0, 14))

    app._refresh_dashboard()

