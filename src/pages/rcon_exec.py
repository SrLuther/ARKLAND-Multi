from __future__ import annotations
import threading
from typing import TYPE_CHECKING
from ..ui_constants import _RED_DARK, _RED_HOVER
import sys
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def rcon_exec(app: "ARKServerManagerApp", server_id: str, command: str) -> None:
    client = app._rcon_clients.get(server_id)
    app._rcon_append(server_id, f"> {command}\n", "cmd")

    if not client:
        app._rcon_append(server_id, "Não conectado. Clique em 'Conectar' primeiro.\n", "err")
        return

    def _do():
        # send_command já reconecta automaticamente se a conexão caiu
        was_connected = client.is_connected
        ok, result = client.send_command_safe(command)

        def _update():
            # Se reconectou silenciosamente, atualiza status e log
            if not was_connected and ok:
                w   = app._server_widgets.get(server_id, {})
                sv  = w.get("rcon_status_var")
                btn = w.get("rcon_connect_btn")
                host, port = client._host, client._port
                if sv:
                    sv.set(f"🟢 Conectado a {host}:{port}")
                if btn:
                    btn.configure(text="🔌 Desconectar",
                                  fg_color=_RED_DARK, hover_color=_RED_HOVER)
                app._rcon_append(server_id,
                                  f"[Auto] Conectado a {host}:{port}\n", "sys")
            level = "resp" if ok else "err"
            app._rcon_append(server_id, (result or "(sem resposta)") + "\n", level)

        app.after(0, _update)

    threading.Thread(target=_do, daemon=True).start()

