from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def on_server_log(app: "ARKServerManagerApp", server_id: str, msg: str, level: str) -> None:
    def _do():
        w = app._server_widgets.get(server_id, {})
        box: Optional[ctk.CTkTextbox] = w.get("_log_box")
        if box:
            box.configure(state="normal")
            box._textbox.insert("end", msg + "\n", level)
            box._textbox.see("end")
            box.configure(state="disabled")
    app.after(0, _do)

