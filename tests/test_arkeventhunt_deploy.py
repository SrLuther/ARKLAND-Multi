"""Testes de deploy do plugin ArkEventHunt."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from src.plugin_versions import read_plugin_info_version
from src.shop_integration import (
    bundled_arkeventhunt_files,
    deploy_arkeventhunt_dll_to_server,
    install_arkeventhunt_to_server,
)


def test_bundled_arkeventhunt_dll_present() -> None:
    bundled = bundled_arkeventhunt_files()
    assert "ArkEventHunt.dll" in bundled
    assert bundled["ArkEventHunt.dll"].is_file()


def test_deploy_arkeventhunt_dll_overwrites(tmp_path: Path) -> None:
    install_dir = tmp_path / "server"
    install_dir.mkdir()

    ok1, notes1 = deploy_arkeventhunt_dll_to_server(str(install_dir), overwrite=True)
    assert not notes1 or all("não copiada" not in n for n in notes1)
    assert any("ArkEventHunt.dll" in line for line in ok1)

    dest = (
        install_dir
        / "ShooterGame/Binaries/Win64/ArkApi/Plugins/ArkEventHunt/ArkEventHunt.dll"
    )
    assert dest.is_file()

    ok2, notes2 = deploy_arkeventhunt_dll_to_server(str(install_dir), overwrite=True)
    assert any("ArkEventHunt.dll" in line for line in ok2)
    assert not notes2 or all("não copiada" not in n for n in notes2)


def test_install_arkeventhunt_copies_config_and_info(tmp_path: Path) -> None:
    install_dir = tmp_path / "server"
    install_dir.mkdir()

    ok, notes = install_arkeventhunt_to_server(str(install_dir), overwrite_dlls=True)
    assert any("ArkEventHunt.dll" in line for line in ok)
    assert "PluginInfo.json" in ok
    assert "config.json (padrão)" in ok

    plugin = install_dir / "ShooterGame/Binaries/Win64/ArkApi/Plugins/ArkEventHunt"
    assert (plugin / "ArkEventHunt.dll").is_file()
    assert (plugin / "config.json").is_file()
    assert read_plugin_info_version(plugin / "PluginInfo.json") == "0.5.2"
    data = json.loads((plugin / "config.json").read_text(encoding="utf-8"))
    assert "ArkEventHunt" in data


def test_sync_arkeventhunt_writes_web_api(tmp_path: Path) -> None:
    from src.shop_integration import sync_arkeventhunt_at_path

    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps({"ArkEventHunt": {"Enabled": True, "WebApiUrl": "http://old"}}),
        encoding="utf-8",
    )
    sync_arkeventhunt_at_path(cfg, "http://192.168.1.10:5177", "secret-key")
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["ArkEventHunt"]["WebApiUrl"] == "http://192.168.1.10:5177"
    assert data["ArkEventHunt"]["WebApiKey"] == "secret-key"
    assert data["ArkEventHunt"]["Enabled"] is True

    install_dir = tmp_path / "server"
    install_dir.mkdir()
    plugin = install_dir / "ShooterGame/Binaries/Win64/ArkApi/Plugins/ArkEventHunt"
    plugin.mkdir(parents=True)
    custom = {"ArkEventHunt": {"SenderNameInChat": "CUSTOM_KEEP"}}
    (plugin / "config.json").write_text(
        json.dumps(custom), encoding="utf-8",
    )

    ok, notes = install_arkeventhunt_to_server(str(install_dir), overwrite_dlls=True)
    assert "config.json (já presente)" in ok
    assert "config.json (padrão)" not in ok
    kept = json.loads((plugin / "config.json").read_text(encoding="utf-8"))
    assert kept["ArkEventHunt"]["SenderNameInChat"] == "CUSTOM_KEEP"


def test_default_arkeventhunt_config_template_from_bundle(
    tmp_path: Path, monkeypatch
) -> None:
    from src.shop_integration import _default_arkeventhunt_config_template

    bundled = tmp_path / "meipass" / "plugins" / "arkeventhunt" / "config.json"
    bundled.parent.mkdir(parents=True)
    bundled.write_text('{"ArkEventHunt":{}}', encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "meipass"), raising=False)

    assert _default_arkeventhunt_config_template() == bundled


def test_deploy_arkeventhunt_copies_bundled_plugin_info(
    tmp_path: Path, monkeypatch
) -> None:
    install_dir = tmp_path / "server"
    install_dir.mkdir()
    bundle_info = tmp_path / "bundle" / "PluginInfo.json"
    bundle_info.parent.mkdir(parents=True)
    bundle_info.write_text(
        json.dumps({"Version": 0.1, "VersionLabel": "0.1.1"}),
        encoding="utf-8",
    )
    bundle_dll = tmp_path / "bundle" / "ArkEventHunt.dll"
    bundle_dll.write_bytes(b"fake-dll")

    monkeypatch.setattr(
        "src.shop_integration.bundled_arkeventhunt_files",
        lambda: {"ArkEventHunt.dll": bundle_dll},
    )
    monkeypatch.setattr(
        "src.shop_integration.bundled_plugin_info_path",
        lambda _name: bundle_info,
    )

    ok, notes = deploy_arkeventhunt_dll_to_server(str(install_dir), overwrite=True)
    assert not notes
    assert "PluginInfo.json" in ok

    dest_info = (
        install_dir
        / "ShooterGame/Binaries/Win64/ArkApi/Plugins/ArkEventHunt/PluginInfo.json"
    )
    assert read_plugin_info_version(dest_info) == "0.1.1"
