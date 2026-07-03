"""Testes do serviço de listings do mercado."""
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
BUYER = "76561198000000002"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'market_test.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    yield
    _configure_database("")


def _seed_species(db, *, include_buyer: bool = False):
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
            species_id=species.id,
            stat_key="melee",
            multiplier=700,
            enabled=True,
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
    if include_buyer:
        db.add(
            MarketPlayerProfile(
                steam_id=BUYER,
                market_display_name="BuyerBR",
                commerce_enabled=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
    db.commit()


def _seed_active_listing(db, *, custom_name: str = "Alpha Rex"):
    from app import MarketCryopodVault, MarketListing

    vault = MarketCryopodVault(
        seller_steam_id=SELLER,
        item_blob=b"\x01\x02",
        blob_hash="abc123unique",
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
        status="ACTIVE",
        computed_base_value=5000,
        effective_price=5500,
        custom_name=custom_name,
        dino_display_name="Rex Clone",
        metadata_json=json.dumps({"admin_classification_approved": True}),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(listing)
    db.commit()
    return listing.id


def test_set_listing_price_and_activate():
    from app import MarketCryopodVault, MarketListing
    from market_listings import set_listing_price

    db = _app_module._SessionLocal()
    try:
        _seed_species(db)
        vault = MarketCryopodVault(
            seller_steam_id=SELLER,
            item_blob=b"\x01\x02",
            blob_hash="abc123unique",
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
            status="DRAFT",
            computed_base_value=5000,
            effective_price=5000,
            metadata_json=json.dumps({"admin_classification_approved": True}),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(listing)
        db.commit()

        out = set_listing_price(db, listing.id, SELLER, price_absolute=6000, activate=True)
        assert out["status"] == "ACTIVE"
        assert out["effective_price"] == 6000
    finally:
        db.close()


def test_list_active_listings():
    from app import MarketCryopodVault, MarketListing
    from market_listings import list_active_listings

    db = _app_module._SessionLocal()
    try:
        _seed_species(db)
        vault = MarketCryopodVault(
            seller_steam_id=SELLER,
            item_blob=b"\x01",
            blob_hash="hash1unique",
            metadata_json="{}",
            species_key="rex_femea",
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(vault)
        db.flush()
        db.add(
            MarketListing(
                vault_id=vault.id,
                seller_steam_id=SELLER,
                species_key="rex_femea",
                status="ACTIVE",
                computed_base_value=5000,
                effective_price=5500,
                dino_display_name="Alpha Rex",
                metadata_json="{}",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
        items = list_active_listings(db)
        assert len(items) == 1
        assert items[0]["seller_display_name"] == "SellerOne"
    finally:
        db.close()


def test_player_market_history_shows_buyer_for_seller():
    from market_listings import player_market_history, purchase_listing

    db = _app_module._SessionLocal()
    try:
        _seed_species(db, include_buyer=True)
        listing_id = _seed_active_listing(db)
        db.execute(
            __import__("sqlalchemy").text(
                "INSERT INTO players (steam_id, points) VALUES (:sid, :pts)"
            ),
            {"sid": BUYER, "pts": 10000},
        )
        db.commit()

        purchase_listing(db, listing_id, BUYER)
        history = player_market_history(db, SELLER)

        assert len(history["sales"]) == 1
        sale = history["sales"][0]
        assert sale["listing_id"] == listing_id
        assert sale["buyer_steam_id"] == BUYER
        assert sale["buyer_display_name"] == "BuyerBR"
        assert sale["price_paid"] == 5500
        assert sale["delivery_status"] == "aguardando_resgate"
        assert sale["display_title"] or sale["custom_name"]

        assert len(history["purchases"]) == 0
        buyer_history = player_market_history(db, BUYER)
        assert len(buyer_history["purchases"]) == 1
        assert buyer_history["purchases"][0]["seller_display_name"] == "SellerOne"
    finally:
        db.close()
