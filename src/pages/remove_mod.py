from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def remove_mod(app: "ARKServerManagerApp", server_id: str, mod_id: str) -> None:
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return
    if mod_id in srv.mods:
        srv.mods.remove(mod_id)
    srv.mod_names.pop(mod_id, None)
    srv.mod_ini_configs.pop(mod_id, None)
    app.config_manager.update_server(srv)
    app._refresh_mods_list(server_id)

