from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def on_auto_updater_log(app: "ARKServerManagerApp", msg: str, level: str) -> None:
    def _do():
        box = app._auto_updater_log_box
        if box:
            box.configure(state="normal")
            box._textbox.insert("end", msg + "\n", level)
            box._textbox.see("end")
            box.configure(state="disabled")
        # Também envia para o log global
        app._global_log(msg, level)
    app.after(0, _do)

