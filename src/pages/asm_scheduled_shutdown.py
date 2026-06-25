"""Desligamento agendado de servidores TEK com avisos RCON (5/3/1 min)."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp

_TICK_MS = 1_000
_WARN_MINUTES = (5, 3, 1)


def _applicable_milestones(total_minutes: int) -> list[int]:
    return [m for m in _WARN_MINUTES if total_minutes >= m]


def format_shutdown_countdown(seconds: int) -> str:
    """Formata restante como M:SS para o card do dashboard."""
    if seconds <= 0:
        return "0:00"
    mins, secs = divmod(int(seconds), 60)
    return f"{mins}:{secs:02d}"


def get_shutdown_state(app: "ARKServerManagerApp", server_id: str) -> dict[str, Any] | None:
    return getattr(app, "_asm_scheduled_shutdowns", {}).get(server_id)


def has_scheduled_shutdown(app: "ARKServerManagerApp", server_id: str) -> bool:
    return get_shutdown_state(app, server_id) is not None


def remaining_seconds(app: "ARKServerManagerApp", server_id: str) -> int:
    state = get_shutdown_state(app, server_id)
    if not state:
        return 0
    return max(0, int(state["deadline"] - time.time()))


def schedule_shutdown(app: "ARKServerManagerApp", server_id: str, minutes: int) -> str | None:
    """Agenda desligamento. Retorna mensagem de erro ou None se ok."""
    minutes = int(minutes)
    if minutes < 1:
        return "Informe ao menos 1 minuto."
    if minutes > 24 * 60:
        return "Máximo de 1440 minutos (24 h)."

    srv = app.asm_config_manager.get_server(server_id)
    if not srv:
        return "Servidor não encontrado."

    from ..asm_engine.asm_server_config import ASM_STATUS_RUNNING

    inst = app.asm_server_manager.get_instance(server_id)
    if not inst or inst.status != ASM_STATUS_RUNNING:
        return "O servidor precisa estar online para agendar desligamento."

    if not hasattr(app, "_asm_scheduled_shutdowns"):
        app._asm_scheduled_shutdowns = {}

    app._asm_scheduled_shutdowns[server_id] = {
        "deadline": time.time() + minutes * 60,
        "total_minutes": minutes,
        "warned": set(),
    }
    _ensure_shutdown_tick(app)
    _refresh_card_shutdown_ui(app, server_id)
    app._global_log(
        f"[Desligamento] {srv.name}: agendado em {minutes} minuto(s).",
        "info",
    )
    return None


def cancel_shutdown(app: "ARKServerManagerApp", server_id: str) -> None:
    shutdowns = getattr(app, "_asm_scheduled_shutdowns", {})
    if server_id not in shutdowns:
        return
    srv = app.asm_config_manager.get_server(server_id)
    name = srv.name if srv else server_id
    shutdowns.pop(server_id, None)
    _refresh_card_shutdown_ui(app, server_id)
    app._global_log(f"[Desligamento] {name}: agendamento cancelado.", "info")


def _send_warning(app: "ARKServerManagerApp", server_id: str, minutes: int) -> None:
    srv = app.asm_config_manager.get_server(server_id)
    if not srv:
        return
    msg = f"[ARKLAND] Este servidor será desligado em {minutes} minuto(s)."
    app._asm_do_scheduled_broadcast(srv, msg)


def _ensure_shutdown_tick(app: "ARKServerManagerApp") -> None:
    if getattr(app, "_asm_shutdown_tick_running", False):
        return
    app._asm_shutdown_tick_running = True
    asm_scheduled_shutdown_tick(app)


def _cancel_shutdown_tick_job(app: "ARKServerManagerApp") -> None:
    job = getattr(app, "_asm_shutdown_tick_job", None)
    if job:
        try:
            app.after_cancel(job)
        except Exception:
            pass
    app._asm_shutdown_tick_job = None


def asm_scheduled_shutdown_tick(app: "ARKServerManagerApp") -> None:
    shutdowns: dict = getattr(app, "_asm_scheduled_shutdowns", {})
    try:
        if not shutdowns:
            return

        from ..asm_engine.asm_server_config import ASM_STATUS_RUNNING

        now = time.time()
        to_stop: list[str] = []

        for server_id, state in list(shutdowns.items()):
            inst = app.asm_server_manager.get_instance(server_id)
            if not inst or inst.status != ASM_STATUS_RUNNING:
                shutdowns.pop(server_id, None)
                _refresh_card_shutdown_ui(app, server_id)
                continue

            remaining = state["deadline"] - now
            total_min = int(state["total_minutes"])

            for milestone in _applicable_milestones(total_min):
                warned: set = state["warned"]
                if milestone in warned:
                    continue
                if remaining <= milestone * 60:
                    warned.add(milestone)
                    _send_warning(app, server_id, milestone)

            if remaining <= 0:
                to_stop.append(server_id)
                shutdowns.pop(server_id, None)

        for server_id in to_stop:
            _refresh_card_shutdown_ui(app, server_id)
            app._asm_stop_server(server_id)

        for server_id in list(shutdowns.keys()):
            _update_countdown_label(app, server_id)
    finally:
        _cancel_shutdown_tick_job(app)
        if getattr(app, "_asm_scheduled_shutdowns", {}):
            app._asm_shutdown_tick_job = app.after(
                _TICK_MS, lambda: asm_scheduled_shutdown_tick(app),
            )
        else:
            app._asm_shutdown_tick_running = False


def _update_countdown_label(app: "ARKServerManagerApp", server_id: str) -> None:
    card = (getattr(app, "_asm_dashboard_cards", {}) or {}).get(server_id)
    if card is None:
        return
    try:
        if not card.winfo_exists():
            return
    except Exception:
        return

    lbl = getattr(card, "_asm_shutdown_countdown_lbl", None)
    if lbl is None:
        return
    try:
        if not lbl.winfo_exists():
            return
        secs = remaining_seconds(app, server_id)
        lbl.configure(text=f"⏱  Desliga em {format_shutdown_countdown(secs)}")
    except Exception:
        pass


def _refresh_card_shutdown_ui(app: "ARKServerManagerApp", server_id: str) -> None:
    try:
        app.after(0, lambda sid=server_id: _refresh_card_shutdown_ui_now(app, sid))
    except Exception:
        pass


def _refresh_card_shutdown_ui_now(app: "ARKServerManagerApp", server_id: str) -> None:
    from ..asm_ui.asm_server_card import refresh_shutdown_row

    card = (getattr(app, "_asm_dashboard_cards", {}) or {}).get(server_id)
    if card is None:
        return
    try:
        if not card.winfo_exists():
            return
    except Exception:
        return

    srv = app.asm_config_manager.get_server(server_id)
    if srv:
        refresh_shutdown_row(app, card, srv)


def open_schedule_dialog(app: "ARKServerManagerApp", server_id: str) -> None:
    from ..asm_ui.asm_shutdown_schedule_dialog import open_shutdown_schedule_dialog

    open_shutdown_schedule_dialog(app, server_id)
