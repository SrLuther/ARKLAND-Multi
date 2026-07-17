"""Testes — stats de criatura nos payloads de anúncios do mercado."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as _app_module
from app import _configure_database
from market_migrate import ensure_market_schema

SELLER = "76561198000000001"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'market_stats_test.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    ensure_market_schema(_app_module._ENGINE, bootstrap=False)
    yield
    _configure_database("")


def _seed_commerce(db):
    from app import MarketPlayerProfile, MarketSpecies, StoreUser

    db.add(
        MarketSpecies(
            species_key="rex",
            catalog_item_id="rex",
            display_name="Rex",
            blueprint_path="/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP",
            reference_level=1,
            root_value=5000,
            tier="A",
            status="ACTIVE",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.add(
        StoreUser(
            steam_id=SELLER,
            steam_persona="Seller",
            display_name="Seller",
            created_at=datetime.now(timezone.utc),
            last_login_at=datetime.now(timezone.utc),
        )
    )
    db.add(
        MarketPlayerProfile(
            steam_id=SELLER,
            market_display_name="Seller",
            commerce_enabled=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


def _make_listing(
    db,
    *,
    is_female: bool,
    price: int,
    status: str = "ACTIVE",
    stat_health: int = 0,
    stat_melee: int = 0,
    stat_weight: int = 0,
    dino_level: int = 0,
    mutations_male: int = 0,
    mutations_female: int = 0,
):
    from app import MarketCryopodVault, MarketListing

    vault = MarketCryopodVault(
        seller_steam_id=SELLER,
        item_blob=b"\x00\x01",
        blob_hash=f"hash_{is_female}_{price}_{stat_health}",
        metadata_json='{"admin_classification_approved": true}',
        species_key="rex",
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(vault)
    db.flush()
    listing = MarketListing(
        vault_id=vault.id,
        seller_steam_id=SELLER,
        species_key="rex",
        status=status,
        price_mode="ABSOLUTE",
        price_absolute=price,
        computed_base_value=100,
        effective_price=price,
        dino_display_name="Rex",
        imprint_pct=100.0,
        is_female=is_female,
        stat_health=stat_health,
        stat_melee=stat_melee,
        stat_weight=stat_weight,
        dino_level=dino_level,
        mutations_male=mutations_male,
        mutations_female=mutations_female,
        metadata_json='{"admin_classification_approved": true}',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


def test_listing_to_public_includes_creature_stats():
    from market_listings import listing_to_public

    class Row:
        id = 1
        seller_steam_id = SELLER
        species_key = "rex"
        status = "ACTIVE"
        computed_base_value = 100
        effective_price = 200
        price_mode = "ABSOLUTE"
        dino_display_name = "Rex"
        imprint_pct = 100.0
        mutations_male = 10
        mutations_female = 5
        dino_level = 324
        is_female = False
        metadata_json = "{}"
        created_at = datetime.now(timezone.utc)
        custom_name = None
        category = None
        stat_health = 17
        stat_melee = 103
        stat_weight = 15
        stat_stamina = 0
        stat_oxygen = 0
        stat_food = 0
        stat_speed = 0
        pair_mate_listing_id = None
        pair_group_id = None

    pub = listing_to_public(Row())
    assert pub["stats"]["health"] == 17
    assert pub["stats"]["melee"] == 103
    assert pub["stats"]["weight"] == 15
    assert pub["dino_level"] == 324
    assert pub["mutations_male"] == 10
    assert pub["mutations_female"] == 5


def test_active_pair_listing_includes_mate_stats():
    from market_listings import link_pair_listings, list_active_listings

    db = _app_module._SessionLocal()
    try:
        _seed_commerce(db)
        male = _make_listing(
            db,
            is_female=False,
            price=100,
            stat_health=17,
            stat_melee=103,
            stat_weight=15,
            dino_level=324,
            mutations_male=4624,
            mutations_female=4624,
        )
        female = _make_listing(
            db,
            is_female=True,
            price=100,
            stat_health=22,
            stat_melee=88,
            stat_weight=12,
            dino_level=310,
            mutations_male=100,
            mutations_female=200,
        )
        link_pair_listings(db, male.id, female.id, SELLER)
        active = list_active_listings(db)
        assert len(active) == 1
        card = active[0]
        mate = card["pair_mate"]
        assert mate is not None
        assert card["stats"]["health"] == 17
        assert card["stats"]["melee"] == 103
        assert mate["stats"]["health"] == 22
        assert mate["stats"]["melee"] == 88
        bd = card["pair_breakdown"]
        assert bd["male"]["stats"]["health"] == 17
        assert bd["female"]["stats"]["health"] == 22
        assert bd["male"]["dino_level"] == 324
        assert bd["female"]["dino_level"] == 310
    finally:
        db.close()


def test_admin_detail_enriches_pair_mate_stats():
    from market_listings import get_admin_listing_detail, link_pair_listings

    db = _app_module._SessionLocal()
    try:
        _seed_commerce(db)
        male = _make_listing(db, is_female=False, price=100, stat_health=11, stat_melee=55)
        female = _make_listing(db, is_female=True, price=100, stat_health=33, stat_melee=77)
        link_pair_listings(db, male.id, female.id, SELLER)
        detail = get_admin_listing_detail(db, male.id)
        mate = detail["pair_mate"]
        assert mate["stats"]["health"] == 33
        assert mate["stats"]["melee"] == 77
        assert detail["stats"]["health"] == 11
    finally:
        db.close()
