"""Testes de upload do mercado (process_plugin_upload)."""
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
TRACE = "abc123uploadid0000000000000001"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'market_upload_test.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    yield
    _configure_database("")


def _seed(db):
    from app import MarketPlayerProfile, MarketSpecies, MarketSpeciesStatMultiplier

    species = MarketSpecies(
        species_key="rex_femea",
        catalog_item_id="rex_femea",
        display_name="Rex Fêmea",
        blueprint_path="/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP",
        reference_level=1,
        root_value=5000,
        tier="A",
        status="ACTIVE",
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
    db.add(
        MarketPlayerProfile(
            steam_id=SELLER,
            market_display_name="SellerOne",
            commerce_enabled=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


def _upload_body(**overrides):
    body = {
        "steam_id": SELLER,
        "inventory_removed": True,
        "inventory_verified_empty": True,
        "item_blob_hex": "0102ab",
        "upload_id": TRACE,
        "market_trace_id": TRACE,
        "metadata": {
            "species_blueprint": "/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP",
            "imprint_pct": 1.0,
            "name_map": "Alpha Rex",
            "stats_max": {"melee": {"points": 59}},
        },
    }
    body.update(overrides)
    return body


def test_process_plugin_upload_creates_listing():
    from market_listings import process_plugin_upload

    db = _app_module._SessionLocal()
    try:
        _seed(db)
        result = process_plugin_upload(db, _upload_body())
        assert result["listing_id"] > 0
        assert result["status"] == "DRAFT"
        assert result["computed_base_value"] >= 5000
    finally:
        db.close()


def test_upload_deduplicated_by_trace_id():
    from market_listings import process_plugin_upload

    db = _app_module._SessionLocal()
    try:
        _seed(db)
        first = process_plugin_upload(db, _upload_body())
        second = process_plugin_upload(db, _upload_body(item_blob_hex="0102ac"))
        assert second.get("deduplicated") is True
        assert second["listing_id"] == first["listing_id"]
    finally:
        db.close()


def test_upload_rejects_without_commerce_profile():
    from market_listings import process_plugin_upload

    db = _app_module._SessionLocal()
    try:
        with pytest.raises(ValueError, match="comércio"):
            process_plugin_upload(db, _upload_body(steam_id="76561198999999999"))
    finally:
        db.close()


def test_upload_pending_classification_unknown_species():
    from market_listings import process_plugin_upload

    db = _app_module._SessionLocal()
    try:
        from app import MarketPlayerProfile

        db.add(
            MarketPlayerProfile(
                steam_id=SELLER,
                market_display_name="SellerOne",
                commerce_enabled=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
        result = process_plugin_upload(
            db,
            _upload_body(
                metadata={
                    "species_blueprint": "/Game/Mods/Unknown/Dino_BP.Dino_BP",
                    "imprint_pct": 1.0,
                    "name_map": "Mod Dino",
                    "stats_max": {},
                }
            ),
        )
        assert result["status"] == "PENDING_CLASSIFICATION"
    finally:
        db.close()
