from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Any

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _GREEN, _GREEN_DARK, _GREEN_HOVER, _RED_DARK, _RED_HOVER, _CARD_BG

if TYPE_CHECKING:
    pass


def build_tek_mod_auto_update_card(app: Any, parent, srv_id: str = "") -> None:
    """Card de atualização automática de mods Workshop (modo TEK)."""
    card = ctk.CTkFrame(parent, corner_radius=10, fg_color=_CARD_BG)
    card.pack(fill="x", padx=8, pady=(8, 12))

    ctk.CTkLabel(
        card, text="🔄  Atualização Automática de Mods (Workshop)",
        font=ctk.CTkFont(size=13, weight="bold"),
    ).pack(anchor="w", padx=14, pady=(12, 4))

    ctk.CTkLabel(
        card,
        text="Verifica o Steam Workshop periodicamente. Ao detectar mod atualizado, "
             "avisa via broadcast, baixa o mod e reinicia o servidor.",
        text_color="gray55", font=ctk.CTkFont(size=10), wraplength=760, justify="left",
    ).pack(anchor="w", padx=14, pady=(0, 8))

    row = ctk.CTkFrame(card, fg_color="transparent")
    row.pack(fill="x", padx=12, pady=(0, 10))

    ctk.CTkLabel(row, text="Intervalo (min):", text_color="gray70").pack(side="left", padx=(0, 4))
    app._tek_au_interval_var = tk.StringVar(value="15")
    ctk.CTkEntry(row, textvariable=app._tek_au_interval_var, width=60, height=28).pack(side="left", padx=(0, 14))

    ctk.CTkLabel(row, text="Aviso (min):", text_color="gray70").pack(side="left", padx=(0, 4))
    app._tek_au_warning_var = tk.StringVar(value="5")
    ctk.CTkEntry(row, textvariable=app._tek_au_warning_var, width=60, height=28).pack(side="left", padx=(0, 14))

    is_active = app._mod_auto_updater is not None and app._mod_auto_updater.enabled
    app._tek_au_toggle_btn = ctk.CTkButton(
        row,
        text="⏸ Parar" if is_active else "▶ Ativar",
        width=110, height=28,
        fg_color=_RED_DARK if is_active else _GREEN_DARK,
        hover_color=_RED_HOVER if is_active else _GREEN_HOVER,
        command=lambda: app._toggle_mod_auto_updater(srv_id),
    )
    app._tek_au_toggle_btn.pack(side="left", padx=(0, 8))

    app._tek_au_status_lbl = ctk.CTkLabel(
        row,
        text="● ATIVO" if is_active else "● INATIVO",
        text_color=_GREEN if is_active else "gray50",
        font=ctk.CTkFont(size=11, weight="bold"),
    )
    app._tek_au_status_lbl.pack(side="left")

    log_box = ctk.CTkTextbox(card, height=90, state="disabled",
                             font=ctk.CTkFont(family="Courier New", size=10))
    log_box.pack(fill="x", padx=12, pady=(0, 12))
    app._auto_updater_log_box = log_box
