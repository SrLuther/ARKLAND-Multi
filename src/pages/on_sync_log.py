from __future__ import annotations
from typing import TYPE_CHECKING
import datetime
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def on_sync_log(app: "ARKServerManagerApp", msg: str, level: str = "info") -> None:
    ts = __import__("datetime").datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}\n"
    def _do():
        if app._sync_log_box:
            app._sync_log_box.configure(state="normal")
            app._sync_log_box.insert("end", line)
            app._sync_log_box.see("end")
            app._sync_log_box.configure(state="disabled")
    app.after(0, _do)

