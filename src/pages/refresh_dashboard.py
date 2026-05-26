from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _GREEN
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def refresh_dashboard(app: "ARKServerManagerApp") -> None:
    frame = app._dashboard_scroll
    for w in frame.winfo_children():
        w.destroy()

    servers = app.config_manager.servers
    if not servers:
        ctk.CTkLabel(
            frame,
            text="Nenhum servidor configurado.\nClique em '＋ Novo Servidor' para começar.",
            font=ctk.CTkFont(size=15), text_color="gray50", justify="center",
        ).grid(row=0, column=0, columnspan=2, pady=60)
        return

    for idx, srv in enumerate(servers):
        row, col = divmod(idx, 2)
        app._build_server_card(frame, srv, row, col)

