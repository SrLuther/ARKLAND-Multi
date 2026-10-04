"""Sync catalog.json → MySQL e comparação do Couro. O arquivo de teste é temporário."""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as _app_module
from app import _configure_database
import resource_vitrine_service as svc
import vitrine_catalog_sync as sync
import vitrine_match as match

BP_HIDE = match.HIDE_BLUEPRINT
BP_WOOD = "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Wood.PrimalItemResource_Wood"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    _orig_start = threading.Thread.start

    def _patched_start(self):
        if getattr(self, "name", None) == "arkshop-db-migrate":
            self.run()
        else:
            _orig_start(self)

    monkeypatch.setattr(threading.Thread, "start", _patched_start)
    monkeypatch.setattr(_app_module, "_kick_background_db_init", lambda: None)
    monkeypatch.setattr(_app_module, "_start_db_reconnect_watcher", lambda: None)
    _app_module._db_reconnect_stop.set()
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(f"sqlite:///{tmp_path / 'rv_catalog.db'}")
    yield
    _app_module._db_reconnect_stop.set()
    _configure_database("")


@pytest.fixture()
def db():
    session = _app_module._SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_hide_forms_match_registered_blueprint():
    for raw in match.HIDE_ARK_FORMS:
        assert match.resources_match(BP_HIDE, raw), raw
    assert not match.resources_match(BP_HIDE, BP_WOOD)
    # Stack 1000 do cadastro e quantidade 100000 não são argumentos da comparação.
    assert "quantity" not in match.resources_match.__code__.co_varnames


def test_plugin_fallback_uses_file_when_mysql_list_is_empty():
    hide = {"blueprint": BP_HIDE, "name": "Couro"}
    assert match.choose_vitrine_source(True, [], [hide]) == ("arquivo", [hide])
    assert match.choose_vitrine_source(False, None, [hide]) == ("arquivo", [hide])
    assert match.choose_vitrine_source(True, [hide], []) == ("mysql", [hide])


def test_catalog_file_wins_over_database_row(db):
    svc.upsert_catalog_resource(db, {"blueprint": BP_WOOD, "name": "Madeira", "stack_size": 100})
    svc.upsert_catalog_resource(db, {"blueprint": BP_HIDE, "name": "Couro velho", "stack_size": 100})
    catalog = {
        "Items": {"pedra": {"Name": "Pedra"}},
        "ResourceVitrine": {
            "max_types_per_player": 5,
            "resources": [
                {
                    "blueprint": BP_HIDE,
                    "name": "Couro",
                    "stack_size": 1000,
                    "min_lot_price": 100,
                    "max_lot_price": 1000,
                    "enabled": True,
                }
            ],
        },
    }
    result = svc.sync_vitrine_from_catalog(db, catalog)
    assert result["applied"] is True
    enabled = svc.plugin_config(db)["resources"]
    assert [row["name"] for row in enabled] == ["Couro"]
    assert enabled[0]["stack_size"] == 1000
    wood = next(row for row in svc.list_catalog(db, include_disabled=True) if "Wood" in row["blueprint"])
    assert wood["enabled"] is False


def test_absent_block_does_not_drop_mysql_rows(db):
    svc.upsert_catalog_resource(db, {"blueprint": BP_HIDE, "name": "Couro", "stack_size": 1000})
    result = svc.sync_vitrine_from_catalog(db, {"Items": {}})
    assert result["applied"] is False
    assert svc.plugin_config(db)["resources"][0]["name"] == "Couro"


def test_atomic_write_keeps_shop_items_and_updates_mysql(db, tmp_path, monkeypatch):
    svc.upsert_catalog_resource(db, {"blueprint": BP_WOOD, "name": "Madeira", "stack_size": 100})
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"Items": {"pedra": 1}, "Kits": {}}), encoding="utf-8")
    monkeypatch.setenv("ARKLAND_VITRINE_CATALOG", str(path))
    monkeypatch.setenv("ARKLAND_VITRINE_CATALOG_ALLOW", "1")
    saved = sync.publish_admin_upsert(
        db,
        {
            "blueprint": f"Blueprint'{BP_HIDE}'",
            "name": "Couro",
            "stack_size": 1000,
            "min_lot_price": 100,
            "max_lot_price": 1000,
            "enabled": True,
        },
    )
    assert saved["name"] == "Couro"
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["Items"] == {"pedra": 1}
    blueprints = [row["blueprint"] for row in written["ResourceVitrine"]["resources"]]
    assert BP_HIDE in blueprints and BP_WOOD in blueprints
    enabled = [row["name"] for row in svc.plugin_config(db)["resources"]]
    assert "Couro" in enabled
    assert "Madeira" in enabled  # o bloco nasceu da cópia do banco + o Couro novo

    # Arquivo sem a madeira: o banco não ressuscita a linha.
    written["ResourceVitrine"]["resources"] = [
        row for row in written["ResourceVitrine"]["resources"] if "Hide" in row["blueprint"]
    ]
    path.write_text(json.dumps(written), encoding="utf-8")
    refreshed = sync.refresh_db_from_catalog_path(db, path)
    assert refreshed["applied"] is True and refreshed["disabled"] >= 1
    names = [row["name"] for row in svc.plugin_config(db)["resources"]]
    assert names == ["Couro"]
