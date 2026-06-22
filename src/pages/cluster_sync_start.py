from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

from ..sync_engine import SyncEngine


def cluster_sync_start(app: "ARKServerManagerApp", cluster_id: str) -> None:
    """Inicia o SyncEngine bidirecional para o cluster."""
    from .cluster_helpers import build_cluster_sync_cycles

    prof = app.config_manager.get_cluster(cluster_id)
    if not prof:
        return

    cycles = build_cluster_sync_cycles(app, prof, cluster_id)
    if not cycles:
        app._toast(
            "Configure a pasta de rede (UNC) e vincule servidores antes de iniciar a sincronização.",
            kind="warning",
        )
        return
    if not getattr(app, "_cluster_sync_engines", None):
        app._cluster_sync_engines = {}

    app._cluster_sync_stop(cluster_id)

    class _ClusterSyncCfg:
        def __init__(self, sync_cycles: list, interval: int) -> None:
            self.sync_cycles = sync_cycles
            self.sync_interval = max(5, interval)
            self.log_debug = False

    engine = SyncEngine(
        config=_ClusterSyncCfg(cycles, prof.sync_interval),
        on_log=lambda msg, lvl: app._cluster_sync_log(cluster_id, msg, lvl),
        on_status_change=lambda s: None,
    )
    app._cluster_sync_engines[cluster_id] = engine
    engine.start()
    app._toast(f"Sincronização iniciada: {prof.name}", kind="info")
