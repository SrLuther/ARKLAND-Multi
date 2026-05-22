from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
from ..ui_constants import _GREEN, _GREEN_DARK, _GREEN_HOVER, _RED_DARK, _RED_HOVER
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..mod_auto_updater import ModAutoUpdater


def toggle_mod_auto_updater(app: "ARKServerManagerApp", server_id: str) -> None:
    """Liga/desliga o verificador automático de mods."""
    w = app._server_widgets.get(server_id, {})
    try:
        interval  = max(1, int(w.get("_au_interval_var", tk.StringVar(value="15")).get()))
        warn_mins = max(1, int(w.get("_au_warning_var",  tk.StringVar(value="5")).get()))
    except ValueError:
        interval, warn_mins = 15, 5

    if app._mod_auto_updater and app._mod_auto_updater.enabled:
        app._mod_auto_updater.stop()
        for sid, ww in app._server_widgets.items():
            btn = ww.get("_au_toggle_btn")
            lbl = ww.get("_au_status_lbl")
            if btn:
                btn.configure(text="▶ Ativar", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER)
            if lbl:
                lbl.configure(text="● INATIVO", text_color="gray50")
    else:
        if app._mod_auto_updater is None:
            app._mod_auto_updater = ModAutoUpdater(
                server_manager=app.server_manager,
                mod_manager=app.mod_manager,
                get_servers=lambda: app.config_manager.servers,
                on_log=app._on_auto_updater_log,
                check_interval_minutes=interval,
                warning_minutes=warn_mins,
                discord_notifier=app._discord_notifier,
            )
        else:
            app._mod_auto_updater.set_interval(interval)
            app._mod_auto_updater.set_warning_minutes(warn_mins)
        app._mod_auto_updater.start()
        for sid, ww in app._server_widgets.items():
            btn = ww.get("_au_toggle_btn")
            lbl = ww.get("_au_status_lbl")
            if btn:
                btn.configure(text="⏸ Parar", fg_color=_RED_DARK, hover_color=_RED_HOVER)
            if lbl:
                lbl.configure(text="● ATIVO", text_color=_GREEN)

