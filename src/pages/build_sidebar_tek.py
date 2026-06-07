"""Constrói a sidebar TEK (modo ASM)."""
from __future__ import annotations
import os
from typing import TYPE_CHECKING, Dict
import tkinter as tk
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..asm_engine.asm_theme import get_theme, get_tek_variant
from ..utils import _resource_path
from ..version import APP_VERSION
try:
    from PIL import Image as _PILImage  # type: ignore[reportMissingImports]
except ImportError:
    _PILImage = None  # type: ignore[assignment]
if TYPE_CHECKING:
    from ..app_tek import ARKTEKApp

_SIDEBAR_W = 220


def _build_sidebar_tek_logo(app, sb, accent: str, t_muted: str) -> None:
    logo_f = ctk.CTkFrame(sb, fg_color="transparent")
    logo_f.grid(row=0, column=0, padx=20, pady=(20, 0), sticky="ew")
    logo_f.grid_columnconfigure(1, weight=1)
    logo_loaded = False
    try:
        _img = _PILImage.open(_resource_path(os.path.join("ig", "ark_manager.png")))
        _logo_ctk = ctk.CTkImage(light_image=_img, dark_image=_img, size=(66, 44))
        ctk.CTkLabel(logo_f, image=_logo_ctk, text="").grid(row=0, column=0, rowspan=2, padx=(0, 12))
        logo_loaded = True
    except Exception:
        pass
    col = 1 if logo_loaded else 0
    ctk.CTkLabel(logo_f, text="ARK Manager",
                 font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
                 text_color=accent).grid(row=0, column=col, sticky="w")
    ctk.CTkLabel(logo_f, text="Command Center",
                 font=ctk.CTkFont(family="Segoe UI", size=10),
                 text_color=t_muted).grid(row=1, column=col, sticky="w")


def _build_sidebar_tek_nav(app, sb, theme: dict, accent: str,
                            t_sec: str, sep_col: str) -> int:
    ctk.CTkFrame(sb, height=1, fg_color=sep_col).grid(
        row=1, column=0, sticky="ew", padx=16, pady=(4, 8))
    nav_items = [
        ("⊞",  "dashboard",  "Dashboard"),
        ("🔄", "sync",       "Sincronização"),
        ("⚡", "buffs",      "BUFFs"),
        ("📊", "desempenho", "Desempenho"),
        ("🔴", "crashes",    "Crashes"),
        ("🔗", "clusters",   "Clusters"),
        ("🖥",  "remoto",     "Remoto"),
        ("⚙",  "settings",   "Configurações"),
        ("ℹ",  "about",      "Sobre"),
    ]
    app._nav_btns: Dict[str, ctk.CTkButton] = {}
    for i, (icon, key, label) in enumerate(nav_items):
        btn = ctk.CTkButton(
            sb, text=f"  {icon}  {label}", anchor="w",
            width=_SIDEBAR_W - 24, height=40, fg_color="transparent",
            text_color=accent if key == app._nav_active else t_sec,
            hover_color=theme["accent_hover"], corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI", size=12,
                             weight="bold" if key == app._nav_active else "normal"),
            command=lambda k=key: app._show_frame(k),
        )
        btn.grid(row=3 + i, column=0, padx=12, pady=2, sticky="ew")
        app._nav_btns[key] = btn
    return 3 + len(nav_items)


def _build_sidebar_tek_servers(app, sb, sep_row: int,
                                sep_col: str, theme: dict, accent: str) -> None:
    ctk.CTkFrame(sb, height=1, fg_color=sep_col).grid(
        row=sep_row, column=0, sticky="ew", padx=16, pady=(8, 6))
    srv_hdr = ctk.CTkFrame(sb, fg_color="transparent")
    srv_hdr.grid(row=sep_row + 1, column=0, padx=16, pady=(0, 4), sticky="ew")
    srv_hdr.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(srv_hdr, text="SERVIDORES",
                 font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                 text_color=theme["text_muted"]).grid(row=0, column=0, sticky="w")
    ctk.CTkButton(srv_hdr, text="＋", width=26, height=22,
                  fg_color=theme["accent_muted_bg"], hover_color=theme["accent_hover"],
                  text_color=accent, font=ctk.CTkFont(size=13, weight="bold"),
                  corner_radius=6, command=app._asm_add_server_dialog).grid(row=0, column=1)
    app._servers_list_sb = ctk.CTkScrollableFrame(
        sb, fg_color="transparent", height=160, scrollbar_button_color=sep_col)
    app._servers_list_sb.grid(row=sep_row + 2, column=0, sticky="ew", padx=8)
    app._servers_list_sb.grid_columnconfigure(0, weight=1)


def _build_sidebar_tek_footer(app, sb, sep_row: int,
                               sep_col: str, theme: dict, accent: str, t_muted: str) -> None:
    ctk.CTkFrame(sb, height=1, fg_color=sep_col).grid(
        row=sep_row + 3, column=0, sticky="ew", padx=16, pady=(8, 4))
    footer_f = ctk.CTkFrame(sb, fg_color="transparent")
    footer_f.grid(row=sep_row + 4, column=0, padx=16, pady=(0, 4), sticky="ew")
    footer_f.grid_columnconfigure(0, weight=1)
    app._sidebar_clock_lbl = ctk.CTkLabel(
        footer_f, text="",
        font=ctk.CTkFont(family="Segoe UI", size=10), text_color=t_muted)
    app._sidebar_clock_lbl.grid(row=0, column=0, sticky="w")
    ctk.CTkLabel(footer_f, text=f"v{APP_VERSION}",
                 font=ctk.CTkFont(size=10), text_color=t_muted).grid(row=0, column=1, sticky="e")
    _is_light   = get_tek_variant() == "light"
    _toggle_icon = "☀ Claro" if _is_light else "🌙 Escuro"
    ctk.CTkButton(
        sb, text=_toggle_icon, width=_SIDEBAR_W - 32, height=28,
        fg_color=theme["accent_muted_bg"], hover_color=theme["accent_hover"],
        text_color=accent, font=ctk.CTkFont(family="Segoe UI", size=11),
        corner_radius=8, command=app._toggle_theme,
    ).grid(row=sep_row + 5, column=0, padx=16, pady=(0, 14), sticky="ew")


def build_sidebar_tek(app) -> None:
    theme   = get_theme("tek")
    sb_bg   = theme["sidebar_bg"]
    accent  = theme["accent"]
    sep_col = theme["separator"]
    t_sec   = theme["text_secondary"]
    t_muted = theme["text_muted"]

    sb = ctk.CTkFrame(app, width=_SIDEBAR_W, corner_radius=0, fg_color=sb_bg)
    sb.grid(row=0, column=0, sticky="nsew")
    sb.grid_propagate(False)
    sb.grid_columnconfigure(0, weight=1)
    app._sidebar = sb

    _build_sidebar_tek_logo(app, sb, accent, t_muted)
    sep_row = _build_sidebar_tek_nav(app, sb, theme, accent, t_sec, sep_col)
    _build_sidebar_tek_servers(app, sb, sep_row, sep_col, theme, accent)
    _build_sidebar_tek_footer(app, sb, sep_row, sep_col, theme, accent, t_muted)

    app.after(100, app._sidebar_clock_tick)
    app.after(60_000, app._asm_scheduler_tick)
    app._rebuild_server_sidebar()
