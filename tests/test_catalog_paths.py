"""Testes para resolução de caminho persistente do catálogo CustomShop."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config_manager import ShopGlobalConfig
from src.shop_integration import (
    is_ephemeral_pyinstaller_path,
    resolve_persistent_catalog_path,
    sync_arkshop_web_settings,
    webstore_data_dir,
)


def test_is_ephemeral_pyinstaller_path_detects_mei():
    bad = r"C:\Users\ArkServerII\AppData\Local\Temp\_MEI31402\plugin\CustomShop\configs\config.json"
    assert is_ephemeral_pyinstaller_path(bad)
    assert not is_ephemeral_pyinstaller_path(
        r"C:\Program Files\ARKLAND-ServerManager\plugin\CustomShop\configs\config.json"
    )


def test_resolve_persistent_catalog_path_rejects_mei(tmp_path, monkeypatch):
    good = tmp_path / "catalog" / "config.json"
    good.parent.mkdir(parents=True)
    good.write_text("{}", encoding="utf-8")
    mei = r"C:\Temp\_MEI12345\plugin\CustomShop\configs\config.json"

    monkeypatch.setattr(
        "src.shop_integration.installed_catalog_candidates",
        lambda: [good],
    )
    resolved = resolve_persistent_catalog_path(mei)
    assert resolved == good


def test_load_settings_migrates_ephemeral_config_path(tmp_path, monkeypatch):
    import os
    import sys

    web_dir = Path(__file__).resolve().parent.parent / "plugin" / "arkshop_web"
    sys.path.insert(0, str(web_dir))
    os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")
    import app as app_module

    settings_file = tmp_path / "settings.json"
    bad = r"C:\Users\X\AppData\Local\Temp\_MEI99999\plugin\CustomShop\configs\config.json"
    good = tmp_path / "config.json"
    good.write_text("{}", encoding="utf-8")

    settings_file.write_text(json.dumps({"config_path": bad}), encoding="utf-8")
    monkeypatch.setattr(app_module, "_STATE_FILE", settings_file)
    monkeypatch.setattr(
        app_module,
        "resolve_persistent_catalog_path",
        lambda _p: good,
    )

    data = app_module._load_settings()
    assert data["config_path"] == str(good)
    saved = json.loads(settings_file.read_text(encoding="utf-8"))
    assert saved["config_path"] == str(good)


def test_sync_arkshop_web_settings_writes_canonical_path(tmp_path, monkeypatch):
    good = tmp_path / "plugin" / "CustomShop" / "configs" / "config.json"
    good.parent.mkdir(parents=True)
    good.write_text("{}", encoding="utf-8")
    mei = Path(r"C:\Temp\_MEI42\CustomShop\configs\config.json")

    monkeypatch.setattr("src.shop_integration.webstore_data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "src.shop_integration.installed_catalog_candidates",
        lambda: [good],
    )
    shop = ShopGlobalConfig(catalog_config_path=str(mei), port=27199)

    sync_arkshop_web_settings(shop, mei)

    settings = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert "_MEI" not in settings["config_path"]
    assert settings["config_path"] == str(good)
