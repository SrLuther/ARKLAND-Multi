from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

from ..sync_engine import SyncEngine


def cluster_sync_once(app: "ARKServerManagerApp", cluster_id: str) -> None:
    """Executa um ciclo de sync imediato sem iniciar o loop automático."""
    from .cluster_helpers import build_cluster_sync_cycles

    prof = app.config_manager.get_cluster(cluster_id)
    if not prof:
        return
    cycles = build_cluster_sync_cycles(app, prof, cluster_id)
    if not cycles:
        app._toast(
            "Configure a pasta de rede (UNC) e vincule servidores antes de sincronizar.",
            kind="warning",
        )
        return
    engines = getattr(app, "_cluster_sync_engines", {})
    if cluster_id in engines:
        engines[cluster_id].sync_once()
    else:
        class _ClusterSyncCfg:
            def __init__(self, sync_cycles: list) -> None:
                self.sync_cycles = sync_cycles
                self.sync_interval = 999
                self.log_debug = False

        SyncEngine(
            config=_ClusterSyncCfg(cycles),
            on_log=lambda msg, lvl: app._cluster_sync_log(cluster_id, msg, lvl),
        ).sync_once()
