"""Inicializa o scheduler de eventos ARK globais (ActiveEvent)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from ..buff_server_bridge import (
    buff_get_server_status,
    buff_start_server,
    buff_stop_server,
    get_buff_server_config,
)
from ..global_active_event_scheduler import GlobalActiveEventScheduler
from ..pages.global_active_event import apply_active_event_to_servers

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def init_global_ark_event_scheduler(app: "ARKServerManagerApp") -> None:
    if getattr(app, "_global_ark_event_scheduler", None) is not None:
        return

    data_dir = Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager"

    def _apply(sids: list[str], event_id: str):
        return apply_active_event_to_servers(app, sids, event_id)

    app._global_ark_event_scheduler = GlobalActiveEventScheduler(
        data_dir,
        get_server_config=lambda sid: get_buff_server_config(app, sid),
        get_server_status=lambda sid: buff_get_server_status(app, sid),
        stop_server=lambda sid: buff_stop_server(app, sid),
        start_server=lambda sid: buff_start_server(app, sid),
        apply_active_event=_apply,
        on_log=app._global_log if callable(getattr(app, "_global_log", None)) else None,
        on_change=lambda: app.after(0, app._refresh_buffs_ui) if hasattr(app, "_refresh_buffs_ui") else None,
    )
