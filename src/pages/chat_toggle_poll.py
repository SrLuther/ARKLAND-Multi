from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def chat_toggle_poll(app: "ARKServerManagerApp", server_id: str) -> None:
    w = app._server_widgets.get(server_id, {})
    enabled = w.get("chat_auto_poll", tk.BooleanVar()).get()
    if enabled:
        app._chat_poll_loop(server_id)
    else:
        app._chat_cancel_poll(server_id)
        status_var: Optional[tk.StringVar] = w.get("chat_status_var")
        if status_var:
            status_var.set("⬛ Pausado")

