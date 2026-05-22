from __future__ import annotations
import os
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _BG
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def rebuild_server_panel(app: "ARKServerManagerApp", server_id: str) -> None:
    """Reconstrói o painel completo de um servidor para refletir valores atualizados."""
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return
    frame_key = f"server_{server_id}"
    old_frame = app._frames.get(frame_key)
    if old_frame is None:
        return

    # Reinicia o dict de widgets para este servidor
    app._server_widgets[server_id] = {}

    new_frame = ctk.CTkFrame(app, corner_radius=0, fg_color=_BG)
    new_frame.grid(row=0, column=1, sticky="nsew")
    app._build_server_panel(new_frame, srv)
    app._frames[frame_key] = new_frame

    old_frame.destroy()
    app._show_frame(frame_key)

