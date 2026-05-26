"""
TEK — Dashboard principal do modo ASM.
Lista todos os servidores TEK com cards de status.
"""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import get_theme
from ..asm_engine.asm_server_config import ASM_STATUS_RUNNING, ASM_STATUS_STOPPED

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_asm_dashboard(app: "ARKServerManagerApp", parent: ctk.CTkFrame) -> None:
    """Constrói o dashboard TEK dentro de `parent` (frame vazio, parente = _page_area)."""
    theme = get_theme("tek")
    accent  = theme["accent"]    # #00BCD4
    bg      = theme["bg"]        # #0e1820
    card_bg = theme["card_bg"]   # #162228

    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=0)  # header
    parent.grid_rowconfigure(1, weight=0)  # separador
    parent.grid_rowconfigure(2, weight=1)  # scroll
    parent.grid_rowconfigure(3, weight=0)  # footer

    # ── Header ────────────────────────────────────────────────────────────────
    hdr = ctk.CTkFrame(parent, fg_color=card_bg, corner_radius=0, height=64)
    hdr.grid(row=0, column=0, sticky="ew")
    hdr.grid_propagate(False)
    hdr.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(hdr, text="⚡ TEK",
                 font=ctk.CTkFont(size=22, weight="bold"),
                 text_color=accent).grid(row=0, column=0, padx=(20, 8), pady=10, sticky="w")

    ctk.CTkLabel(hdr, text="ARK Server Manager",
                 font=ctk.CTkFont(size=13), text_color="#5a8fa0").grid(
        row=0, column=1, padx=4, pady=10, sticky="w")

    ctk.CTkButton(
        hdr, text="＋ Novo Servidor", width=150, height=32,
        fg_color="#0b3944", hover_color="#094f5c",
        border_width=1, border_color=accent, text_color=accent,
        command=app._asm_add_server_dialog,
    ).grid(row=0, column=2, padx=(0, 16), pady=10, sticky="e")

    # ── Separador ────────────────────────────────────────────────────────────
    tk.Frame(parent, height=1, bg="#094f5c").grid(row=1, column=0, sticky="ew")

    # ── Scroll area ──────────────────────────────────────────────────────────
    scroll = ctk.CTkScrollableFrame(parent, fg_color=bg, corner_radius=0)
    scroll.grid(row=2, column=0, padx=12, pady=(12, 0), sticky="nsew")
    scroll.grid_columnconfigure((0, 1), weight=1)
    app._asm_dashboard_scroll = scroll

    # ── Footer legenda ────────────────────────────────────────────────────────
    footer = ctk.CTkFrame(parent, fg_color=card_bg, corner_radius=0, height=32)
    footer.grid(row=3, column=0, sticky="ew")
    footer.grid_propagate(False)

    _LEGEND = [
        ("🟢", "Rodando", "#00BCD4"),
        ("🟡", "Iniciando/Parando", "#ffaa44"),
        ("⬛", "Parado", "#ff6666"),
        ("🔴", "Travado", "#ff3333"),
    ]
    for icon, label, color in _LEGEND:
        ctk.CTkLabel(footer, text=f"{icon} {label}",
                     font=ctk.CTkFont(size=10), text_color=color).pack(
            side="left", padx=(16, 8), pady=6)

    # Popula cards
    _refresh_asm_dashboard(app)


def _refresh_asm_dashboard(app: "ARKServerManagerApp") -> None:
    """Popula / atualiza os cards de servidor no scroll do dashboard TEK."""
    from .asm_server_card import build_asm_server_card

    scroll = getattr(app, "_asm_dashboard_scroll", None)
    if not scroll:
        return

    for w in scroll.winfo_children():
        w.destroy()

    servers = app.asm_config_manager.servers
    if not servers:
        ctk.CTkLabel(
            scroll,
            text="Nenhum servidor TEK configurado.\nClique em '＋ Novo Servidor' para começar.",
            font=ctk.CTkFont(size=15), text_color="#5a8fa0", justify="center",
        ).grid(row=0, column=0, columnspan=2, pady=60)
        return

    for idx, srv in enumerate(servers):
        row, col = divmod(idx, 2)
        build_asm_server_card(app, scroll, srv, row, col)
