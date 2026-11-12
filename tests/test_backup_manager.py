"""Testes do gerenciador de backup de servidores."""
from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

from src.backup_manager import BackupManager, is_redundant_ark_save_file, resolve_save_source_dirs
from src.config_manager import BackupConfig
from src.asm_engine.asm_server_config import AsmServerConfig


@dataclass
class _Srv:
    install_dir: str
    alt_save_directory_name: str = "savegame"
    name: str = "Test"
    id: str = "t1"
    backup_include_saves: bool = True
    backup_include_config: bool = False
    backup_exclude_redundant: bool = True
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


def test_is_redundant_ark_save_file():
    assert is_redundant_ark_save_file("Ragnarok_AntiCorruptionBackup.bak")
    assert is_redundant_ark_save_file("Ragnarok_NewLaunchBackup.bak")
    assert is_redundant_ark_save_file("anything.bak")
    assert is_redundant_ark_save_file("TheVolcano_01.07.2026_12.00.00.ark")
    assert is_redundant_ark_save_file("Ragnarok_16.07.2026_05.30.15.ark")
    assert not is_redundant_ark_save_file("Ragnarok.ark")
    assert not is_redundant_ark_save_file("TheVolcano.ark")
    assert not is_redundant_ark_save_file("12345678901234567.arkprofile")
    assert not is_redundant_ark_save_file("1234567890.arktribe")
    assert not is_redundant_ark_save_file("1234567890.arktributetribe")


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


def test_do_backup_excludes_redundant_by_default(tmp_path: Path, monkeypatch):
    install = tmp_path / "server"
    savegame = install / "ShooterGame" / "Saved" / "savegame"
    savegame.mkdir(parents=True)
    (savegame / "Ragnarok.ark").write_bytes(b"active" * 1000)
    (savegame / "Ragnarok_16.07.2026_05.30.15.ark").write_bytes(b"dated" * 5000)
    (savegame / "Ragnarok_AntiCorruptionBackup.bak").write_bytes(b"anti" * 5000)
    (savegame / "Ragnarok_NewLaunchBackup.bak").write_bytes(b"launch" * 5000)
    (savegame / "12345678901234567.arkprofile").write_bytes(b"profile")
    (savegame / "9876543210.arktribe").write_bytes(b"tribe")

    logs: list[str] = []
    monkeypatch.setattr(
        "src.backup_manager.default_backups_servers_root",
        lambda: tmp_path / "backups",
    )

    srv = _Srv(install_dir=str(install), backup_exclude_redundant=True)
    bm = BackupManager(get_servers=lambda: [], on_log=lambda m, _lvl: logs.append(m))
    path = bm.do_backup(srv)  # type: ignore[arg-type]
    assert path is not None

    with zipfile.ZipFile(path, "r") as zf:
        names = {Path(n).name for n in zf.namelist() if not n.endswith("/")}
    assert names == {
        "Ragnarok.ark",
        "12345678901234567.arkprofile",
        "9876543210.arktribe",
    }
    assert any("omitidos 3 redundante" in m for m in logs)


def test_do_backup_includes_redundant_when_flag_off(tmp_path: Path, monkeypatch):
    install = tmp_path / "server"
    savegame = install / "ShooterGame" / "Saved" / "savegame"
    savegame.mkdir(parents=True)
    (savegame / "TheVolcano.ark").write_bytes(b"active")
    (savegame / "TheVolcano_01.07.2026_12.00.00.ark").write_bytes(b"dated")
    (savegame / "TheVolcano_AntiCorruptionBackup.bak").write_bytes(b"bak")

    monkeypatch.setattr(
        "src.backup_manager.default_backups_servers_root",
        lambda: tmp_path / "backups",
    )

    srv = _Srv(install_dir=str(install), backup_exclude_redundant=False)
    bm = BackupManager(get_servers=lambda: [])
    path = bm.do_backup(srv)  # type: ignore[arg-type]
    assert path is not None

    with zipfile.ZipFile(path, "r") as zf:
        names = {Path(n).name for n in zf.namelist() if not n.endswith("/")}
    assert names == {
        "TheVolcano.ark",
        "TheVolcano_01.07.2026_12.00.00.ark",
        "TheVolcano_AntiCorruptionBackup.bak",
    }


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


def test_tek_individual_backup_uses_profile_scope_and_retention(tmp_path: Path):
    install = tmp_path / "only-this-server"
    save_dir = install / "ShooterGame" / "Saved" / "savegame"
    save_dir.mkdir(parents=True)
    (save_dir / "TheIsland.ark").write_bytes(b"world")
    (save_dir / "TheIsland.bak").write_bytes(b"redundant")
    config_dir = install / "ShooterGame" / "Saved" / "Config" / "WindowsServer"
    config_dir.mkdir(parents=True)
    (config_dir / "Game.ini").write_text("[External]\nKeep=1\n", encoding="utf-8")

    srv = AsmServerConfig(
        id="tek-one", name="One", install_dir=str(install),
        alt_save_directory_name="savegame", backup_enabled=True,
        backup_keep_count=1, backup_include_saves=True,
        backup_include_config=False, backup_exclude_redundant=True,
        backup_dir=str(tmp_path / "individual-backups"),
    )
    target_dir = tmp_path / "individual-backups" / srv.id
    target_dir.mkdir(parents=True)
    (target_dir / "20000101_000000.zip").write_bytes(b"old")
    global_config = BackupConfig(
        backup_dir=str(tmp_path / "global-backups"),
        include_savegames=False, include_config=True,
        limit_backup_count=False,
    )
    manager = BackupManager(get_servers=lambda: [])

    result = manager.backup_server(srv, global_config)

    assert result is not None
    archive = Path(result)
    assert archive.parent == target_dir
    assert sorted(path.name for path in target_dir.glob("*.zip")) == [archive.name]
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        assert any(name.endswith("TheIsland.ark") for name in names)
        assert not any(name.endswith("TheIsland.bak") for name in names)
        assert not any(name.startswith("config/") for name in names)


def test_tek_global_backup_keeps_global_selection_and_targets_all_servers(tmp_path: Path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    for install in (first_dir, second_dir):
        save_dir = install / "ShooterGame" / "Saved" / "savegame"
        save_dir.mkdir(parents=True)
        (save_dir / "world.ark").write_bytes(b"world")
    manager = BackupManager(get_servers=lambda: [])
    global_config = BackupConfig(
        backup_dir=str(tmp_path / "global-backups"),
        include_savegames=True, include_config=False, limit_backup_count=False,
    )
    first = AsmServerConfig(
        id="global-a", install_dir=str(first_dir), backup_include_saves=False,
        backup_include_config=True,
    )
    second = AsmServerConfig(id="global-b", install_dir=str(second_dir))

    results = manager.backup_all_servers([first, second], global_config)

    assert len(results) == 2
    assert {Path(path).parent.name for path in results} == {"global-a", "global-b"}
    for result in results:
        with zipfile.ZipFile(result) as zf:
            assert any(name.endswith("world.ark") for name in zf.namelist())
            assert not any(name.startswith("config/") for name in zf.namelist())
