from __future__ import annotations
import os
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def ini_rebuild_section_list(app: "ARKServerManagerApp", server_id: str, file_key: str) -> None:
    """Reconstrói a lista de seções no painel esquerdo sem perder os dados."""
    w = app._server_widgets.get(server_id, {})
    sec_scroll = w.get(f"_ini_{file_key}_secscroll")
    if sec_scroll is None:
        return
    for ch in sec_scroll.winfo_children():
        ch.destroy()
    data = w.get(f"_ini_{file_key}_data", [])
    if not data:
        ctk.CTkLabel(sec_scroll,
                     text="Nenhuma seção encontrada.\n"
                          "Adicione uma seção ou configure\n"
                          "o INI de algum mod.",
                     text_color="gray40", font=ctk.CTkFont(size=10),
                     justify="center").pack(pady=20, padx=8)
        return
    for sec in data:
        app._ini_render_section_item(server_id, file_key, sec_scroll, sec)

