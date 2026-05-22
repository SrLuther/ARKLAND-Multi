from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def cluster_sync_once(app: "ARKServerManagerApp", cluster_id: str) -> None:
    """Executa um ciclo de sync imediato sem iniciar o loop automático."""
    prof = app.config_manager.get_cluster(cluster_id)
    if not prof or not prof.local_cluster_dir or not prof.cluster_dir:
        return
    if cluster_id in app._cluster_sync_engines:
        app._cluster_sync_engines[cluster_id].sync_once()
    else:
        # Cria engine temporário apenas para o ciclo único
        class _ClusterSyncCfg:
            def __init__(app, local_dir: str, net_dir: str) -> None:
                app.sync_cycles = [[local_dir, net_dir]]
                app.sync_interval = 999
                app.log_debug = False
        SyncEngine(
            config=_ClusterSyncCfg(prof.local_cluster_dir, prof.cluster_dir),
            on_log=lambda msg, lvl: app._cluster_sync_log(cluster_id, msg, lvl),
        ).sync_once()

