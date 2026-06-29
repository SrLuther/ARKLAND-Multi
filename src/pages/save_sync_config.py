from __future__ import annotations
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def _cycle_to_config(
    paths: list[str],
    numeric_only: bool,
    config_json_only: bool,
) -> dict | list:
    if numeric_only or config_json_only:
        return {
            "folders": paths,
            "numeric_only": numeric_only,
            "config_json_only": config_json_only,
        }
    return paths


def save_sync_config(app: "ARKServerManagerApp") -> None:
    cfg = app.config_manager.config
    cycles = []
    numeric_vars = getattr(app, "_sync_numeric_only_vars", [])
    config_json_vars = getattr(app, "_sync_config_json_only_vars", [])
    for i, folder_vars in enumerate(app._sync_cycle_vars):
        paths = [v.get().strip() for v in folder_vars if v.get().strip()]
        if not paths:
            continue
        numeric_only = numeric_vars[i].get() if i < len(numeric_vars) else False
        config_json_only = config_json_vars[i].get() if i < len(config_json_vars) else False
        cycles.append(_cycle_to_config(paths, numeric_only, config_json_only))
    cfg.sync_cycles = cycles
    try:
        cfg.sync_interval = max(1, int(app._sync_interval_var.get()))
    except ValueError:
        cfg.sync_interval = 5
    app._sync_interval_var.set(str(cfg.sync_interval))
    app.config_manager.save()
    messagebox.showinfo("Salvo", "Configurações de sync salvas!", parent=app)
    if app._sync_engine and app._sync_engine.is_running:
        app._sync_engine.stop()
        app._sync_engine = None
        app._start_sync_engine()
