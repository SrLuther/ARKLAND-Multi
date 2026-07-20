"""Reinício programado TEK — respeita restart_countdown_minutes com avisos RCON."""
from __future__ import annotations

import time
from typing import Callable

# Escada de avisos durante a espera (segundos restantes).
_RESTART_WARN_LADDER_SEC: tuple[int, ...] = (
    3600, 1800, 900, 600, 300, 180, 120, 60, 30, 10, 5,
)


def restart_warning_milestones(total_seconds: int) -> list[int]:
    total = int(total_seconds)
    if total < 1:
        return []
    return [m for m in _RESTART_WARN_LADDER_SEC if 0 < m < total]


def format_restart_wait_human(seconds: int) -> str:
    secs = max(0, int(seconds))
    if secs < 60:
        return f"{secs} segundo(s)"
    mins, rem = divmod(secs, 60)
    if rem == 0:
        return f"{mins} minuto(s)"
    return f"{mins} minuto(s) e {rem}s"


def run_restart_countdown(
    *,
    total_seconds: int,
    broadcast: Callable[[str], None],
    should_abort: Callable[[], bool] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> bool:
    """
    Aguarda total_seconds com broadcasts nos milestones.
    Retorna True se completou (deve reiniciar); False se abortou.
    """
    total = max(0, int(total_seconds))
    if total <= 0:
        broadcast("[ARKLAND] Servidor reiniciando agora!")
        return True

    deadline = monotonic_fn() + total
    warned: set[int] = set()
    broadcast(
        f"[ARKLAND] Servidor reiniciará em {format_restart_wait_human(total)}."
    )

    while True:
        if should_abort and should_abort():
            return False
        remaining = deadline - monotonic_fn()
        if remaining <= 0:
            break
        for milestone in restart_warning_milestones(total):
            if milestone in warned:
                continue
            if remaining <= milestone:
                warned.add(milestone)
                broadcast(
                    f"[ARKLAND] Servidor reiniciará em {format_restart_wait_human(milestone)}."
                )
        sleep_fn(min(1.0, max(0.05, remaining)))

    if should_abort and should_abort():
        return False
    broadcast("[ARKLAND] Servidor reiniciando agora!")
    return True
