from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def cluster_travel_test(app: "ARKServerManagerApp", cluster_id: str) -> None:
    """Executa teste de visibilidade Cross-ARK e abre o resultado."""
    prof = app.config_manager.get_cluster(cluster_id)
    if not prof:
        return

    from .cluster_helpers import asm_servers_in_cluster, legacy_servers_in_cluster
    from .show_cluster_travel_dialog import show_cluster_travel_dialog

    app._toast("Testando viagem entre mapas…", kind="info")

    def _worker() -> None:
        from ..cluster_probe import run_cluster_travel_test
        from ..pages.cluster_helpers import apply_cluster_profile_to_asm_cfg

        asm_list = asm_servers_in_cluster(app, cluster_id)
        for srv in asm_list:
            apply_cluster_profile_to_asm_cfg(srv, app.config_manager.get_cluster)

        result = run_cluster_travel_test(
            prof,
            asm_list,
            legacy_servers_in_cluster(app, cluster_id),
        )
        app.after(0, lambda: show_cluster_travel_dialog(app, result))

    threading.Thread(target=_worker, daemon=True, name="ClusterTravelTest").start()
