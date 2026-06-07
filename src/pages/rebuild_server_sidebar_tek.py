"""Reconstrói a lista de servidores na sidebar TEK."""
from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..asm_engine.asm_theme import get_theme
from ..asm_engine.asm_constants import ASM_STATUS_RUNNING
if TYPE_CHECKING:
    from ..app_tek import ARKTEKApp


def rebuild_server_sidebar_tek(app) -> None:
    """Reconstrói a lista de servidores na sidebar."""
    for w in app._servers_list_sb.winfo_children():
        w.destroy()
    app._sidebar_server_btns.clear()

    theme   = get_theme("tek")
    accent  = theme["accent"]
    sb_bg   = theme["sidebar_bg"]
    t_sec   = theme["text_secondary"]
    hover   = theme["accent_hover"]

    servers = app.asm_config_manager.servers
    if not servers:
        ctk.CTkLabel(
            app._servers_list_sb,
            text="Nenhum servidor.\nClique ＋ para adicionar.",
            text_color=theme["text_muted"],
            font=ctk.CTkFont(size=10), justify="center",
        ).pack(pady=12)
        return

    for srv in servers:
        inst   = app.asm_server_manager.get_instance(srv.id)
        status = inst.status if inst else ASM_STATUS_STOPPED
        dot_color = (
            "#22c55e" if status == ASM_STATUS_RUNNING
            else "#f59e0b" if status in ("starting", "stopping", "updating")
            else "#64748b"
        )
        row_f = ctk.CTkFrame(app._servers_list_sb, fg_color="transparent")
        row_f.pack(fill="x", pady=1)
        row_f.grid_columnconfigure(1, weight=1)

        tk.Label(
            row_f, text="●", fg=dot_color,
            bg=sb_bg, font=("Segoe UI", 9),
        ).grid(row=0, column=0, padx=(4, 2))

        btn = ctk.CTkButton(
            row_f, text=srv.name, anchor="w", height=32,
            fg_color="transparent", text_color=t_sec,
            hover_color=hover, corner_radius=8,
            font=ctk.CTkFont(size=11),
            command=lambda sid=srv.id: app._asm_open_server_panel(sid),
        )
        btn.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        app._sidebar_server_btns[srv.id] = btn

