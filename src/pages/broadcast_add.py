from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def broadcast_add(app: "ARKServerManagerApp", server_id: str) -> None:
    """Adiciona um novo broadcast à biblioteca e persiste."""
    w = app._server_widgets.get(server_id, {})
    label = w.get("bc_new_label", tk.StringVar()).get().strip()
    msg = w.get("bc_new_msg", tk.StringVar()).get().strip()
    if not label or not msg:
        messagebox.showwarning(
            "Campos obrigatórios",
            "Preencha o Rótulo e o Texto do broadcast antes de adicionar.",
            parent=app,
        )
        return
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return
    srv.broadcasts.append({"label": label, "message": msg})
    app.config_manager.update_server(srv)
    w["bc_new_label"].set("")
    w["bc_new_msg"].set("")
    app._broadcast_refresh_list(server_id)

