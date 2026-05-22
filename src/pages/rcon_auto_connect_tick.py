from __future__ import annotations
import threading
import tkinter as tk
from typing import TYPE_CHECKING
from ..ui_constants import _RED_DARK, _RED_HOVER
import sys
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..rcon_client import RconClient


def rcon_auto_connect_tick(app: "ARKServerManagerApp", server_id: str) -> None:
    """Tenta conectar o RCON silenciosamente se o servidor estiver RUNNING e sem conexão."""
    app._rcon_auto_jobs.pop(server_id, None)

    if not app._rcon_auto_enabled.get(server_id):
        return

    # Se já está conectado, apenas reagenda a verificação
    client = app._rcon_clients.get(server_id)
    if client and client.is_connected:
        app._rcon_schedule_auto_connect(server_id, delay_ms=15_000)
        return

    srv = app.config_manager.get_server(server_id)
    if not srv:
        return

    w        = app._server_widgets.get(server_id, {})
    host     = w.get("rcon_host", tk.StringVar(value="127.0.0.1")).get() or "127.0.0.1"
    port_str = w.get("rcon_port_entry", tk.StringVar(value=str(srv.rcon_port))).get()
    password = srv.rcon_password or srv.admin_password
    try:
        port = int(port_str)
    except ValueError:
        port = srv.rcon_port

    def _try():
        new_client = RconClient(
            host, port, password,
            on_log=lambda m, level: app._global_log(f"[RCON] {m}", level),
        )
        try:
            new_client.connect()
            def _ok():
                if not app._rcon_auto_enabled.get(server_id):
                    try:
                        new_client.disconnect()
                    except Exception:
                        pass
                    return
                app._rcon_clients[server_id] = new_client
                sv = w.get("rcon_status_var")
                cb = w.get("rcon_connect_btn")
                if sv:
                    sv.set(f"🟢 Conectado a {host}:{port}")
                if cb:
                    cb.configure(text="🔌 Desconectar",
                                 fg_color=_RED_DARK, hover_color=_RED_HOVER)
                app._rcon_append(server_id, f"[Auto] Conectado a {host}:{port}\n", "sys")
                # reagenda verificação de keep-alive
                app._rcon_schedule_auto_connect(server_id, delay_ms=15_000)
            app.after(0, _ok)
        except Exception:
            # falha silenciosa — tenta de novo em 15s
            def _retry():
                if app._rcon_auto_enabled.get(server_id):
                    app._rcon_schedule_auto_connect(server_id, delay_ms=15_000)
            app.after(0, _retry)

    threading.Thread(target=_try, daemon=True).start()

