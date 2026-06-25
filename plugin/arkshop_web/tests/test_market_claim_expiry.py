"""Testes de reserva de resgate (24h) e reembolso automático."""
from __future__ import annotations

import os
import sys
import threading
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as _app_module
from app import _configure_database
from market_listings import (
    CLAIM_RESERVATION_HOURS,
    CLAIM_STATUS_PENDING,
    CLAIM_STATUS_REFUNDED,
    _apply_claim_reservation,
    _hours_remaining,
    _refund_amount_for_listing,
    claim_deliveries,
    expire_stale_claims,
    get_pending_claims,
)

BUYER = "76561198000000002"
SELLER = "76561198000000001"


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
    db_url = f"sqlite:///{tmp_path / 'market_expiry_test.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    yield
    _app_module._db_reconnect_stop.set()
    _configure_database("")


def _seed_profiles_and_points(db):
    from sqlalchemy import text

    from app import MarketPlayerProfile

    now = datetime.now(timezone.utc)
    for sid, name in ((SELLER, "SellerOne"), (BUYER, "BuyerOne")):
        db.add(
            MarketPlayerProfile(
                steam_id=sid,
                market_display_name=name,
                commerce_enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
        db.execute(
            text("INSERT INTO players (steam_id, points) VALUES (:sid, :pts)"),
            {"sid": sid, "pts": 100_000},
        )
    db.commit()


def _seed_purchased_listing(db):
    from app import MarketClaim, MarketCryopodVault, MarketListing, MarketTransaction

    now = datetime.now(timezone.utc)
    vault = MarketCryopodVault(
        seller_steam_id=SELLER,
        item_blob=b"\x01\x02",
        blob_hash="expiryhash1",
        metadata_json="{}",
        species_key="rex_femea",
        uploaded_at=now,
    )
    db.add(vault)
    db.flush()
    listing = MarketListing(
        vault_id=vault.id,
        seller_steam_id=SELLER,
        species_key="rex_femea",
        status="AWAITING_CLAIM",
        computed_base_value=5000,
        effective_price=8000,
        buyer_steam_id=BUYER,
        sold_at=now,
        metadata_json="{}",
        created_at=now,
        updated_at=now,
    )
    db.add(listing)
    db.flush()
    claim = MarketClaim(
        listing_id=listing.id,
        recipient_steam_id=BUYER,
        claim_type="BUYER",
        status="PENDENTE",
        claim_status=CLAIM_STATUS_PENDING,
        created_at=now,
        updated_at=now,
    )
    _apply_claim_reservation(claim, now=now)
    db.add(claim)
    db.add(
        MarketTransaction(
            listing_id=listing.id,
            buyer_steam_id=BUYER,
            seller_steam_id=SELLER,
            price_paid=8000,
            base_value_at_sale=5000,
            fee_amount=0,
            buyer_points_before=100_000,
            buyer_points_after=92_000,
            seller_points_before=100_000,
            seller_points_after=108_000,
            created_at=now,
        )
    )
    db.commit()
    return claim.id, listing.id


def test_purchase_sets_24h_reservation():
    from app import MarketClaim

    db = _app_module._SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        claim = MarketClaim(
            listing_id=1,
            recipient_steam_id=BUYER,
            claim_type="BUYER",
            status="PENDENTE",
            created_at=now,
            updated_at=now,
        )
        from market_listings import _apply_claim_reservation

        _apply_claim_reservation(claim, now=now)
        assert claim.claim_status == CLAIM_STATUS_PENDING
        assert claim.claim_reserved_at == now
        hrs = _hours_remaining(claim.claim_expires_at, now=now)
        assert hrs == pytest.approx(CLAIM_RESERVATION_HOURS, abs=0.05)
        assert claim.claim_expires_at == now + timedelta(hours=CLAIM_RESERVATION_HOURS)
    finally:
        db.close()


def test_refund_amount_includes_fees():
    db = _app_module._SessionLocal()
    try:
        _, listing_id = _seed_purchased_listing(db)
        assert _refund_amount_for_listing(db, listing_id) == 8000
    finally:
        db.close()


def test_expire_stale_claims_refunds_buyer_and_returns_dino_to_seller():
    from app import MarketClaim, MarketListing
    from sqlalchemy import text

    db = _app_module._SessionLocal()
    try:
        _seed_profiles_and_points(db)
        claim_id, listing_id = _seed_purchased_listing(db)
        claim = db.query(MarketClaim).filter(MarketClaim.id == claim_id).first()
        claim.claim_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()

        result = expire_stale_claims(db)
        assert result["processed"] == 1
        assert result["buyer_refunds"][0]["refund_amount"] == 8000

        buyer_pts = db.execute(
            text("SELECT points FROM players WHERE steam_id = :sid"), {"sid": BUYER}
        ).fetchone()[0]
        seller_pts = db.execute(
            text("SELECT points FROM players WHERE steam_id = :sid"), {"sid": SELLER}
        ).fetchone()[0]
        assert buyer_pts == 108_000
        assert seller_pts == 92_000

        expired = db.query(MarketClaim).filter(MarketClaim.id == claim_id).first()
        assert expired.claim_status == CLAIM_STATUS_REFUNDED

        listing = db.query(MarketListing).filter(MarketListing.id == listing_id).first()
        assert listing.buyer_steam_id is None
        assert listing.status == "AWAITING_CLAIM"

        seller_claim = (
            db.query(MarketClaim)
            .filter(MarketClaim.listing_id == listing_id, MarketClaim.claim_type == "SELLER")
            .first()
        )
        assert seller_claim is not None
        assert seller_claim.status == "PENDENTE"

        pending = get_pending_claims(db, BUYER)
        assert len(pending) == 0
    finally:
        db.close()


def test_expire_is_idempotent():
    from app import MarketClaim

    db = _app_module._SessionLocal()
    try:
        _seed_profiles_and_points(db)
        claim_id, _ = _seed_purchased_listing(db)
        claim = db.query(MarketClaim).filter(MarketClaim.id == claim_id).first()
        claim.claim_expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
        db.commit()

        first = expire_stale_claims(db)
        second = expire_stale_claims(db)
        assert first["processed"] == 1
        assert second["processed"] == 0
    finally:
        db.close()


def test_claim_deliveries_skips_expired_after_auto_refund():
    from app import MarketClaim

    db = _app_module._SessionLocal()
    try:
        _seed_profiles_and_points(db)
        claim_id, listing_id = _seed_purchased_listing(db)
        claim = db.query(MarketClaim).filter(MarketClaim.id == claim_id).first()
        claim.claim_expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.commit()

        claimed = claim_deliveries(db, BUYER, [claim_id])
        assert claimed == []

        claim = db.query(MarketClaim).filter(MarketClaim.id == claim_id).first()
        assert claim.claim_status == CLAIM_STATUS_REFUNDED
    finally:
        db.close()
