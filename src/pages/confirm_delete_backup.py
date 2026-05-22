from __future__ import annotations
from typing import TYPE_CHECKING
from pathlib import Path
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def confirm_delete_backup(app: "ARKServerManagerApp", server_id: str, backup_path: str) -> None:
    snap = Path(backup_path).name
    if not messagebox.askyesno(
        "Confirmar Exclusão",
        f"Excluir permanentemente o snapshot '{snap}'?",
        parent=app,
    ):
        return
    if app._backup_manager:
        app._backup_manager.delete_backup(backup_path)
        app._refresh_backup_list(server_id)

