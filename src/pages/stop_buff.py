from __future__ import annotations
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def stop_buff(app: "ARKServerManagerApp", event_id: str) -> None:
    if not messagebox.askyesno(
        "Encerrar BUFF",
        "Encerrar o BUFF ativo agora?\n\n"
        "O servidor será reiniciado para restaurar as configurações originais.",
        parent=app,
    ):
        return
    if not app._buff_manager:
        return
    err = app._buff_manager.stop_active_event(event_id)
    if err:
        messagebox.showerror("Erro", err, parent=app)
