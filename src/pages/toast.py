from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def toast(app: "ARKServerManagerApp", msg: str, kind: str = "info") -> None:
    """Exibe uma notificação flutuante breve na parte inferior da janela."""
    colors = {"info": "#1e4a2a", "warning": "#5a4a00", "error": "#5a1a1a"}
    fg = colors.get(kind, colors["info"])
    label = ctk.CTkLabel(app, text=msg, fg_color=fg, corner_radius=8,
                         padx=16, pady=10, wraplength=500)
    label.place(relx=0.5, rely=0.97, anchor="s")
    app.after(3500, label.destroy)

