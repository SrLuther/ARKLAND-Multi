"""
Content host — constrói o container col=1:
  row=0  server_tab_bar  (38px, sempre visível)
  row=1  _page_area      (flex, frames de página vivem aqui)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import tkinter as tk
import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import get_theme
from ..ui_components import ServerTabBar

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_content_host(app: "ARKServerManagerApp") -> None:
    theme = get_theme(app._active_mode)
    tab_bg = theme["tab_bar_bg"]
    bg = theme["bg"]

    host = tk.Frame(app, bg=bg)
    host.grid(row=0, column=1, sticky="nsew")
    app._content_host = host

    # ── Server tab bar (pack para evitar conflito com separador interno) ──────
    tab_bar = ServerTabBar(
        host,
        on_select=lambda sid: (
            app._asm_open_server_panel(sid)
            if app._active_mode == "tek"
            else app._open_server_panel(sid)
        ),
        on_add=lambda: (
            app._asm_add_server_dialog()
            if app._active_mode == "tek"
            else app._add_server_dialog()
        ),
        on_close=lambda sid: app._close_server_tab(sid),
        accent=theme["accent"],
        bg=tab_bg,
    )
    tab_bar.pack(side="top", fill="x")
    app._server_tab_bar = tab_bar

    # Separador
    tk.Frame(host, bg="#2a2a44", height=1).pack(side="top", fill="x")

    # ── Page area ─────────────────────────────────────────────────────────────
    page_area = tk.Frame(host, bg=bg)
    page_area.pack(side="top", fill="both", expand=True)
    page_area.grid_columnconfigure(0, weight=1)
    page_area.grid_rowconfigure(0, weight=1)
    app._page_area = page_area
