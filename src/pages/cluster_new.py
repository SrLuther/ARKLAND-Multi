from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def cluster_new(app: "ARKServerManagerApp") -> None:
    from .server_config import ClusterProfile
    prof = ClusterProfile()
    # Pré-preenche com valores de servidor manual se existir
    _manual = [s for s in app.config_manager.servers
               if getattr(s.cluster, "enabled", False)
               and getattr(s.cluster, "cluster_id", "")]
    if _manual:
        src = _manual[0]
        prof.cluster_id = src.cluster.cluster_id
        prof.cluster_dir = src.cluster.cluster_dir_override
    app.config_manager.add_cluster(prof)
    app._cluster_selected_id = prof.id
    app._clusters_refresh_list()
    app._cluster_build_detail(prof)

