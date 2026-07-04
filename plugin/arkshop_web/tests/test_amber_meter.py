"""Testes do Âmbarômetro (amber_ledger + API pública)."""
from __future__ import annotations

import json
import os
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")
os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")

import app as _app_module
from amber_ledger import (
    ensure_amber_schema,
    get_public_stats,
    record_donation,
    record_market_purchase,
    record_movement,
    record_shop_debit,
)
from app import _configure_database, app


@pytest.fixture()
def amber_db(tmp_path):
    path = tmp_path / "amber.db"
    engine = create_engine(f"sqlite:///{path}", future=True)
    ensure_amber_schema(engine, run_backfill=False)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _test_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_WEB_SECRET", "test-secret")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(_app_module, "_migrate_schema", lambda _engine: None)
    (tmp_path / "admin_steamids.json").write_text("[]", encoding="utf-8")


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "web_amber.db")
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    from amber_ledger import ensure_amber_schema

    if _app_module._ENGINE is not None:
        ensure_amber_schema(_app_module._ENGINE, run_backfill=False)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_record_movement_idempotent(amber_db):
    ok1 = record_donation(
        amber_db,
        payment_id="pay-1",
        steam_id="76561198000000001",
        points=5000,
        commit=True,
    )
    ok2 = record_donation(
        amber_db,
        payment_id="pay-1",
        steam_id="76561198000000001",
        points=5000,
        commit=True,
    )
    assert ok1 is True
    assert ok2 is False
    row = amber_db.execute(text("SELECT COUNT(*) FROM amber_ledger")).fetchone()
    assert int(row[0]) == 1


def test_gross_uses_absolute_delta(amber_db):
    record_shop_debit(
        amber_db,
        order_id="ord-1",
        steam_id="76561198000000001",
        points=2500,
        commit=True,
    )
    row = amber_db.execute(
        text("SELECT gross_amount, signed_delta FROM amber_ledger WHERE source_id = 'ord-1'")
    ).fetchone()
    assert int(row.gross_amount) == 2500
    assert int(row.signed_delta) == -2500


def test_market_counts_two_legs(amber_db):
    record_market_purchase(
        amber_db,
        tx_id=42,
        listing_id=7,
        buyer_steam_id="76561198000000001",
        seller_steam_id="76561198000000002",
        price=10000,
        commit=True,
    )
    rows = amber_db.execute(
        text("SELECT idempotency_key, gross_amount FROM amber_ledger ORDER BY id")
    ).fetchall()
    assert len(rows) == 2
    assert sum(int(r.gross_amount) for r in rows) == 20000
    keys = {r.idempotency_key for r in rows}
    assert "market:tx:42:buyer" in keys
    assert "market:tx:42:seller" in keys


def test_zero_delta_ignored(amber_db):
    ok = record_movement(
        amber_db,
        channel="admin",
        event_type="noop",
        signed_delta=0,
        idempotency_key="zero:1",
        commit=True,
    )
    assert ok is False


def test_public_stats_and_cache(amber_db):
    record_donation(amber_db, payment_id="p1", steam_id="76561198000000001", points=1000, commit=True)
    record_donation(amber_db, payment_id="p2", steam_id="76561198000000002", points=2000, commit=True)
    amber_db.commit()
    stats = get_public_stats(amber_db, currency=lambda: {"singular": "Âmbar", "plural": "Âmbares", "image_url": "/ambar.png"})
    assert stats["ok"] is True
    assert stats["total_gross_all_time"] == 3000
    assert stats["channels"]["donation"] == 3000
    assert "coverage_note" in stats
    assert stats["display"]["label"] == "Âmbares movimentados"


def test_public_amber_stats_api(client):
    db = _app_module._SessionLocal()
    try:
        record_donation(db, payment_id="api-pay", steam_id="76561198000000009", points=750, commit=True)
    finally:
        _app_module._release_db_session(db)

    r = client.get("/api/public/amber-stats")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["total_gross_all_time"] >= 750
    assert r.headers.get("Cache-Control") == "public, max-age=60"


def test_backfill_point_payments(amber_db):
    amber_db.execute(
        text(
            "CREATE TABLE IF NOT EXISTS point_payments ("
            "payment_id TEXT, steam_id TEXT, points INTEGER, credited INTEGER, created_at DATETIME)"
        )
    )
    amber_db.execute(
        text(
            "INSERT INTO point_payments (payment_id, steam_id, points, credited, created_at) "
            "VALUES ('bf-1', '76561198000000001', 300, 1, datetime('now'))"
        )
    )
    amber_db.commit()
    from amber_ledger import backfill_historical

    counts = backfill_historical(amber_db)
    amber_db.commit()
    assert counts["donation"] >= 1
    stats = get_public_stats(amber_db)
    assert stats["total_gross_all_time"] >= 300
