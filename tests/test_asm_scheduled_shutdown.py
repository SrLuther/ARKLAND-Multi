"""Testes do desligamento programado TEK (segundos + milestones RCON)."""
from __future__ import annotations

from src.pages.asm_scheduled_shutdown import (
    broadcast_message_for_remaining,
    format_remaining_human,
    format_shutdown_countdown,
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
