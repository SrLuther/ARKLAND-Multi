from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def remove_sync_cycle(app: "ARKServerManagerApp", card, folder_vars: list) -> None:
    """Remove um ciclo do painel."""
    if folder_vars in app._sync_cycle_vars:
        app._sync_cycle_vars.remove(folder_vars)
    card.destroy()
    app._refresh_add_cycle_btn()
    # Renumera os labels dos ciclos restantes
    for i, child in enumerate(app._sync_cycles_frame.winfo_children()):
        for sub in child.winfo_children():
            if not isinstance(sub, ctk.CTkFrame):
                continue
            for lbl in sub.winfo_children():
                if isinstance(lbl, ctk.CTkLabel) and lbl.cget("text").startswith("Ciclo "):
                    lbl.configure(text=f"Ciclo {i + 1}")
                    break
            break

