"""Testes do teto de preço de anúncios no Comércio."""
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
from market_economy import (
    calculate_listing_price_ceiling,
    format_price_ceiling_error,
    load_price_ceiling_config,
    patch_economy_global_config,
)

SELLER = "76561198000000001"
ADMIN = "76561198000000099"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'ceiling_test.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    defaults = tmp_path / "market_species_defaults.json"
    defaults.write_text(
        json.dumps(
            {
                "species": [],
                "_size_caps": {"small": 100000, "medium": 250000, "large": 300000},
                "_price_ceiling": {
                    "enabled": True,
                    "global_multiplier": 10,
                    "absolute_max": 500000,
                    "tier_multipliers": {"C": 6, "A": 10},
                },
            }
        ),
        encoding="utf-8",
    )
    import market_economy as me

    monkeypatch.setattr(me, "_DEFAULTS_FILE", defaults)
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN]), encoding="utf-8")
    yield
    _configure_database("")
    monkeypatch.setattr(me, "_DEFAULTS_FILE", None)


def test_calculate_listing_price_ceiling_tier_c():
    cfg = load_price_ceiling_config()
    assert cfg["enabled"] is True
    # Kairuku-like: sugerido 400, tier C, porte small
    ceiling = calculate_listing_price_ceiling(400, tier="C", size_class="small")
    assert ceiling == 2400  # 400 × 6


def test_calculate_listing_price_ceiling_porte_cap():
    # Sugerido alto mas limitado pelo teto do porte small
    ceiling = calculate_listing_price_ceiling(50000, tier="S", size_class="small")
    assert ceiling == 100000


def test_format_price_ceiling_error_pt_br():
    msg = format_price_ceiling_error(400_000_000, 400, 2400, tier="C")
    assert "2.400" in msg
    assert "400.000.000" in msg
    assert "tier C" in msg


def test_set_listing_price_rejects_above_ceiling():
    from app import MarketCryopodVault, MarketListing, MarketSpecies
    from market_listings import set_listing_price

    db = _app_module._SessionLocal()
    try:
        species = MarketSpecies(
            species_key="kairuku",
            display_name="Kairuku",
            blueprint_path="/Game/PrimalEarth/Dinos/Kairuku/Kairuku_Character_BP.Kairuku_Character_BP",
            reference_level=1,
            root_value=400,
            tier="C",
            status="ACTIVE",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(species)
        db.flush()
        vault = MarketCryopodVault(
            seller_steam_id=SELLER,
            item_blob=b"\x01",
            blob_hash="ceilinghash1",
            metadata_json="{}",
            species_key="kairuku",
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(vault)
        db.flush()
        listing = MarketListing(
            vault_id=vault.id,
            seller_steam_id=SELLER,
            species_key="kairuku",
            status="DRAFT",
            computed_base_value=400,
            effective_price=400,
            metadata_json=json.dumps({"admin_classification_approved": True}),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(listing)
        db.commit()

        with pytest.raises(ValueError, match="Preço máximo permitido"):
            set_listing_price(db, listing.id, SELLER, price_absolute=400_000_000, activate=True)

        out = set_listing_price(db, listing.id, SELLER, price_absolute=2000, activate=True)
        assert out["status"] == "ACTIVE"
        assert out["effective_price"] == 2000
    finally:
        db.close()


def test_admin_set_listing_price_bypasses_ceiling():
    from app import MarketCryopodVault, MarketListing, MarketSpecies
    from market_listings import admin_set_listing_price

    db = _app_module._SessionLocal()
    try:
        species = MarketSpecies(
            species_key="kairuku",
            display_name="Kairuku",
            blueprint_path="/bp",
            reference_level=1,
            root_value=400,
            tier="C",
            status="ACTIVE",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(species)
        db.flush()
        vault = MarketCryopodVault(
            seller_steam_id=SELLER,
            item_blob=b"\x02",
            blob_hash="ceilinghash2",
            metadata_json="{}",
            species_key="kairuku",
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(vault)
        db.flush()
        listing = MarketListing(
            vault_id=vault.id,
            seller_steam_id=SELLER,
            species_key="kairuku",
            status="ACTIVE",
            computed_base_value=400,
            effective_price=400_000_000,
            metadata_json="{}",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(listing)
        db.commit()

        out = admin_set_listing_price(db, listing.id, ADMIN, 5000, pause=True)
        assert out["effective_price"] == 5000
        assert out["status"] == "PAUSED"
    finally:
        db.close()


def test_process_plugin_admin_remove():
    from app import MarketCryopodVault, MarketListing, MarketSpecies
    from market_listings import process_plugin_admin_action

    db = _app_module._SessionLocal()
    try:
        species = MarketSpecies(
            species_key="rex_femea",
            display_name="Rex",
            blueprint_path="/bp",
            reference_level=1,
            root_value=5000,
            tier="A",
            status="ACTIVE",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(species)
        db.flush()
        vault = MarketCryopodVault(
            seller_steam_id=SELLER,
            item_blob=b"\x03",
            blob_hash="ceilinghash3",
            metadata_json="{}",
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
            effective_price=999999,
            metadata_json="{}",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(listing)
        db.commit()

        result = process_plugin_admin_action(
            db,
            {"admin_steam_id": ADMIN, "action": "remover", "listing_id": listing.id},
        )
        assert result["status"] == "AWAITING_CLAIM"
        assert result["claim_id"] > 0
    finally:
        db.close()


def test_patch_price_ceiling_config():
    patch_economy_global_config({"price_ceiling": {"global_multiplier": 8, "tier_multipliers": {"B": 5}}})
    cfg = load_price_ceiling_config()
    assert cfg["global_multiplier"] == 8
    assert cfg["tier_multipliers"]["B"] == 5
