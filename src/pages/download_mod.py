from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def download_mod(app: "ARKServerManagerApp", server_id: str, mod_id: str) -> None:
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return
    app.mod_manager.steamcmd_path = app.config_manager.config.steamcmd_path
    app.mod_manager.download_mods(
        [mod_id], srv.install_dir,
        on_done=lambda ok: app.after(0, lambda: app._refresh_mods_list(server_id)),  # type: ignore[arg-type]
    )

