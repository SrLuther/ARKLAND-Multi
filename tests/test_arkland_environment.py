"""Testes do ambiente padronizado ARKLAND SERVER."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.arkland_environment import (
    DEFAULT_BACKUP_ROOT,
    EnvironmentPaths,
    apply_paths_to_config,
    create_environment,
    default_backups_servers_root,
    default_db_backup_dir,
    default_ini_backup_root,
    environment_root_from_parent,
    resolve_backup_root,
    sanitize_map_folder_name,
    suggest_map_install_dir,
    suggest_next_server_dir,
    validate_environment,
)
from src.config_manager import AppConfig, BackupConfig, DbBackupConfig, EnvironmentConfig


@pytest.fixture
def parent(tmp_path: Path) -> Path:
    return tmp_path / "drive"


@pytest.fixture(autouse=True)
def _isolated_backup_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Evita criar D:\\Backups reais durante os testes."""
    root = tmp_path / "Backups"
    monkeypatch.setenv("ARKLAND_BACKUP_ROOT", str(root))
    return root


def test_resolve_backup_root_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARKLAND_BACKUP_ROOT", raising=False)
    assert resolve_backup_root() == DEFAULT_BACKUP_ROOT
    assert default_backups_servers_root() == DEFAULT_BACKUP_ROOT / "servers"
    assert default_db_backup_dir() == DEFAULT_BACKUP_ROOT / "database"
    assert default_ini_backup_root() == DEFAULT_BACKUP_ROOT / ".ini"


def test_resolve_backup_root_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    custom = tmp_path / "CustomBackups"
    monkeypatch.setenv("ARKLAND_BACKUP_ROOT", str(custom))
    assert resolve_backup_root() == custom
    assert default_backups_servers_root() == custom / "servers"


def test_environment_root_from_parent(parent: Path) -> None:
    root = environment_root_from_parent(parent)
    assert root.name == "ARKLAND SERVER"
    assert root.parent == parent
    assert environment_root_from_parent(root) == root


def test_create_environment_creates_tree(parent: Path, _isolated_backup_root: Path) -> None:
    result = create_environment(parent, write_readmes=False)
    assert result.failed == []
    for d in result.paths.all_directories():
        assert d.is_dir()
    assert not validate_environment(result.paths.root)
    assert result.paths.backup == _isolated_backup_root
    assert (result.paths.backup / "servers").is_dir()
    assert (result.paths.backup / ".ini").is_dir()
    # Disco dedicado: backups não ficam sob ARKLAND SERVER/
    assert not (result.paths.root / "BACKUP").exists()


def test_create_environment_idempotent(parent: Path) -> None:
    first = create_environment(parent, write_readmes=False)
    second = create_environment(parent, write_readmes=False)
    assert second.failed == []
    assert len(second.created) == 0
    assert len(second.existing) >= len(first.paths.all_directories())


def test_validate_environment_detects_missing(parent: Path) -> None:
    parent.mkdir(parents=True)
    root = environment_root_from_parent(parent)
    root.mkdir()
    (root / "MAPAS").mkdir()
    missing = validate_environment(root)
    assert any("CLUSTER" in m for m in missing)


def test_apply_paths_to_config(parent: Path) -> None:
    result = create_environment(parent, write_readmes=False)
    cfg = AppConfig(environment=EnvironmentConfig())
    apply_paths_to_config(cfg, result.paths)
    assert cfg.environment.enabled is True
    assert cfg.default_install_dir == str(result.paths.maps)
    assert cfg.steamcmd_path == str(result.paths.steamcmd_exe)
    assert cfg.backup.backup_dir == str(result.paths.backup_servers)
    assert cfg.db_backup.backup_dir == str(result.paths.backup_database)
    assert cfg.auto_update.cache_dir == str(result.paths.cache_updates)


def test_apply_paths_preserves_custom_backup_dirs(parent: Path) -> None:
    result = create_environment(parent, write_readmes=False)
    cfg = AppConfig(
        environment=EnvironmentConfig(),
        backup=BackupConfig(backup_dir=r"E:\MeusBackups\servers"),
        db_backup=DbBackupConfig(backup_dir=r"E:\MeusBackups\db"),
    )
    apply_paths_to_config(cfg, result.paths)
    assert cfg.backup.backup_dir == r"E:\MeusBackups\servers"
    assert cfg.db_backup.backup_dir == r"E:\MeusBackups\db"


def test_suggest_map_install_dir(parent: Path) -> None:
    paths = EnvironmentPaths(root=environment_root_from_parent(parent))
    p = suggest_map_install_dir(paths, "The_Volcano")
    assert p.endswith("The Volcano") or "Volcano" in p
    assert sanitize_map_folder_name('bad<>:"/\\|?*name') == "badname"


def test_suggest_next_server_dir(parent: Path) -> None:
    paths = EnvironmentPaths(root=environment_root_from_parent(parent))
    paths.maps.mkdir(parents=True)
    first = suggest_next_server_dir(paths, existing_count=0)
    assert "Servidor 01" in first
    Path(first).mkdir()
    second = suggest_next_server_dir(paths, existing_count=1, occupied_paths=[first])
    assert second != first
    assert "Servidor 02" in second

    assert EnvironmentPaths(root=environment_root_from_parent(parent)).preview_tree()
