"""Scheduler global de broadcasts TEK — reenvio por intervalo."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp

_TICK_MS = 30_000


def broadcast_tek_scheduler_tick(app: "ARKServerManagerApp") -> None:
    from .broadcast_send_tek import broadcast_send_tek_sync
    from .broadcast_tek_settings import (
        format_countdown,
        get_settings,
        pick_next_message,
        resolve_target_server_ids,
        save_settings,
        seconds_until_next,
    )

    settings = get_settings(app)
    if not settings.scheduler_enabled:
        _reschedule(app)
        return

    remaining = seconds_until_next(settings)
    if remaining > 0:
        _update_status_ui(app, f"Ativo — próximo envio em {format_countdown(remaining)}")
        _reschedule(app)
        return

    pool_ok = bool(resolve_target_server_ids(app))
    entry, next_index = pick_next_message(app)
    if not entry or not pool_ok:
        _update_status_ui(app, "Ativo — configure mensagens e servidores")
        _reschedule(app)
        return

    message = str(entry.get("message", "")).strip()
    server_ids = resolve_target_server_ids(app)
    if message and server_ids:
        broadcast_send_tek_sync(app, message, server_ids=server_ids)
        settings.last_sent_at = time.time()
        if not settings.random_order:
            settings.rotation_index = next_index
        save_settings(app, settings)
        label = entry.get("label", "mensagem")
        app._global_log(
            f"[Broadcast auto] «{label}» → {len(server_ids)} servidor(es)",
            "info",
        )

    _update_status_ui(app, f"Ativo — próximo envio em {format_countdown(seconds_until_next(settings))}")
    _reschedule(app)


def broadcast_tek_scheduler_start(app: "ARKServerManagerApp") -> None:
    from .broadcast_tek_settings import get_settings, save_settings

    settings = get_settings(app)
    settings.scheduler_enabled = True
    if not settings.last_sent_at:
        settings.last_sent_at = time.time()
    save_settings(app, settings)
    broadcast_tek_scheduler_stop(app, refresh_ui=False)
    app._broadcast_tek_scheduler_running = True
    job = app.after(1000, lambda: broadcast_tek_scheduler_tick(app))
    app._broadcast_tek_scheduler_job = job
    _refresh_scheduler_ui(app)


def broadcast_tek_scheduler_stop(app: "ARKServerManagerApp", *, refresh_ui: bool = True) -> None:
    from .broadcast_tek_settings import get_settings, save_settings

    app._broadcast_tek_scheduler_running = False
    job = getattr(app, "_broadcast_tek_scheduler_job", None)
    if job:
        try:
            app.after_cancel(job)
        except Exception:
            pass
    app._broadcast_tek_scheduler_job = None

    settings = get_settings(app)
    if settings.scheduler_enabled:
        settings.scheduler_enabled = False
        save_settings(app, settings)

    if refresh_ui:
        _refresh_scheduler_ui(app)


def ensure_broadcast_tek_scheduler(app: "ARKServerManagerApp") -> None:
    """Inicia o tick se o scheduler estava ativo ao abrir o app."""
    from .broadcast_tek_settings import get_settings

    if get_settings(app).scheduler_enabled:
        broadcast_tek_scheduler_start(app)


def _reschedule(app: "ARKServerManagerApp") -> None:
    if not getattr(app, "_broadcast_tek_scheduler_running", False):
        return
    job = getattr(app, "_broadcast_tek_scheduler_job", None)
    if job:
        try:
            app.after_cancel(job)
        except Exception:
            pass
    app._broadcast_tek_scheduler_job = app.after(
        _TICK_MS, lambda: broadcast_tek_scheduler_tick(app),
    )


def _update_status_ui(app: "ARKServerManagerApp", text: str) -> None:
    var = getattr(app, "_broadcast_sched_status_var", None)
    if var is not None:
        try:
            var.set(text)
        except Exception:
            pass


def _refresh_scheduler_ui(app: "ARKServerManagerApp") -> None:
    try:
        app.after(0, app._broadcast_tek_sync_scheduler_ui)
    except Exception:
        pass
