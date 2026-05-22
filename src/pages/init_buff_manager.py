from __future__ import annotations
import os
from pathlib import Path
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..server_config import SERVER_STATUS_STOPPED
from ..buff_manager import BuffManager


def init_buff_manager(app: "ARKServerManagerApp") -> None:
    """Inicializa o BuffManager após a UI ser construída."""
    data_dir = Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager"
    app._buff_manager = BuffManager(
        data_dir=data_dir,
        get_server_config=lambda sid: next(
            (s for s in app.config_manager.servers if s.id == sid), None
        ),
        start_server=app.server_manager.start_server,
        stop_server=app.server_manager.stop_server,
        get_server_status=lambda sid: (
            inst.status
            if (inst := app.server_manager.get_instance(sid))
            else SERVER_STATUS_STOPPED
        ),
        on_log=app._global_log,
    )
    app._buff_manager.add_change_callback(
        lambda: app.after(0, app._refresh_buffs_ui)
    )
    app._refresh_buffs_ui()

