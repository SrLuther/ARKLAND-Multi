"""Testes de versionamento de plugins ARKLAND."""
from __future__ import annotations

import json
from pathlib import Path

from src.plugin_versions import (
    OFFICIAL_PLUGIN_NAMES,
    compare_versions,
    expected_plugin_version,
    format_plugin_version,
    get_bundled_plugin_version,
    get_installed_plugin_version,
    plugin_version_status,
    read_plugin_info_version,
)
from src.version import APP_VERSION


def test_parse_and_compare_semver() -> None:
    assert compare_versions("1.10.6", "1.10.5") == 1
    assert compare_versions("1.10.6", "1.10.6") == 0
    assert compare_versions("1.9.207", "1.10.0") == -1
    assert compare_versions("1.0.3", "1.0.2") == 1
    assert compare_versions(1.0, "1.0.0") == 0


def test_plugin_version_status() -> None:
    assert plugin_version_status("1.0.3", "1.0.3", plugin_present=True) == "match"
    assert plugin_version_status("1.0.2", "1.0.3", plugin_present=True) == "outdated"
    assert plugin_version_status("1.0.4", "1.0.3", plugin_present=True) == "newer"
    assert plugin_version_status(None, "1.0.3", plugin_present=True) == "missing"
    assert plugin_version_status(None, "1.0.3", plugin_present=False) == "not_installed"


def test_read_plugin_info_version_prefers_version_label(tmp_path: Path) -> None:
    info = tmp_path / "PluginInfo.json"
    info.write_text(
        json.dumps({"Version": 1.0, "VersionLabel": "1.0.3"}),
        encoding="utf-8",
    )
    assert read_plugin_info_version(info) == "1.0.3"

    info.write_text(json.dumps({"Version": 1.0}), encoding="utf-8")
    assert read_plugin_info_version(info) == "1.0.0"

    info.write_text(json.dumps({"Version": "1.10.6"}), encoding="utf-8")
    assert read_plugin_info_version(info) == "1.10.6"
    assert format_plugin_version(1.0) == "1.0.0"


def test_bundled_plugin_versions_match_app_after_sync() -> None:
    for name in OFFICIAL_PLUGIN_NAMES:
        bundled = get_bundled_plugin_version(name)
        expected = expected_plugin_version(name)
        assert bundled == expected, f"{name}: bundle={bundled} expected={expected}"


def test_installed_plugin_version_from_server_tree(tmp_path: Path) -> None:
    plugin_dir = (
        tmp_path
        / "ShooterGame/Binaries/Win64/ArkApi/Plugins/CustomShop"
    )
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "CustomShop.dll").write_bytes(b"fake")
    (plugin_dir / "PluginInfo.json").write_text(
        json.dumps({"Version": 1.0, "VersionLabel": "1.0.2"}),
        encoding="utf-8",
    )
    assert get_installed_plugin_version(str(tmp_path), "CustomShop") == "1.0.2"


def test_deploy_customdino_copies_bundled_plugin_info(tmp_path: Path, monkeypatch) -> None:
    from src.shop_integration import deploy_customdino_dll_to_server

    install_dir = tmp_path / "server"
    install_dir.mkdir()
    bundle_info = tmp_path / "bundle" / "PluginInfo.json"
    bundle_info.parent.mkdir(parents=True)
    bundle_info.write_text(
        json.dumps({"Version": 1.0, "VersionLabel": "1.0.5"}),
        encoding="utf-8",
    )
    bundle_dll = tmp_path / "bundle" / "CustomDinoDeliver.dll"
    bundle_dll.write_bytes(b"fake-dll")

    monkeypatch.setattr(
        "src.shop_integration.bundled_customdino_files",
        lambda: {"CustomDinoDeliver.dll": bundle_dll},
    )
    monkeypatch.setattr(
        "src.shop_integration.bundled_plugin_info_path",
        lambda _name: bundle_info,
    )

    ok, notes = deploy_customdino_dll_to_server(str(install_dir), overwrite=True)
    assert not notes
    assert "PluginInfo.json" in ok

    dest_info = (
        install_dir
        / "ShooterGame/Binaries/Win64/ArkApi/Plugins/CustomDinoDeliver/PluginInfo.json"
    )
    assert read_plugin_info_version(dest_info) == "1.0.5"
