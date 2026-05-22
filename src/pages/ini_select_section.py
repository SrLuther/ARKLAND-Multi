from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def ini_select_section(app: "ARKServerManagerApp", server_id: str, file_key: str, section_name: str) -> None:
    """Exibe as entradas da seção selecionada no painel direito."""
    w = app._server_widgets.get(server_id, {})
    # Flush da seção anterior
    app._ini_flush_current(server_id, file_key)

    data = w.get(f"_ini_{file_key}_data", [])
    sec_data = next((s for s in data if s["section"] == section_name), None)
    if sec_data is None:
        return

    w[f"_ini_{file_key}_sel_section"] = section_name
    name_var = w.get(f"_ini_{file_key}_sec_name_var")
    if name_var:
        name_var.set(section_name)

    kv_scroll = w.get(f"_ini_{file_key}_kvscroll")
    if kv_scroll is None:
        return
    for ch in kv_scroll.winfo_children():
        ch.destroy()

    for idx, entry in enumerate(sec_data.get("entries", [])):
        app._ini_render_entry_row(server_id, file_key, kv_scroll, sec_data, entry, idx)

