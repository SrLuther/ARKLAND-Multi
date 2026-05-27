from __future__ import annotations
import threading
import tkinter as tk
from typing import TYPE_CHECKING
from ..ui_constants import _RED_DARK, _RED_HOVER
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..rcon_client import RconClient, RconError

# Intervalos de backoff exponencial (ms) para reconexão após falhas:
# 1ª falha → 10s, 2ª → 20s, 3ª → 40s, 4ª+ → 60s
_BACKOFF_STEPS = [10_000, 20_000, 40_000, 60_000]
_KEEPALIVE_OK_MS = 20_000   # intervalo quando conectado e saudável

# Contador de falhas consecutivas por servidor (módulo local — não persiste)
_fail_counts: dict[str, int] = {}


def rcon_auto_connect_tick(app: "ARKServerManagerApp", server_id: str) -> None:
    """Tick do loop de keep-alive/auto-reconexão RCON.

    Comportamento:
    - Se conectado: faz ping leve. Se o ping falha, marca como desconectado e agenda retry.
    - Se desconectado: tenta reconectar com backoff exponencial.
    - Para de tentar se `_rcon_auto_enabled[server_id]` for False.
    """
    app._rcon_auto_jobs.pop(server_id, None)

    if not app._rcon_auto_enabled.get(server_id):
        return

    client = app._rcon_clients.get(server_id)
    w = app._server_widgets.get(server_id, {})

    # ── Já conectado: verificar com ping ──────────────────────────────────
    if client and client.is_connected:
        def _ping_check() -> None:
            alive = client.ping()
            def _after() -> None:
                if not app._rcon_auto_enabled.get(server_id):
                    return
                if alive:
                    _fail_counts[server_id] = 0
                    # Atualiza label com tempo de conexão
                    sv = w.get("rcon_status_var")
                    if sv:
                        secs = int(client.connected_seconds)
                        m, s = divmod(secs, 60)
                        sv.set(f"🟢 {client._host}:{client._port}  ⏱ {m:02d}:{s:02d}")
                    app._rcon_schedule_auto_connect(server_id, delay_ms=_KEEPALIVE_OK_MS)
                else:
                    # Ping falhou — conexão morreu silenciosamente
                    app._rcon_clients.pop(server_id, None)
                    sv = w.get("rcon_status_var")
                    if sv:
                        sv.set("🟡 Conexão perdida — reconectando...")
                    app._rcon_append(server_id, "⚠ Conexão RCON perdida. Tentando reconectar...\n", "sys")
                    _fail_counts[server_id] = _fail_counts.get(server_id, 0) + 1
                    _schedule_with_backoff(app, server_id)
            app.after(0, _after)
        threading.Thread(target=_ping_check, daemon=True).start()
        return

    # ── Desconectado: tentar reconectar ──────────────────────────────────
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return

    host     = (w.get("rcon_host", tk.StringVar(value="127.0.0.1")).get() or "127.0.0.1").strip()
    port_str = (w.get("rcon_port_entry", tk.StringVar(value=str(srv.rcon_port))).get() or "").strip()
    password = (srv.rcon_password or srv.admin_password or "").strip()

    if not password:
        return  # sem senha, não adianta tentar

    try:
        port = int(port_str)
        if not (1 <= port <= 65535):
            port = srv.rcon_port
    except ValueError:
        port = srv.rcon_port

    def _try() -> None:
        new_client = RconClient(
            host, port, password,
            on_log=lambda m, level: app._global_log(f"[RCON-Auto] {m}", level),
        )
        try:
            new_client.connect()

            def _ok() -> None:
                if not app._rcon_auto_enabled.get(server_id):
                    new_client.disconnect()
                    return
                app._rcon_clients[server_id] = new_client
                _fail_counts[server_id] = 0
                sv  = w.get("rcon_status_var")
                btn = w.get("rcon_connect_btn")
                if sv:
                    sv.set(f"🟢 {host}:{port}")
                if btn:
                    btn.configure(
                        text="🔌 Desconectar",
                        fg_color=_RED_DARK,
                        hover_color=_RED_HOVER,
                    )
                app._rcon_append(server_id, f"[Auto] ✅ Reconectado a {host}:{port}\n", "sys")
                app._rcon_schedule_auto_connect(server_id, delay_ms=_KEEPALIVE_OK_MS)
            app.after(0, _ok)

        except RconError:
            def _fail() -> None:
                if not app._rcon_auto_enabled.get(server_id):
                    return
                _fail_counts[server_id] = _fail_counts.get(server_id, 0) + 1
                sv = w.get("rcon_status_var")
                if sv:
                    fails = _fail_counts[server_id]
                    sv.set(f"🔴 Offline ({fails} tentativa(s))")
                _schedule_with_backoff(app, server_id)
            app.after(0, _fail)

    threading.Thread(target=_try, daemon=True).start()


def _schedule_with_backoff(app: "ARKServerManagerApp", server_id: str) -> None:
    """Agenda o próximo tick com backoff exponencial baseado no número de falhas."""
    fails    = _fail_counts.get(server_id, 0)
    idx      = min(fails, len(_BACKOFF_STEPS) - 1)
    delay_ms = _BACKOFF_STEPS[idx]
    app._rcon_schedule_auto_connect(server_id, delay_ms=delay_ms)

