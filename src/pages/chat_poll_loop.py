from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def chat_poll_loop(app: "ARKServerManagerApp", server_id: str) -> None:
    w = app._server_widgets.get(server_id, {})
    if not w.get("chat_auto_poll", tk.BooleanVar()).get():
        return
    app._chat_fetch(server_id)
    try:
        interval_ms = int(w.get("chat_interval", tk.StringVar(value="5")).get()) * 1000
    except (ValueError, AttributeError):
        interval_ms = 5000
    job = app.after(interval_ms, lambda: app._chat_poll_loop(server_id))
    app._chat_poll_jobs[server_id] = job

