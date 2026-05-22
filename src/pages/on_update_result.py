from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _GREEN
from ..version import APP_VERSION
import datetime
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def on_update_result(app: "ARKServerManagerApp", info, manual: bool = False) -> None:
    from datetime import datetime
    app._last_check_var.set(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    app._check_update_btn.configure(state="normal", text="🔍  Verificar Atualizações")
    if info is None:
        if manual:
            app._update_status_var.set("❌  Não foi possível verificar")
            app._update_status_lbl.configure(text_color="#ff6666")
        return
    if info.is_newer_than(APP_VERSION):
        app._update_status_var.set(f"🔔  v{info.version} disponível!")
        app._update_status_lbl.configure(text_color="#ffaa44")
        app._install_update_btn.configure(
            state="normal", text=f"⬇️  Instalar v{info.version}")
        app._sidebar_update_lbl.configure(text=f"🔔 v{info.version} disponível")
        app._nav_buttons.get("sobre", ctk.CTkButton(app)).configure(text="ℹ️  Sobre  🔔")
    else:
        app._update_status_var.set("✅  Versão mais recente")
        app._update_status_lbl.configure(text_color=_GREEN)
        app._install_update_btn.configure(state="disabled", text="⬇️  Baixar e Instalar")
        app._sidebar_update_lbl.configure(text="")

