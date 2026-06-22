from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

from ..sync_engine import SyncEngine


def cluster_sync_once(app: "ARKServerManagerApp", cluster_id: str) -> None:
    """Executa um ciclo de sync imediato sem iniciar o loop automático."""
    prof = app.config_manager.get_cluster(cluster_id)
    if not prof or not prof.local_cluster_dir or not prof.cluster_dir:
        app._toast(
            "Configure pasta local e pasta de rede antes de sincronizar.",
            kind="warning",
        )
        return
    engines = getattr(app, "_cluster_sync_engines", {})
    if cluster_id in engines:
        engines[cluster_id].sync_once()
    else:
        class _ClusterSyncCfg:
            def __init__(self, local_dir: str, net_dir: str) -> None:
                self.sync_cycles = [[local_dir, net_dir]]
                self.sync_interval = 999
                self.log_debug = False

        SyncEngine(
            config=_ClusterSyncCfg(prof.local_cluster_dir, prof.cluster_dir),
            on_log=lambda msg, lvl: app._cluster_sync_log(cluster_id, msg, lvl),
        ).sync_once()

