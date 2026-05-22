from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def toggle_players_auto(app: "ARKServerManagerApp", server_id: str) -> None:
    w = app._server_widgets.get(server_id, {})
    auto_var: Optional[tk.BooleanVar] = w.get("_players_auto_var")
    if not auto_var:
        return
    if auto_var.get():
        app._schedule_players_refresh(server_id)
    else:
        job = w.get("_players_auto_job")
        if job:
            try:
                app.after_cancel(job)
            except Exception:
                pass
            w["_players_auto_job"] = None

