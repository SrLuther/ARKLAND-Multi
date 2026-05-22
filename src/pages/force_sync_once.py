from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..sync_engine import SyncEngine


def force_sync_once(app: "ARKServerManagerApp") -> None:
    if app._sync_engine is None:
        app._sync_engine = SyncEngine(
            app.config_manager.config,
            on_log=app._on_sync_log,
            on_status_change=app._on_sync_status,
            on_stats_update=app._on_sync_stats,
        )
    app._sync_engine.sync_once()

