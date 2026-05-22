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
        frame = ctk.CTkFrame(app, corner_radius=0, fg_color=_BG)
        frame.grid(row=0, column=1, sticky="nsew")
        frame.grid_remove()
        app._server_frames[server_id] = frame
        app._server_widgets[server_id] = {}
        app._build_server_panel(frame, srv)
        app._frames[f"server_{server_id}"] = frame

    app._show_frame(f"server_{server_id}")

