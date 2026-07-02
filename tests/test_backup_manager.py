"""Testes do gerenciador de backup de servidores."""
from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

from src.backup_manager import BackupManager, resolve_save_source_dirs


@dataclass
class _Srv:
    install_dir: str
    alt_save_directory_name: str = "savegame"
    name: str = "Test"
    id: str = "t1"
    backup_include_saves: bool = True
    backup_include_config: bool = False
    backup_keep_count: int = 5
    backup_dir: str = ""


def test_resolve_save_source_prefers_alt_directory(tmp_path: Path):
    install = tmp_path / "server"
    savegame = install / "ShooterGame" / "Saved" / "savegame"
    savegame.mkdir(parents=True)
    (savegame / "Genesis2.ark").write_bytes(b"x" * 1024)

    srv = _Srv(install_dir=str(install), alt_save_directory_name="savegame")
    dirs = resolve_save_source_dirs(srv)  # type: ignore[arg-type]
    assert savegame in dirs


def test_do_backup_includes_alt_save_files(tmp_path: Path, monkeypatch):
    install = tmp_path / "server"
    savegame = install / "ShooterGame" / "Saved" / "savegame"
    savegame.mkdir(parents=True)
    ark = savegame / "Genesis2.ark"
    ark.write_bytes(b"world-data" * 10000)

    cfg = install / "ShooterGame" / "Saved" / "Config" / "WindowsServer"
    cfg.mkdir(parents=True)
    (cfg / "Game.ini").write_text("[x]", encoding="utf-8")

    monkeypatch.setattr(
        "src.backup_manager.default_backups_servers_root",
        lambda: tmp_path / "backups",
    )

    srv = _Srv(install_dir=str(install))
    bm = BackupManager(get_servers=lambda: [])
    path = bm.do_backup(srv)  # type: ignore[arg-type]
    assert path is not None

    zp = Path(path)
    assert zp.is_file()
    with zipfile.ZipFile(zp, "r") as zf:
        names = zf.namelist()
        assert any(n.startswith("saves/savegame/Genesis2.ark") for n in names)
        assert not any(n.startswith("config/") for n in names)


def test_restore_alt_save_layout(tmp_path: Path, monkeypatch):
    install = tmp_path / "server"
    savegame = install / "ShooterGame" / "Saved" / "savegame"
    savegame.mkdir(parents=True)
    (savegame / "Genesis2.ark").write_bytes(b"old")

    monkeypatch.setattr(
        "src.backup_manager.default_backups_servers_root",
        lambda: tmp_path / "backups",
    )

    srv = _Srv(install_dir=str(install))
    bm = BackupManager(get_servers=lambda: [])
    path = bm.do_backup(srv)  # type: ignore[arg-type]
    assert path

    (savegame / "Genesis2.ark").write_bytes(b"corrupted")
    assert bm.restore_backup(srv, path)  # type: ignore[arg-type]
    assert (savegame / "Genesis2.ark").read_bytes() == b"old"
