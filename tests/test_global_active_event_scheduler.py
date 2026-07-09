"""Testes do scheduler de eventos ARK globais."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock

from src.global_active_event_scheduler import (
    ARK_EVENT_STATUS_NOTIFYING,
    ARK_EVENT_STATUS_SCHEDULED,
    GlobalActiveEventScheduler,
    parse_brasilia_datetime,
    format_brasilia_datetime,
)
from src.buff_manager import now_brasilia
from src.pages.global_active_event import ApplyActiveEventResult


def test_parse_brasilia_datetime():
    dt = parse_brasilia_datetime("09/07/2026 15:30")
    assert dt.year == 2026 and dt.month == 7 and dt.hour == 15


def test_schedule_event_future(tmp_path):
    applied: list[tuple[list[str], str]] = []

    sched = GlobalActiveEventScheduler(
        tmp_path,
        get_server_config=lambda _s: MagicMock(rcon_enabled=False),
        get_server_status=lambda _s: "stopped",
        stop_server=lambda _s: None,
        start_server=lambda _s: None,
        apply_active_event=lambda sids, eid: (
            applied.append((list(sids), eid))
            or [ApplyActiveEventResult(sids[0], "A", True, "ok")]
        ),
    )
    when = now_brasilia() + timedelta(hours=2)
    ev, err = sched.schedule_event("Easter", when, ["srv-1"])
    assert not err
    assert ev is not None
    assert ev.status == ARK_EVENT_STATUS_SCHEDULED
    assert sched._file.is_file()


def test_countdown_warning_once(tmp_path):
    broadcasts: list[tuple[list[str], str]] = []

    class _Cfg:
        rcon_enabled = True
        admin_password = "pwd"
        server_ip = "127.0.0.1"
        rcon_port = 27020

    sched = GlobalActiveEventScheduler(
        tmp_path,
        get_server_config=lambda _s: _Cfg(),
        get_server_status=lambda _s: "running",
        stop_server=lambda _s: None,
        start_server=lambda _s: None,
        apply_active_event=lambda sids, eid: [
            ApplyActiveEventResult(sids[0], "A", True, "ok"),
        ],
    )
    orig = sched._broadcast
    sched._broadcast = lambda sids, msg: broadcasts.append((list(sids), msg))

    when = now_brasilia() + timedelta(minutes=4)
    ev, _ = sched.schedule_event("Easter", when, ["srv-1"])
    assert ev is not None

    sched._tick()
    five_min = [b for b in broadcasts if "5 minutos" in b[1]]
    assert len(five_min) == 1
    sched._tick()
    assert len([b for b in broadcasts if "5 minutos" in b[1]]) == 1


def test_post_notify_completes_after_one_hour(tmp_path):
    from src.global_active_event_scheduler import ScheduledArkEvent, ARK_EVENT_STATUS_COMPLETED

    sched = GlobalActiveEventScheduler(
        tmp_path,
        get_server_config=lambda _s: None,
        get_server_status=lambda _s: "stopped",
        stop_server=lambda _s: None,
        start_server=lambda _s: None,
        apply_active_event=lambda sids, eid: [],
    )
    activated = now_brasilia() - timedelta(hours=1, minutes=5)
    ev = ScheduledArkEvent(
        id="x",
        event_id="Easter",
        scheduled_at=activated.isoformat(),
        server_ids=["a"],
        status=ARK_EVENT_STATUS_NOTIFYING,
        activated_at=activated.isoformat(),
        last_notify_at=0.0,
    )
    sched._events = [ev]
    sched._tick()
    assert ev.status == ARK_EVENT_STATUS_COMPLETED
