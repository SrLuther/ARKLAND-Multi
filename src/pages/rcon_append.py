from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING, Optional
import customtkinter as ctk  # type: ignore[reportMissingImports]
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

_MAX_LINES = 1000   # mantém no máximo 1000 linhas no log; descarta as mais antigas


def rcon_append(app: "ARKServerManagerApp", server_id: str, text: str, tag: str = "resp") -> None:
    """Adiciona texto ao log RCON. Descarta linhas antigas quando passa de _MAX_LINES."""
    w: dict = app._server_widgets.get(server_id, {})
    box: Optional[ctk.CTkTextbox] = w.get("rcon_output")
    if not box:
        return
    tb = box._textbox
    box.configure(state="normal")
    tb.insert("end", text, tag)
    # Trimming: mantém no máximo _MAX_LINES linhas
    total_lines = int(tb.index("end-1c").split(".")[0])
    if total_lines > _MAX_LINES:
        excess = total_lines - _MAX_LINES
        tb.delete("1.0", f"{excess + 1}.0")
    tb.see("end")
    box.configure(state="disabled")

