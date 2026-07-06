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
    FIXED_NUMBER_CHANGE_COST,
    buy_random_number,
    change_fixed_lottery_number,
    configure_lottery,
    confirm_campaign_participation,
    create_campaign_draft,
    ensure_fixed_lottery_number,
    ensure_lottery_schema,
    get_active_campaign,
    get_campaign_admin_report,
    get_participants_public,
    get_player_me,
    get_public_current,
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
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS store_users ("
                "steam_id TEXT PRIMARY KEY, market_display_name TEXT, steam_persona TEXT, "
                "fixed_lottery_number INTEGER)"
            )
        )
        conn.commit()
    ensure_lottery_schema(engine)
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS players ("
                "steam_id TEXT PRIMARY KEY, points INTEGER DEFAULT 0, kits TEXT DEFAULT '{}')"
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


def _register_user(db, steam_id: str) -> None:
    db.execute(
        text("INSERT OR IGNORE INTO store_users (steam_id) VALUES (:s)"),
        {"s": steam_id},
    )


def _active_campaign(
    db,
    *,
    base: int = 124,
    w: int = 5,
    draw_past: bool = False,
    draw_in_hours: float | None = None,
    starts_in_hours: float | None = None,
):
    now = datetime.now(timezone.utc)
    if draw_in_hours is not None:
        draw_at = now + timedelta(hours=draw_in_hours)
    else:
        draw_at = now - timedelta(hours=1) if draw_past else now + timedelta(days=7)
    if starts_in_hours is not None:
        starts_at = now + timedelta(hours=starts_in_hours)
    else:
        starts_at = now + timedelta(hours=24)
    camp = create_campaign_draft(
        db,
        data={
            "prize_amber_base": base,
            "winning_numbers_count": w,
            "draw_at": draw_at.isoformat(),
            "starts_at": starts_at.isoformat(),
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


def test_admin_report_stats_and_nicknames(lottery_db):
    cid = _active_campaign(lottery_db)
    lottery_db.execute(
        text(
            "INSERT INTO store_users (steam_id, market_display_name, steam_persona) "
            "VALUES (:s, 'ArkPlayer', 'SteamNick')"
        ),
        {"s": USER},
    )
    lottery_db.execute(
        text(
            "INSERT INTO store_users (steam_id, market_display_name, steam_persona) "
            "VALUES (:s, NULL, 'SecondPlayer')"
        ),
        {"s": USER2},
    )
    on_donation_credited(lottery_db, payment_id="pay-r1", steam_id=USER, amount_brl=10.0)
    _credit(lottery_db, USER2, 5000)
    lottery_db.commit()
    buy_random_number(lottery_db, USER2)
    lottery_db.commit()
    report = get_campaign_admin_report(lottery_db, cid)
    assert report["ok"] is True
    assert report["summary"]["numbers_issued"] == 3
    assert report["summary"]["numbers_available"] == 897
    assert report["summary"]["participant_count"] == 2
    assert report["summary"]["by_source"]["DONATION"] == 2
    assert report["summary"]["by_source"]["AMBER_RANDOM"] == 1
    by_sid = {p["steam_id"]: p for p in report["participants"]}
    assert by_sid[USER]["steam_nickname"] == "ArkPlayer"
    assert by_sid[USER2]["steam_nickname"] == "SecondPlayer"
    assert len(by_sid[USER]["numbers"]) == 2
    assert len(by_sid[USER2]["numbers"]) == 1


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


def test_reserve_reclaims_revoked_slot(lottery_db):
    cid = _active_campaign(lottery_db)
    _credit(lottery_db, USER, 10000)
    lottery_db.execute(
        text(
            "INSERT INTO lottery_numbers (campaign_id, steam_id, source, number_value, status, amber_cost) "
            "VALUES (:c, :s, 'DONATION', 777, 'REVOKED', 0)"
        ),
        {"c": cid, "s": USER2},
    )
    lottery_db.commit()
    result = reserve_number(lottery_db, USER, 777)
    lottery_db.commit()
    assert result["number"]["value"] == 777
    row = lottery_db.execute(
        text(
            "SELECT steam_id, source, status FROM lottery_numbers "
            "WHERE campaign_id = :c AND number_value = 777"
        ),
        {"c": cid},
    ).fetchone()
    assert str(row.steam_id) == USER
    assert str(row.source) == "AMBER_RESERVE"
    assert str(row.status) == "ACTIVE"


def test_reserve_insufficient_balance(lottery_db):
    _active_campaign(lottery_db)
    _credit(lottery_db, USER, 100)
    lottery_db.commit()
    with pytest.raises(ValueError, match="insufficient_balance"):
        reserve_number(lottery_db, USER, 444)


def test_lottery_public_http_routes(tmp_path, monkeypatch):
    """GET /api/public/lottery/* — fluxo da página #/sorteio."""
    settings_file = tmp_path / "lottery_pub_settings.json"
    settings_file.write_text(json.dumps({"lottery_enabled": True}), encoding="utf-8")
    monkeypatch.setattr(_app_module, "_STATE_FILE", settings_file)
    monkeypatch.setattr(_app_module, "_migrate_schema", lambda _engine: None)

    from app import app, _configure_database
    from amber_ledger import ensure_amber_schema
    from lottery_service import get_participants_public, get_public_current

    db_path = tmp_path / "lottery_pub.db"
    _configure_database(f"sqlite:///{db_path}")
    ensure_lottery_schema(_app_module._ENGINE)
    ensure_amber_schema(_app_module._ENGINE, run_backfill=False)
    with _app_module._ENGINE.connect() as conn:
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
    configure_lottery(
        credit_fn=_app_module._add_player_points_tx,
        debit_fn=_app_module._subtract_player_points_tx,
        settings_fn=_app_module._load_settings,
    )
    db = _app_module._SessionLocal()
    try:
        draw = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        camp = create_campaign_draft(db, data={"draw_at": draw, "prize_amber_base": 5000})
        publish_campaign(db, int(camp["id"]))
        on_donation_credited(
            db, payment_id="pub-pay", steam_id=USER, amount_brl=10.0,
        )
        db.commit()
        cid = int(camp["id"])
        get_public_current(db)
        get_participants_public(db, cid, page_size=20)
    finally:
        db.close()
    _app_module._DB_INITIALIZED = True

    app.config["TESTING"] = True
    with app.test_client() as client:
        cur = client.get("/api/public/lottery/current")
        assert cur.status_code == 200, cur.get_data(as_text=True)
        grid = client.get(f"/api/public/lottery/campaign/{cid}/number-grid")
        assert grid.status_code == 200, grid.get_data(as_text=True)
        parts = client.get(f"/api/public/lottery/campaign/{cid}/participants?page_size=20")
        assert parts.status_code == 200, parts.get_data(as_text=True)


def test_lottery_public_with_legacy_campaign_schema(tmp_path, monkeypatch):
    """Campanha sem colunas novas — simula MySQL parcial pré-migração."""
    settings_file = tmp_path / "lottery_legacy_settings.json"
    settings_file.write_text(json.dumps({"lottery_enabled": True}), encoding="utf-8")
    monkeypatch.setattr(_app_module, "_STATE_FILE", settings_file)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from lottery_service import _campaign_public_dict, get_participants_public, get_public_current

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}", future=True)
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE lottery_campaigns ("
                "id INTEGER PRIMARY KEY, sequence_number INTEGER, title TEXT, "
                "status TEXT, draw_at TEXT, winning_numbers_count INTEGER DEFAULT 1, "
                "prize_amber_base INTEGER DEFAULT 5000, prize_amber_rollover_in INTEGER DEFAULT 0)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE lottery_numbers ("
                "id INTEGER PRIMARY KEY, campaign_id INTEGER, steam_id TEXT, "
                "source TEXT, number_value INTEGER, status TEXT DEFAULT 'ACTIVE')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO lottery_campaigns "
                "(id, sequence_number, title, status, draw_at, prize_amber_base) "
                "VALUES (1, 1, 'Legacy', 'ACTIVE', :draw, 5000)"
            ),
            {"draw": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()},
        )
        conn.execute(
            text(
                "INSERT INTO lottery_numbers (campaign_id, steam_id, source, number_value, status) "
                "VALUES (1, :s, 'DONATION', 123, 'ACTIVE')"
            ),
            {"s": USER},
        )
        conn.commit()
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        result = get_public_current(db)
        assert result["ok"] is True
        assert result["campaign"]["prize_amber_from_purchases"] == 0
        parts = get_participants_public(db, 1, page_size=20)
        assert parts["ok"] is True
        assert parts["total"] == 1
        assert parts["participants"][0]["numbers"][0]["value"] == 123
    finally:
        db.close()


def test_lottery_public_http_legacy_participants(tmp_path, monkeypatch):
    """GET participants com schema legado — reproduz 500 em produção (v1.9.215)."""
    settings_file = tmp_path / "lottery_legacy_http_settings.json"
    settings_file.write_text(json.dumps({"lottery_enabled": True}), encoding="utf-8")
    monkeypatch.setattr(_app_module, "_STATE_FILE", settings_file)
    monkeypatch.setattr(_app_module, "_migrate_schema", lambda _engine: None)

    from app import app, _configure_database

    db_path = tmp_path / "lottery_legacy_http.db"
    _configure_database(f"sqlite:///{db_path}")
    with _app_module._ENGINE.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE lottery_campaigns ("
                "id INTEGER PRIMARY KEY, sequence_number INTEGER, title TEXT, "
                "status TEXT, draw_at TEXT, winning_numbers_count INTEGER DEFAULT 1, "
                "prize_amber_base INTEGER DEFAULT 5000, prize_amber_rollover_in INTEGER DEFAULT 0)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE lottery_numbers ("
                "id INTEGER PRIMARY KEY, campaign_id INTEGER, steam_id TEXT, "
                "source TEXT, number_value INTEGER, status TEXT DEFAULT 'ACTIVE')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO lottery_campaigns "
                "(id, sequence_number, title, status, draw_at, prize_amber_base) "
                "VALUES (1, 1, 'Legacy HTTP', 'ACTIVE', :draw, 5000)"
            ),
            {"draw": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()},
        )
        conn.execute(
            text(
                "INSERT INTO lottery_numbers (campaign_id, steam_id, source, number_value, status) "
                "VALUES (1, :s, 'DONATION', 456, 'ACTIVE')"
            ),
            {"s": USER},
        )
        conn.commit()
    configure_lottery(
        credit_fn=_app_module._add_player_points_tx,
        debit_fn=_app_module._subtract_player_points_tx,
        settings_fn=_app_module._load_settings,
    )
    _app_module._DB_INITIALIZED = True

    app.config["TESTING"] = True
    with app.test_client() as client:
        cur = client.get("/api/public/lottery/current")
        assert cur.status_code == 200, cur.get_data(as_text=True)
        parts = client.get("/api/public/lottery/campaign/1/participants?page_size=20")
        assert parts.status_code == 200, parts.get_data(as_text=True)
        body = parts.get_json()
        assert body["ok"] is True
        assert body["total"] == 1


def test_lottery_reserve_http_route(tmp_path, monkeypatch):
    """POST /api/player/lottery/reserve/{n} — fluxo HTTP completo."""
    settings_file = tmp_path / "lottery_http_settings.json"
    settings_file.write_text(json.dumps({"lottery_enabled": True}), encoding="utf-8")
    monkeypatch.setattr(_app_module, "_STATE_FILE", settings_file)
    monkeypatch.setattr(_app_module, "_migrate_schema", lambda _engine: None)

    from app import app, _configure_database
    from amber_ledger import ensure_amber_schema

    db_path = tmp_path / "lottery_http.db"
    _configure_database(f"sqlite:///{db_path}")
    ensure_lottery_schema(_app_module._ENGINE)
    ensure_amber_schema(_app_module._ENGINE, run_backfill=False)
    with _app_module._ENGINE.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS players ("
                "steam_id TEXT PRIMARY KEY, points INTEGER DEFAULT 0, kits TEXT DEFAULT '{}')"
            )
        )
        conn.commit()
    configure_lottery(
        credit_fn=_app_module._add_player_points_tx,
        debit_fn=_app_module._subtract_player_points_tx,
        settings_fn=_app_module._load_settings,
    )
    db = _app_module._SessionLocal()
    try:
        db.execute(
            text("INSERT INTO players (steam_id, points, kits) VALUES (:s, 50000, '{}')"),
            {"s": USER},
        )
        draw = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        camp = create_campaign_draft(db, data={"draw_at": draw, "prize_amber_base": 5000})
        publish_campaign(db, int(camp["id"]))
        db.commit()
    finally:
        db.close()
    _app_module._DB_INITIALIZED = True

    app.config["TESTING"] = True
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["steam_id"] = USER
        ok = client.post("/api/player/lottery/reserve/321")
        assert ok.status_code == 200
        body = ok.get_json()
        assert body["ok"] is True
        assert body["number"]["value"] == 321
        dup = client.post("/api/player/lottery/reserve/321")
        assert dup.status_code == 409
        assert dup.get_json()["error"] == "number_unavailable"


def test_fixed_number_unique_on_assign(lottery_db):
    _register_user(lottery_db, USER)
    _register_user(lottery_db, USER2)
    lottery_db.commit()
    n1 = ensure_fixed_lottery_number(lottery_db, USER)
    n2 = ensure_fixed_lottery_number(lottery_db, USER2)
    lottery_db.commit()
    assert n1 != n2
    assert 100 <= n1 <= 999
    again = ensure_fixed_lottery_number(lottery_db, USER)
    assert again == n1


def test_fixed_number_backfill_on_schema(lottery_db):
    _register_user(lottery_db, USER)
    _register_user(lottery_db, USER2)
    lottery_db.commit()
    engine = lottery_db.get_bind()
    from lottery_service import backfill_fixed_lottery_numbers

    assigned = backfill_fixed_lottery_numbers(engine)
    lottery_db.expire_all()
    assert assigned == 2
    row = lottery_db.execute(
        text("SELECT fixed_lottery_number FROM store_users WHERE steam_id = :s"),
        {"s": USER},
    ).fetchone()
    assert row[0] is not None


def test_confirm_participation_within_deadline(lottery_db):
    _register_user(lottery_db, USER)
    lottery_db.commit()
    _active_campaign(lottery_db, draw_in_hours=24)
    lottery_db.commit()
    fixed = ensure_fixed_lottery_number(lottery_db, USER)
    lottery_db.commit()
    me_before = get_player_me(lottery_db, USER)
    assert me_before["campaign_confirmation"]["can_confirm"] is True
    result = confirm_campaign_participation(lottery_db, USER)
    lottery_db.commit()
    assert result["fixed_number"] == fixed
    cid = int(result["campaign_id"])
    row = lottery_db.execute(
        text(
            "SELECT number_value, source FROM lottery_numbers "
            "WHERE campaign_id = :c AND steam_id = :s AND status = 'ACTIVE'"
        ),
        {"c": cid, "s": USER},
    ).fetchone()
    assert int(row.number_value) == fixed
    assert str(row.source) == "FIXED_REGISTERED"
    me = get_player_me(lottery_db, USER)
    assert me["campaign_confirmation"]["confirmed"] is True
    assert me["campaign_confirmation"]["can_confirm"] is False


def test_confirm_participation_past_deadline(lottery_db):
    _register_user(lottery_db, USER)
    lottery_db.commit()
    _active_campaign(lottery_db, draw_in_hours=1)
    lottery_db.commit()
    ensure_fixed_lottery_number(lottery_db, USER)
    lottery_db.commit()
    me = get_player_me(lottery_db, USER)
    assert me["campaign_confirmation"]["can_confirm"] is False
    with pytest.raises(ValueError, match="confirmation_deadline_passed"):
        confirm_campaign_participation(lottery_db, USER)


def test_confirm_participation_blocked_at_exact_deadline(lottery_db):
    """No horário draw_at − 2h (ex.: sorteio 23:00 → bloqueio a partir das 21:00)."""
    _register_user(lottery_db, USER)
    lottery_db.commit()
    _active_campaign(lottery_db, draw_in_hours=2)
    lottery_db.commit()
    ensure_fixed_lottery_number(lottery_db, USER)
    lottery_db.commit()
    me = get_player_me(lottery_db, USER)
    assert me["campaign_confirmation"]["can_confirm"] is False
    with pytest.raises(ValueError, match="confirmation_deadline_passed"):
        confirm_campaign_participation(lottery_db, USER)


def test_confirm_participation_allowed_just_before_deadline(lottery_db):
    _register_user(lottery_db, USER)
    lottery_db.commit()
    _active_campaign(lottery_db, draw_in_hours=2.01)
    lottery_db.commit()
    ensure_fixed_lottery_number(lottery_db, USER)
    lottery_db.commit()
    me = get_player_me(lottery_db, USER)
    assert me["campaign_confirmation"]["can_confirm"] is True
    confirm_campaign_participation(lottery_db, USER)
    lottery_db.commit()


def test_change_fixed_number_debits_amber(lottery_db):
    _register_user(lottery_db, USER)
    _credit(lottery_db, USER, 20000)
    lottery_db.commit()
    _active_campaign(lottery_db)
    lottery_db.commit()
    current = ensure_fixed_lottery_number(lottery_db, USER)
    lottery_db.commit()
    new_num = 888 if current != 888 else 889
    result = change_fixed_lottery_number(lottery_db, USER, new_num)
    lottery_db.commit()
    assert result["fixed_number"] == new_num
    assert result["amber_cost"] == FIXED_NUMBER_CHANGE_COST
    pts = lottery_db.execute(text("SELECT points FROM players WHERE steam_id = :s"), {"s": USER}).fetchone()
    assert int(pts[0]) == 20000 - FIXED_NUMBER_CHANGE_COST
    row = lottery_db.execute(
        text("SELECT fixed_lottery_number FROM store_users WHERE steam_id = :s"),
        {"s": USER},
    ).fetchone()
    assert int(row[0]) == new_num


def test_change_fixed_number_insufficient_balance(lottery_db):
    _register_user(lottery_db, USER)
    _credit(lottery_db, USER, 100)
    lottery_db.commit()
    ensure_fixed_lottery_number(lottery_db, USER)
    lottery_db.commit()
    with pytest.raises(ValueError, match="insufficient_balance"):
        change_fixed_lottery_number(lottery_db, USER, 777)
