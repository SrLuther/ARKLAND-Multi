"""Adiciona um novo broadcast agendado (por intervalo)."""
from __future__ import annotations

import uuid
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def broadcast_sched_add(app: "ARKServerManagerApp", server_id: str) -> None:
    """Lê o formulário de novo auto-broadcast e persiste."""
    w = app._server_widgets.get(server_id, {})

    label   = w.get("bcs_new_label",    tk.StringVar()).get().strip()
    msg     = w.get("bcs_new_msg",      tk.StringVar()).get().strip()
    try:
        interval = int(w.get("bcs_new_interval", tk.StringVar(value="30")).get())
        if interval < 1:
            interval = 1
    except (ValueError, AttributeError):
        interval = 30

    if not label or not msg:
        messagebox.showwarning(
            "Campos obrigatórios",
            "Preencha o Rótulo e a Mensagem antes de adicionar.",
            parent=app,
        )
        return

    srv = app.config_manager.get_server(server_id)
    if not srv:
        return

    if not hasattr(srv, "auto_broadcasts") or srv.auto_broadcasts is None:
        srv.auto_broadcasts = []

    srv.auto_broadcasts.append({
        "id":           str(uuid.uuid4()),
        "label":        label,
        "message":      msg,
        "interval_min": interval,
        "enabled":      True,
        "last_sent":    0.0,
    })
    app.config_manager.update_server(srv)

    # Limpa formulário
    try:
        w["bcs_new_label"].set("")
        w["bcs_new_msg"].set("")
    except Exception:
        pass

    app._bc_sched_refresh(server_id)
