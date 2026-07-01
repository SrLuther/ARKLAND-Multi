"""Testes do gerenciador de saves nativos (savegame)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.asm_engine.asm_savegame_manager import (
    SaveFileKind,
    active_save_path,
    backup_timestamp,
    can_load_save,
    classify_save_files,
    create_manual_backup,
    delete_save_file,
    list_server_saves,
    load_save,
    map_save_basename,
    parse_dated_backup_filename,
    savegame_dir,
)
from src.asm_engine.asm_server_config import (
    ASM_STATUS_CRASHED,
    ASM_STATUS_RUNNING,
    ASM_STATUS_STOPPED,
    AsmServerConfig,
)


def _srv(**kwargs) -> AsmServerConfig:
    base = dict(
        id="srv-1",
        name="Test Server",
        install_dir="C:/ARK",
        server_map="Alps",
        alt_save_directory_name="savegame",
    )
    base.update(kwargs)
    return AsmServerConfig(**base)


def test_savegame_dir_default_and_custom():
    srv = _srv()
    assert savegame_dir(srv) == Path("C:/ARK/ShooterGame/Saved/savegame")
    srv2 = _srv(alt_save_directory_name="TheIsland")
    assert savegame_dir(srv2).name == "TheIsland"


def test_map_save_basename_vanilla_and_mod_path():
    assert map_save_basename(_srv(server_map="TheIsland")) == "TheIsland"
    mod = _srv(server_map="/Game/Mods/123456/Alps")
    assert map_save_basename(mod) == "Alps"


def test_parse_dated_backup_filename():
    dt = parse_dated_backup_filename("Alps_01.07.2026_01.39.14.ark")
    assert dt == datetime(2026, 7, 1, 1, 39, 14)
    assert parse_dated_backup_filename("Alps.ark") is None
    assert parse_dated_backup_filename("Alps_99.99.2026_01.39.14.ark") is None


def test_classify_save_files(tmp_path: Path):
    map_name = "Alps"
    (tmp_path / f"{map_name}.ark").write_bytes(b"x" * 100)
    (tmp_path / f"{map_name}_01.07.2026_01.39.14.ark").write_bytes(b"y" * 50)
    (tmp_path / f"{map_name}_AntiCorruptionBackup.bak").write_bytes(b"z")
    (tmp_path / f"{map_name}_NewLaunchBackup.bak").write_bytes(b"w")
    (tmp_path / "other.ark").write_bytes(b"o")

    entries = classify_save_files(tmp_path, map_name)
    kinds = {e.name: e.kind for e in entries}
    assert kinds[f"{map_name}.ark"] == SaveFileKind.ACTIVE
    assert kinds[f"{map_name}_01.07.2026_01.39.14.ark"] == SaveFileKind.DATED_BACKUP
    assert kinds[f"{map_name}_AntiCorruptionBackup.bak"] == SaveFileKind.ANTI_CORRUPTION
    assert kinds[f"{map_name}_NewLaunchBackup.bak"] == SaveFileKind.NEW_LAUNCH
    assert kinds["other.ark"] == SaveFileKind.OTHER

    dated = next(e for e in entries if e.kind == SaveFileKind.DATED_BACKUP)
    assert dated.parsed_date == datetime(2026, 7, 1, 1, 39, 14)


def test_list_server_saves_missing_dir(tmp_path: Path):
    srv = _srv(install_dir=str(tmp_path))
    inv = list_server_saves(srv)
    assert inv.dir_exists is False
    assert "não encontrada" in inv.error.lower()


def test_can_load_save_blocks_when_running():
    app = MagicMock()
    app.asm_server_manager.get_status.return_value = ASM_STATUS_RUNNING
    ok, msg = can_load_save(app, "srv-1")
    assert ok is False
    assert "desligado" in msg.lower()


def test_can_load_save_allows_stopped_and_crashed():
    app = MagicMock()
    for status in (ASM_STATUS_STOPPED, ASM_STATUS_CRASHED):
        app.asm_server_manager.get_status.return_value = status
        ok, msg = can_load_save(app, "srv-1")
        assert ok is True
        assert msg == ""


def test_load_save_creates_safety_backup_and_replaces_active(tmp_path: Path):
    install = tmp_path / "ARK"
    sg = install / "ShooterGame" / "Saved" / "savegame"
    sg.mkdir(parents=True)

    srv = _srv(install_dir=str(install), server_map="Alps")
    active = active_save_path(srv)
    active.write_bytes(b"active-old")

    backup = sg / "Alps_01.07.2026_12.00.00.ark"
    backup.write_bytes(b"restored-content")

    result = load_save(srv, backup)
    assert result == active
    assert active.read_bytes() == b"restored-content"

    safety = list(sg.glob("Alps_*.ark"))
    assert len(safety) == 2
    names = {p.name for p in safety}
    assert "Alps_01.07.2026_12.00.00.ark" in names
    assert any(n != "Alps_01.07.2026_12.00.00.ark" and n.endswith(".ark") for n in names)


def test_create_manual_backup(tmp_path: Path):
    install = tmp_path / "ARK"
    sg = install / "ShooterGame" / "Saved" / "savegame"
    sg.mkdir(parents=True)
    srv = _srv(install_dir=str(install), server_map="Alps")
    active = active_save_path(srv)
    active.write_bytes(b"world")

    when = datetime(2026, 7, 1, 2, 30, 45)
    dest = create_manual_backup(srv, when=when)
    assert dest.name == f"Alps_{backup_timestamp(when)}.ark"
    assert dest.read_bytes() == b"world"


def test_delete_save_file_blocks_active(tmp_path: Path):
    active = tmp_path / "Alps.ark"
    active.write_bytes(b"x")
    with pytest.raises(ValueError, match="save ativo"):
        delete_save_file(active)

    backup = tmp_path / "Alps_01.07.2026_01.39.14.ark"
    backup.write_bytes(b"y")
    delete_save_file(backup)
    assert not backup.exists()
