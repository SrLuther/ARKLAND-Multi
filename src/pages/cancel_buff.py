from __future__ import annotations
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def cancel_buff(app: "ARKServerManagerApp", event_id: str) -> None:
    if messagebox.askyesno(
        "Cancelar BUFF",
        "Confirmar cancelamento do BUFF agendado?",
        parent=app,
    ):
        if app._buff_manager:
            app._buff_manager.cancel_event(event_id)

