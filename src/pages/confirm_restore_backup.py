from __future__ import annotations
import os
import threading
from typing import TYPE_CHECKING
from pathlib import Path
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def confirm_restore_backup(app: "ARKServerManagerApp", server_id: str, backup_path: str) -> None:
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return
    inst = app.server_manager.get_instance(server_id)
    if inst and inst.status != SERVER_STATUS_STOPPED:
        messagebox.showwarning(
            "Servidor em execução",
            "Pare o servidor antes de restaurar um backup.",
            parent=app,
        )
        return
    snap = Path(backup_path).name
    if not messagebox.askyesno(
        "Confirmar Restauração",
        f"Restaurar o snapshot '{snap}' para '{srv.name}'?\n\n"
        "Os arquivos atuais de config e/ou saves serão sobrescritos.",
        parent=app,
    ):
        return

    bm = app._backup_manager
    if not bm:
        return

    def _run() -> None:
        ok = bm.restore_backup(srv, backup_path)
        app.after(0, lambda: messagebox.showinfo(
            "Restauração concluída" if ok else "Erro na Restauração",
            f"Backup de '{snap}' restaurado com sucesso." if ok
            else "Falha ao restaurar. Verifique os logs.",
            parent=app,
        ))

    threading.Thread(target=_run, daemon=True).start()

