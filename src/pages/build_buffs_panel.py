from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _GREEN_DARK, _GREEN_HOVER, _BLUE, _BLUE_HOVER, _CARD_BG, _BG
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_buffs_panel(app: "ARKServerManagerApp", parent: "ctk.CTkFrame") -> None:
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(2, weight=1)

    # ── Cabeçalho (row 0) ───────────────────────────────────────────────
    hdr = ctk.CTkFrame(parent, fg_color="transparent")
    hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 6))
    hdr.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        hdr, text="⚡  BUFFs — Rates Temporários",
        font=ctk.CTkFont(size=24, weight="bold"),
    ).grid(row=0, column=0, sticky="w")
    ctk.CTkLabel(
        hdr,
        text="Eventos globais de rates com início e fim automáticos — estilo servidores oficiais.",
        text_color="gray60",
    ).grid(row=1, column=0, sticky="w", pady=(0, 4))

    btn_bar = ctk.CTkFrame(hdr, fg_color="transparent")
    btn_bar.grid(row=0, column=2, rowspan=2, sticky="e", padx=(0, 0))
    ctk.CTkButton(
        btn_bar, text="⚡  Criar BUFF", height=38, width=150,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        font=ctk.CTkFont(size=13, weight="bold"),
        command=app._open_create_buff_dialog,
    ).pack(side="left", padx=(0, 8))
    ctk.CTkButton(
        btn_bar, text="📋  Presets", height=38, width=120,
        fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=app._open_presets_manager,
    ).pack(side="left")

    # ── Seletor de servidor (row 1) ─────────────────────────────────────
    sel_bar = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=10)
    sel_bar.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 4))
    sel_bar.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        sel_bar, text="Servidor:", text_color="gray60",
        font=ctk.CTkFont(size=12),
    ).grid(row=0, column=0, padx=(16, 8), pady=10, sticky="w")

    app._buffs_server_var = tk.StringVar()
    srv_names = [s.name for s in app.config_manager.servers]
    srv_combo = ctk.CTkComboBox(
        sel_bar,
        variable=app._buffs_server_var,
        values=srv_names if srv_names else ["(nenhum servidor)"],
        state="readonly",
        width=300,
        command=lambda _: app._refresh_buffs_ui(),
    )
    if srv_names:
        app._buffs_server_var.set(srv_names[0])
    srv_combo.grid(row=0, column=1, padx=(0, 16), pady=10, sticky="w")

    # ── Body scrollável (row 2, reconstruído no refresh) ────────────────
    body = ctk.CTkScrollableFrame(parent, fg_color=_BG)
    body.grid(row=2, column=0, sticky="nsew", padx=0, pady=(4, 0))
    body.grid_columnconfigure(0, weight=1)
    app._buffs_body_frame = body

