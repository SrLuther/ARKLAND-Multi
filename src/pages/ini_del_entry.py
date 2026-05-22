from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def ini_del_entry(app: "ARKServerManagerApp", server_id: str, file_key: str, sec_data: dict, entry: dict) -> None:
    """Remove uma entrada da seção e reconstrói o painel de entradas."""
    sec_data["entries"] = [e for e in sec_data["entries"] if e is not entry]
    # Remove os StringVars para forçar recriação
    for e in sec_data["entries"]:
        e.pop("_key_var", None)
        e.pop("_val_var", None)
    app._ini_select_section(server_id, file_key, sec_data["section"])

