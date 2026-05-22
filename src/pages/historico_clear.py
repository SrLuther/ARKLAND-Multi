from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def historico_clear(app: "ARKServerManagerApp", server_id: str, filter_var: "tk.StringVar") -> None:
    """Limpa o arquivo de log após confirmação."""
    if not messagebox.askyesno(
        "Limpar histórico",
        "Tem certeza que deseja apagar todo o histórico\nde alterações deste servidor?",
        parent=app,
    ):
        return
    app._get_change_logger(server_id).clear()
    app._historico_refresh(server_id, filter_var)

