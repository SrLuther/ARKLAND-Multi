"""Testes do desligamento/reinício programado TEK (unidades de tempo)."""
from __future__ import annotations

from src.pages.asm_scheduled_restart import (
    format_restart_wait_human,
    restart_warning_milestones,
    run_restart_countdown,
)
from src.pages.asm_scheduled_shutdown import (
    broadcast_message_for_remaining,
    format_remaining_human,
    format_shutdown_countdown,
    total_seconds_from_parts,
    warning_milestones_seconds,
)


def test_milestones_short_timer_dense_near_end():
    assert warning_milestones_seconds(60) == [45, 30, 20, 15, 10, 5, 3, 1]
    assert 60 not in warning_milestones_seconds(60)  # start announce é separado


def test_milestones_long_timer_not_every_second():
    ms = warning_milestones_seconds(3600)
    assert 3600 not in ms
    assert 1800 in ms
    assert 60 in ms
    assert 5 in ms
    # Sem spam: longe de 3600 milestones
    assert len(ms) < 30


def test_milestones_empty_for_subsecond():
    assert warning_milestones_seconds(0) == []
    assert warning_milestones_seconds(1) == []


def test_format_countdown():
    assert format_shutdown_countdown(0) == "0:00"
    assert format_shutdown_countdown(75) == "1:15"
    assert format_shutdown_countdown(3661) == "1:01:01"


def test_broadcast_messages_pt():
    assert "desligado em 45s" in broadcast_message_for_remaining(45)
    assert "minuto" in broadcast_message_for_remaining(120).lower()
    assert "agora" in broadcast_message_for_remaining(0).lower()
    assert format_remaining_human(90) == "1m 30s"


def test_dialog_minutes_plus_seconds_not_bare_seconds():
    """Operador que define 5 min + 0 s deve obter 300s, não 5s."""
    assert total_seconds_from_parts(5, 0) == 300
    assert total_seconds_from_parts(0, 30) == 30
    assert total_seconds_from_parts(1, 30) == 90


def test_restart_countdown_waits_full_duration():
    """Bug histórico: anunciava N minutos e reiniciava no after(0)."""
    sleeps: list[float] = []
    messages: list[str] = []
    clock = {"t": 0.0}

    def mono() -> float:
        return clock["t"]

    def sleep(dt: float) -> None:
        sleeps.append(dt)
        clock["t"] += dt

    ok = run_restart_countdown(
        total_seconds=5,
        broadcast=messages.append,
        sleep_fn=sleep,
        monotonic_fn=mono,
    )
    assert ok is True
    assert clock["t"] >= 5.0
    assert any("5 segundo" in m for m in messages)
    assert messages[-1].endswith("agora!")


def test_restart_countdown_abort():
    messages: list[str] = []
    clock = {"t": 0.0}

    def mono() -> float:
        return clock["t"]

    def sleep(dt: float) -> None:
        clock["t"] += dt

    ok = run_restart_countdown(
        total_seconds=60,
        broadcast=messages.append,
        should_abort=lambda: clock["t"] >= 2,
        sleep_fn=sleep,
        monotonic_fn=mono,
    )
    assert ok is False
    assert clock["t"] < 60


def test_restart_milestones_skip_total():
    assert 300 not in restart_warning_milestones(300)
    assert 60 in restart_warning_milestones(300)
    assert "minuto" in format_restart_wait_human(120)
