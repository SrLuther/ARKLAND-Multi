from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def cluster_sync_restart(app: "ARKServerManagerApp", cluster_id: str) -> None:
    """Reinicia o sync se estava ativo e continua habilitado no perfil."""
    prof = app.config_manager.get_cluster(cluster_id)
    if not prof:
        return
    engines = getattr(app, "_cluster_sync_engines", {})
    was_running = (
        cluster_id in engines
        and getattr(engines[cluster_id], "is_running", False)
    )
    app._cluster_sync_stop(cluster_id)
    if was_running and prof.sync_enabled:
        app._cluster_sync_start(cluster_id)
