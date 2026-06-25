"""Testes de promoção de listings e pré-cadastro."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as _app_module
from app import _configure_database

SELLER = "76561198000000001"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'market_promote_test.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    yield
    _configure_database("")


def test_promote_listings_on_species_activate():
    from app import MarketCryopodVault, MarketListing, MarketSpecies, MarketSpeciesStatMultiplier
    from market_listings import promote_listings_on_species_activate

    db = _app_module._SessionLocal()
    try:
        species = MarketSpecies(
            species_key="rex_femea",
            display_name="Rex",
            root_value=5000,
            status="PRE_REGISTERED",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(species)
        db.flush()
        db.add(
            MarketSpeciesStatMultiplier(
                species_id=species.id, stat_key="melee", multiplier=700, enabled=True
            )
        )
        vault = MarketCryopodVault(
            seller_steam_id=SELLER,
            item_blob=b"\x01",
            blob_hash="promotehash1",
            metadata_json=json.dumps({"stats_max": {"melee": {"points": 59}}}),
            species_key="rex_femea",
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(vault)
        db.flush()
        listing = MarketListing(
            vault_id=vault.id,
            seller_steam_id=SELLER,
            species_key="rex_femea",
            status="PENDING_CLASSIFICATION",
            computed_base_value=0,
            effective_price=0,
            metadata_json=json.dumps({"stats_max": {"melee": {"points": 59}}}),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(listing)
        db.commit()

        species.status = "ACTIVE"
        db.commit()

        count = promote_listings_on_species_activate(db, "rex_femea")
        assert count == 0

        db.refresh(listing)
        assert listing.status == "PENDING_CLASSIFICATION"
        assert listing.computed_base_value == 0
    finally:
        db.close()


def test_reconcile_does_not_auto_promote_pending():
    from app import MarketCryopodVault, MarketListing, MarketSpecies, MarketSpeciesAlias, MarketSpeciesStatMultiplier
    from market_listings import admin_classify_listing, reconcile_pending_listings

    CARCHA_BP = "/Game/PrimalEarth/Dinos/Carcharodontosaurus/Carcha_Character_BP.Carcha_Character_BP"
    CARCHA_CRYO = (
        "BlueprintGeneratedClass "
        "/Game/PrimalEarth/Dinos/Carcharodontosaurus/Carcha_Character_BP.Carcha_Character_BP_C"
    )

    db = _app_module._SessionLocal()
    try:
        species = MarketSpecies(
            species_key="carcha_femea",
            display_name="Carcha",
            blueprint_path=CARCHA_BP,
            root_value=12000,
            status="ACTIVE",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(species)
        db.flush()
        db.add(
            MarketSpeciesAlias(
                species_id=species.id,
                blueprint_path=CARCHA_BP,
                blueprint_norm=CARCHA_BP.lower(),
            )
        )
        db.add(
            MarketSpeciesStatMultiplier(
                species_id=species.id, stat_key="melee", multiplier=720, enabled=True
            )
        )
        meta = {
            "species_blueprint": CARCHA_CRYO,
            "imprint_pct": 1.0,
            "stats_max": {"health": {"value": 30470}, "melee": {"value": 0}},
        }
        vault = MarketCryopodVault(
            seller_steam_id=SELLER,
            item_blob=b"\x02",
            blob_hash="carchahash1",
            metadata_json=json.dumps(meta),
            species_key=None,
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(vault)
        db.flush()
        listing = MarketListing(
            vault_id=vault.id,
            seller_steam_id=SELLER,
            species_key=None,
            status="PENDING_CLASSIFICATION",
            computed_base_value=0,
            effective_price=0,
            metadata_json=json.dumps(meta),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(listing)
        db.commit()

        count = reconcile_pending_listings(db)
        assert count == 0
        db.refresh(listing)
        assert listing.status == "PENDING_CLASSIFICATION"
        assert listing.computed_base_value == 0

        admin_classify_listing(
            db,
            listing.id,
            species_key="carcha_femea",
            approve=True,
        )
        db.refresh(listing)
        assert listing.status == "DRAFT"
        assert listing.species_key == "carcha_femea"
        assert listing.computed_base_value >= 12000
    finally:
        db.close()


def test_pre_register_catalog_item():
    from app import MarketSpecies
    from market_service import pre_register_catalog_item

    db = _app_module._SessionLocal()
    try:
        catalog = {
            "ShopItems": {
                "giga_m": {
                    "Type": "dino",
                    "Name": "Giga Macho",
                    "Price": 12000,
                    "Dinos": [{"Blueprint": "/Game/Dinos/Giga/Giga_BP.Giga_BP", "Level": 1}],
                }
            }
        }
        result = pre_register_catalog_item(db, catalog, "giga_m")
        assert result["species_key"]
        assert result["status"] == "PRE_REGISTERED"
        row = db.query(MarketSpecies).filter(MarketSpecies.species_key == result["species_key"]).first()
        assert row is not None
        assert row.root_value == 12000
    finally:
        db.close()
