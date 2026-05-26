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

    # ── Atualiza o painel da welcome screen se ela ainda estiver visível ─────
    _wlbl = getattr(app, "_welcome_update_status", None)
    _wbtn = getattr(app, "_welcome_update_btn", None)
    if _wlbl is not None and _wbtn is not None:
        try:
            if _wlbl.winfo_exists():
                _wbtn.configure(state="normal", text="🔍  Verificar Atualização")
                if info is None:
                    _wlbl.configure(text="❌  Falha ao verificar", text_color="#ff6666")
                elif info.is_newer_than(APP_VERSION):
                    _wlbl.configure(text=f"🔔  v{info.version} disponível!", text_color="#ffaa44")
                else:
                    _wlbl.configure(text="✅  Versão mais recente", text_color="#4CAF50")
        except Exception:
            pass

    # ── Aba Sobre: só atualiza se já foi construída ───────────────────────────
    if not hasattr(app, "_last_check_var"):
        return

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
        if getattr(app, "_sidebar_update_lbl", None):
            app._sidebar_update_lbl.configure(text=f"🔔 v{info.version} disponível")
        for _btn in [getattr(app, "_rail_nav_btns", {}).get("sobre"), app._nav_buttons.get("sobre") if getattr(app, "_nav_buttons", None) else None]:
            if _btn:
                try: _btn.configure(text="ℹ️  Sobre  🔔")
                except Exception: pass
    else:
        app._update_status_var.set("✅  Versão mais recente")
        app._update_status_lbl.configure(text_color=_GREEN)
        app._install_update_btn.configure(state="disabled", text="⬇️  Baixar e Instalar")
        if getattr(app, "_sidebar_update_lbl", None):
            app._sidebar_update_lbl.configure(text="")

