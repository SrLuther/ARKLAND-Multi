from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def ini_delete_section(app: "ARKServerManagerApp", server_id: str, file_key: str, section_name: str) -> None:
    """Remove a seção da lista."""
    w = app._server_widgets.get(server_id, {})
    data = w.get(f"_ini_{file_key}_data", [])
    data[:] = [s for s in data if s["section"] != section_name]
    if w.get(f"_ini_{file_key}_sel_section") == section_name:
        w[f"_ini_{file_key}_sel_section"] = None
        kv_scroll = w.get(f"_ini_{file_key}_kvscroll")
        if kv_scroll:
            for ch in kv_scroll.winfo_children():
                ch.destroy()
        name_var = w.get(f"_ini_{file_key}_sec_name_var")
        if name_var:
            name_var.set("")
    # Reconstrói lista (mais simples que remover item individual)
    app._ini_rebuild_section_list(server_id, file_key)

