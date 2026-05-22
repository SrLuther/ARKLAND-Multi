from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def remove_admin_id(app: "ARKServerManagerApp", server_id: str, steam_id: str) -> None:
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return
    if steam_id in srv.admin_ids:
        srv.admin_ids.remove(steam_id)
    srv.admin_names.pop(steam_id, None)
    app.config_manager.update_server(srv)
    app._write_allowed_admins(server_id)
    app._refresh_admins_list(server_id)

