from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _CARD_BG, _BG
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def show_cluster_health_dialog(app: "ARKServerManagerApp", server_id: str) -> None:
    """Abre dialog com o resultado do diagnóstico de cluster para o servidor."""
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return

    results = app._get_cluster_health(srv)

    dlg = tk.Toplevel(app)
    dlg.title(f"Diagnóstico de Cluster — {srv.name}")
    dlg.configure(bg=_BG)
    dlg.resizable(True, True)
    dlg.grab_set()

    # Cabeçalho
    hdr = ctk.CTkFrame(dlg, fg_color=_CARD_BG, corner_radius=0)
    hdr.pack(fill="x")
    ctk.CTkLabel(
        hdr, text=f"🔍  Diagnóstico de Cluster — {srv.name}",
        font=ctk.CTkFont(size=14, weight="bold"),
    ).pack(anchor="w", padx=16, pady=10)

    # Área de itens
    body = ctk.CTkScrollableFrame(dlg, fg_color="transparent", width=560, height=460)
    body.pack(fill="both", expand=True, padx=12, pady=8)

    _ICON  = {"ok": "✅", "warn": "⚠️", "error": "❌"}
    _COLOR = {"ok": "#5aaa5a", "warn": "#e0a020", "error": "#cc4444"}

    for entry in results:
        # Suporta tupla 3 (legado) e tupla 4 (com sugestão)
        if len(entry) == 4:
            status, title, detail, suggestion = entry
        else:
            status, title, detail = entry
            suggestion = ""

        row = ctk.CTkFrame(body, fg_color="#1e1e2e", corner_radius=6)
        row.pack(fill="x", pady=3, padx=2)
        row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            row, text=_ICON[status], width=30,
            font=ctk.CTkFont(size=14),
        ).grid(row=0, column=0, padx=(8, 4), pady=(6, 2), sticky="n")

        ctk.CTkLabel(
            row, text=title, anchor="w",
            text_color=_COLOR[status],
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=1, padx=(0, 8), pady=(6, 1), sticky="w")

        next_row = 1
        if detail:
            ctk.CTkLabel(
                row, text=detail, anchor="w", wraplength=480,
                text_color="gray60",
                font=ctk.CTkFont(size=10),
            ).grid(row=next_row, column=1, padx=(0, 8), pady=(0, 2), sticky="w")
            next_row += 1

        # Sugestão — apenas para warn/error
        if suggestion and status in ("warn", "error"):
            sug_fr = ctk.CTkFrame(row, fg_color="#12122a", corner_radius=4)
            sug_fr.grid(row=next_row, column=0, columnspan=2,
                        padx=(8, 8), pady=(2, 8), sticky="ew")
            sug_fr.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(
                sug_fr, text="💡", width=22,
                font=ctk.CTkFont(size=11),
            ).grid(row=0, column=0, padx=(6, 2), pady=(4, 4), sticky="n")
            ctk.CTkLabel(
                sug_fr, text=suggestion, anchor="w", wraplength=470,
                text_color="#7ab0e8",
                font=ctk.CTkFont(size=10),
                justify="left",
            ).grid(row=0, column=1, padx=(0, 6), pady=(4, 4), sticky="w")

    # Resumo
    errors = sum(1 for e in results if e[0] == "error")
    warns  = sum(1 for e in results if e[0] == "warn")
    if errors:
        summary_text  = f"❌  {errors} problema(s) crítico(s) encontrado(s)."
        summary_color = "#cc4444"
    elif warns:
        summary_text  = f"⚠️  {warns} aviso(s) — verifique antes de iniciar o servidor."
        summary_color = "#e0a020"
    else:
        summary_text  = "✅  Cluster configurado corretamente para cross-ARK."
        summary_color = "#5aaa5a"

    ctk.CTkLabel(
        dlg, text=summary_text, text_color=summary_color,
        font=ctk.CTkFont(size=12, weight="bold"),
    ).pack(pady=(0, 6))

    ctk.CTkButton(
        dlg, text="Fechar", width=100, height=32,
        command=dlg.destroy,
    ).pack(pady=(0, 12))

    dlg.update_idletasks()
    w = dlg.winfo_reqwidth()
    h = dlg.winfo_reqheight()
    x = app.winfo_x() + (app.winfo_width()  - w) // 2
    y = app.winfo_y() + (app.winfo_height() - h) // 2
    dlg.geometry(f"+{x}+{y}")

