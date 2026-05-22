from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def broadcast_send_quick(app: "ARKServerManagerApp", server_id: str) -> None:
    """Envia o broadcast da barra de envio rápido."""
    w = app._server_widgets.get(server_id, {})
    msg = w.get("bc_quick_var", tk.StringVar()).get().strip()
    if not msg:
        return
    w["bc_quick_var"].set("")
    app._broadcast_rcon(server_id, msg)

