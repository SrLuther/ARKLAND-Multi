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
ADMIN = "76561198000000099"


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


def test_purchase_notifies_seller(tmp_path, monkeypatch):
    from notification_service import list_notifications
    from market_listings import list_seller_vitrine_audit_events, purchase_listing

    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN]), encoding="utf-8")

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

        items, total = list_notifications(db, SELLER, unread_only=True)
        assert total >= 1
        assert any(n["type"] == "market_sale" for n in items)
        assert any("vendido" in (n["title"] or "").lower() for n in items)

        audit = list_seller_vitrine_audit_events(db, SELLER)
        assert any(e["event_type"] == "MARKET_SELLER_LISTING_SOLD" for e in audit)
    finally:
        db.close()


def test_admin_flag_notifies_seller_and_audit(tmp_path, monkeypatch):
    from notification_service import list_notifications
    from market_listings import admin_flag_listing, list_seller_vitrine_audit_events

    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN]), encoding="utf-8")

    db = _app_module._SessionLocal()
    try:
        _seed_species(db)
        listing_id = _seed_active_listing(db)

        admin_flag_listing(
            db,
            listing_id,
            ADMIN,
            reason="Preço abusivo",
            pause=True,
        )

        items, total = list_notifications(db, SELLER, unread_only=True)
        assert total >= 1
        flagged = [n for n in items if n["type"] == "market_admin_flag"]
        assert flagged
        assert "abusivo" in (flagged[0]["body"] or "").lower() or "sinalizado" in (flagged[0]["title"] or "").lower()
        assert "Preço abusivo" in (flagged[0]["body"] or "")

        audit = list_seller_vitrine_audit_events(db, SELLER)
        removed = [e for e in audit if e["event_type"] == "MARKET_SELLER_LISTING_ADMIN_FLAGGED"]
        assert removed
        assert removed[0]["metadata"].get("reason") == "Preço abusivo"
    finally:
        db.close()


def test_admin_remove_notifies_seller_and_audit(tmp_path, monkeypatch):
    from notification_service import list_notifications
    from market_listings import admin_remove_listing, list_seller_vitrine_audit_events

    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN]), encoding="utf-8")

    db = _app_module._SessionLocal()
    try:
        _seed_species(db)
        listing_id = _seed_active_listing(db)

        admin_remove_listing(db, listing_id, ADMIN, reason="Conteúdo proibido")

        items, total = list_notifications(db, SELLER, unread_only=True)
        assert total >= 1
        assert any(n["type"] == "market_admin_remove" for n in items)

        audit = list_seller_vitrine_audit_events(db, SELLER)
        assert any(e["event_type"] == "MARKET_SELLER_LISTING_ADMIN_REMOVED" for e in audit)
        removed = [e for e in audit if e["event_type"] == "MARKET_SELLER_LISTING_ADMIN_REMOVED"][0]
        assert removed["metadata"].get("reason") == "Conteúdo proibido"
    finally:
        db.close()
