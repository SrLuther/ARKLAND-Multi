"""O catalog.json configurado continua a ser o que a Web Store serve depois do save.

Regressão: ``resolve_persistent_catalog_path`` tratava um catálogo reajustado
(menos itens) como truncado e copiava uma cópia mais rica — e antiga — por cima.
"""
from __future__ import annotations

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")
os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")

import app as app_module
import src.shop_integration as shop_integration


def _isolate(monkeypatch, tmp_path, live, old):
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps({"config_path": str(live)}),
        encoding="utf-8",
    )
    servers = tmp_path / "servers.json"
    servers.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(app_module, "_STATE_FILE", settings)
    monkeypatch.setattr(app_module, "_SERVERS_FILE", servers)
    monkeypatch.setattr(shop_integration, "canonical_master_catalog_path", lambda: live)
    monkeypatch.setattr(
        shop_integration, "migrate_catalog_to_canonical", lambda force=False: live
    )
    monkeypatch.setattr(shop_integration, "push_catalog_to_webstore", lambda source: None)
    monkeypatch.setattr(
        shop_integration, "_collect_catalog_search_paths", lambda: [live, old]
    )
    monkeypatch.setattr(app_module, "_collect_catalog_search_paths", lambda: [live, old])
    app_module._invalidate_shop_config_cache()
    app_module._invalidate_public_catalog_cache()
    return settings


def test_configured_catalog_is_not_replaced_by_richer_copy(tmp_path, monkeypatch):
    live = tmp_path / "catalog.json"
    old = tmp_path / "old" / "catalog.json"
    old.parent.mkdir()
    fresh = {"Items": {"fresh_item": {"Price": 7, "Name": "FRESH"}}, "Kits": {}}
    stale = {"Items": {f"old_{i}": {"Price": 1} for i in range(80)}, "Kits": {}}
    live.write_text(json.dumps(fresh), encoding="utf-8")
    old.write_text(json.dumps(stale), encoding="utf-8")
    settings = _isolate(monkeypatch, tmp_path, live, old)

    resolved, data, _note = app_module._resolve_shop_catalog()
    assert resolved.resolve() == live.resolve()
    assert "fresh_item" in (data.get("Items") or {})
    assert "old_0" not in (data.get("Items") or {})

    loaded = app_module._load_settings()
    assert loaded["config_path"] == str(live)

    # Segunda leitura / reload: o caminho antigo reexecutava o resolve e copiava.
    app_module._resolve_shop_catalog()
    app_module._load_settings()
    app_module._heal_empty_shop_config_path(live)

    disk = json.loads(live.read_text(encoding="utf-8"))
    assert "fresh_item" in (disk.get("Items") or {})
    assert "old_0" not in (disk.get("Items") or {})
    saved_settings = json.loads(settings.read_text(encoding="utf-8"))
    assert saved_settings["config_path"] == str(live)
    untouched = json.loads(old.read_text(encoding="utf-8"))
    assert "old_0" in (untouched.get("Items") or {})
    assert "fresh_item" not in (untouched.get("Items") or {})


def test_reread_after_external_save_does_not_restore_previous(tmp_path, monkeypatch, caplog):
    live = tmp_path / "catalog.json"
    old = tmp_path / "old" / "catalog.json"
    old.parent.mkdir()
    old.write_text(
        json.dumps({"Items": {f"old_{i}": {"Price": 1} for i in range(80)}, "Kits": {}}),
        encoding="utf-8",
    )
    v1 = {"Items": {"version_one": {"Price": 1, "Name": "OLD"}}, "Kits": {}}
    v2 = {
        "Items": {
            "version_two": {"Price": 2, "Name": "NEW"},
            "extra": {"Price": 3},
        },
        "Kits": {"kit_new": {"Price": 0}},
    }
    live.write_text(json.dumps(v1), encoding="utf-8")
    _isolate(monkeypatch, tmp_path, live, old)

    with caplog.at_level(logging.INFO, logger="arkshop"):
        first = app_module._read_shop_config()
    assert "version_one" in (first.get("Items") or {})
    reload_lines = [r.message for r in caplog.records if "Catálogo recarregado" in r.message]
    assert reload_lines
    assert str(live) in reload_lines[-1]
    assert "mtime=" in reload_lines[-1]
    assert "version_one" not in reload_lines[-1]

    token = live.stat().st_mtime_ns
    size_v1 = live.stat().st_size
    live.write_text(json.dumps(v2), encoding="utf-8")
    os.utime(live, ns=(token, token))
    assert live.stat().st_size != size_v1

    second = app_module._read_shop_config()
    assert "version_two" in (second.get("Items") or {})
    assert "version_one" not in (second.get("Items") or {})

    assert app_module._save_featured_maps(
        [{
            "id": "mapa",
            "name": "Mapa",
            "enabled": True,
            "sort_order": 0,
            "mod_map": False,
            "description": "",
            "server_id": "",
        }]
    )
    disk = json.loads(live.read_text(encoding="utf-8"))
    assert "version_two" in (disk.get("Items") or {})
    assert "version_one" not in (disk.get("Items") or {})
    assert any(m.get("name") == "Mapa" for m in (disk.get("FeaturedMaps") or []))
    assert "old_0" not in (disk.get("Items") or {})
