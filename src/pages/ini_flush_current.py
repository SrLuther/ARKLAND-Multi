from __future__ import annotations
import os
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def ini_flush_current(app: "ARKServerManagerApp", server_id: str, file_key: str) -> None:
    """Salva o conteúdo dos StringVars da seção exibida de volta nos dados."""
    w = app._server_widgets.get(server_id, {})
    sel = w.get(f"_ini_{file_key}_sel_section")
    if sel is None:
        return
    data = w.get(f"_ini_{file_key}_data", [])
    sec_data = next((s for s in data if s["section"] == sel), None)
    if sec_data is None:
        return
    # Atualiza nome da seção
    name_var = w.get(f"_ini_{file_key}_sec_name_var")
    if name_var:
        new_name = name_var.get().strip()
        if new_name and new_name != sel:
            sec_data["section"] = new_name
            w[f"_ini_{file_key}_sel_section"] = new_name
    # Atualiza entradas (os StringVars estão in-place no dicionário)
    for entry in sec_data.get("entries", []):
        kv = entry.get("_key_var")
        vv = entry.get("_val_var")
        if kv:
            entry["key"] = kv.get()
        if vv:
            entry["value"] = vv.get()

