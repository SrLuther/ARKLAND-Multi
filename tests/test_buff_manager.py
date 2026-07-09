"""Testes do sistema de BUFFs (multiplicadores por setor, backup e encerramento)."""
from __future__ import annotations

import tempfile
import threading
import time
import zipfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.asm_engine.asm_ini_manager import write_ini
from src.asm_engine.asm_server_config import AsmServerConfig
from src.buff_ini_backups import backup_ini_files, restore_ini_from_backup
from src.buff_manager import (
    BUFF_STATUS_ACTIVE,
    BUFF_STATUS_CANCELLED,
    BUFF_STATUS_SCHEDULED,
    BUFF_TYPE_BREEDING,
    BUFF_TYPE_FARM,
    BUFF_TYPE_XP,
    BuffEvent,
    BuffManager,
    BuffRates,
    BuffSectorMults,
    compute_buff_field_value,
    now_brasilia,
    stack_buff_rate,
)


class _FakeGameSettings:
    baby_mature_speed_multiplier: float = 25.0
    egg_hatch_speed_multiplier: float = 25.0
    mating_interval_multiplier: float = 0.2
    xp_multiplier: float = 5.0


class _FakeServerConfig:
    install_dir = "/fake/ark"
    game_settings = _FakeGameSettings()
    rcon_enabled = False


def test_compute_buff_field_value_normal():
    assert compute_buff_field_value(25.0, 10.0, is_inverse=False) == 50.0
    assert compute_buff_field_value(5.0, 10.0, is_inverse=False) == 10.0


def test_compute_buff_field_value_inverse():
    assert compute_buff_field_value(0.2, 10.0, is_inverse=True) == 0.1
    assert compute_buff_field_value(0.5, 5.0, is_inverse=True) == 0.5


def test_stack_buff_rate_multiplies_base():
    assert stack_buff_rate(44.0, 10.0) == 440.0
    assert stack_buff_rate(0.5, 0.1) == 0.05


def test_stack_buff_rate_defaults_invalid_base():
    assert stack_buff_rate(0, 10.0) == 10.0
    assert stack_buff_rate(-1, 10.0) == 10.0


@patch("src.buff_manager.ArkIniManager")
def test_apply_sector_rates_from_base_5x(mock_ini_cls):
    mock_ini = MagicMock()
    mock_ini_cls.return_value = mock_ini
    cfg = _FakeServerConfig()
    event = BuffEvent(
        id="e1",
        name="Boost",
        server_id="srv1",
        types=[BUFF_TYPE_BREEDING],
        rates=BuffRates(),
        sector_mults=BuffSectorMults(breeding=10.0),
        start_dt=now_brasilia().isoformat(),
        end_dt=(now_brasilia() + timedelta(hours=1)).isoformat(),
        status=BUFF_STATUS_SCHEDULED,
    )

    mgr = BuffManager(
        data_dir=Path(tempfile.mkdtemp()),
        get_server_config=lambda _sid: cfg,
        start_server=lambda _sid: None,
        stop_server=lambda _sid: None,
        get_server_status=lambda _sid: "stopped",
    )

    ok = mgr._apply_event_rates("srv1", event)
    assert ok is True
    assert cfg.game_settings.baby_mature_speed_multiplier == 50.0
    assert cfg.game_settings.mating_interval_multiplier == 0.1
    mock_ini.save_game_user_settings.assert_called_once()


def test_backup_ini_files_creates_zip(tmp_path, monkeypatch):
    install = tmp_path / "TheIsland"
    ini_dir = install / "ShooterGame" / "Saved" / "Config" / "WindowsServer"
    ini_dir.mkdir(parents=True)
    (ini_dir / "GameUserSettings.ini").write_text("[x]", encoding="utf-8")
    (ini_dir / "Game.ini").write_text("[y]", encoding="utf-8")

    class _Cfg:
        install_dir = str(install)
        name = "TheIsland"

    monkeypatch.setattr(
        "src.buff_ini_backups.resolve_ini_backup_root",
        lambda: tmp_path / "BACKUP" / ".ini",
    )

    zip_path = backup_ini_files(_Cfg(), "TestBuff")
    assert zip_path is not None
    zp = Path(zip_path)
    assert zp.suffix == ".zip"
    with zipfile.ZipFile(zp, "r") as zf:
        assert "GameUserSettings.ini" in zf.namelist()
        assert "Game.ini" in zf.namelist()


def test_restore_ini_from_zip(tmp_path, monkeypatch):
    install = tmp_path / "Ragnarok"
    ini_dir = install / "ShooterGame" / "Saved" / "Config" / "WindowsServer"
    ini_dir.mkdir(parents=True)
    (ini_dir / "GameUserSettings.ini").write_text("old", encoding="utf-8")

    zip_path = tmp_path / "bkp.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("GameUserSettings.ini", "restored")
        zf.writestr("Game.ini", "game")

    class _Cfg:
        install_dir = str(install)

    assert restore_ini_from_backup(_Cfg(), str(zip_path))
    assert (ini_dir / "GameUserSettings.ini").read_text(encoding="utf-8") == "restored"


@patch("src.buff_manager.time.sleep")
def test_stop_active_event_marks_cancelled(mock_sleep):
    data_dir = Path(tempfile.mkdtemp())
    event = BuffEvent(
        id="evt-stop",
        name="Boost Teste",
        server_id="srv1",
        types=[BUFF_TYPE_BREEDING],
        rates=BuffRates(),
        sector_mults=BuffSectorMults(breeding=10.0),
        start_dt=(now_brasilia() - timedelta(hours=1)).isoformat(),
        end_dt=(now_brasilia() + timedelta(hours=1)).isoformat(),
        status=BUFF_STATUS_ACTIVE,
        backup_path=str(data_dir / "backup.zip"),
    )
    zip_path = data_dir / "backup.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("GameUserSettings.ini", "[x]")

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


def test_restore_ini_syncs_tek_profile_from_backup(tmp_path, monkeypatch):
    """Após restaurar INI, o perfil TEK deve refletir os rates do backup (não os do evento)."""
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.harvest_amount_multiplier = 25.0  # 5x efetivo (base × server_mult 5)
    write_ini(cfg)

    monkeypatch.setattr(
        "src.buff_ini_backups.resolve_ini_backup_root",
        lambda: tmp_path / "BACKUP" / ".ini",
    )
    backup_path = backup_ini_files(cfg, "FarmEvent")
    assert backup_path is not None

    event = BuffEvent(
        id="evt-farm",
        name="Farm Boost",
        server_id="tek1",
        types=[BUFF_TYPE_FARM],
        rates=BuffRates(),
        sector_mults=BuffSectorMults(farm=10.0),
        start_dt=now_brasilia().isoformat(),
        end_dt=(now_brasilia() + timedelta(hours=1)).isoformat(),
        status=BUFF_STATUS_SCHEDULED,
    )

    persisted: list[float] = []

    def _persist(_sid: str, srv: AsmServerConfig) -> None:
        persisted.append(srv.harvest_amount_multiplier)

    mgr = BuffManager(
        data_dir=Path(tempfile.mkdtemp()),
        get_server_config=lambda _sid: cfg,
        start_server=lambda _sid: None,
        stop_server=lambda _sid: None,
        get_server_status=lambda _sid: "stopped",
        persist_server_config=_persist,
    )

    assert mgr._apply_event_rates("tek1", event) is True
    assert cfg.harvest_amount_multiplier == 50.0
    assert persisted == [50.0]

    assert mgr._restore_ini("tek1", backup_path) is True
    assert cfg.harvest_amount_multiplier == 25.0
    assert persisted[-1] == 25.0


def test_restore_ini_sync_preserves_active_event(tmp_path, monkeypatch):
    """Buff restore + _sync_profile_from_ini mantém Easter no perfil e no GUS."""
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.harvest_amount_multiplier = 25.0
    cfg.active_event = ""
    write_ini(cfg)

    monkeypatch.setattr(
        "src.buff_ini_backups.resolve_ini_backup_root",
        lambda: tmp_path / "BACKUP" / ".ini",
    )
    backup_path = backup_ini_files(cfg, "FarmEvent")
    assert backup_path is not None

    cfg.active_event = "Easter"
    write_ini(cfg)

    persisted_events: list[str] = []

    def _persist(_sid: str, srv: AsmServerConfig) -> None:
        persisted_events.append(srv.active_event)

    mgr = BuffManager(
        data_dir=Path(tempfile.mkdtemp()),
        get_server_config=lambda _sid: cfg,
        start_server=lambda _sid: None,
        stop_server=lambda _sid: None,
        get_server_status=lambda _sid: "stopped",
        persist_server_config=_persist,
    )

    assert mgr._restore_ini("tek1", backup_path) is True
    assert cfg.active_event == "Easter"
    assert persisted_events == ["Easter"]

    gus = (
        tmp_path
        / "ShooterGame"
        / "Saved"
        / "Config"
        / "WindowsServer"
        / "GameUserSettings.ini"
    )
    assert "ActiveEvent=Easter" in gus.read_text(encoding="utf-16")


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
    assert err == "Só é possível encerrar eventos ativos."
