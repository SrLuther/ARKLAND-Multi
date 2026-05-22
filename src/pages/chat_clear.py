from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def chat_clear(app: "ARKServerManagerApp", server_id: str) -> None:
    w = app._server_widgets.get(server_id, {})
    box: Optional[ctk.CTkTextbox] = w.get("chat_box")
    if not box:
        return
    box.configure(state="normal")
    box.delete("1.0", "end")
    box.configure(state="disabled")

