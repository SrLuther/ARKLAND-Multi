"""
Rail de navegação — substitui a sidebar lateral.
48px de largura, ícones de seção, mode switch P/T no rodapé.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Dict

import tkinter as tk
import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import get_theme, _resource_path
from ..version import APP_VERSION

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

_RAIL_W = 56

# (ícone, chave de frame, tooltip)
_NAV_ITEMS_PRIMITIVE = [
    ("🏠", "dashboard",  "Dashboard"),
    ("⚡", "buffs",      "Eventos Globais"),
    ("📊", "desempenho", "Desempenho"),
    ("🔄", "sync",       "Sincronização"),
    ("🔗", "clusters",   "Clusters"),
    ("🖥",  "remoto",     "Remoto"),
    ("⚙",  "config",     "Configurações"),
    ("ℹ",  "sobre",      "Sobre"),
]

_NAV_ITEMS_TEK = [
    ("🏠", "dashboard",  "Dashboard TEK"),
    ("⚙",  "config",     "Configurações"),
    ("ℹ",  "sobre",      "Sobre"),
]

# Legado — aponta para PRIMITIVE (compatibilidade)
_NAV_ITEMS = _NAV_ITEMS_PRIMITIVE


def build_rail(app: "ARKServerManagerApp") -> None:
    theme = get_theme(app._active_mode)
    rail_bg = theme["rail_bg"]

    rail = tk.Frame(app, bg=rail_bg, width=_RAIL_W)
    rail.grid(row=0, column=0, sticky="nsew")
    rail.grid_propagate(False)
    app._rail = rail

    # ── Logo ─────────────────────────────────────────────────────────────────
    try:
        from PIL import Image, ImageTk  # type: ignore[reportMissingImports]
        _logo = Image.open(_resource_path(os.path.join("ig", "ark_manager.png"))).resize((36, 36))
        app._rail_logo_img = ImageTk.PhotoImage(_logo)
        logo_lbl = tk.Label(rail, image=app._rail_logo_img, bg=rail_bg, cursor="hand2")
        logo_lbl.pack(side="top", pady=(12, 8))
        logo_lbl.bind("<Button-1>", lambda _: app._show_frame("dashboard"))
    except Exception:
        tk.Label(rail, text="⚡", bg=rail_bg, fg=theme["accent"],
                 font=("Segoe UI", 18)).pack(side="top", pady=(12, 8))

    tk.Frame(rail, bg="#2a2a44", height=1).pack(fill="x", padx=8, pady=(0, 6))

    # ── Botões de navegação ──────────────────────────────────────────────────────────────────────────
    app._rail_nav_btns: Dict[str, tk.Label] = {}
    for icon, key, tooltip in _NAV_ITEMS_PRIMITIVE:
        btn = _make_rail_btn(rail, icon, rail_bg, theme["accent"])
        btn.pack(side="top", pady=2)
        btn.bind("<Button-1>", lambda _, k=key: _nav_click(app, k))
        _add_tooltip(btn, tooltip)
        app._rail_nav_btns[key] = btn

    # ── Rodapé: clock + mode switch ───────────────────────────────────────────
    footer = tk.Frame(rail, bg=rail_bg)
    footer.pack(side="bottom", fill="x", pady=(0, 8))

    # clock
    app._rail_clock_lbl = tk.Label(
        footer, text="", bg=rail_bg, fg="#55556a",
        font=("Segoe UI", 9),
    )
    app._rail_clock_lbl.pack(pady=(0, 4))
    app.after(100, app._sidebar_clock_tick)

    # separador
    tk.Frame(footer, bg="#2a2a44", height=1).pack(fill="x", padx=8, pady=(0, 6))

    # mode buttons P / T
    mode_row = tk.Frame(footer, bg=rail_bg)
    mode_row.pack()

    app._rail_mode_btns: Dict[str, tk.Label] = {}
    for short, mode in [("P", "primitive"), ("T", "tek")]:
        is_active = (app._active_mode == mode)
        fg = theme["accent"] if is_active else "#55556a"
        font_w = "bold" if is_active else "normal"
        btn = tk.Label(
            mode_row, text=short, bg=rail_bg, fg=fg,
            font=("Segoe UI", 11, font_w),
            width=2, cursor="hand2",
        )
        btn.pack(side="left", padx=2)
        btn.bind("<Button-1>", lambda _, m=mode: app._switch_mode(m))
        app._rail_mode_btns[mode] = btn

    # ── Atualiza highlight do nav btn ativo ───────────────────────────────────
    _set_rail_active(app, app._current_frame or "dashboard")


def _make_rail_btn(parent, icon: str, bg: str, accent: str) -> tk.Label:
    return tk.Label(
        parent, text=icon, bg=bg, fg="#8888aa",
        font=("Segoe UI Emoji", 14),
        width=3, height=1,
        anchor="center", cursor="hand2",
    )


def _nav_click(app: "ARKServerManagerApp", key: str) -> None:
    app._show_frame(key)


def _set_rail_active(app: "ARKServerManagerApp", key: str) -> None:
    """Atualiza o destaque visual do botão de nav ativo no rail."""
    theme = get_theme(app._active_mode)
    for k, btn in getattr(app, "_rail_nav_btns", {}).items():
        btn.configure(fg=theme["accent"] if k == key else "#8888aa")


# ── Tooltip simples ───────────────────────────────────────────────────────────

class _Tooltip:
    def __init__(self, widget, text: str):
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)
        self._text = text

    def _show(self, event) -> None:
        x = event.widget.winfo_rootx() + _RAIL_W + 4
        y = event.widget.winfo_rooty()
        self._tip = tk.Toplevel()
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self._tip, text=self._text,
            bg="#1e1e30", fg="#d8d8e8",
            font=("Segoe UI", 10),
            relief="flat", padx=8, pady=4,
        ).pack()

    def _hide(self, _event) -> None:
        if self._tip:
            self._tip.destroy()
            self._tip = None


def _add_tooltip(widget, text: str) -> None:
    _Tooltip(widget, text)
