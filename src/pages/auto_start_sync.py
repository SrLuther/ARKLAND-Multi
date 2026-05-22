from __future__ import annotations
import os
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def auto_start_sync(app: "ARKServerManagerApp") -> None:
    """Inicia o sync automaticamente ao abrir, se houver ciclos configurados."""
    cycles = app.config_manager.config.sync_cycles or []
    has_paths = any(
        any(str(p).strip() for p in cycle)
        for cycle in cycles
        if isinstance(cycle, list)
    )
    if has_paths:
        app._start_sync_engine()

