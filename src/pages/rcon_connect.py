from __future__ import annotations
import threading
import tkinter as tk
from typing import TYPE_CHECKING
from ..ui_constants import _GREEN_DARK, _GREEN_HOVER, _RED_DARK, _RED_HOVER
import sys
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..rcon_client import RconClient, RconError


def rcon_connect(app: "ARKServerManagerApp", server_id: str) -> None:
    w   = app._server_widgets.get(server_id, {})
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return

    host     = w.get("rcon_host",        tk.StringVar(value="127.0.0.1")).get()
    port_str = w.get("rcon_port_entry",   tk.StringVar(value=str(srv.rcon_port))).get()
    password = srv.rcon_password or srv.admin_password

    existing = app._rcon_clients.get(server_id)
    if existing and existing.is_connected:
        # Desconexão manual: desativa auto-connect e cancela o loop
        app._rcon_auto_enabled[server_id] = False
        app._rcon_cancel_auto_job(server_id)
        existing.disconnect()
        del app._rcon_clients[server_id]
        w.get("rcon_status_var", tk.StringVar()).set("⬛ Desconectado")
        w["rcon_connect_btn"].configure(text="🔌 Conectar",
                                        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER)
        return

    try:
        port = int(port_str)
    except ValueError:
        port = srv.rcon_port

    def _do_connect():
        client = RconClient(host, port, password,
                            on_log=lambda m, level: app._global_log(f"[RCON] {m}", level))
        try:
            client.connect()
            app._rcon_clients[server_id] = client
            def _ok():
                w.get("rcon_status_var", tk.StringVar()).set(f"🟢 Conectado a {host}:{port}")
                w["rcon_connect_btn"].configure(text="🔌 Desconectar",
                                               fg_color=_RED_DARK, hover_color=_RED_HOVER)
                app._rcon_append(server_id, f"Conectado a {host}:{port}\n", "sys")
            app.after(0, _ok)
        except RconError as exc:
            err_msg = str(exc)
            def _err(msg: str = err_msg):
                w.get("rcon_status_var", tk.StringVar()).set(f"🔴 Erro: {msg}")
                app._rcon_append(server_id, f"Erro de conexão: {msg}\n", "err")
            app.after(0, _err)

    threading.Thread(target=_do_connect, daemon=True).start()

