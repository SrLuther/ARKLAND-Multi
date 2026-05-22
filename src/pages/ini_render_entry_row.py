from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _RED_DARK, _RED_HOVER
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def ini_render_entry_row(app: "ARKServerManagerApp", server_id: str, file_key: str, container, sec_data: dict, entry: dict, idx: int) -> None:
    """Cria uma linha Chave=Valor no painel direito."""
    if "_key_var" not in entry:
        entry["_key_var"] = tk.StringVar(value=entry.get("key", ""))
    if "_val_var" not in entry:
        entry["_val_var"] = tk.StringVar(value=entry.get("value", ""))

    row = ctk.CTkFrame(container, fg_color="transparent")
    row.grid(row=idx, column=0, columnspan=3, sticky="ew", pady=1)
    row.grid_columnconfigure(0, weight=1)
    row.grid_columnconfigure(1, weight=2)

    ctk.CTkEntry(row, textvariable=entry["_key_var"], height=28,
                 placeholder_text="chave",
                 font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="ew", padx=(0, 4))
    ctk.CTkEntry(row, textvariable=entry["_val_var"], height=28,
                 placeholder_text="valor",
                 font=ctk.CTkFont(size=11)).grid(row=0, column=1, sticky="ew")
    ctk.CTkButton(row, text="×", width=24, height=28,
                  fg_color=_RED_DARK, hover_color=_RED_HOVER,
                  font=ctk.CTkFont(size=13, weight="bold"),
                  command=lambda e=entry, sd=sec_data, sid=server_id, fk=file_key:
                      app._ini_del_entry(sid, fk, sd, e)).grid(row=0, column=2, padx=(4, 0))

