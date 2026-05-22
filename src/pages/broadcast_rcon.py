from __future__ import annotations
import threading
from typing import TYPE_CHECKING
import datetime
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def broadcast_rcon(app: "ARKServerManagerApp", server_id: str, message: str) -> None:
    """Envia um Broadcast via RCON para todos os jogadores online.

    Usa o cliente RCON já conectado (Console RCON) se disponível;
    caso contrário, cria uma conexão temporária com as configs do servidor.
    """
    safe = message.replace('"', "'")[:900]
    existing = app._rcon_clients.get(server_id)

    if existing and existing.is_connected:
        # Usa a sessão RCON já aberta no console
        ts = datetime.now().strftime("%H:%M:%S")
        app._chat_append(server_id, f"[{ts}] ", "ts")
        app._chat_append(server_id, "[BROADCAST]", "server")
        app._chat_append(server_id, f": {message}\n", "message")

        def _do_existing() -> None:
            existing.send_command_safe(f"Broadcast {safe}")

        threading.Thread(target=_do_existing, daemon=True).start()
        return

    # RCON não conectado no console — cria conexão temporária
    srv = app.config_manager.get_server(server_id)
    if not srv or not srv.rcon_enabled or not srv.rcon_password:
        messagebox.showwarning(
            "RCON não configurado",
            "Habilite o RCON e defina a senha nas configurações do servidor antes de enviar broadcasts.",
            parent=app,
        )
        return

    ts = datetime.now().strftime("%H:%M:%S")
    app._chat_append(server_id, f"[{ts}] ", "ts")
    app._chat_append(server_id, "[BROADCAST]", "server")
    app._chat_append(server_id, f": {message}\n", "message")

    rcon_port = srv.rcon_port
    rcon_pass = srv.rcon_password

    def _do_temp() -> None:
        try:
            tmp = RconClient("127.0.0.1", rcon_port, rcon_pass)
            ok, resp = tmp.send_command_safe(f"Broadcast {safe}")
            tmp.disconnect()
            if not ok:
                app._global_log(f"[RCON] Broadcast falhou: {resp}", "warning")
        except Exception as exc:
            app._global_log(f"[RCON] Broadcast falhou: {exc}", "warning")

    threading.Thread(target=_do_temp, daemon=True).start()

