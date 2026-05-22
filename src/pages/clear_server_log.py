from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def clear_server_log(app: "ARKServerManagerApp", server_id: str) -> None:
    inst = app.server_manager.get_instance(server_id)
    if inst and hasattr(inst, "log_buffer"):
        inst.log_buffer.clear()
    w = app._server_widgets.get(server_id, {})
    box: Optional[ctk.CTkTextbox] = w.get("_log_box")
    if box:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.configure(state="disabled")

