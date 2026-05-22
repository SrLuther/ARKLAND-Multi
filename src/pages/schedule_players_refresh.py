from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def schedule_players_refresh(app: "ARKServerManagerApp", server_id: str) -> None:
    w = app._server_widgets.get(server_id, {})
    auto_var: Optional[tk.BooleanVar] = w.get("_players_auto_var")
    if not auto_var or not auto_var.get():
        return
    app._refresh_players(server_id)
    job = app.after(30_000, lambda: app._schedule_players_refresh(server_id))
    w["_players_auto_job"] = job

