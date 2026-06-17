from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def do_quit(app: "ARKServerManagerApp") -> None:
    tray = getattr(app, "_tray_icon", None)
    if tray:
        try:
            tray.stop()
        except Exception:
            pass
        app._tray_icon = None
    sync = getattr(app, "_sync_engine", None)
    if sync and sync.is_running:
        sync.stop()
    for _eng in list(getattr(app, "_cluster_sync_engines", {}).values()):
        if _eng.is_running:
            _eng.stop()
    if hasattr(app, "_cluster_sync_engines"):
        app._cluster_sync_engines.clear()
    dyn = getattr(app, "_dynamic_config_server", None)
    if dyn is not None:
        dyn.stop()
    if app._mod_auto_updater and app._mod_auto_updater.enabled:
        app._mod_auto_updater.stop()
    if app._buff_manager:
        app._buff_manager.stop()
    backup = getattr(app, "_backup_manager", None)
    if backup is not None:
        backup.shutdown()
    remote = getattr(app, "_remote_agent", None)
    if remote and remote.is_running:
        remote.stop()
    app._perf_running = False
    for client in list(getattr(app, "_rcon_clients", {}).values()):
        try:
            client.disconnect()
        except Exception:
            pass
    app.config_manager.save()
    app.destroy()
