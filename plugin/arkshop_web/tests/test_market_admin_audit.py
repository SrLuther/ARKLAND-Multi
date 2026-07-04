"""Testes da auditoria admin do Mercado (v1.9.193)."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")
os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")

import app as _app_module
from app import _configure_database, app
from market_audit import market_audit_event, market_audit_label

SELLER = "76561198000000001"
BUYER = "76561198000000002"
ADMIN = "76561198000000099"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'market_admin_audit.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN]), encoding="utf-8")
    _configure_database(db_url)
    yield
    _configure_database("")


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login(client, steam_id: str) -> None:
    with client.session_transaction() as sess:
        sess["steam_id"] = steam_id


def _seed_listing_with_audit(db) -> int:
    from app import MarketCryopodVault, MarketListing, MarketPlayerProfile

    db.add(
        MarketPlayerProfile(
            steam_id=SELLER,
            market_display_name="SellerOne",
            commerce_enabled=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    vault = MarketCryopodVault(
        seller_steam_id=SELLER,
        item_blob=b"\x01\x02",
        blob_hash="audit_hash_1",
        metadata_json=json.dumps({"calculation_breakdown": [{"stat": "melee", "points": 59}]}),
        species_key="rex_femea",
        parser_version="1.0.0",
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
        custom_name="Alpha Rex",
        dino_level=337,
        market_trace_id="mkt-trace-abc",
        metadata_json=json.dumps({"admin_classification_approved": True}),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(listing)
    db.flush()

    market_audit_event(
        db,
        "MARKET_LISTING_ACTIVATED",
        steam_id=SELLER,
        listing_id=listing.id,
        market_trace_id="mkt-trace-abc",
        metadata={
            "seller_steam_id": SELLER,
            "summary_pt": f"Anúncio #{listing.id} ativado",
            "listing_status_before": "DRAFT",
            "listing_status_after": "ACTIVE",
        },
        commit=True,
    )
    market_audit_event(
        db,
        "MARKET_LISTING_ADMIN_FLAGGED",
        steam_id=ADMIN,
        counterparty_steam_id=SELLER,
        listing_id=listing.id,
        severity="WARN",
        source="admin",
        metadata={
            "seller_steam_id": SELLER,
            "admin_steam_id": ADMIN,
            "reason": "preço abusivo",
            "summary_pt": f"Admin sinalizou anúncio #{listing.id}",
        },
        commit=True,
    )
    db.commit()
    return listing.id


def test_market_audit_label_pt_br():
    assert market_audit_label("MARKET_PURCHASE_COMPLETED") == "Compra concluída"
    assert market_audit_label("MARKET_LISTING_ADMIN_FLAGGED") == "Moderação: sinalizado"
    assert market_audit_label("UNKNOWN_EVENT") == "UNKNOWN_EVENT"


def test_query_market_audit_filters_listing_and_severity():
    from market_listings import get_market_audit_event, query_market_audit_events

    db = _app_module._SessionLocal()
    try:
        listing_id = _seed_listing_with_audit(db)

        all_events, total = query_market_audit_events(db, listing_id=listing_id)
        assert total >= 2
        assert all(e["listing_id"] == listing_id for e in all_events)

        warn_events, warn_total = query_market_audit_events(
            db, listing_id=listing_id, severity="WARN"
        )
        assert warn_total >= 1
        assert all(e["severity"] == "WARN" for e in warn_events)
        assert warn_events[0]["event_label"] == "Moderação: sinalizado"
        assert "summary_pt" in warn_events[0]

        by_seller, _ = query_market_audit_events(
            db, steam_id=SELLER, steam_id_mode="any", listing_id=listing_id
        )
        assert len(by_seller) >= 1

        event_id = warn_events[0]["id"]
        detail = get_market_audit_event(db, event_id)
        assert detail is not None
        assert detail["event_type"] == "MARKET_LISTING_ADMIN_FLAGGED"
        assert detail["metadata"].get("reason") == "preço abusivo"
    finally:
        db.close()


def test_get_listing_timeline():
    from market_listings import get_listing_timeline

    db = _app_module._SessionLocal()
    try:
        listing_id = _seed_listing_with_audit(db)
        timeline = get_listing_timeline(db, listing_id)

        assert timeline["listing"]["listing_id"] == listing_id
        assert len(timeline["audit_events"]) >= 2
        assert timeline["amber_snapshot"]["seller_steam_id"] == SELLER
        assert timeline["listing"].get("cryo_preview") is not None
        assert timeline["listing"]["cryo_preview"]["blob_hash"] == "audit_hash_1"
    finally:
        db.close()


def test_list_admin_listings_search():
    from market_listings import list_admin_listings

    db = _app_module._SessionLocal()
    try:
        listing_id = _seed_listing_with_audit(db)

        by_id, total = list_admin_listings(db, q=str(listing_id))
        assert total == 1
        assert by_id[0]["listing_id"] == listing_id

        by_seller, total2 = list_admin_listings(db, seller_steam_id=SELLER)
        assert total2 >= 1
        assert any(r["listing_id"] == listing_id for r in by_seller)
    finally:
        db.close()


def test_admin_audit_api_pagination_and_detail(client):
    db = _app_module._SessionLocal()
    try:
        listing_id = _seed_listing_with_audit(db)
    finally:
        db.close()

    _login(client, ADMIN)
    r = client.get(f"/api/market/admin/audit?listing_id={listing_id}&limit=10&offset=0")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["total"] >= 2
    assert len(data["events"]) >= 2
    assert data["events"][0].get("event_label")

    event_id = data["events"][0]["id"]
    r2 = client.get(f"/api/market/admin/audit/{event_id}")
    assert r2.status_code == 200
    detail = r2.get_json()
    assert detail["ok"] is True
    assert detail["event"]["id"] == event_id


def test_admin_listing_timeline_api(client):
    db = _app_module._SessionLocal()
    try:
        listing_id = _seed_listing_with_audit(db)
    finally:
        db.close()

    _login(client, ADMIN)
    r = client.get(f"/api/market/admin/listings/{listing_id}/timeline")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["listing"]["listing_id"] == listing_id
    assert len(data["audit_events"]) >= 2


def test_admin_listings_panel_api(client):
    db = _app_module._SessionLocal()
    try:
        listing_id = _seed_listing_with_audit(db)
    finally:
        db.close()

    _login(client, ADMIN)
    r = client.get(f"/api/market/admin/listings?q={listing_id}")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["total"] >= 1

    r2 = client.get(f"/api/market/admin/listings/{listing_id}")
    assert r2.status_code == 200
    listing = r2.get_json()["listing"]
    assert listing["listing_id"] == listing_id
    assert listing["cryo_preview"]["blob_hash"] == "audit_hash_1"
