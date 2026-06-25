"""Testes de claims (release, deliver)."""
from __future__ import annotations

import os
import sys
import threading
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as _app_module
from app import _configure_database

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
    db_url = f"sqlite:///{tmp_path / 'market_claims_test.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    yield
    _configure_database("")


def _seed_claim(db):
    from app import MarketClaim, MarketCryopodVault, MarketListing

    now = datetime.now(timezone.utc)
    vault = MarketCryopodVault(
        seller_steam_id=SELLER,
        item_blob=b"\x01\x02",
        blob_hash="claimhash1",
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
        effective_price=5000,
        buyer_steam_id=BUYER,
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
        created_at=now,
        updated_at=now,
    )
    from market_listings import _apply_claim_reservation

    _apply_claim_reservation(claim, now=now)
    db.add(claim)
    db.commit()
    return claim.id, listing.id


def test_claim_and_release():
    from market_listings import claim_deliveries, get_pending_claims, release_claims

    db = _app_module._SessionLocal()
    try:
        claim_id, _ = _seed_claim(db)
        pending = get_pending_claims(db, BUYER)
        assert len(pending) == 1

        claimed = claim_deliveries(db, BUYER, [claim_id])
        assert claimed[0]["claim_id"] == claim_id

        pending2 = get_pending_claims(db, BUYER)
        assert len(pending2) == 0

        released = release_claims(db, BUYER, [claim_id])
        assert released[0]["claim_id"] == claim_id

        pending3 = get_pending_claims(db, BUYER)
        assert len(pending3) == 1
    finally:
        db.close()


def test_mark_claim_delivered():
    from app import MarketClaim, MarketListing
    from market_listings import claim_deliveries, mark_claim_delivered

    db = _app_module._SessionLocal()
    try:
        claim_id, listing_id = _seed_claim(db)
        claim_deliveries(db, BUYER, [claim_id])
        result = mark_claim_delivered(db, claim_id, BUYER)
        assert result["status"] == "DELIVERED"

        listing = db.query(MarketListing).filter(MarketListing.id == listing_id).first()
        assert listing.status == "DELIVERED"
        claim = db.query(MarketClaim).filter(MarketClaim.id == claim_id).first()
        assert claim.status == "DELIVERED"
    finally:
        db.close()
