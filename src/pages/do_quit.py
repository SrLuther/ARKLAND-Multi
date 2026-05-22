from __future__ import annotations
import os
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def do_quit(app: "ARKServerManagerApp") -> None:
    if app._tray_icon:
        try:
            app._tray_icon.stop()
        except Exception:
            pass
        app._tray_icon = None
    if app._sync_engine and app._sync_engine.is_running:
        app._sync_engine.stop()
    for _eng in list(app._cluster_sync_engines.values()):
        if _eng.is_running:
            _eng.stop()
    app._cluster_sync_engines.clear()
    app._dynamic_config_server.stop()
    if app._mod_auto_updater and app._mod_auto_updater.enabled:
        app._mod_auto_updater.stop()
    if app._buff_manager:
        app._buff_manager.stop()
    if app._backup_manager:
        app._backup_manager.shutdown()
    if app._remote_agent and app._remote_agent.is_running:
        app._remote_agent.stop()
    app._perf_running = False
    # Os processos dos servidores (mapas) são mantidos em execução intencionalmente.
    # Apenas recursos internos do app são encerrados.
    for client in list(app._rcon_clients.values()):
        try:
            client.disconnect()
        except Exception:
            pass
    app.config_manager.save()
    app.destroy()

