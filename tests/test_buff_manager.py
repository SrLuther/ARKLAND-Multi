"""Testes do sistema de BUFFs (empilhamento de rates e encerramento)."""
from __future__ import annotations

import tempfile
import threading
import time
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.buff_manager import (
    BUFF_STATUS_ACTIVE,
    BUFF_STATUS_CANCELLED,
    BUFF_STATUS_SCHEDULED,
    BUFF_TYPE_BREEDING,
    BuffEvent,
    BuffManager,
    BuffRates,
    now_brasilia,
    stack_buff_rate,
)


class _FakeGameSettings:
    baby_mature_speed_multiplier: float = 44.0
    egg_hatch_speed_multiplier: float = 20.0
    mating_interval_multiplier: float = 0.5


class _FakeServerConfig:
    install_dir = "/fake/ark"
    game_settings = _FakeGameSettings()


def test_stack_buff_rate_multiplies_base():
    assert stack_buff_rate(44.0, 10.0) == 440.0
    assert stack_buff_rate(0.5, 0.1) == 0.05


def test_stack_buff_rate_defaults_invalid_base():
    assert stack_buff_rate(0, 10.0) == 10.0
    assert stack_buff_rate(-1, 10.0) == 10.0


@patch("src.buff_manager.ArkIniManager")
def test_apply_rates_stacks_on_base_not_replaces(mock_ini_cls):
    mock_ini = MagicMock()
    mock_ini_cls.return_value = mock_ini
    cfg = _FakeServerConfig()
    rates = BuffRates(baby_mature_speed_multiplier=10.0)

    mgr = BuffManager(
        data_dir=Path(tempfile.mkdtemp()),
        get_server_config=lambda _sid: cfg,
        start_server=lambda _sid: None,
        stop_server=lambda _sid: None,
        get_server_status=lambda _sid: "stopped",
    )

    ok = mgr._apply_rates("srv1", rates)
    assert ok is True
    assert cfg.game_settings.baby_mature_speed_multiplier == 440.0
    mock_ini.save_game_user_settings.assert_called_once()


@patch("src.buff_manager.time.sleep")
def test_stop_active_event_marks_cancelled(mock_sleep):
    data_dir = Path(tempfile.mkdtemp())
    event = BuffEvent(
        id="evt-stop",
        name="Boost Teste",
        server_id="srv1",
        types=[BUFF_TYPE_BREEDING],
        rates=BuffRates(baby_mature_speed_multiplier=10.0),
        start_dt=(now_brasilia() - timedelta(hours=1)).isoformat(),
        end_dt=(now_brasilia() + timedelta(hours=1)).isoformat(),
        status=BUFF_STATUS_ACTIVE,
        backup_path=str(data_dir / "backup"),
    )
    (data_dir / "backup").mkdir()
    (data_dir / "backup" / "GameUserSettings.ini").write_text("[x]", encoding="utf-8")

    restored = threading.Event()

    mgr = BuffManager(
        data_dir=data_dir,
        get_server_config=lambda _sid: _FakeServerConfig(),
        start_server=lambda _sid: None,
        stop_server=lambda _sid: None,
        get_server_status=lambda _sid: "stopped",
    )
    mgr._events = [event]
    mgr._rcon_broadcast = lambda *_a, **_k: None  # type: ignore[method-assign]
    mgr._restore_ini = lambda _sid, _bp: restored.set() or True  # type: ignore[method-assign]

    err = mgr.stop_active_event("evt-stop")
    assert err is None

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with mgr._lock:
            if event.status == BUFF_STATUS_CANCELLED:
                break
        time.sleep(0.05)
    else:
        pytest.fail("evento não foi marcado como cancelado")

    assert restored.is_set()


def test_stop_active_event_rejects_non_active():
    data_dir = Path(tempfile.mkdtemp())
    event = BuffEvent(
        id="evt-sched",
        name="Agendado",
        server_id="srv1",
        types=[BUFF_TYPE_BREEDING],
        rates=BuffRates(),
        start_dt=(now_brasilia() + timedelta(hours=1)).isoformat(),
        end_dt=(now_brasilia() + timedelta(hours=2)).isoformat(),
        status=BUFF_STATUS_SCHEDULED,
    )
    mgr = BuffManager(
        data_dir=data_dir,
        get_server_config=MagicMock(),
        start_server=MagicMock(),
        stop_server=MagicMock(),
        get_server_status=MagicMock(return_value="stopped"),
    )
    mgr._events = [event]

    err = mgr.stop_active_event("evt-sched")
    assert err == "Só é possível encerrar BUFFs ativos."


def test_stop_active_event_rejects_unknown_id():
    mgr = BuffManager(
        data_dir=Path(tempfile.mkdtemp()),
        get_server_config=MagicMock(),
        start_server=MagicMock(),
        stop_server=MagicMock(),
        get_server_status=MagicMock(return_value="stopped"),
    )
    assert mgr.stop_active_event("missing") == "Evento não encontrado."


@patch("src.buff_manager.time.sleep", lambda _s: None)
def test_stop_active_event_without_backup_still_finishes():
    data_dir = Path(tempfile.mkdtemp())
    event = BuffEvent(
        id="evt-nobkp",
        name="Sem backup",
        server_id="srv1",
        types=[BUFF_TYPE_BREEDING],
        rates=BuffRates(baby_mature_speed_multiplier=10.0),
        start_dt=(now_brasilia() - timedelta(hours=1)).isoformat(),
        end_dt=(now_brasilia() + timedelta(hours=1)).isoformat(),
        status=BUFF_STATUS_ACTIVE,
        backup_path=None,
    )
    stopped = threading.Event()

    mgr = BuffManager(
        data_dir=data_dir,
        get_server_config=lambda _sid: _FakeServerConfig(),
        start_server=lambda _sid: stopped.set(),
        stop_server=lambda _sid: None,
        get_server_status=lambda _sid: "stopped",
    )
    mgr._events = [event]
    mgr._rcon_broadcast = lambda *_a, **_k: None  # type: ignore[method-assign]

    assert mgr.stop_active_event("evt-nobkp") is None

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with mgr._lock:
            if event.status == BUFF_STATUS_CANCELLED:
                break
        time.sleep(0.05)
    else:
        pytest.fail("evento sem backup não foi cancelado")

    assert stopped.is_set()


def test_cancel_event_only_scheduled():
    data_dir = Path(tempfile.mkdtemp())
    event = BuffEvent(
        id="evt-cancel",
        name="Agendado",
        server_id="srv1",
        types=[BUFF_TYPE_BREEDING],
        rates=BuffRates(),
        start_dt=(now_brasilia() + timedelta(hours=1)).isoformat(),
        end_dt=(now_brasilia() + timedelta(hours=2)).isoformat(),
        status=BUFF_STATUS_SCHEDULED,
    )

    mgr = BuffManager(
        data_dir=data_dir,
        get_server_config=MagicMock(),
        start_server=MagicMock(),
        stop_server=MagicMock(),
        get_server_status=MagicMock(return_value="stopped"),
    )
    mgr._events = [event]
    mgr.cancel_event("evt-cancel")

    assert event.status == BUFF_STATUS_CANCELLED
