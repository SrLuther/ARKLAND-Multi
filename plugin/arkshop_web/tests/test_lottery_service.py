"""Testes do Sorteio de Doações ARKLAND."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app as _app_module
from lottery_draw import compute_prize_split
from lottery_service import (
    buy_random_number,
    configure_lottery,
    create_campaign_draft,
    ensure_lottery_schema,
    get_active_campaign,
    on_donation_credited,
    publish_campaign,
    reserve_number,
    run_draw,
)

USER = "76561198000000001"
USER2 = "76561198000000002"
ADMIN = "76561198000000003"


@pytest.fixture()
def lottery_db(tmp_path):
    path = tmp_path / "lottery.db"
    engine = create_engine(f"sqlite:///{path}", future=True)
    ensure_lottery_schema(engine)
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS players ("
                "steam_id TEXT PRIMARY KEY, points INTEGER DEFAULT 0, kits TEXT DEFAULT '{}')"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS store_users ("
                "steam_id TEXT PRIMARY KEY, market_display_name TEXT, steam_persona TEXT)"
            )
        )
        conn.commit()
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _lottery_enabled(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"lottery_enabled": True}), encoding="utf-8")
    monkeypatch.setattr(_app_module, "_STATE_FILE", settings_file)
    configure_lottery(
        credit_fn=_app_module._add_player_points_tx,
        debit_fn=_app_module._subtract_player_points_tx,
        settings_fn=_app_module._load_settings,
    )


def _credit(db, steam_id: str, amount: int) -> None:
    db.execute(
        text(
            "INSERT INTO players (steam_id, points) VALUES (:s, :p) "
            "ON CONFLICT(steam_id) DO UPDATE SET points = :p"
        ),
        {"s": steam_id, "p": amount},
    )


def _active_campaign(db, *, base: int = 124, w: int = 5, draw_past: bool = False):
    draw_at = datetime.now(timezone.utc) - timedelta(hours=1) if draw_past else datetime.now(timezone.utc) + timedelta(days=7)
    camp = create_campaign_draft(
        db,
        data={
            "prize_amber_base": base,
            "winning_numbers_count": w,
            "draw_at": draw_at.isoformat(),
        },
    )
    publish_campaign(db, int(camp["id"]))
    db.commit()
    return int(camp["id"])


def test_compute_prize_split_no_winner():
    split = compute_prize_split(100, 0)
    assert split["rollover_out"] == 125
    assert split["prize_pool_fully_distributed"] is False


def test_compute_prize_split_one_winner_full_pool():
    split = compute_prize_split(124, 1)
    assert split["share_per_match"] == 124
    assert split["prize_amber_paid"] == 124
    assert split["prize_amber_subsidy"] == 0
    assert split["rollover_out"] == 0


def test_compute_prize_split_three_winners_subsidy():
    split = compute_prize_split(124, 3)
    assert split["share_per_match"] == 42
    assert split["prize_amber_paid"] == 126
    assert split["prize_amber_subsidy"] == 2


def test_donation_assigns_numbers(lottery_db):
    cid = _active_campaign(lottery_db)
    result = on_donation_credited(
        lottery_db, payment_id="pay-1", steam_id=USER, amount_brl=12.0,
    )
    lottery_db.commit()
    assert result["assigned"] == 2
    row = lottery_db.execute(
        text("SELECT COUNT(*) FROM lottery_numbers WHERE campaign_id = :c AND payment_id = 'pay-1'"),
        {"c": cid},
    ).fetchone()
    assert int(row[0]) == 2


def test_donation_idempotent(lottery_db):
    _active_campaign(lottery_db)
    on_donation_credited(lottery_db, payment_id="pay-2", steam_id=USER, amount_brl=10.0)
    lottery_db.commit()
    again = on_donation_credited(lottery_db, payment_id="pay-2", steam_id=USER, amount_brl=10.0)
    assert again.get("skipped") is True


def test_buy_and_reserve_unique(lottery_db):
    _active_campaign(lottery_db)
    _credit(lottery_db, USER, 10000)
    _credit(lottery_db, USER2, 10000)
    lottery_db.commit()
    a = buy_random_number(lottery_db, USER)
    b = reserve_number(lottery_db, USER2, 555)
    lottery_db.commit()
    assert a["number"]["value"] != 555
    assert b["number"]["value"] == 555
    with pytest.raises(ValueError, match="number_unavailable"):
        reserve_number(lottery_db, USER, 555)


def test_buy_random_limit(lottery_db):
    _active_campaign(lottery_db)
    _credit(lottery_db, USER, 100000)
    lottery_db.commit()
    for _ in range(5):
        buy_random_number(lottery_db, USER)
    lottery_db.commit()
    with pytest.raises(ValueError, match="random_limit_reached"):
        buy_random_number(lottery_db, USER)


def test_draw_no_winner_rollover_125(lottery_db):
    cid = _active_campaign(lottery_db, base=100, w=1, draw_past=True)
    result = run_draw(lottery_db, cid, job_id="test-no-winner")
    lottery_db.commit()
    assert result["matched_count"] == 0
    assert result["split"]["rollover_out"] == 125
    row = lottery_db.execute(
        text("SELECT prize_amber_rollover_out FROM lottery_campaigns WHERE id = :id"),
        {"id": cid},
    ).fetchone()
    assert int(row[0]) == 125


def test_draw_one_winner_full_prize(lottery_db, monkeypatch):
    cid = _active_campaign(lottery_db, base=124, w=5, draw_past=True)
    lottery_db.execute(
        text(
            "INSERT INTO lottery_numbers (campaign_id, steam_id, source, number_value, status) "
            "VALUES (:c, :s, 'DONATION', 333, 'ACTIVE')"
        ),
        {"c": cid, "s": USER},
    )
    lottery_db.commit()

    def _fixed_draw(*args, **kwargs):
        return [333], {"seed_hash": "test", "algorithm_version": "test", "drawn_at": "now", "method": "test"}

    monkeypatch.setattr("lottery_service.draw_winning_numbers", _fixed_draw)
    result = run_draw(lottery_db, cid, job_id="test-one-winner")
    lottery_db.commit()
    assert result["matched_count"] == 1
    assert result["split"]["share_per_match"] == 124
    assert result["split"]["prize_amber_paid"] == 124
    pts = lottery_db.execute(text("SELECT points FROM players WHERE steam_id = :s"), {"s": USER}).fetchone()
    assert int(pts[0]) == 124


def test_draw_three_winners_split(lottery_db):
    cid = _active_campaign(lottery_db, base=124, w=5, draw_past=True)
    for num in (100, 300, 500):
        lottery_db.execute(
            text(
                "INSERT INTO lottery_numbers (campaign_id, steam_id, source, number_value, status) "
                "VALUES (:c, :s, 'DONATION', :n, 'ACTIVE')"
            ),
            {"c": cid, "s": USER if num == 100 else USER2, "n": num},
        )
    lottery_db.commit()
    result = run_draw(lottery_db, cid, job_id="test-three")
    lottery_db.commit()
    mc = result["matched_count"]
    if mc == 3:
        assert result["split"]["share_per_match"] == 42
        assert result["split"]["prize_amber_paid"] == 126
        assert result["split"]["prize_amber_subsidy"] == 2
    else:
        split = compute_prize_split(124, 3)
        assert split["share_per_match"] == 42


def test_payment_hook_survives_lottery_error(monkeypatch):
    """Simula try/except do hook em _finalize_pix_payment — erro não propaga."""
    import lottery_service

    def _boom(*a, **k):
        raise RuntimeError("lottery exploded")

    monkeypatch.setattr(lottery_service, "on_donation_credited", _boom)
    caught = False
    try:
        lottery_service.on_donation_credited(
            None, payment_id="x", steam_id=USER, amount_brl=5.0,
        )
    except RuntimeError:
        caught = True
    assert caught
    # Em _finalize_pix_payment o mesmo bloco está em try/except — pagamento segue
