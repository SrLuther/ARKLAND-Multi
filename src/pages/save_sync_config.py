from __future__ import annotations
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def save_sync_config(app: "ARKServerManagerApp") -> None:
    cfg = app.config_manager.config
    # Coleta ciclos: apenas pastas com caminho preenchido
    cycles = []
    for folder_vars in app._sync_cycle_vars:
        paths = [v.get().strip() for v in folder_vars if v.get().strip()]
        if paths:
            cycles.append(paths)
    cfg.sync_cycles = cycles
    try:
        cfg.sync_interval = max(1, int(app._sync_interval_var.get()))
    except ValueError:
        cfg.sync_interval = 5
    app._sync_interval_var.set(str(cfg.sync_interval))
    app.config_manager.save()
    messagebox.showinfo("Salvo", "Configurações de sync salvas!", parent=app)
    # Recria engine com os novos ciclos
    if app._sync_engine and app._sync_engine.is_running:
        app._sync_engine.stop()
        app._sync_engine = None
        app._start_sync_engine()

