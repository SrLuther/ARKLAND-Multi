from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def cluster_sync_stop(app: "ARKServerManagerApp", cluster_id: str) -> None:
    engines = getattr(app, "_cluster_sync_engines", None)
    if not engines:
        return
    engine = engines.pop(cluster_id, None)
    if engine is not None:
        try:
            engine.stop()
        except Exception:
            pass
