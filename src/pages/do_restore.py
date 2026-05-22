from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def do_restore(app: "ARKServerManagerApp") -> None:
    if app._tray_icon:
        try:
            app._tray_icon.stop()
        except Exception:
            pass
        app._tray_icon = None
    app.deiconify()
    app.lift()
    app.focus_force()

