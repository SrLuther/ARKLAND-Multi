from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def ini_add_entry(app: "ARKServerManagerApp", server_id: str, file_key: str) -> None:
    """Adiciona uma nova linha vazia na seção selecionada."""
    w = app._server_widgets.get(server_id, {})
    sel = w.get(f"_ini_{file_key}_sel_section")
    if sel is None:
        return
    data = w.get(f"_ini_{file_key}_data", [])
    sec_data = next((s for s in data if s["section"] == sel), None)
    if sec_data is None:
        return
    new_entry = {"key": "", "value": ""}
    sec_data["entries"].append(new_entry)
    kv_scroll = w.get(f"_ini_{file_key}_kvscroll")
    if kv_scroll:
        idx = len(sec_data["entries"]) - 1
        app._ini_render_entry_row(server_id, file_key, kv_scroll, sec_data, new_entry, idx)

