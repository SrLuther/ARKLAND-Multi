"""Testes — venda em casal (M+F) + contribuição ao sorteio."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as _app_module
from app import _configure_database
from market_pair import (
    pair_checkout_price,
    pair_claim_refund,
    pair_prize_contribution,
    pair_pricing_breakdown,
    validate_pair_eligibility,
)
from market_migrate import ensure_market_schema

SELLER = "76561198000000001"
BUYER = "76561198000000002"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'market_pair_test.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    ensure_market_schema(_app_module._ENGINE, bootstrap=False)
    yield
    _configure_database("")


def test_pair_pricing_canonical_example():
    """S=200 → Y=120, pote +80."""
    assert pair_checkout_price(100, 100) == 120
    assert pair_prize_contribution(100, 100) == 80
    bd = pair_pricing_breakdown(100, 100)
    assert bd["sum_asking"] == 200
    assert bd["checkout_price"] == 120
    assert bd["prize_contribution"] == 80


def test_single_style_asking_unchanged_math():
    """Solteiro não usa fatores de casal — checkout = pedido."""
    assert pair_checkout_price(5000, 0) == 3000  # só se forçado como par
    # Solteiro no fluxo real usa effective_price direto (fee=0)


def test_validate_pair_requires_opposite_gender_same_species():
    class Fake:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    a = Fake(
        id=1,
        seller_steam_id=SELLER,
        species_key="rex",
        is_female=False,
        status="DRAFT",
        pair_mate_listing_id=None,
    )
    b = Fake(
        id=2,
        seller_steam_id=SELLER,
        species_key="rex",
        is_female=True,
        status="DRAFT",
        pair_mate_listing_id=None,
    )
    validate_pair_eligibility(a, b)

    b.is_female = False
    with pytest.raises(ValueError, match="macho e uma fêmea"):
        validate_pair_eligibility(a, b)

    b.is_female = True
    b.species_key = "giga"
    with pytest.raises(ValueError, match="mesma espécie"):
        validate_pair_eligibility(a, b)


def _seed_commerce(db):
    from app import MarketPlayerProfile, MarketSpecies, StoreUser

    db.add(
        MarketSpecies(
            species_key="rex",
            catalog_item_id="rex_femea",
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
    for sid, name in ((SELLER, "Seller"), (BUYER, "Buyer")):
        db.add(
            StoreUser(
                steam_id=sid,
                steam_persona=name,
                display_name=name,
                created_at=datetime.now(timezone.utc),
                last_login_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            MarketPlayerProfile(
                steam_id=sid,
                market_display_name=name,
                commerce_enabled=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        db.execute(
            text("INSERT INTO players (steam_id, points, kits) VALUES (:sid, :pts, '{}')"),
            {"sid": sid, "pts": 1_000_000},
        )
    db.commit()


def _make_listing(db, *, is_female: bool, price: int, status: str = "DRAFT"):
    from app import MarketCryopodVault, MarketListing

    vault = MarketCryopodVault(
        seller_steam_id=SELLER,
        item_blob=b"\x00\x01",
        blob_hash=f"hash_{is_female}_{price}",
        metadata_json="{}",
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
        metadata_json='{"admin_classification_approved": true}',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


def test_pair_link_purchase_and_pot_credit():
    from lottery_service import ensure_lottery_schema
    from market_listings import (
        link_pair_listings,
        list_active_listings,
        purchase_listing,
        set_listing_price,
    )

    db = _app_module._SessionLocal()
    try:
        _seed_commerce(db)
        ensure_lottery_schema(_app_module._ENGINE)
        # Campanha ativa mínima
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.execute(
            text(
                "INSERT INTO lottery_campaigns "
                "(sequence_number, title, status, draw_at, prize_amber_base, "
                "prize_amber_from_market, created_at, updated_at) "
                "VALUES (1, 'Test', 'ACTIVE', :draw, 5000, 0, :now, :now)"
            ),
            {"draw": now + timedelta(days=7), "now": now},
        )
        db.commit()

        male = _make_listing(db, is_female=False, price=100)
        female = _make_listing(db, is_female=True, price=100)
        linked = link_pair_listings(db, male.id, female.id, SELLER)
        assert linked["is_pair"] is True
        assert linked["pair_checkout_price"] == 120

        set_listing_price(db, male.id, SELLER, activate=True)
        active = list_active_listings(db)
        # Só o primário (menor id) na vitrine
        pair_cards = [x for x in active if x.get("is_pair")]
        assert len(pair_cards) == 1
        assert pair_cards[0]["pair_checkout_price"] == 120
        assert pair_cards[0]["effective_price"] == 120

        buyer_before = db.execute(
            text("SELECT points FROM players WHERE steam_id=:s"), {"s": BUYER}
        ).scalar()
        seller_before = db.execute(
            text("SELECT points FROM players WHERE steam_id=:s"), {"s": SELLER}
        ).scalar()

        result = purchase_listing(db, male.id, BUYER)
        assert result["price_paid"] == 120
        assert result["is_pair"] is True
        assert result["prize_contribution"] == 80
        assert result.get("pair_mate_claim_id")

        buyer_after = db.execute(
            text("SELECT points FROM players WHERE steam_id=:s"), {"s": BUYER}
        ).scalar()
        seller_after = db.execute(
            text("SELECT points FROM players WHERE steam_id=:s"), {"s": SELLER}
        ).scalar()
        assert buyer_before - buyer_after == 120
        assert seller_after - seller_before == 120

        pot = db.execute(
            text("SELECT prize_amber_from_market FROM lottery_campaigns WHERE status='ACTIVE'")
        ).scalar()
        assert int(pot or 0) == 80

        tx = db.execute(
            text("SELECT price_paid, fee_amount FROM market_transactions ORDER BY id DESC LIMIT 1")
        ).fetchone()
        assert int(tx[0]) == 120
        assert int(tx[1]) == 0
    finally:
        db.close()


def test_single_purchase_no_pot_and_full_price():
    from market_listings import purchase_listing, set_listing_price

    db = _app_module._SessionLocal()
    try:
        _seed_commerce(db)
        listing = _make_listing(db, is_female=True, price=5000)
        set_listing_price(db, listing.id, SELLER, activate=True, skip_price_ceiling=True)
        seller_before = db.execute(
            text("SELECT points FROM players WHERE steam_id=:s"), {"s": SELLER}
        ).scalar()
        result = purchase_listing(db, listing.id, BUYER)
        assert result["price_paid"] == 5000
        assert result.get("is_pair") is False
        assert result.get("prize_contribution", 0) == 0
        seller_after = db.execute(
            text("SELECT points FROM players WHERE steam_id=:s"), {"s": SELLER}
        ).scalar()
        assert seller_after - seller_before == 5000
        tx = db.execute(
            text("SELECT fee_amount FROM market_transactions WHERE listing_id=:id"),
            {"id": listing.id},
        ).scalar()
        assert int(tx or 0) == 0
    finally:
        db.close()


def test_pair_claim_refund_is_sixty_percent_of_y():
    assert pair_claim_refund(120) == 72
    assert pair_claim_refund(100) == 60
    assert pair_claim_refund(0) == 0


def test_pair_claim_expiry_refunds_60pct_y_pot_unchanged():
    """Casal: comprador +0,60×Y; vendedor −Y; pote mantém 0,40×S da compra."""
    from app import MarketClaim
    from lottery_service import ensure_lottery_schema
    from market_listings import (
        CLAIM_STATUS_REFUNDED,
        expire_stale_claims,
        link_pair_listings,
        purchase_listing,
        set_listing_price,
    )

    db = _app_module._SessionLocal()
    try:
        _seed_commerce(db)
        ensure_lottery_schema(_app_module._ENGINE)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.execute(
            text(
                "INSERT INTO lottery_campaigns "
                "(sequence_number, title, status, draw_at, prize_amber_base, "
                "prize_amber_from_market, created_at, updated_at) "
                "VALUES (1, 'Test', 'ACTIVE', :draw, 5000, 0, :now, :now)"
            ),
            {"draw": now + timedelta(days=7), "now": now},
        )
        db.commit()

        male = _make_listing(db, is_female=False, price=100)
        female = _make_listing(db, is_female=True, price=100)
        link_pair_listings(db, male.id, female.id, SELLER)
        set_listing_price(db, male.id, SELLER, activate=True)

        buyer_before = db.execute(
            text("SELECT points FROM players WHERE steam_id=:s"), {"s": BUYER}
        ).scalar()
        seller_before = db.execute(
            text("SELECT points FROM players WHERE steam_id=:s"), {"s": SELLER}
        ).scalar()

        purchase_listing(db, male.id, BUYER)
        y = 120
        expected_refund = 72  # round(0.60 × 120)

        pot_after_buy = int(
            db.execute(
                text("SELECT prize_amber_from_market FROM lottery_campaigns WHERE status='ACTIVE'")
            ).scalar()
            or 0
        )
        assert pot_after_buy == 80

        # Expira ambos os claims do comprador
        claims = (
            db.query(MarketClaim)
            .filter(MarketClaim.claim_type == "BUYER", MarketClaim.status == "PENDENTE")
            .all()
        )
        assert len(claims) == 2
        expired_at = datetime.now(timezone.utc) - timedelta(hours=1)
        for c in claims:
            c.claim_expires_at = expired_at
        db.commit()

        result = expire_stale_claims(db)
        refunds = result["buyer_refunds"]
        primary_refunds = [r for r in refunds if r.get("refund_amount", 0) > 0]
        assert len(primary_refunds) == 1
        assert primary_refunds[0]["refund_amount"] == expected_refund
        assert primary_refunds[0].get("price_paid") == y

        buyer_after = db.execute(
            text("SELECT points FROM players WHERE steam_id=:s"), {"s": BUYER}
        ).scalar()
        seller_after = db.execute(
            text("SELECT points FROM players WHERE steam_id=:s"), {"s": SELLER}
        ).scalar()
        # Comprou −Y, reembolso +0,60×Y → líquido −0,40×Y
        assert buyer_before - buyer_after == y - expected_refund
        # Vendedor recebeu Y e devolveu Y → saldo igual ao pré-compra
        assert seller_after == seller_before

        pot_after_refund = int(
            db.execute(
                text("SELECT prize_amber_from_market FROM lottery_campaigns WHERE status='ACTIVE'")
            ).scalar()
            or 0
        )
        assert pot_after_refund == pot_after_buy == 80

        for c in claims:
            db.refresh(c)
            assert c.claim_status == CLAIM_STATUS_REFUNDED
    finally:
        db.close()


def test_single_claim_expiry_still_full_refund():
    """Solteiro: reembolso 100% do valor pago; sem pote."""
    from app import MarketClaim
    from market_listings import expire_stale_claims, purchase_listing, set_listing_price

    db = _app_module._SessionLocal()
    try:
        _seed_commerce(db)
        listing = _make_listing(db, is_female=True, price=5000)
        set_listing_price(db, listing.id, SELLER, activate=True, skip_price_ceiling=True)

        buyer_before = db.execute(
            text("SELECT points FROM players WHERE steam_id=:s"), {"s": BUYER}
        ).scalar()
        seller_before = db.execute(
            text("SELECT points FROM players WHERE steam_id=:s"), {"s": SELLER}
        ).scalar()

        purchase_listing(db, listing.id, BUYER)

        claim = (
            db.query(MarketClaim)
            .filter(MarketClaim.listing_id == listing.id, MarketClaim.claim_type == "BUYER")
            .first()
        )
        claim.claim_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()

        result = expire_stale_claims(db)
        assert result["buyer_refunds"][0]["refund_amount"] == 5000

        buyer_after = db.execute(
            text("SELECT points FROM players WHERE steam_id=:s"), {"s": BUYER}
        ).scalar()
        seller_after = db.execute(
            text("SELECT points FROM players WHERE steam_id=:s"), {"s": SELLER}
        ).scalar()
        assert buyer_after == buyer_before
        assert seller_after == seller_before
    finally:
        db.close()
