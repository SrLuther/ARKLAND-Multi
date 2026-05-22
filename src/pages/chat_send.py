from __future__ import annotations
import threading
import tkinter as tk
from typing import TYPE_CHECKING
import datetime
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def chat_send(app: "ARKServerManagerApp", server_id: str) -> None:
    from datetime import datetime
    w = app._server_widgets.get(server_id, {})
    msg = w.get("chat_input", tk.StringVar()).get().strip()
    if not msg:
        return
    w["chat_input"].set("")
    client = app._rcon_clients.get(server_id)
    if not client or not client.is_connected:
        app._chat_append(
            server_id,
            "⚠  RCON não conectado. Vá para 'Console RCON' e clique em Conectar primeiro.\n",
            "err",
        )
        return
    ts = datetime.now().strftime("%H:%M:%S")
    app._chat_append(server_id, f"[{ts}] ", "ts")
    app._chat_append(server_id, "[SERVIDOR]", "server")
    app._chat_append(server_id, f": {msg}\n", "message")
    safe_msg = msg.replace('"', "'")

    def _do() -> None:
        client.send_command_safe(f"ServerChat {safe_msg}")

    threading.Thread(target=_do, daemon=True).start()

