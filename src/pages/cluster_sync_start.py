from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def cluster_sync_start(app: "ARKServerManagerApp", cluster_id: str) -> None:
    """Inicia o SyncEngine bidirecional para o cluster."""
    prof = app.config_manager.get_cluster(cluster_id)
    if not prof:
        return
    if not prof.local_cluster_dir or not prof.cluster_dir:
        return
    app._cluster_sync_stop(cluster_id)

    class _ClusterSyncCfg:
        def __init__(app, local_dir: str, net_dir: str, interval: int) -> None:
            app.sync_cycles = [[local_dir, net_dir]]
            app.sync_interval = max(5, interval)
            app.log_debug = False

    engine = SyncEngine(
        config=_ClusterSyncCfg(prof.local_cluster_dir, prof.cluster_dir, prof.sync_interval),
        on_log=lambda msg, lvl: app._cluster_sync_log(cluster_id, msg, lvl),
        on_status_change=lambda s: None,
    )
    app._cluster_sync_engines[cluster_id] = engine
    engine.start()

