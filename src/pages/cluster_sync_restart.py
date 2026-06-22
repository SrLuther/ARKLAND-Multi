from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def cluster_sync_restart(app: "ARKServerManagerApp", cluster_id: str) -> None:
    """Reinicia o sync quando habilitado no perfil (inicia se ainda não estava rodando)."""
    prof = app.config_manager.get_cluster(cluster_id)
    if not prof:
        return
    app._cluster_sync_stop(cluster_id)
    if prof.sync_enabled:
        app._cluster_sync_start(cluster_id)
