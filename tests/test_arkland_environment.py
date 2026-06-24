"""Testes do ambiente padronizado ARKLAND SERVER."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.arkland_environment import (
    EnvironmentPaths,
    apply_paths_to_config,
    create_environment,
    environment_root_from_parent,
    sanitize_map_folder_name,
    suggest_map_install_dir,
    suggest_next_server_dir,
    validate_environment,
)
from src.config_manager import AppConfig, EnvironmentConfig


@pytest.fixture
def parent(tmp_path: Path) -> Path:
    return tmp_path / "drive"


def test_environment_root_from_parent(parent: Path) -> None:
    root = environment_root_from_parent(parent)
    assert root.name == "ARKLAND SERVER"
    assert root.parent == parent
    assert environment_root_from_parent(root) == root


def test_create_environment_creates_tree(parent: Path) -> None:
    result = create_environment(parent, write_readmes=False)
    assert result.failed == []
    for d in result.paths.all_directories():
        assert d.is_dir()
    assert not validate_environment(result.paths.root)


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
