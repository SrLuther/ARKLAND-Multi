from __future__ import annotations
import os
from pathlib import Path
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..server_config import SERVER_STATUS_STOPPED
from ..buff_manager import BuffManager
from ..buff_server_bridge import (
    buff_get_server_status,
    buff_persist_server_config,
    buff_start_server,
    buff_stop_server,
    get_buff_server_config,
    list_buff_servers,
)


def init_buff_manager(app: "ARKServerManagerApp") -> None:
    """Inicializa o BuffManager após a UI ser construída (TEK + legado)."""
    data_dir = Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager"

    def _discord_notify(action: str, event) -> None:
        notifier = getattr(app, "_discord_notifier", None)
        if notifier:
            notifier.notify_buff(action, event)

    app._buff_manager = BuffManager(
        data_dir=data_dir,
        get_server_config=lambda sid: get_buff_server_config(app, sid),
        start_server=lambda sid: buff_start_server(app, sid),
        stop_server=lambda sid: buff_stop_server(app, sid),
        get_server_status=lambda sid: buff_get_server_status(app, sid),
        on_log=app._global_log if callable(getattr(app, "_global_log", None)) else None,
        discord_notify=_discord_notify,
        persist_server_config=lambda sid, cfg: buff_persist_server_config(app, sid, cfg),
        list_all_servers=lambda: [e.id for e in list_buff_servers(app)],
    )
    app._buff_manager.add_change_callback(
        lambda: app.after(0, app._refresh_buffs_ui)
    )
    app._refresh_buffs_ui()
