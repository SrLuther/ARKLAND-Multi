from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def start_download_update(app: "ARKServerManagerApp") -> None:
    info = app.update_checker.latest
    if not info:
        return
    app._install_update_btn.configure(state="disabled", text="⏳  Iniciando agente...")
    app._check_update_btn.configure(state="disabled")
    app.update_checker.download_and_install(
        info,
        on_done=lambda ok, msg: app.after(0, lambda: app._on_download_done(ok, msg)),  # type: ignore[arg-type]
    )

