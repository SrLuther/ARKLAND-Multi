"""Feed catálogo → Mercado com deduplicação forte."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as _app_module
from app import _configure_database

REX_BP = "/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP"
TEK_REX_BP = "/Game/PrimalEarth/Dinos/Rex/BionicRex_Character_BP.BionicRex_Character_BP"
GIGA_BP = "/Game/PrimalEarth/Dinos/Giganotosaurus/Gigant_Character_BP.Gigant_Character_BP"

CATALOG_SIBLINGS = {
    "ShopItems": {
        "rex_femea": {
            "Type": "dino",
            "Name": "Rex Fêmea Nível 1",
            "Price": 5000,
            "Dinos": [{"Blueprint": REX_BP, "Level": 1}],
        },
        "bionicrex_femea": {
            "Type": "dino",
            "Name": "Rex Tek Fêmea Nível 1",
            "Price": 8000,
            "Dinos": [{"Blueprint": TEK_REX_BP, "Level": 1}],
        },
        "rex_lvl200": {
            "Type": "dino",
            "Name": "Rex Nível 200",
            "Price": 99999,
            "Dinos": [{"Blueprint": REX_BP, "Level": 200}],
        },
        "giga_m": {
            "Type": "dino",
            "Name": "Giga Macho",
            "Price": 12000,
            "Dinos": [{"Blueprint": GIGA_BP, "Level": 1}],
        },
    }
}

CATALOG_DUPLICATE_BP = {
    "ShopItems": {
        "rex_copy_a": {
            "Type": "dino",
            "Name": "Rex cópia A",
            "Price": 5000,
            "Dinos": [{"Blueprint": REX_BP, "Level": 1}],
        },
        "rex_copy_b": {
            "Type": "dino",
            "Name": "Rex cópia B",
            "Price": 5100,
            "Dinos": [{"Blueprint": REX_BP, "Level": 1}],
        },
    }
}


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'catalog_feed_dedup.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    yield
    _configure_database("")


def test_feed_merges_sibling_variants_into_one_species():
    from app import MarketSpecies, MarketSpeciesAlias
    from market_service import feed_catalog_to_market

    db = _app_module._SessionLocal()
    try:
        result = feed_catalog_to_market(
            db,
            CATALOG_SIBLINGS,
            include_reference_and_registry=False,
        )
        assert result["created"] == 2
        assert result["merged"] >= 1
        rex_rows = db.query(MarketSpecies).filter(MarketSpecies.species_key == "rex").all()
        assert len(rex_rows) == 1
        aliases = db.query(MarketSpeciesAlias).filter(
            MarketSpeciesAlias.species_id == rex_rows[0].id
        ).all()
        assert len(aliases) >= 2
        assert rex_rows[0].display_name == "Rex"
    finally:
        db.close()


def test_feed_skips_non_level1_dinos():
    from app import MarketSpecies
    from market_service import feed_catalog_to_market

    db = _app_module._SessionLocal()
    try:
        feed_catalog_to_market(db, CATALOG_SIBLINGS, include_reference_and_registry=False)
        assert db.query(MarketSpecies).filter(MarketSpecies.species_key == "rex_lvl200").count() == 0
    finally:
        db.close()


def test_feed_dedup_same_blueprint_different_item_ids():
    from app import MarketSpecies
    from market_service import feed_catalog_to_market

    db = _app_module._SessionLocal()
    try:
        result = feed_catalog_to_market(
            db,
            CATALOG_DUPLICATE_BP,
            include_reference_and_registry=False,
        )
        assert db.query(MarketSpecies).count() == 1
        assert result["created"] == 1
        assert result["merged"] >= 1 or result["skipped_duplicate"] >= 1
    finally:
        db.close()


def test_feed_only_missing_skips_registered():
    from market_service import bulk_pre_register_catalog_items, feed_catalog_to_market

    db = _app_module._SessionLocal()
    try:
        first = feed_catalog_to_market(
            db,
            CATALOG_SIBLINGS,
            include_reference_and_registry=False,
        )
        assert first["created"] == 2

        again = bulk_pre_register_catalog_items(db, CATALOG_SIBLINGS, only_missing=True)
        assert again["created"] == 0
        assert again["skipped_duplicate"] >= 2
    finally:
        db.close()


def test_dinolab_species_list_deduped():
    from custom_dino_service import list_species_admin
    from market_service import feed_catalog_to_market

    db = _app_module._SessionLocal()
    try:
        feed_catalog_to_market(db, CATALOG_SIBLINGS, include_reference_and_registry=False)
        species = list_species_admin()
        keys = [s["species_key"] for s in species]
        assert keys.count("rex") == 1
        assert "giga" in keys or "giga_m" in keys or any("giga" in k for k in keys)
    finally:
        db.close()


def test_feed_reports_summary_fields():
    from market_service import feed_catalog_to_market

    db = _app_module._SessionLocal()
    try:
        result = feed_catalog_to_market(
            db,
            CATALOG_SIBLINGS,
            include_reference_and_registry=False,
        )
        for key in ("created", "updated", "merged", "skipped_duplicate"):
            assert key in result
    finally:
        db.close()
