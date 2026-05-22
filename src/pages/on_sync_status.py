from __future__ import annotations
from typing import TYPE_CHECKING
from ..ui_constants import _GREEN, _GREEN_DARK, _GREEN_HOVER, _RED_DARK, _RED_HOVER
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def on_sync_status(app: "ARKServerManagerApp", status: str) -> None:
    def _do():
        if app._sync_toggle_btn is None or app._sync_status_lbl is None:
            return
        if status == "running":
            app._sync_status_lbl.configure(
                text="🟢  Sincronizando", text_color=_GREEN)
            app._sync_toggle_btn.configure(
                text="⏹  Parar Sync", fg_color=_RED_DARK, hover_color=_RED_HOVER)
        else:
            app._sync_status_lbl.configure(
                text="⬜  Parado", text_color="gray60")
            app._sync_toggle_btn.configure(
                text="▶  Iniciar Sync", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER)
    app.after(0, _do)

