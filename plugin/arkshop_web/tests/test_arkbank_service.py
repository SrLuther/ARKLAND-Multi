"""Testes unitários do ARKBANK (tesouraria)."""
from __future__ import annotations

import os

os.environ.setdefault("ARKSHOP_SYNC_DB_MIGRATE", "1")
os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def ark_db(tmp_path):
    from arkbank_service import ensure_arkbank_schema

    path = tmp_path / "arkbank.db"
    engine = create_engine(f"sqlite:///{path}", future=True)
    ensure_arkbank_schema(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def test_credit_debit_and_negative_balance(ark_db):
    from arkbank_service import credit, debit, get_balance

    r1 = credit(
        ark_db,
        tx_type="catalog_spend",
        amount=1000,
        idempotency_key="arkbank:test:c1",
        commit=True,
    )
    assert r1["applied"] is True
    assert get_balance(ark_db) == 1000

    r2 = debit(
        ark_db,
        tx_type="timed_reward",
        amount=2500,
        idempotency_key="arkbank:test:d1",
        commit=True,
    )
    assert r2["applied"] is True
    assert get_balance(ark_db) == -1500
    assert r2["balance_after"] == -1500


def test_idempotency_no_double_credit(ark_db):
    from arkbank_service import credit, get_balance

    key = "arkbank:catalog:order-xyz"
    a = credit(ark_db, tx_type="catalog_spend", amount=500, idempotency_key=key, commit=True)
    b = credit(ark_db, tx_type="catalog_spend", amount=500, idempotency_key=key, commit=True)
    assert a["applied"] is True
    assert b["duplicate"] is True
    assert get_balance(ark_db) == 500


def test_donation_conversion_r1_equals_1000(ark_db):
    from arkbank_service import (
        ARKBANK_DONATION_AMBER_PER_REAL,
        credit_donation_brl,
        donation_amber_from_brl,
        get_balance,
    )

    assert ARKBANK_DONATION_AMBER_PER_REAL == 1000
    assert donation_amber_from_brl(5) == 5000
    assert donation_amber_from_brl(5.0) == 5000

    r = credit_donation_brl(
        ark_db,
        payment_id="pay-1",
        steam_id="76561198000000001",
        amount_brl=5,
        payment_method="pix",
        commit=True,
    )
    assert r["applied"] is True
    assert r["amount"] == 5000
    assert get_balance(ark_db) == 5000

    # Segunda chamada idempotente
    r2 = credit_donation_brl(
        ark_db,
        payment_id="pay-1",
        steam_id="76561198000000001",
        amount_brl=5,
        commit=True,
    )
    assert r2["duplicate"] is True
    assert get_balance(ark_db) == 5000


def test_catalog_spend_and_refund_retention_20pct(ark_db):
    """Compra +P; desistência clawback 0.80P → líquido +0.20P no banco."""
    from arkbank_service import (
        credit_catalog_spend,
        debit_catalog_refund_clawback,
        get_balance,
    )

    P = 10_000
    credit_catalog_spend(
        ark_db,
        order_id="ord-1",
        steam_id="76561198000000001",
        points=P,
        commit=True,
    )
    assert get_balance(ark_db) == P

    refund = int(round(P * 0.80))
    debit_catalog_refund_clawback(
        ark_db,
        order_id="ord-1",
        steam_id="76561198000000001",
        refunded=refund,
        event="cancel",
        commit=True,
    )
    assert get_balance(ark_db) == P - refund
    assert get_balance(ark_db) == 2000  # 20% retenção


def test_market_pair_share_credits_bank(ark_db):
    from arkbank_service import credit_market_pair_share, get_balance

    r = credit_market_pair_share(
        ark_db,
        amount=80,
        listing_id=1,
        tx_id=99,
        seller_steam_id="76561198000000002",
        commit=True,
    )
    assert r["applied"] is True
    assert get_balance(ark_db) == 80


def test_dino_order_pay_and_refund(ark_db):
    from arkbank_service import (
        credit_dino_order_pay,
        debit_dino_order_refund,
        get_balance,
    )

    credit_dino_order_pay(
        ark_db,
        order_id="dino-1",
        steam_id="76561198000000001",
        total=50_000,
        commit=True,
    )
    assert get_balance(ark_db) == 50_000
    debit_dino_order_refund(
        ark_db,
        order_id="dino-1",
        steam_id="76561198000000001",
        refunded=50_000,
        commit=True,
    )
    assert get_balance(ark_db) == 0


def test_timed_outbox_process_debits(ark_db):
    from arkbank_service import (
        credit,
        enqueue_timed_outbox,
        get_balance,
        process_timed_outbox,
    )

    credit(
        ark_db,
        tx_type="catalog_spend",
        amount=100,
        idempotency_key="arkbank:test:seed",
        commit=True,
    )
    enqueue_timed_outbox(
        ark_db,
        steam_id="76561198000000001",
        amount=250,
        map_id="TheIsland",
        cycle_key="1700000000",
        commit=True,
    )
    result = process_timed_outbox(ark_db)
    assert result["processed"] == 1
    assert get_balance(ark_db) == -150  # nunca bloqueia

    # Reprocessar mesma linha já marcada → 0
    result2 = process_timed_outbox(ark_db)
    assert result2["processed"] == 0
    assert get_balance(ark_db) == -150


def test_summary_inflow_outflow(ark_db):
    from arkbank_service import credit, debit, summary

    credit(ark_db, tx_type="catalog_spend", amount=1000, idempotency_key="s1", commit=True)
    credit(ark_db, tx_type="donation_brl", amount=5000, idempotency_key="s2", commit=True)
    debit(ark_db, tx_type="timed_reward", amount=200, idempotency_key="s3", commit=True)
    s = summary(ark_db, days=7)
    assert s["balance"] == 5800
    assert s["inflow"] == 6000
    assert s["outflow"] == 200
    assert s["health"] == "saudavel"


def test_contribute_market_pair_goes_to_arkbank_not_prize(tmp_path):
    """Cutover A: 40% casal → ARKBANK; prize_amber_from_market não sobe."""
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from arkbank_service import ensure_arkbank_schema, get_balance
    from lottery_service import contribute_market_pair_to_prize, ensure_lottery_schema

    engine = create_engine(f"sqlite:///{tmp_path / 'pair.db'}", future=True)
    ensure_lottery_schema(engine)
    ensure_arkbank_schema(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        now = "2026-01-01 00:00:00"
        db.execute(
            text(
                "INSERT INTO lottery_campaigns "
                "(sequence_number, title, status, draw_at, prize_amber_base, "
                "prize_amber_from_market, created_at, updated_at) "
                "VALUES (1, 'T', 'ACTIVE', '2099-01-01 00:00:00', 1000, 0, :now, :now)"
            ),
            {"now": now},
        )
        db.commit()

        result = contribute_market_pair_to_prize(
            db,
            amount=80,
            listing_id=10,
            tx_id=55,
            seller_steam_id="76561198000000002",
        )
        db.commit()
        assert result.get("destination") == "arkbank"
        assert result["credited"] == 80
        pot = db.execute(
            text("SELECT prize_amber_from_market FROM lottery_campaigns WHERE status='ACTIVE'")
        ).scalar()
        assert int(pot or 0) == 0
        assert get_balance(db) == 80
    finally:
        db.close()
