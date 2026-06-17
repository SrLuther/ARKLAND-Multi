from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

from .start_mod_auto_updater import _refresh_auto_updater_ui, create_mod_auto_updater

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def toggle_mod_auto_updater(app: "ARKServerManagerApp", server_id: str = "") -> None:
    """Liga/desliga o verificador automático de mods."""
    w = getattr(app, "_server_widgets", {}).get(server_id, {})
    try:
        interval = max(1, int(w.get("_au_interval_var", tk.StringVar(value="15")).get()))
        warn_mins = max(1, int(w.get("_au_warning_var", tk.StringVar(value="5")).get()))
    except ValueError:
        interval, warn_mins = 15, 5

    tek_interval = getattr(app, "_tek_au_interval_var", None)
    tek_warn = getattr(app, "_tek_au_warning_var", None)
    if tek_interval is not None:
        try:
            interval = max(1, int(tek_interval.get()))
        except ValueError:
            pass
    if tek_warn is not None:
        try:
            warn_mins = max(1, int(tek_warn.get()))
        except ValueError:
            pass

    if app._mod_auto_updater and app._mod_auto_updater.enabled:
        app._mod_auto_updater.stop()
        _refresh_auto_updater_ui(app, active=False)
    else:
        if app._mod_auto_updater is None:
            app._mod_auto_updater = create_mod_auto_updater(
                app,
                check_interval_minutes=interval,
                warning_minutes=warn_mins,
            )
        else:
            app._mod_auto_updater.set_interval(interval)
            app._mod_auto_updater.set_warning_minutes(warn_mins)
            app._mod_auto_updater.set_steam_api_key(
                getattr(app.config_manager.config, "steam_api_key", "")
            )
        app._mod_auto_updater.start()
        _refresh_auto_updater_ui(app, active=True)
