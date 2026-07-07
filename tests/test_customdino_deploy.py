"""CustomDinoDeliver DLL deploy durante sync."""
from __future__ import annotations

import time
from pathlib import Path

from src.shop_integration import (
    bundled_customdino_files,
    deploy_customdino_dll_to_server,
    sync_customdino_at_path,
)


def test_deploy_customdino_dll_overwrites(tmp_path: Path) -> None:
    install_dir = tmp_path / "server"
    install_dir.mkdir()
    bundled = bundled_customdino_files()
    assert "CustomDinoDeliver.dll" in bundled

    ok1, notes1 = deploy_customdino_dll_to_server(str(install_dir), overwrite=True)
    assert not notes1
    assert any("CustomDinoDeliver.dll" in line for line in ok1)

    dest = (
        install_dir
        / "ShooterGame/Binaries/Win64/ArkApi/Plugins/CustomDinoDeliver/CustomDinoDeliver.dll"
    )
    assert dest.is_file()
    old_mtime = dest.stat().st_mtime
    time.sleep(0.05)

    ok2, notes2 = deploy_customdino_dll_to_server(str(install_dir), overwrite=True)
    assert not notes2
    assert dest.stat().st_mtime >= old_mtime


def test_sync_customdino_only_updates_config(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text('{"WebApiUrl": "http://old"}', encoding="utf-8")
    sync_customdino_at_path(cfg, "http://new", "key123")
    data = __import__("json").loads(cfg.read_text(encoding="utf-8"))
    assert data["WebApiUrl"] == "http://new"
    assert data["WebApiKey"] == "key123"
