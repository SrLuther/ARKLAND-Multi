from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

from ..sync_engine import SyncEngine


def cluster_sync_start(app: "ARKServerManagerApp", cluster_id: str) -> None:
    """Inicia o SyncEngine bidirecional para o cluster."""
    prof = app.config_manager.get_cluster(cluster_id)
    if not prof:
        return
    if not prof.local_cluster_dir or not prof.cluster_dir:
        app._toast(
            "Configure pasta local e pasta de rede antes de iniciar a sincronização.",
            kind="warning",
        )
        return
    if not getattr(app, "_cluster_sync_engines", None):
        app._cluster_sync_engines = {}
    app._cluster_sync_stop(cluster_id)

    class _ClusterSyncCfg:
        def __init__(self, local_dir: str, net_dir: str, interval: int) -> None:
            self.sync_cycles = [[local_dir, net_dir]]
            self.sync_interval = max(5, interval)
            self.log_debug = False

    engine = SyncEngine(
        config=_ClusterSyncCfg(prof.local_cluster_dir, prof.cluster_dir, prof.sync_interval),
        on_log=lambda msg, lvl: app._cluster_sync_log(cluster_id, msg, lvl),
        on_status_change=lambda s: None,
    )
    app._cluster_sync_engines[cluster_id] = engine
    engine.start()
    app._toast(f"Sincronização iniciada: {prof.name}", kind="info")

