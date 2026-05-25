from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def download_mod(app: "ARKServerManagerApp", server_id: str, mod_id: str) -> None:
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return
    from ..dialogs.mod_download_dialog import open_mod_download_dialog
    open_mod_download_dialog(app, server_id, [mod_id])

