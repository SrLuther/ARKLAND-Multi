from __future__ import annotations
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def save_global_config(app: "ARKServerManagerApp") -> None:
    cfg = app.config_manager.config
    cfg.steamcmd_path        = app._steamcmd_var.get().strip()
    cfg.default_install_dir  = app._default_dir_var.get().strip()
    cfg.startup_with_windows = app._cfg_startup_var.get()
    cfg.minimize_to_tray     = app._cfg_minimize_tray_var.get()
    cfg.log_debug            = app._cfg_log_debug_var.get()
    # Discord
    dc = cfg.discord_notify
    dc.enabled       = app._discord_enabled_var.get()
    dc.webhook_url   = app._discord_url_var.get().strip()
    dc.sender_name   = app._discord_sender_var.get().strip() or "ARKLAND"
    dc.notify_start  = app._discord_notify_start.get()
    dc.notify_stop   = app._discord_notify_stop.get()
    dc.notify_crash  = app._discord_notify_crash.get()
    dc.notify_update = app._discord_notify_update.get()
    dc.notify_backup = app._discord_notify_backup.get()
    _set_windows_startup(cfg.startup_with_windows)
    app.config_manager.save()
    app.mod_manager.steamcmd_path = cfg.steamcmd_path
    messagebox.showinfo("Salvo", "Configurações globais salvas!", parent=app)

