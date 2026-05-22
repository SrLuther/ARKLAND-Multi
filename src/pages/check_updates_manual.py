from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def check_updates_manual(app: "ARKServerManagerApp") -> None:
    url = app.config_manager.config.update_url
    if not url:
        return
    app._check_update_btn.configure(state="disabled", text="🔍  Verificando...")
    app.update_checker.check_async(
        url,
        on_result=lambda info: app.after(  # type: ignore[arg-type]
            0, lambda: app._on_update_result(info, manual=True)))

