from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _BG
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def open_server_panel(app: "ARKServerManagerApp", server_id: str) -> None:
    if server_id not in app._server_frames:
        srv = app.config_manager.get_server(server_id)
        if not srv:
            return
        frame = ctk.CTkFrame(app._page_area, corner_radius=0, fg_color=_BG)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_remove()
        app._server_frames[server_id] = frame
        app._server_widgets[server_id] = {}
        app._build_server_panel(frame, srv)
        app._frames[f"server_{server_id}"] = frame

    # Adiciona tab se ainda não existir
    if getattr(app, "_server_tab_bar", None):
        srv2 = app.config_manager.get_server(server_id)
        if srv2:
            from ..ui_constants import _STATUS_COLOR
            status = getattr(app, "_server_status", {}).get(server_id, "stopped")
            color = _STATUS_COLOR.get(status, "#ff6666")
            tab_name = getattr(srv2, "server_name", None) or getattr(srv2, "name", server_id)
            app._server_tab_bar.add_tab(server_id, tab_name, color)
    app._show_frame(f"server_{server_id}")

