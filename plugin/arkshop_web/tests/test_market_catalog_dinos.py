"""Status e pré-cadastro em lote de dinos do catálogo."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as _app_module
from app import _configure_database

CATALOG = {
    "ShopItems": {
        "rex_femea": {
            "Type": "dino",
            "Name": "Rex Fêmea",
            "Price": 5000,
            "MarketInclude": True,
            "Dinos": [{"Blueprint": "/Game/Dinos/Rex/Rex_BP.Rex_BP", "Level": 1}],
        },
        "giga_m": {
            "Type": "dino",
            "Name": "Giga Macho",
            "Price": 12000,
            "Dinos": [{"Blueprint": "/Game/Dinos/Giga/Giga_BP.Giga_BP", "Level": 1}],
        },
        "metal_100": {
            "Type": "item",
            "Name": "Metal",
            "Price": 10,
            "Blueprint": "/Game/Metal",
        },
    }
}


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'market_catalog_dinos.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    yield
    _configure_database("")


def test_list_catalog_dinos_market_status_empty():
    from market_service import list_catalog_dinos_market_status

    db = _app_module._SessionLocal()
    try:
        rows = list_catalog_dinos_market_status(db, CATALOG)
        assert len(rows) == 2
        ids = {r["catalog_item_id"] for r in rows}
        assert ids == {"rex_femea", "giga_m"}
        assert all(not r["market_registered"] for r in rows)
        assert next(r for r in rows if r["catalog_item_id"] == "rex_femea")["market_include"]
    finally:
        db.close()


def test_bulk_pre_register_only_missing():
    from app import MarketSpecies
    from market_service import bulk_pre_register_catalog_items, list_catalog_dinos_market_status

    db = _app_module._SessionLocal()
    try:
        result = bulk_pre_register_catalog_items(db, CATALOG, only_missing=True)
        assert result["created"] == 2
        assert result["skipped"] == 0
        rows = list_catalog_dinos_market_status(db, CATALOG)
        assert all(r["market_registered"] for r in rows)
        assert db.query(MarketSpecies).count() >= 2

        again = bulk_pre_register_catalog_items(db, CATALOG, only_missing=True)
        assert again["created"] == 0
        assert again["updated"] == 0
        assert again["skipped"] == 0

        refresh = bulk_pre_register_catalog_items(
            db, CATALOG, item_ids=["rex_femea", "giga_m"], only_missing=False
        )
        assert refresh["updated"] == 2
    finally:
        db.close()


def test_bulk_pre_register_specific_ids():
    from market_service import bulk_pre_register_catalog_items, list_catalog_dinos_market_status

    db = _app_module._SessionLocal()
    try:
        result = bulk_pre_register_catalog_items(
            db, CATALOG, item_ids=["giga_m"], only_missing=True
        )
        assert result["created"] == 1
        rows = list_catalog_dinos_market_status(db, CATALOG)
        giga = next(r for r in rows if r["catalog_item_id"] == "giga_m")
        rex = next(r for r in rows if r["catalog_item_id"] == "rex_femea")
        assert giga["market_registered"]
        assert not rex["market_registered"]
    finally:
        db.close()
