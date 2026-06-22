from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def cluster_sync_log(app: "ARKServerManagerApp", cluster_id: str, msg: str, lvl: str) -> None:
    prof = app.config_manager.get_cluster(cluster_id)
    name = prof.name if prof else cluster_id
    prefix = f"[Cluster:{name}]"
    log_fn = getattr(app, "_global_log", None)
    if log_fn:
        log_fn(f"{prefix} {msg}", lvl)
    else:
        print(f"{prefix} [{lvl}] {msg}")
