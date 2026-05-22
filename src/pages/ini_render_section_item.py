from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _RED_DARK, _RED_HOVER
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def ini_render_section_item(app: "ARKServerManagerApp", server_id: str, file_key: str, container, sec: dict) -> None:
    """Cria o item de seção no painel esquerdo."""
    is_custom = sec.get("mod_id") is None
    bg_btn = "#2a4060" if not is_custom else "#2a3a25"
    bg_hover = "#3a5080" if not is_custom else "#3a5230"
    src_text = (sec.get("mod_name") or "Personalizado")[:18]

    row = ctk.CTkFrame(container, fg_color="transparent")
    row.pack(fill="x", pady=1, padx=2)
    row.grid_columnconfigure(0, weight=1)

    btn = ctk.CTkButton(
        row, text=sec["section"], anchor="w", height=28,
        fg_color=bg_btn, hover_color=bg_hover,
        font=ctk.CTkFont(size=11),
        command=lambda s=sec["section"], sid=server_id, fk=file_key:
            app._ini_select_section(sid, fk, s))
    btn.grid(row=0, column=0, sticky="ew")

    del_btn = ctk.CTkButton(
        row, text="×", width=24, height=28,
        fg_color=_RED_DARK, hover_color=_RED_HOVER,
        font=ctk.CTkFont(size=13, weight="bold"),
        command=lambda s=sec["section"], sid=server_id, fk=file_key:
            app._ini_delete_section(sid, fk, s))
    del_btn.grid(row=0, column=1, padx=(2, 0))

    ctk.CTkLabel(row, text=f"  {src_text}", text_color="gray38",
                 font=ctk.CTkFont(size=9)).grid(row=1, column=0, sticky="w")

