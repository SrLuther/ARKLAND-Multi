"""Testes para resolução de caminho persistente do catálogo CustomShop."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config_manager import ShopGlobalConfig
from src.shop_integration import (
    ensure_webstore_catalog_config,
    is_ephemeral_pyinstaller_path,
    merge_catalog_content_from_source,
    reconcile_catalog_before_sync,
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
        "src.arkland_environment.try_load_environment_paths",
        lambda: None,
    )
    monkeypatch.setattr(
        "src.shop_integration.installed_catalog_candidates",
        lambda: [good],
    )
    shop = ShopGlobalConfig(catalog_config_path=str(mei), port=27199)

    sync_arkshop_web_settings(shop, mei)

    settings = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert "_MEI" not in settings["config_path"]
    assert settings["config_path"] == str(good)


def test_webstore_data_dir_prefers_arkshop_data_dir(tmp_path, monkeypatch):
    env_dir = tmp_path / "custom_webstore"
    env_dir.mkdir()
    monkeypatch.setenv("ARKSHOP_DATA_DIR", str(env_dir))

    assert webstore_data_dir() == env_dir


def test_webstore_data_dir_uses_environment_webstore(tmp_path, monkeypatch):
    webstore = tmp_path / "ARKLAND SERVER" / "WEBSTORE"
    webstore.mkdir(parents=True)
    monkeypatch.delenv("ARKSHOP_DATA_DIR", raising=False)
    monkeypatch.setattr(
        "src.arkland_environment.try_load_environment_paths",
        lambda: type("P", (), {"webstore": webstore})(),
    )
    monkeypatch.setattr(
        "src.arkland_environment.default_webstore_dir",
        lambda: webstore,
    )

    assert webstore_data_dir() == webstore


def test_ensure_webstore_catalog_config_copies_when_missing(tmp_path, monkeypatch):
    webstore = tmp_path / "WEBSTORE"
    webstore.mkdir()
    master = tmp_path / "master" / "config.json"
    master.parent.mkdir()
    master.write_text('{"Kits":{}}', encoding="utf-8")

    monkeypatch.setattr(
        "src.arkland_environment.try_load_environment_paths",
        lambda: type("P", (), {"webstore": webstore})(),
    )
    monkeypatch.setattr("src.shop_integration.webstore_data_dir", lambda: webstore)

    dest = ensure_webstore_catalog_config(master)
    assert dest == webstore / "config.json"
    assert (webstore / "config.json").is_file()
    assert json.loads((webstore / "config.json").read_text(encoding="utf-8")) == {"Kits": {}}


def test_sync_arkshop_web_settings_creates_webstore_config(tmp_path, monkeypatch):
    webstore = tmp_path / "WEBSTORE"
    webstore.mkdir()
    master = tmp_path / "master" / "config.json"
    master.parent.mkdir()
    master.write_text('{"ShopItems":{}}', encoding="utf-8")

    monkeypatch.setattr("src.shop_integration.webstore_data_dir", lambda: webstore)
    monkeypatch.setattr(
        "src.arkland_environment.try_load_environment_paths",
        lambda: type("P", (), {"webstore": webstore})(),
    )
    monkeypatch.setattr(
        "src.shop_integration.installed_catalog_candidates",
        lambda: [master],
    )

    shop = ShopGlobalConfig(catalog_config_path=str(master), port=27200)
    sync_arkshop_web_settings(shop, master)

    settings = json.loads((webstore / "settings.json").read_text(encoding="utf-8"))
    assert settings["config_path"] == str(webstore / "config.json")
    assert (webstore / "config.json").is_file()


def test_resolve_skips_truncated_webstore_stub(tmp_path, monkeypatch):
    """v1.9.128 priorizava WEBSTORE/config.json — não deve vencer mapa completo."""
    webstore = tmp_path / "WEBSTORE"
    webstore.mkdir()
    stub = webstore / "config.json"
    stub.write_text(
        json.dumps({"Items": {f"lic_{i}": {"Price": 1} for i in range(4)}, "Kits": {}}),
        encoding="utf-8",
    )
    maps = tmp_path / "MAPAS" / "Ragnarok" / "ShooterGame" / "Binaries" / "Win64" / "ArkApi" / "Plugins" / "CustomShop"
    maps.mkdir(parents=True)
    full = maps / "config.json"
    full.write_text(
        json.dumps({
            "Items": {f"item_{i}": {"Price": i} for i in range(120)},
            "Kits": {f"kit_{i}": {"Price": i} for i in range(30)},
        }),
        encoding="utf-8",
    )

    env = type("P", (), {"webstore": webstore, "maps": tmp_path / "MAPAS"})()
    monkeypatch.setattr("src.arkland_environment.try_load_environment_paths", lambda: env)
    monkeypatch.setattr("src.shop_integration.webstore_data_dir", lambda: webstore)
    monkeypatch.setattr("src.shop_integration.installed_catalog_candidates", lambda: [stub])

    resolved = resolve_persistent_catalog_path(str(stub))
    assert resolved == full


def test_ensure_webstore_refreshes_when_master_larger(tmp_path, monkeypatch):
    webstore = tmp_path / "WEBSTORE"
    webstore.mkdir()
    stub = webstore / "config.json"
    stub.write_text('{"Items":{"a":{}},"Kits":{}}', encoding="utf-8")
    master = tmp_path / "master" / "config.json"
    master.parent.mkdir()
    master.write_text(
        json.dumps({"Items": {f"x{i}": {} for i in range(50)}, "Kits": {"k1": {}}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "src.arkland_environment.try_load_environment_paths",
        lambda: type("P", (), {"webstore": webstore})(),
    )
    monkeypatch.setattr("src.shop_integration.webstore_data_dir", lambda: webstore)

    dest = ensure_webstore_catalog_config(master)
    assert dest == stub
    data = json.loads(stub.read_text(encoding="utf-8"))
    assert len(data.get("Items") or {}) == 50


def test_app_data_dir_delegates_to_webstore_data_dir(tmp_path, monkeypatch):
    import os
    import sys

    webstore = tmp_path / "WEBSTORE"
    webstore.mkdir()
    monkeypatch.setattr("src.shop_integration.webstore_data_dir", lambda: webstore)

    web_dir = Path(__file__).resolve().parent.parent / "plugin" / "arkshop_web"
    sys.path.insert(0, str(web_dir))
    os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")
    import app as app_module

    monkeypatch.setattr(app_module, "webstore_data_dir", lambda: webstore)
    assert app_module._data_dir() == webstore


def test_reconcile_catalog_prefers_newer_webstore(tmp_path, monkeypatch):
    webstore = tmp_path / "WEBSTORE"
    webstore.mkdir()
    master = tmp_path / "master" / "config.json"
    master.parent.mkdir()
    master.write_text(
        json.dumps({"Items": {"old": {"Price": 1}}, "Kits": {}}),
        encoding="utf-8",
    )
    ws_cfg = webstore / "config.json"
    ws_cfg.write_text(
        json.dumps({"Items": {"new_from_web": {"Price": 99}}, "Kits": {"k1": {}}}),
        encoding="utf-8",
    )
    import os
    import time

    time.sleep(0.05)
    os.utime(ws_cfg, None)

    stale_memory = {"Items": {"old": {"Price": 1}}, "Kits": {}}
    monkeypatch.setattr("src.shop_integration._webstore_catalog_file", lambda: ws_cfg)

    path, merged = reconcile_catalog_before_sync(master, stale_memory)
    assert path == master
    assert "new_from_web" in (merged.get("Items") or {})
    assert "k1" in (merged.get("Kits") or {})


def test_ensure_webstore_skips_when_webstore_newer(tmp_path, monkeypatch):
    webstore = tmp_path / "WEBSTORE"
    webstore.mkdir()
    master = tmp_path / "master" / "config.json"
    master.parent.mkdir()
    master.write_text(
        json.dumps({"Items": {f"x{i}": {} for i in range(50)}, "Kits": {}}),
        encoding="utf-8",
    )
    dest = webstore / "config.json"
    dest.write_text('{"Items":{"web_edit":{}},"Kits":{}}', encoding="utf-8")
    import os
    import time

    time.sleep(0.05)
    os.utime(dest, None)

    monkeypatch.setattr(
        "src.arkland_environment.try_load_environment_paths",
        lambda: type("P", (), {"webstore": webstore})(),
    )
    monkeypatch.setattr("src.shop_integration.webstore_data_dir", lambda: webstore)

    result = ensure_webstore_catalog_config(master)
    assert result == dest
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert "web_edit" in (data.get("Items") or {})


def test_reconcile_catalog_merges_timed_points_without_item_change(tmp_path, monkeypatch):
    webstore = tmp_path / "WEBSTORE"
    webstore.mkdir()
    master = tmp_path / "master" / "config.json"
    master.parent.mkdir()
    master.write_text(
        json.dumps({
            "Items": {"item1": {"Price": 1}},
            "Kits": {},
            "TimedPointsReward": {
                "Enabled": False,
                "Groups": {"Alfa": {"Amount": 75}, "Default": {"Amount": 25}},
            },
        }),
        encoding="utf-8",
    )
    ws_cfg = webstore / "config.json"
    ws_cfg.write_text(
        json.dumps({
            "Items": {"item1": {"Price": 1}},
            "Kits": {},
            "TimedPointsReward": {
                "Enabled": True,
                "Groups": {
                    "Default": {"Amount": 25},
                    "VIPBronze": {"Amount": 20},
                    "VIPDiamante": {"Amount": 75},
                },
            },
        }),
        encoding="utf-8",
    )
    import os
    import time

    time.sleep(0.05)
    os.utime(ws_cfg, None)

    stale_memory = json.loads(master.read_text(encoding="utf-8"))
    monkeypatch.setattr("src.shop_integration._webstore_catalog_file", lambda: ws_cfg)

    path, merged = reconcile_catalog_before_sync(master, stale_memory)
    tp = merged.get("TimedPointsReward") or {}
    assert tp.get("Enabled") is True
    assert "VIPBronze" in (tp.get("Groups") or {})
    assert "Alfa" not in (tp.get("Groups") or {})


def test_push_catalog_to_webstore_overwrites(tmp_path, monkeypatch):
    webstore = tmp_path / "WEBSTORE"
    webstore.mkdir()
    master = tmp_path / "master.json"
    master.write_text(
        json.dumps({"TimedPointsReward": {"Enabled": True, "Groups": {"VIP": {"Amount": 50}}}}),
        encoding="utf-8",
    )
    dest = webstore / "config.json"
    dest.write_text('{"TimedPointsReward":{"Enabled":false}}', encoding="utf-8")

    monkeypatch.setattr("src.shop_integration.webstore_data_dir", lambda: webstore)
    monkeypatch.setattr(
        "src.arkland_environment.try_load_environment_paths",
        lambda: type("P", (), {"webstore": webstore})(),
    )
    from src.shop_integration import push_catalog_to_webstore

    result = push_catalog_to_webstore(master)
    assert result == dest
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert data["TimedPointsReward"]["Enabled"] is True


def test_merge_catalog_content_preserves_urls_in_base():
    base = {
        "Items": {"a": {}},
        "Settings": {"WebsiteUrl": "https://arkland.com.br", "ShopName": "Old"},
    }
    source = {
        "Items": {"b": {}},
        "Settings": {"WebsiteUrl": "http://bad", "ShopName": "New"},
    }
    merged = merge_catalog_content_from_source(base, source)
    assert "b" in merged["Items"]
    assert merged["Settings"]["WebsiteUrl"] == "https://arkland.com.br"
    assert merged["Settings"]["ShopName"] == "New"
