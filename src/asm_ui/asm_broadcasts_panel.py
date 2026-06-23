"""Painel global de broadcasts TEK — cadastro, envio e sync."""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp


def build_broadcasts_panel(app: "ARKServerManagerApp", parent: ctk.CTkFrame) -> None:
    theme = get_theme("tek")
    accent = theme["accent"]
    bg = theme["bg"]
    card_bg = theme["card_bg"]
    sep = theme["separator"]
    t_pri = theme["text_primary"]
    t_sec = theme["text_secondary"]
    t_mut = theme["text_muted"]
    acc_mb = theme["accent_muted_bg"]
    acc_dk = theme["accent_dark"]
    is_light = theme.get("_is_light", False)
    card_bdr = theme.get("card_border", sep)

    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(2, weight=1)

    n_servers = len(app.asm_config_manager.servers)

    # ── Cabeçalho ─────────────────────────────────────────────────────────────
    hdr = ctk.CTkFrame(parent, fg_color="transparent")
    hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 8))
    hdr.grid_columnconfigure(0, weight=1)

    title_col = ctk.CTkFrame(hdr, fg_color="transparent")
    title_col.grid(row=0, column=0, sticky="w")
    ctk.CTkLabel(
        title_col, text="📢  Broadcasts",
        font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
        text_color=t_pri,
    ).pack(anchor="w")
    ctk.CTkLabel(
        title_col,
        text="Biblioteca global — envie mensagens a todos os servidores gerenciados via RCON.",
        font=ctk.CTkFont(size=12),
        text_color=t_sec,
    ).pack(anchor="w", pady=(4, 0))

    btn_bar = ctk.CTkFrame(hdr, fg_color="transparent")
    btn_bar.grid(row=0, column=1, sticky="e")
    ctk.CTkButton(
        btn_bar, text="⬇  Importar", width=110, height=36,
        fg_color=acc_mb, hover_color=acc_dk,
        text_color=accent, border_width=1, border_color=acc_dk,
        command=app._broadcast_tek_import,
    ).pack(side="left", padx=(0, 8))
    ctk.CTkButton(
        btn_bar, text="⬆  Exportar", width=110, height=36,
        fg_color=acc_mb, hover_color=acc_dk,
        text_color=accent, border_width=1, border_color=acc_dk,
        command=app._broadcast_tek_export,
    ).pack(side="left")

    # ── Envio rápido ──────────────────────────────────────────────────────────
    quick = ctk.CTkFrame(parent, fg_color=card_bg, corner_radius=10,
                         border_width=1, border_color=card_bdr)
    quick.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 8))
    quick.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        quick, text="📡 Envio rápido",
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=t_sec,
    ).grid(row=0, column=0, padx=(14, 8), pady=12, sticky="w")

    app._broadcast_quick_var = tk.StringVar()
    ctk.CTkEntry(
        quick, textvariable=app._broadcast_quick_var, height=34,
        placeholder_text="Mensagem para todos os servidores gerenciados...",
        font=ctk.CTkFont(size=11),
    ).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=12)

    send_bg = "#dcfce7" if is_light else "#052e16"
    send_hover = "#bbf7d0" if is_light else "#14532d"
    send_tc = "#166534" if is_light else "#4ade80"

    ctk.CTkButton(
        quick, text="📢  Enviar a todos", width=140, height=34,
        fg_color=send_bg, hover_color=send_hover,
        text_color=send_tc,
        font=ctk.CTkFont(size=11, weight="bold"),
        command=app._broadcast_tek_send_quick,
    ).grid(row=0, column=2, padx=(0, 14), pady=12)

    ctk.CTkLabel(
        quick,
        text=f"{n_servers} servidor(es) gerenciado(s) — tenta RCON em cada um",
        font=ctk.CTkFont(size=10),
        text_color=t_mut,
    ).grid(row=1, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))

    # ── Cadastro ──────────────────────────────────────────────────────────────
    body = ctk.CTkScrollableFrame(parent, fg_color=bg, corner_radius=0)
    body.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)
    body.grid_columnconfigure(0, weight=1)

    add_fr = ctk.CTkFrame(body, fg_color=card_bg, corner_radius=10,
                          border_width=1, border_color=card_bdr)
    add_fr.grid(row=0, column=0, sticky="ew", padx=20, pady=(8, 8))
    add_fr.grid_columnconfigure(2, weight=1)

    ctk.CTkLabel(
        add_fr, text="+ Nova mensagem",
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=t_sec,
    ).grid(row=0, column=0, padx=(14, 8), pady=12, sticky="w")

    app._broadcast_new_label = tk.StringVar()
    ctk.CTkEntry(
        add_fr, textvariable=app._broadcast_new_label, height=32, width=180,
        placeholder_text="Rótulo (ex: Reinício 5min)",
        font=ctk.CTkFont(size=11),
    ).grid(row=0, column=1, padx=(0, 8), pady=12, sticky="w")

    app._broadcast_new_msg = tk.StringVar()
    ctk.CTkEntry(
        add_fr, textvariable=app._broadcast_new_msg, height=32,
        placeholder_text="Texto do broadcast...",
        font=ctk.CTkFont(size=11),
    ).grid(row=0, column=2, sticky="ew", padx=(0, 8), pady=12)

    ctk.CTkButton(
        add_fr, text="Adicionar", width=100, height=32,
        fg_color=acc_mb, hover_color=acc_dk,
        text_color=accent, border_width=1, border_color=acc_dk,
        font=ctk.CTkFont(size=11, weight="bold"),
        command=app._broadcast_library_add_from_ui,
    ).grid(row=0, column=3, padx=(0, 14), pady=12)

    ctk.CTkLabel(
        body, text="Mensagens salvas",
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color=t_mut,
    ).grid(row=1, column=0, sticky="w", padx=24, pady=(4, 2))

    lib_scroll = ctk.CTkScrollableFrame(body, fg_color="transparent")
    lib_scroll.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 8))
    lib_scroll.grid_columnconfigure(0, weight=1)
    body.grid_rowconfigure(2, weight=1)
    app._broadcast_lib_scroll = lib_scroll

    ctk.CTkLabel(
        body,
        text="Biblioteca global — sincronize entre PCs com Exportar / Importar (.arkbroadcast)",
        font=ctk.CTkFont(size=10),
        text_color=t_mut,
    ).grid(row=3, column=0, sticky="w", padx=24, pady=(0, 16))

    app._broadcast_library_refresh()
