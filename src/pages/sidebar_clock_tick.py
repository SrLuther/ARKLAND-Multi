from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..ui_constants import now_brasilia


def sidebar_clock_tick(app: "ARKServerManagerApp") -> None:
    """Atualiza o relógio da sidebar a cada segundo."""
    try:
        n = now_brasilia()
        app._sidebar_clock_lbl.configure(
            text=n.strftime("%d/%m/%Y\n%H:%M:%S")
        )
    except Exception:
        pass
    app.after(1000, app._sidebar_clock_tick)

