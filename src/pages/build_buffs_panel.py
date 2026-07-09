from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _GREEN_DARK, _GREEN_HOVER, _BLUE, _BLUE_HOVER, _CARD_BG, _BG
from ..buff_server_bridge import list_buff_servers
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_buffs_panel(app: "ARKServerManagerApp", parent: "ctk.CTkFrame") -> None:
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(4, weight=1)

    # ── Cabeçalho (row 0) ───────────────────────────────────────────────
    hdr = ctk.CTkFrame(parent, fg_color="transparent")
    hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 6))
    hdr.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        hdr, text="⚡  Eventos Globais",
        font=ctk.CTkFont(size=24, weight="bold"),
    ).grid(row=0, column=0, sticky="w")
    ctk.CTkLabel(
        hdr,
        text="Eventos oficiais ARK (Páscoa, Halloween…) e rates temporários por servidor.",
        text_color="gray60",
    ).grid(row=1, column=0, sticky="w", pady=(0, 4))

    btn_bar = ctk.CTkFrame(hdr, fg_color="transparent")
    btn_bar.grid(row=0, column=2, rowspan=2, sticky="e", padx=(0, 0))
    ctk.CTkButton(
        btn_bar, text="⚡  Novo rate temporário", height=38, width=180,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        font=ctk.CTkFont(size=13, weight="bold"),
        command=app._open_create_buff_dialog,
    ).pack(side="left", padx=(0, 8))
    ctk.CTkButton(
        btn_bar, text="📋  Presets", height=38, width=120,
        fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=app._open_presets_manager,
    ).pack(side="left")

    # ── Evento ARK oficial — todos ou selecionados (row 1) ───────────────
    from .global_active_event import build_global_active_event_section

    global_evt = ctk.CTkFrame(parent, fg_color="transparent")
    global_evt.grid(row=1, column=0, sticky="ew")
    global_evt.grid_columnconfigure(0, weight=1)
    build_global_active_event_section(app, global_evt)

    ctk.CTkLabel(
        parent,
        text="RATES TEMPORÁRIOS (POR SERVIDOR)",
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color="#88d4a0",
    ).grid(row=2, column=0, padx=20, pady=(8, 4), sticky="w")

    # ── Seletor de servidor (row 3) ─────────────────────────────────────
    sel_bar = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=10)
    sel_bar.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 4))
    sel_bar.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        sel_bar, text="Servidor:", text_color="gray60",
        font=ctk.CTkFont(size=12),
    ).grid(row=0, column=0, padx=(16, 8), pady=10, sticky="w")

    app._buffs_server_var = tk.StringVar()
    entries = list_buff_servers(app)
    labels = [e.label for e in entries]
    srv_combo = ctk.CTkComboBox(
        sel_bar,
        variable=app._buffs_server_var,
        values=labels if labels else ["(nenhum servidor)"],
        state="readonly",
        width=300,
        command=lambda _: app._refresh_buffs_ui(),
    )
    if labels:
        app._buffs_server_var.set(labels[0])
    srv_combo.grid(row=0, column=1, padx=(0, 16), pady=10, sticky="w")

    # ── Body scrollável (row 4, reconstruído no refresh) ────────────────
    body = ctk.CTkScrollableFrame(parent, fg_color=_BG)
    body.grid(row=4, column=0, sticky="nsew", padx=0, pady=(4, 0))
    body.grid_columnconfigure(0, weight=1)
    app._buffs_body_frame = body

