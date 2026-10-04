"""Testes de deploy do plugin EngramLevel."""
from __future__ import annotations

import json
from pathlib import Path

from src.plugin_versions import read_plugin_info_version, read_plugin_version_file
from src.shop_integration import (
    bundled_engramlevel_files,
    install_engramlevel_to_server,
)


def test_bundled_engramlevel_dll_present() -> None:
    bundled = bundled_engramlevel_files()
    assert "EngramLevel.dll" in bundled
    assert bundled["EngramLevel.dll"].is_file()


def test_install_engramlevel_copies_config_and_info(tmp_path: Path) -> None:
    install_dir = tmp_path / "server"
    install_dir.mkdir()

    ok, notes = install_engramlevel_to_server(str(install_dir), overwrite_dlls=True)
    assert not notes or all("não copiada" not in n for n in notes)
    assert any("EngramLevel.dll" in line for line in ok)
    assert "PluginInfo.json" in ok
    assert "config.json (padrão)" in ok

    plugin = install_dir / "ShooterGame/Binaries/Win64/ArkApi/Plugins/EngramLevel"
    assert (plugin / "EngramLevel.dll").is_file()
    assert (plugin / "config.json").is_file()
    assert read_plugin_info_version(plugin / "PluginInfo.json") == read_plugin_version_file(
        "EngramLevel"
    )
    data = json.loads((plugin / "config.json").read_text(encoding="utf-8"))
    assert data["EngramLevel"]["UnlockTotal"] is False


def test_install_engramlevel_does_not_overwrite_existing_config(tmp_path: Path) -> None:
    install_dir = tmp_path / "server"
    install_dir.mkdir()
    plugin = install_dir / "ShooterGame/Binaries/Win64/ArkApi/Plugins/EngramLevel"
    plugin.mkdir(parents=True)
    custom = {"EngramLevel": {"UnlockTotal": True, "SenderNameInChat": "CUSTOM_KEEP"}}
    (plugin / "config.json").write_text(json.dumps(custom), encoding="utf-8")

    ok, _notes = install_engramlevel_to_server(str(install_dir), overwrite_dlls=True)
    assert "config.json (já presente)" in ok
    assert "config.json (padrão)" not in ok
    kept = json.loads((plugin / "config.json").read_text(encoding="utf-8"))
    assert kept["EngramLevel"]["SenderNameInChat"] == "CUSTOM_KEEP"
    assert kept["EngramLevel"]["UnlockTotal"] is True
