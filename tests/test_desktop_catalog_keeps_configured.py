"""O catálogo configurado no app desktop sobrevive ao boot e ao sync.

Regressão: ``resolve_persistent_catalog_path`` tratava um catálogo reajustado
(menos itens) como truncado, copiava a versão antiga mais cheia por cima e
fazia o sync gravar outro path em settings.json.
"""
from __future__ import annotations

import json

from src.config_manager import ConfigManager, ShopGlobalConfig
from src.shop_integration import (
    build_webstore_launch,
    get_shop_subprocess_env,
    migrate_stale_plugin_website_urls,
    resolve_persistent_catalog_path,
    sync_all_plugins,
    sync_arkshop_web_settings,
)


def test_sync_and_boot_keep_smaller_configured_catalog(tmp_path, monkeypatch):
    live = tmp_path / "CustomShop" / "catalog.json"
    old = tmp_path / "old" / "config.json"
    live.parent.mkdir()
    old.parent.mkdir()
    fresh = {"Items": {"fresh_item": {"Price": 7, "Name": "FRESH"}}, "Kits": {}}
    stale = {"Items": {f"old_{i}": {"Price": 1} for i in range(80)}, "Kits": {}}
    live.write_text(json.dumps(fresh), encoding="utf-8")
    old.write_text(json.dumps(stale), encoding="utf-8")

    appdata = tmp_path / "appdata"
    cfg_dir = appdata / "ARKLAND-ServerManager"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.json").write_text(
        json.dumps({
            "remote_agent_token": "tok-teste",
            "shop": {"catalog_config_path": str(live)},
        }),
        encoding="utf-8",
    )
    webstore = tmp_path / "WEBSTORE"
    webstore.mkdir()
    (webstore / "settings.json").write_text(
        json.dumps({"config_path": str(live)}),
        encoding="utf-8",
    )

    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setattr("src.arkland_environment.try_load_environment_paths", lambda: None)
    monkeypatch.setattr("src.shop_integration.webstore_data_dir", lambda: webstore)
    monkeypatch.setattr("src.shop_integration.canonical_master_catalog_path", lambda: live)
    monkeypatch.setattr(
        "src.shop_integration._collect_catalog_search_paths",
        lambda: [live, old],
    )
    monkeypatch.setattr(
        "src.shop_integration.installed_catalog_candidates",
        lambda: [live, old],
    )

    cm = ConfigManager()
    shop = cm.config.shop
    assert shop.catalog_config_path == str(live)

    resolved = resolve_persistent_catalog_path(shop.catalog_config_path, shop=shop)
    assert resolved.resolve() == live.resolve()

    migrate_stale_plugin_website_urls(cm, shop)
    sync_all_plugins(cm, shop, fresh, live)
    sync_arkshop_web_settings(shop, live)
    get_shop_subprocess_env(shop)
    build_webstore_launch(shop)

    disk = json.loads(live.read_text(encoding="utf-8"))
    assert set(disk.get("Items") or {}) == {"fresh_item"}
    assert disk["Items"]["fresh_item"]["Price"] == 7
    assert "old_0" not in (disk.get("Items") or {})

    saved_settings = json.loads((webstore / "settings.json").read_text(encoding="utf-8"))
    assert saved_settings["config_path"] == str(live)

    saved_app = json.loads((cfg_dir / "config.json").read_text(encoding="utf-8"))
    assert saved_app["shop"]["catalog_config_path"] == str(live)
    assert cm.config.shop.catalog_config_path == str(live)

    untouched = json.loads(old.read_text(encoding="utf-8"))
    assert "old_0" in (untouched.get("Items") or {})
    assert "fresh_item" not in (untouched.get("Items") or {})

    env = get_shop_subprocess_env(shop)
    assert env["ARKSHOP_CONFIG_PATH"] == str(live)


def test_configured_path_is_not_swapped_for_canonical(tmp_path, monkeypatch):
    """Catálogo salvo fora do canônico não é promovido nem substituído no sync."""
    live = tmp_path / "salvo" / "catalog.json"
    canonical = tmp_path / "CustomShop" / "catalog.json"
    old = tmp_path / "mapa" / "config.json"
    live.parent.mkdir()
    canonical.parent.mkdir()
    old.parent.mkdir()
    fresh = {"Items": {"fresh_item": {"Price": 3, "Name": "NOVO"}}, "Kits": {}}
    stale = {"Items": {f"old_{i}": {"Price": 1} for i in range(80)}, "Kits": {}}
    live.write_text(json.dumps(fresh), encoding="utf-8")
    canonical.write_text(json.dumps(stale), encoding="utf-8")
    old.write_text(json.dumps(stale), encoding="utf-8")

    webstore = tmp_path / "WEBSTORE"
    webstore.mkdir()
    (webstore / "settings.json").write_text(
        json.dumps({"config_path": str(live), "mp_access_token": "mantem"}),
        encoding="utf-8",
    )

    monkeypatch.setattr("src.arkland_environment.try_load_environment_paths", lambda: None)
    monkeypatch.setattr("src.shop_integration.webstore_data_dir", lambda: webstore)
    monkeypatch.setattr("src.shop_integration.canonical_master_catalog_path", lambda: canonical)
    monkeypatch.setattr(
        "src.shop_integration._collect_catalog_search_paths",
        lambda: [live, canonical, old],
    )

    shop = ShopGlobalConfig(catalog_config_path=str(live), port=27199)
    resolved = resolve_persistent_catalog_path(live, shop=shop)
    assert resolved.resolve() == live.resolve()

    sync_arkshop_web_settings(shop, live)

    disk = json.loads(live.read_text(encoding="utf-8"))
    assert set(disk.get("Items") or {}) == {"fresh_item"}
    canon_disk = json.loads(canonical.read_text(encoding="utf-8"))
    assert "old_0" in (canon_disk.get("Items") or {})
    assert "fresh_item" not in (canon_disk.get("Items") or {})

    saved = json.loads((webstore / "settings.json").read_text(encoding="utf-8"))
    assert saved["config_path"] == str(live)
    assert saved["mp_access_token"] == "mantem"
    assert shop.catalog_config_path == str(live)
