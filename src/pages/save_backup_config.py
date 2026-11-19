from __future__ import annotations
import tkinter as tk
from pathlib import Path
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def save_backup_config(app: "ARKServerManagerApp", server_id: str) -> None:
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return
    w = app._server_widgets.get(server_id, {})
    from ..arkland_environment import default_backups_servers_root, ensure_backup_destination
    selected_dir = w.get("backup_dir", tk.StringVar()).get().strip()
    global_dir = app.config_manager.config.backup.backup_dir.strip()
    target_dir = (
        Path(selected_dir or global_dir)
        if selected_dir or global_dir
        else default_backups_servers_root()
    ) / srv.id
    try:
        ensure_backup_destination(target_dir)
    except OSError as exc:
        messagebox.showerror(
            "Destino de backup indisponível",
            f"Não foi possível gravar no disco/pasta selecionado.\n\n{exc}",
            parent=app,
        )
        return

    srv.backup_enabled          = w.get("backup_enabled",  tk.BooleanVar()).get()
    srv.backup_interval_hours   = 0.5
    srv.backup_include_saves    = w.get("backup_inc_saves",  tk.BooleanVar(value=True)).get()
    srv.backup_include_config   = w.get("backup_inc_config", tk.BooleanVar(value=True)).get()
    srv.backup_dir              = w.get("backup_dir", tk.StringVar()).get().strip()
    try:
        srv.backup_keep_count   = max(1, int(w.get("backup_keep", tk.StringVar(value="10")).get()))
    except ValueError:
        pass

    app.config_manager.update_server(srv)
    app.config_manager.save_servers()

    # Reinicia o timer para este servidor
    if app._backup_manager:
        app._backup_manager.stop_auto_backup(server_id)
        if srv.backup_enabled:
            app._backup_manager.start_auto_backup(srv)

    # Feedback visual
    w_entry = w.get("backup_keep")
    if w_entry:
        w_entry.set(str(srv.backup_keep_count))

