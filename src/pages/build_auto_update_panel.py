from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _GREEN, _GREEN_DARK, _GREEN_HOVER, _RED_DARK, _RED_HOVER, _CARD_BG
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig


def build_auto_update_panel(app: "ARKServerManagerApp", parent, srv: "ServerConfig") -> None:
    """Card de atualização automática de mods, embutido na aba Mods."""
    w = app._server_widgets[srv.id]
    card = ctk.CTkFrame(parent, corner_radius=10, fg_color=_CARD_BG)
    card.grid(row=4, column=0, padx=12, pady=(4, 12), sticky="ew")
    card.grid_columnconfigure(1, weight=1)

    # ── Título ────────────────────────────────────────────────────────────
    ctk.CTkLabel(
        card, text="🔄  Atualização Automática de Mods",
        font=ctk.CTkFont(size=14, weight="bold"),
    ).grid(row=0, column=0, columnspan=4, padx=16, pady=(12, 4), sticky="w")

    ctk.CTkLabel(
        card,
        text="Verifica periodicamente o Steam Workshop. Quando um mod for atualizado, "
             "avisa os jogadores via broadcast, aguarda o tempo configurado e reinicia o servidor.",
        text_color="gray55", font=ctk.CTkFont(size=10), wraplength=750, justify="left",
    ).grid(row=1, column=0, columnspan=4, padx=16, pady=(0, 8), sticky="w")

    # ── Linha de configurações ────────────────────────────────────────────
    cfg_row = ctk.CTkFrame(card, fg_color="transparent")
    cfg_row.grid(row=2, column=0, columnspan=4, padx=12, pady=(0, 8), sticky="ew")

    ctk.CTkLabel(cfg_row, text="Intervalo de verificação (min):",
                 text_color="gray70").pack(side="left", padx=(4, 4))
    w["_au_interval_var"] = tk.StringVar(value="15")
    ctk.CTkEntry(cfg_row, textvariable=w["_au_interval_var"], width=60, height=30,
                 justify="center").pack(side="left", padx=(0, 16))

    ctk.CTkLabel(cfg_row, text="Aviso antecipado (min):",
                 text_color="gray70").pack(side="left", padx=(0, 4))
    w["_au_warning_var"] = tk.StringVar(value="5")
    ctk.CTkEntry(cfg_row, textvariable=w["_au_warning_var"], width=60, height=30,
                 justify="center").pack(side="left", padx=(0, 16))

    # ── Botão ligar/desligar ──────────────────────────────────────────────
    is_active = (
        app._mod_auto_updater is not None and app._mod_auto_updater.enabled
    )
    w["_au_toggle_btn"] = ctk.CTkButton(
        cfg_row,
        text="⏸ Parar" if is_active else "▶ Ativar",
        width=110, height=30,
        fg_color=_RED_DARK if is_active else _GREEN_DARK,
        hover_color=_RED_HOVER if is_active else _GREEN_HOVER,
        command=lambda sid=srv.id: app._toggle_mod_auto_updater(sid),
    )
    w["_au_toggle_btn"].pack(side="left", padx=(0, 8))

    # status pill
    w["_au_status_lbl"] = ctk.CTkLabel(
        cfg_row,
        text="● ATIVO" if is_active else "● INATIVO",
        text_color=_GREEN if is_active else "gray50",
        font=ctk.CTkFont(size=11, weight="bold"),
    )
    w["_au_status_lbl"].pack(side="left")

    # ── Log ───────────────────────────────────────────────────────────────
    log_box = ctk.CTkTextbox(card, height=100, state="disabled",
                             font=ctk.CTkFont(family="Courier New", size=10))
    log_box._textbox.tag_configure("info",    foreground="#e0e0e0")
    log_box._textbox.tag_configure("warning", foreground="#ffaa44")
    log_box._textbox.tag_configure("error",   foreground="#ff6666")
    log_box._textbox.tag_configure("debug",   foreground="#888888")
    log_box.grid(row=3, column=0, columnspan=4, padx=12, pady=(0, 12), sticky="ew")
    w["_au_log_box"] = log_box
    # Registra o log box global (última instância criada serve como painel)
    app._auto_updater_log_box = log_box

