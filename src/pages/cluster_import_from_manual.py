from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def cluster_import_from_manual(app: "ARKServerManagerApp") -> None:
    """Cria um Perfil de Cluster a partir das configurações manuais dos servidores."""
    from .server_config import ClusterProfile
    _manual = [s for s in app.config_manager.servers
               if getattr(s.cluster, "enabled", False)
               and getattr(s.cluster, "cluster_id", "")
               and not s.cluster_profile_id]
    if not _manual:
        return
    src = _manual[0]
    prof = ClusterProfile()
    prof.name = "Cluster Importado"
    prof.cluster_id = src.cluster.cluster_id
    prof.cluster_dir = src.cluster.cluster_dir_override
    prof.no_transfer_from_filtering = src.cluster.no_transfer_from_filtering
    prof.prevent_download_survivors = src.cluster.prevent_download_survivors
    prof.prevent_download_items = src.cluster.prevent_download_items
    prof.prevent_download_dinos = src.cluster.prevent_download_dinos
    app.config_manager.add_cluster(prof)
    # Vincula automaticamente os servidores manuais ao novo perfil
    for srv in _manual:
        srv.cluster_profile_id = prof.id
        app.config_manager.update_server(srv)
        app.server_manager.update_server_config(srv)
    app._cluster_selected_id = prof.id
    app._clusters_refresh_list()
    app._cluster_build_detail(prof)
    app._toast(f"✅ Perfil criado e {len(_manual)} servidor(es) vinculado(s).", kind="info")

