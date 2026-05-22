from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def chat_append(app: "ARKServerManagerApp", server_id: str, text: str, tag: str = "message") -> None:
    w = app._server_widgets.get(server_id, {})
    box: Optional[ctk.CTkTextbox] = w.get("chat_box")
    if not box:
        return
    box.configure(state="normal")
    box._textbox.insert("end", text, tag)
    box._textbox.see("end")
    box.configure(state="disabled")

