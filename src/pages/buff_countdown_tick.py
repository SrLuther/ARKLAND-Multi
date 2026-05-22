from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def buff_countdown_tick(app: "ARKServerManagerApp") -> None:
    """Atualiza todos os labels de countdown registrados (chamado a cada 1s)."""
    alive = []
    for lbl, target, prefix in app._buff_countdown_labels:
        try:
            if lbl.winfo_exists():
                lbl.configure(text=prefix + app._format_countdown(target))
                alive.append((lbl, target, prefix))
        except Exception:
            pass
    app._buff_countdown_labels = alive
    if alive:
        app._buff_countdown_job = app.after(1000, app._buff_countdown_tick)
    else:
        app._buff_countdown_job = None

