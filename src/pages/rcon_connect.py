from __future__ import annotations
import threading
import tkinter as tk
from datetime import datetime
from typing import TYPE_CHECKING
from ..ui_constants import _GREEN_DARK, _GREEN_HOVER, _RED_DARK, _RED_HOVER
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..rcon_client import RconClient, RconError, RconAuthError


def rcon_connect(app: "ARKServerManagerApp", server_id: str) -> None:
    """Conecta ou desconecta o RCON de um servidor com validação de entrada."""
    w   = app._server_widgets.get(server_id, {})
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return

    host     = (srv.server_ip or "127.0.0.1").strip()
    port     = srv.rcon_port
    password = (srv.rcon_password or srv.admin_password or "").strip()

    # ── Desconexão manual ─────────────────────────────────────────────────
    existing = app._rcon_clients.get(server_id)
    if existing and existing.is_connected:
        app._rcon_auto_enabled[server_id] = False
        app._rcon_cancel_auto_job(server_id)
        existing.disconnect()
        app._rcon_clients.pop(server_id, None)
        sv = w.get("rcon_status_var")
        if sv:
            sv.set("⬛ Desconectado")
        btn = w.get("rcon_connect_btn")
        if btn:
            btn.configure(text="🔌 Conectar", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER)
        app._rcon_append(server_id, "Desconectado manualmente.\n", "sys")
        return

    if not password:
        app._rcon_append(
            server_id,
            "❌ Senha RCON não configurada. Vá em Configurações → Geral e defina a Senha RCON.\n",
            "err",
        )
        sv = w.get("rcon_status_var")
        if sv:
            sv.set("🔴 Sem senha RCON")
        return

    sv = w.get("rcon_status_var")
    if sv:
        sv.set("⏳ Conectando...")
    btn = w.get("rcon_connect_btn")
    if btn:
        btn.configure(state="disabled")

    # ── Conexão em thread ─────────────────────────────────────────────────
    def _do_connect() -> None:
        client = RconClient(
            host, port, password,
            on_log=lambda m, level: app._global_log(f"[RCON] {m}", level),
        )
        try:
            client.connect()
            app._rcon_clients[server_id] = client
            # Ativa auto-reconexão mantendo a sessão viva
            app._rcon_auto_enabled[server_id] = True
            app._rcon_schedule_auto_connect(server_id, delay_ms=20_000)

            def _ok() -> None:
                ts = datetime.now().strftime("%H:%M:%S")
                if sv:
                    sv.set(f"🟢 {host}:{port}")
                if btn:
                    btn.configure(
                        state="normal",
                        text="🔌 Desconectar",
                        fg_color=_RED_DARK,
                        hover_color=_RED_HOVER,
                    )
                app._rcon_append(server_id, f"[{ts}] ✅ Conectado a {host}:{port}\n", "sys")
            app.after(0, _ok)

        except RconAuthError as exc:
            err_msg = str(exc)
            def _auth_err(msg: str = err_msg) -> None:
                if sv:
                    sv.set("🔴 Senha incorreta")
                if btn:
                    btn.configure(state="normal")
                app._rcon_append(
                    server_id,
                    f"❌ Autenticação falhou: {msg}\n"
                    "   Verifique se a Senha RCON está correta nas configurações.\n",
                    "err",
                )
            app.after(0, _auth_err)

        except RconError as exc:
            err_msg = str(exc)
            def _err(msg: str = err_msg) -> None:
                if sv:
                    sv.set(f"🔴 Falha na conexão")
                if btn:
                    btn.configure(state="normal")
                app._rcon_append(
                    server_id,
                    f"❌ Erro de conexão: {msg}\n"
                    "   Verifique se o servidor está online e a porta RCON está correta.\n",
                    "err",
                )
            app.after(0, _err)

    threading.Thread(target=_do_connect, daemon=True).start()

