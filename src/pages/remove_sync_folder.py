from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def remove_sync_folder(app: "ARKServerManagerApp", folders_frame, folder_vars: list, var: "tk.StringVar", row_frame, add_btn) -> None:
    """Remove uma linha de pasta de um ciclo (mantém pelo menos 1)."""
    if len(folder_vars) <= 1:
        var.set("")
        return
    if var in folder_vars:
        folder_vars.remove(var)
    row_frame.destroy()
    # Re-numera labels das linhas restantes
    for i, child in enumerate(folders_frame.winfo_children()):
        for lbl in child.winfo_children():
            if isinstance(lbl, ctk.CTkLabel):
                lbl.configure(text=f"Pasta {i + 1}:")
                break
    add_btn.configure(state="normal")

