"""Testes de deploy do plugin ArkPlayer."""
from __future__ import annotations

import json
from pathlib import Path

from src.plugin_versions import read_plugin_info_version
from src.shop_integration import (
    bundled_arkplayer_files,
    deploy_arkplayer_dll_to_server,
    install_arkplayer_to_server,
)


def test_bundled_arkplayer_dll_present() -> None:
    bundled = bundled_arkplayer_files()
    assert "ArkPlayer.dll" in bundled
    assert bundled["ArkPlayer.dll"].is_file()


def test_deploy_arkplayer_dll_overwrites(tmp_path: Path) -> None:
    install_dir = tmp_path / "server"
    install_dir.mkdir()

    ok1, notes1 = deploy_arkplayer_dll_to_server(str(install_dir), overwrite=True)
    assert not notes1 or all("PlayerUtilities" not in n for n in notes1)
    assert any("ArkPlayer.dll" in line for line in ok1)

    dest = (
        install_dir
        / "ShooterGame/Binaries/Win64/ArkApi/Plugins/ArkPlayer/ArkPlayer.dll"
    )
    assert dest.is_file()

    ok2, notes2 = deploy_arkplayer_dll_to_server(str(install_dir), overwrite=True)
    assert any("ArkPlayer.dll" in line for line in ok2)
    assert not notes2 or all("não copiada" not in n for n in notes2)


def test_install_arkplayer_copies_config_and_info(tmp_path: Path) -> None:
    install_dir = tmp_path / "server"
    install_dir.mkdir()

    ok, notes = install_arkplayer_to_server(str(install_dir), overwrite_dlls=True)
    assert any("ArkPlayer.dll" in line for line in ok)
    assert "PluginInfo.json" in ok
    assert "config.json (padrão)" in ok

    plugin = install_dir / "ShooterGame/Binaries/Win64/ArkApi/Plugins/ArkPlayer"
    assert (plugin / "ArkPlayer.dll").is_file()
    assert (plugin / "config.json").is_file()
    assert read_plugin_info_version(plugin / "PluginInfo.json") == "1.0.0"


def test_install_arkplayer_warns_on_playerutilities(tmp_path: Path) -> None:
    install_dir = tmp_path / "server"
    pu = (
        install_dir
        / "ShooterGame/Binaries/Win64/ArkApi/Plugins/PlayerUtilities"
    )
    pu.mkdir(parents=True)
    (pu / "PlayerUtilities.dll").write_bytes(b"legacy")

    ok, notes = install_arkplayer_to_server(str(install_dir), overwrite_dlls=True)
    assert any("ArkPlayer.dll" in line for line in ok)
    assert any("PlayerUtilities" in n for n in notes)


def test_deploy_arkplayer_copies_bundled_plugin_info(
    tmp_path: Path, monkeypatch
) -> None:
    install_dir = tmp_path / "server"
    install_dir.mkdir()
    bundle_info = tmp_path / "bundle" / "PluginInfo.json"
    bundle_info.parent.mkdir(parents=True)
    bundle_info.write_text(
        json.dumps({"Version": 1.0, "VersionLabel": "1.0.1"}),
        encoding="utf-8",
    )
    bundle_dll = tmp_path / "bundle" / "ArkPlayer.dll"
    bundle_dll.write_bytes(b"fake-dll")

    monkeypatch.setattr(
        "src.shop_integration.bundled_arkplayer_files",
        lambda: {"ArkPlayer.dll": bundle_dll},
    )
    monkeypatch.setattr(
        "src.shop_integration.bundled_plugin_info_path",
        lambda _name: bundle_info,
    )

    ok, notes = deploy_arkplayer_dll_to_server(str(install_dir), overwrite=True)
    assert not notes
    assert "PluginInfo.json" in ok

    dest_info = (
        install_dir
        / "ShooterGame/Binaries/Win64/ArkApi/Plugins/ArkPlayer/PluginInfo.json"
    )
    assert read_plugin_info_version(dest_info) == "1.0.1"
