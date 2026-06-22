from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def cluster_select(app: "ARKServerManagerApp", cluster_id: str) -> None:
    """Seleciona um perfil de cluster e exibe o painel de detalhes."""
    prof = app.config_manager.get_cluster(cluster_id)
    if not prof:
        app._toast("Perfil de cluster não encontrado.", kind="warning")
        return
    app._cluster_selected_id = cluster_id
    app._clusters_refresh_list()
    try:
        app._cluster_build_detail(prof)
    except Exception as exc:
        app._toast(f"Erro ao abrir perfil: {exc}", kind="error")
        raise
