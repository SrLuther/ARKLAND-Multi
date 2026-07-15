"""Desligamento agendado de servidores TEK — countdown em segundos + avisos RCON."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp

_TICK_MS = 1_000

# Escada de avisos (segundos restantes). Dense no fim; esparsa em waits longos.
_WARN_LADDER_SEC: tuple[int, ...] = (
    7200, 3600, 1800, 900, 600, 300, 180, 120,
    60, 45, 30, 20, 15, 10, 5, 3, 1,
)


def warning_milestones_seconds(total_seconds: int) -> list[int]:
    """Milestones (segundos restantes) para broadcast — sem spam a cada segundo."""
    total = int(total_seconds)
    if total < 1:
        return []
    return [m for m in _WARN_LADDER_SEC if 0 < m < total]


def format_shutdown_countdown(seconds: int) -> str:
    """Formata restante como H:MM:SS / M:SS para o card do dashboard."""
    secs = max(0, int(seconds))
    if secs >= 3600:
        hrs, rem = divmod(secs, 3600)
        mins, s = divmod(rem, 60)
        return f"{hrs}:{mins:02d}:{s:02d}"
    mins, s = divmod(secs, 60)
    return f"{mins}:{s:02d}"


def format_remaining_human(seconds: int) -> str:
    """Texto humano PT para mensagem de broadcast."""
    secs = max(0, int(seconds))
    if secs <= 0:
        return "agora"
    if secs < 60:
        return f"{secs}s"
    mins, rem = divmod(secs, 60)
    if mins < 60:
        if rem == 0:
            return f"{mins} minuto(s)"
        return f"{mins}m {rem:02d}s"
    hrs, rem = divmod(secs, 3600)
    mins, s = divmod(rem, 60)
    if mins == 0 and s == 0:
        return f"{hrs} hora(s)"
    if s == 0:
        return f"{hrs}h {mins:02d}m"
    return f"{hrs}h {mins:02d}m {s:02d}s"


def broadcast_message_for_remaining(seconds: int) -> str:
    secs = max(0, int(seconds))
    if secs <= 0:
        return "[ARKLAND] Desligando o servidor agora!"
    return f"[ARKLAND] Servidor será desligado em {format_remaining_human(secs)}"


def get_shutdown_state(app: "ARKServerManagerApp", server_id: str) -> dict[str, Any] | None:
    return getattr(app, "_asm_scheduled_shutdowns", {}).get(server_id)


def has_scheduled_shutdown(app: "ARKServerManagerApp", server_id: str) -> bool:
    return get_shutdown_state(app, server_id) is not None


def remaining_seconds(app: "ARKServerManagerApp", server_id: str) -> int:
    state = get_shutdown_state(app, server_id)
    if not state:
        return 0
    return max(0, int(state["deadline"] - time.time()))


def _ensure_store(app: "ARKServerManagerApp") -> dict:
    if not hasattr(app, "_asm_scheduled_shutdowns"):
        app._asm_scheduled_shutdowns = {}
    return app._asm_scheduled_shutdowns


def schedule_shutdown(app: "ARKServerManagerApp", server_id: str, seconds: int) -> str | None:
    """Agenda desligamento de um servidor. Retorna erro ou None se ok."""
    return schedule_shutdown_many(app, [server_id], seconds)


def schedule_shutdown_many(
    app: "ARKServerManagerApp",
    server_ids: Iterable[str],
    seconds: int,
) -> str | None:
    """Agenda desligamento para vários servidores. Retorna erro ou None se ok."""
    seconds = int(seconds)
    if seconds < 1:
        return "Informe ao menos 1 segundo."
    if seconds > 24 * 3600:
        return "Máximo de 86400 segundos (24 h)."

    ids = [sid for sid in server_ids if sid]
    if not ids:
        return "Selecione ao menos um servidor."

    from ..asm_engine.asm_server_config import ASM_STATUS_RUNNING

    store = _ensure_store(app)
    ok_names: list[str] = []
    skipped: list[str] = []

    for server_id in ids:
        srv = app.asm_config_manager.get_server(server_id)
        if not srv:
            skipped.append(server_id)
            continue
        inst = app.asm_server_manager.get_instance(server_id)
        if not inst or inst.status != ASM_STATUS_RUNNING:
            skipped.append(srv.name)
            continue

        store[server_id] = {
            "deadline": time.time() + seconds,
            "total_seconds": seconds,
            "warned": set(),
            "announced_start": False,
        }
        ok_names.append(srv.name)
        _refresh_card_shutdown_ui(app, server_id)
        # Aviso imediato do prazo total
        _send_remaining_warning(app, server_id, seconds)
        store[server_id]["announced_start"] = True

    if not ok_names:
        if skipped:
            return "Nenhum servidor online selecionado para agendar desligamento."
        return "Servidor não encontrado."

    _ensure_shutdown_tick(app)
    human = format_remaining_human(seconds)
    app._global_log(
        f"[Desligamento] Agendado em {human} para: {', '.join(ok_names)}.",
        "info",
    )
    if skipped:
        app._global_log(
            f"[Desligamento] Ignorados (offline/inexistentes): {', '.join(skipped)}.",
            "warning",
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


def cancel_all_shutdowns(app: "ARKServerManagerApp") -> None:
    shutdowns = getattr(app, "_asm_scheduled_shutdowns", {})
    for server_id in list(shutdowns.keys()):
        cancel_shutdown(app, server_id)


def _send_remaining_warning(app: "ARKServerManagerApp", server_id: str, seconds: int) -> None:
    srv = app.asm_config_manager.get_server(server_id)
    if not srv:
        return
    app._asm_do_scheduled_broadcast(srv, broadcast_message_for_remaining(seconds))


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
            total_sec = int(state.get("total_seconds") or 0)
            # Compat: agendas antigas em minutos
            if not total_sec and "total_minutes" in state:
                total_sec = int(state["total_minutes"]) * 60

            warned: set = state.setdefault("warned", set())
            for milestone in warning_milestones_seconds(total_sec):
                if milestone in warned:
                    continue
                if remaining <= milestone:
                    warned.add(milestone)
                    _send_remaining_warning(app, server_id, milestone)

            if remaining <= 0:
                _send_remaining_warning(app, server_id, 0)
                to_stop.append(server_id)
                shutdowns.pop(server_id, None)

        for server_id in to_stop:
            _refresh_card_shutdown_ui(app, server_id)
            # stop path já cancela agenda (noop) e usa saveworld/doexit existente
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


def open_schedule_dialog(
    app: "ARKServerManagerApp",
    server_id: str | None = None,
    preselected: list[str] | None = None,
) -> None:
    from ..asm_ui.asm_shutdown_schedule_dialog import open_shutdown_schedule_dialog

    open_shutdown_schedule_dialog(app, server_id=server_id, preselected=preselected)
