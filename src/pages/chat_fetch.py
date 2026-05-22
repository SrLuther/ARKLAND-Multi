from __future__ import annotations
import threading
import tkinter as tk
from datetime import datetime
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def chat_fetch(app: "ARKServerManagerApp", server_id: str) -> None:
    client = app._rcon_clients.get(server_id)
    w = app._server_widgets.get(server_id, {})
    if not client or not client.is_connected:
        app._chat_append(
            server_id,
            "⚠  RCON não conectado. Vá para 'Console RCON' e clique em Conectar primeiro.\n",
            "err",
        )
        # Desativa auto-poll em caso de erro
        if w.get("chat_auto_poll") and w["chat_auto_poll"].get():
            w["chat_auto_poll"].set(False)
            app._chat_cancel_poll(server_id)
        return

    status_var: Optional[tk.StringVar] = w.get("chat_status_var")
    if status_var:
        status_var.set("⏳ Buscando...")

    def _do() -> None:
        ok, result = client.send_command_safe("GetChat")
        from datetime import datetime as _dt
        ts_now = _dt.now().strftime("%H:%M:%S")

        def _apply() -> None:
            if status_var:
                status_var.set(f"🟢 {ts_now}")
            if ok and result and result.strip().lower() not in ("", "no chat"):
                app._chat_process(server_id, result)

        app.after(0, _apply)

    threading.Thread(target=_do, daemon=True).start()

