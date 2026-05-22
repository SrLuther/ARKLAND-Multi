from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _MAX_SYNC_FOLDERS, _RED_DARK
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def add_sync_folder(app: "ARKServerManagerApp", folders_frame, folder_vars: list, add_btn, path: str = "") -> None:
    """Adiciona uma linha de pasta em um ciclo."""
    if len(folder_vars) >= _MAX_SYNC_FOLDERS:
        return
    var = tk.StringVar(value=path)
    folder_vars.append(var)
    idx = len(folder_vars) - 1

    row = ctk.CTkFrame(folders_frame, fg_color="transparent")
    row.pack(fill="x", pady=2)
    row.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(row, text=f"Pasta {idx + 1}:",
                 text_color="gray50", width=60, anchor="e",
                 font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(0, 4))
    ctk.CTkEntry(row, textvariable=var, height=28,
                 placeholder_text="Caminho da pasta...").grid(
        row=0, column=1, padx=(0, 4), sticky="ew")
    ctk.CTkButton(
        row, text="📁", width=30, height=28,
        fg_color="#2a2a40", hover_color="#363656",
        command=lambda v=var: app._browse_sync_folder(v),
    ).grid(row=0, column=2, padx=(0, 4))
    ctk.CTkButton(
        row, text="✕", width=28, height=28,
        fg_color="transparent", hover_color=_RED_DARK, text_color="gray50",
        command=lambda v=var, r=row, ff=folders_frame, fv=folder_vars, ab=add_btn:
            app._remove_sync_folder(ff, fv, v, r, ab),
    ).grid(row=0, column=3)

    add_btn.configure(
        state="disabled" if len(folder_vars) >= _MAX_SYNC_FOLDERS else "normal")

