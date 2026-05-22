from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def ini_add_section(app: "ARKServerManagerApp", server_id: str, file_key: str) -> None:
    """Adiciona uma nova seção personalizada vazia."""
    w = app._server_widgets.get(server_id, {})
    data = w.get(f"_ini_{file_key}_data", [])
    new_sec = {
        "section": f"NovaSeção_{len(data)+1}",
        "mod_id": None,
        "mod_name": "Personalizado",
        "entries": [],
    }
    data.append(new_sec)
    sec_scroll = w.get(f"_ini_{file_key}_secscroll")
    if sec_scroll:
        # Remove mensagem de vazio se existir
        for ch in list(sec_scroll.winfo_children()):
            if isinstance(ch, ctk.CTkLabel):
                ch.destroy()
        app._ini_render_section_item(server_id, file_key, sec_scroll, new_sec)
    app._ini_select_section(server_id, file_key, new_sec["section"])

