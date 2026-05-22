from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _GREEN
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def refresh_dashboard(app: "ARKServerManagerApp") -> None:
    frame = app._dashboard_scroll
    for w in frame.winfo_children():
        w.destroy()

    servers = app.config_manager.servers
    if not servers:
        ctk.CTkLabel(
            frame,
            text="Nenhum servidor configurado.\nClique em '＋ Novo Servidor' para começar.",
            font=ctk.CTkFont(size=15), text_color="gray50", justify="center",
        ).grid(row=0, column=0, columnspan=2, pady=60)
        return

    for idx, srv in enumerate(servers):
        row, col = divmod(idx, 2)
        app._build_server_card(frame, srv, row, col)

    # ── Legenda de status ─────────────────────────────────────────────────
    legend_row = (len(servers) + 1) // 2
    legend = ctk.CTkFrame(frame, fg_color="#1a1a2e", corner_radius=8)
    legend.grid(row=legend_row, column=0, columnspan=2,
                padx=8, pady=(4, 8), sticky="ew")
    ctk.CTkLabel(legend, text="Legenda:",
                 text_color="gray50", font=ctk.CTkFont(size=11, weight="bold")
                 ).pack(side="left", padx=(12, 10), pady=6)
    _LEGEND_ITEMS = [
        ("⬛ PARADO",      "#ff6666",  "Servidor encerrado"),
        ("🟡 INICIANDO",   "#ffaa44",  "Aguardando startup do ARK"),
        ("🟢 RODANDO",     _GREEN,      "Online e acessível"),
        ("🟡 PARANDO",     "#ffaa44",  "Encerrando servidor"),
        ("🔴 TRAVADO",     "#ff3333",  "Processo travado — use 💀 Forçar Enc."),
        ("🟡 ATUALIZANDO", "#ffaa44",  "SteamCMD em execução"),
    ]
    for lbl, col, tip in _LEGEND_ITEMS:
        ctk.CTkLabel(legend, text=lbl, text_color=col,
                     font=ctk.CTkFont(size=11, weight="bold")
                     ).pack(side="left", padx=(0, 2), pady=6)
        ctk.CTkLabel(legend, text=f"= {tip}",
                     text_color="gray55", font=ctk.CTkFont(size=11)
                     ).pack(side="left", padx=(0, 16), pady=6)

