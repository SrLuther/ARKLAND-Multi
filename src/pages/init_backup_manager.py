from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..backup_manager import BackupManager


def init_backup_manager(app: "ARKServerManagerApp") -> None:
    """Inicializa o BackupManager e agenda os timers de auto-backup."""
    app._backup_manager = BackupManager(
        get_servers=lambda: app.config_manager.servers,
        on_log=app._global_log,
        discord_notifier=app._discord_notifier,
    )
    app._backup_manager.restart_all(app.config_manager.servers)

