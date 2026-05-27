"""Scheduler tick para broadcasts automáticos por intervalo.

Cada servidor tem seu próprio ciclo independente.
O tick dispara a cada _TICK_MS ms e envia as mensagens cujo intervalo foi
atingido desde o último envio.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

_TICK_MS = 30_000   # verifica a cada 30 s


def broadcast_sched_tick(app: "ARKServerManagerApp", server_id: str) -> None:
    """Checa e envia broadcasts agendados cujo intervalo foi cumprido."""
    if not app._bc_sched_running.get(server_id, False):
        return

    srv = app.config_manager.get_server(server_id)
    if not srv:
        return

    now = time.time()
    changed = False

    for bc in srv.auto_broadcasts:
        if not bc.get("enabled", True):
            continue
        interval_sec = bc.get("interval_min", 30) * 60
        last_sent = bc.get("last_sent", 0.0)
        if now - last_sent >= interval_sec:
            msg = bc.get("message", "").strip()
            if msg:
                bc["last_sent"] = now
                changed = True
                # Envia de forma segura; falhas são logadas internamente
                try:
                    app._broadcast_rcon(server_id, msg)
                except Exception:
                    pass

    if changed:
        app.config_manager.update_server(srv)

    # Atualiza UI (mesmo sem envio, para atualizar countdowns)
    try:
        app.after(0, lambda: _safe_refresh(app, server_id))
    except Exception:
        pass

    # Reagenda próximo tick
    job = app.after(_TICK_MS, lambda: broadcast_sched_tick(app, server_id))
    app._bc_sched_jobs[server_id] = job


def broadcast_sched_start(app: "ARKServerManagerApp", server_id: str) -> None:
    """Inicia o scheduler de broadcasts automáticos para um servidor."""
    broadcast_sched_stop(app, server_id)
    app._bc_sched_running[server_id] = True
    # Primeiro tick em 1 s para checar imediatamente após ativação
    job = app.after(1000, lambda: broadcast_sched_tick(app, server_id))
    app._bc_sched_jobs[server_id] = job
    _safe_refresh(app, server_id)


def broadcast_sched_stop(app: "ARKServerManagerApp", server_id: str) -> None:
    """Para o scheduler de broadcasts automáticos para um servidor."""
    app._bc_sched_running[server_id] = False
    job = app._bc_sched_jobs.pop(server_id, None)
    if job:
        try:
            app.after_cancel(job)
        except Exception:
            pass
    _safe_refresh(app, server_id)


def _safe_refresh(app: "ARKServerManagerApp", server_id: str) -> None:
    try:
        app._bc_sched_refresh(server_id)
    except Exception:
        pass
