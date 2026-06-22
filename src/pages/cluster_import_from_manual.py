from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def cluster_import_from_manual(app: "ARKServerManagerApp") -> None:
    """Cria um Perfil de Cluster a partir das configurações manuais dos servidores."""
    from .server_config import ClusterProfile
    from .cluster_helpers import manual_asm_without_profile

    _manual = [
        s for s in app.config_manager.servers
        if getattr(s.cluster, "enabled", False)
        and getattr(s.cluster, "cluster_id", "")
        and not s.cluster_profile_id
    ]
    _manual_asm = manual_asm_without_profile(app)

    if not _manual and not _manual_asm:
        app._toast("Nenhum servidor com cluster manual detectado.", kind="warning")
        return

    prof = ClusterProfile()
    prof.name = "Cluster Importado"

    if _manual_asm:
        src = _manual_asm[0]
        prof.cluster_id = src.cross_ark_cluster_id
        prof.cluster_dir = src.cluster_dir_override
    else:
        src = _manual[0]
        prof.cluster_id = src.cluster.cluster_id
        prof.cluster_dir = src.cluster.cluster_dir_override
        prof.no_transfer_from_filtering = src.cluster.no_transfer_from_filtering
        prof.prevent_download_survivors = src.cluster.prevent_download_survivors
        prof.prevent_download_items = src.cluster.prevent_download_items
        prof.prevent_download_dinos = src.cluster.prevent_download_dinos

    app.config_manager.add_cluster(prof)

    linked = 0
    from .cluster_helpers import apply_profile_to_asm_server

    for srv in _manual_asm:
        srv.cluster_profile_id = prof.id
        apply_profile_to_asm_server(srv, prof)
        app.asm_config_manager.update_server(srv)
        linked += 1

    for srv in _manual:
        srv.cluster_profile_id = prof.id
        app.config_manager.update_server(srv)
        app.server_manager.update_server_config(srv)
        linked += 1

    app._cluster_selected_id = prof.id
    app._clusters_refresh_list()
    app._cluster_build_detail(prof)
    app._toast(f"✅ Perfil criado e {linked} servidor(es) vinculado(s).", kind="info")
