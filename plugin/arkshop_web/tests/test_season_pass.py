"""Testes Season Pass — calendário, XP cap, claims, Premium."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app as _app_module
from app import app
import season_pass_config as spcfg
import season_pass_service as sps

ADMIN_STEAM = "76561198000000001"
USER_STEAM = "76561198000000002"


def _xp_at(level: int) -> int:
    """XP cumulativo exacto para atingir o nível (thresholds live da curva)."""
    return int(spcfg.build_xp_thresholds()[int(level) - 1])


@pytest.fixture(autouse=True)
def _sp_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_WEB_SECRET", "test-secret")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]), encoding="utf-8")
    (tmp_path / "settings.json").write_text("{}", encoding="utf-8")
    cfg_path = tmp_path / "season_pass_config.json"
    claims_path = tmp_path / "season_pass_claims.json"
    monkeypatch.setattr(_app_module, "_SEASON_PASS_CONFIG_FILE", cfg_path)
    monkeypatch.setattr(_app_module, "_SEASON_PASS_CLAIMS_FILE", claims_path)
    spcfg.configure_season_pass(config_file=cfg_path, claims_file=claims_path)
    yield


@pytest.fixture
def client(tmp_path, monkeypatch):
    catalog = tmp_path / "config.json"
    catalog.write_text(json.dumps({"Settings": {}}), encoding="utf-8")
    servers_file = tmp_path / "servers.json"
    servers_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", servers_file)
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def sp_db(tmp_path):
    path = tmp_path / "sp.db"
    engine = create_engine(f"sqlite:///{path}", future=True)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE players (steam_id TEXT PRIMARY KEY, points INTEGER NOT NULL DEFAULT 0, kits TEXT DEFAULT '{}')"
        ))
        conn.execute(text(
            "CREATE TABLE orders ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "order_id TEXT UNIQUE, steam_id TEXT, server_id TEXT,"
            "item_type TEXT, item_id TEXT, amount INTEGER,"
            "points_spent INTEGER DEFAULT 0, status TEXT,"
            "original_order_id TEXT, created_at TEXT, updated_at TEXT)"
        ))
        conn.execute(text(
            "CREATE TABLE arkbank_state ("
            "id INTEGER PRIMARY KEY CHECK (id = 1),"
            "balance INTEGER NOT NULL DEFAULT 0,"
            "updated_at DATETIME, version INTEGER DEFAULT 0)"
        ))
        conn.execute(text(
            "CREATE TABLE arkbank_transactions ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "created_at DATETIME, tx_type TEXT, amount INTEGER,"
            "balance_after INTEGER, steam_id TEXT, ref_table TEXT,"
            "ref_id TEXT, map_id TEXT, idempotency_key TEXT UNIQUE,"
            "metadata_json TEXT, created_by_admin TEXT)"
        ))
    sps.ensure_season_pass_schema(engine)
    from arkbank_service import ensure_arkbank_schema
    ensure_arkbank_schema(engine)
    Session = sessionmaker(bind=engine, future=True)
    db = Session()
    db.execute(
        text("INSERT INTO players (steam_id, points) VALUES (:s, 100000)"),
        {"s": USER_STEAM},
    )
    db.commit()

    def subtract(db_, sid, amt):
        row = db_.execute(text("SELECT points FROM players WHERE steam_id=:s"), {"s": sid}).fetchone()
        bal = int(row[0]) if row else 0
        if bal < amt:
            raise ValueError("insufficient_balance")
        nb = bal - amt
        db_.execute(text("UPDATE players SET points=:p WHERE steam_id=:s"), {"p": nb, "s": sid})
        return nb

    def add(db_, sid, amt):
        db_.execute(
            text("UPDATE players SET points = points + :a WHERE steam_id=:s"),
            {"a": amt, "s": sid},
        )
        row = db_.execute(text("SELECT points FROM players WHERE steam_id=:s"), {"s": sid}).fetchone()
        return int(row[0])

    def queue(db_, *, steam_id, item_type, item_id, amount, original_order_id):
        oid = f"ord-{original_order_id}"
        db_.execute(
            text(
                "INSERT INTO orders (order_id, steam_id, server_id, item_type, item_id, amount, "
                "points_spent, status, original_order_id, created_at, updated_at) "
                "VALUES (:oid,:sid,'default',:it,:iid,:amt,0,'PENDENTE',:orig,'now','now')"
            ),
            {
                "oid": oid, "sid": steam_id, "it": item_type, "iid": item_id,
                "amt": amount, "orig": original_order_id,
            },
        )
        return oid

    def reset_pending(db_, order_id):
        db_.execute(
            text("UPDATE orders SET status='PENDENTE', updated_at='now' WHERE order_id=:oid"),
            {"oid": order_id},
        )

    granted = []

    def grant_lic(db_, sid, group, days, *, source=""):
        granted.append({"sid": sid, "group": group, "days": days, "source": source})

    from arkbank_service import credit_season_pass_premium

    sps.configure_engine(
        subtract_points_tx=subtract,
        add_points_tx=add,
        credit_arkbank_premium=lambda db_, **kw: credit_season_pass_premium(db_, **kw),
        queue_catalog_order=queue,
        reset_order_to_pending=reset_pending,
        grant_license=grant_lic,
        get_entitlements=lambda sid, db=None: [],
        license_catalog_price=lambda g: 5000,
    )
    try:
        yield db, granted
    finally:
        db.close()


def _login(client, steam_id: str):
    with client.session_transaction() as sess:
        sess["steam_id"] = steam_id


def test_default_seed_has_typed_amber_and_ready_skus():
    cfg = spcfg.load_config()
    assert cfg["current_tier"] == "Delta"
    assert cfg.get("season_id") is None
    assert cfg["premium_price_by_tier"]["Delta"] == 15_000
    free4 = cfg["free_rewards"]["4"]
    assert free4[0]["type"] == "amber"
    assert free4[0]["grant_ready"] is True
    pending = []
    for track in ("free_rewards", "premium_rewards"):
        for lv, grants in (cfg.get(track) or {}).items():
            for g in grants:
                if not g.get("grant_ready"):
                    pending.append((track, lv, g.get("type"), g.get("id"), g.get("label")))
    assert pending == [], pending
    assert cfg["free_rewards"]["16"][0]["id"] == "cryopod"
    assert cfg["premium_rewards"]["21"][0]["id"] == "moschops_pack10"


def test_calendar_inactive_by_default():
    cfg = spcfg.load_config()
    assert sps.compute_status(cfg) == "inactive"
    season = sps.season_public(cfg)
    assert season["status"] == "inactive"
    assert season["starts_at"] is None


def test_start_season_sets_calendar():
    now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    cfg = sps.start_season(now=now)
    assert sps.compute_status(cfg, now=now) == "active"
    assert cfg["season_id"].startswith("season-delta-")
    assert cfg["starts_at"]
    assert cfg["ends_at"]
    ends = datetime.fromisoformat(cfg["ends_at"].replace("Z", "+00:00"))
    assert (ends - now).days == 30
    left = sps.days_remaining(cfg, now=now)
    assert left == 30


def test_auto_claim_window_after_ends():
    now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    cfg = sps.start_season(now=now)
    later = now + timedelta(days=31)
    assert sps.compute_status(cfg, now=later) == "claim_window"
    assert sps.days_remaining(cfg, now=later) == 0


def test_start_next_advances_tier():
    now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    sps.start_season(now=now)
    later = now + timedelta(days=31)
    cfg2 = sps.start_season(advance_tier=True, now=later)
    assert cfg2["current_tier"] == "Gamma"
    assert sps.compute_status(cfg2, now=later) == "active"
    assert "gamma" in cfg2["season_id"]


def test_xp_cap_freeze(sp_db):
    db, _ = sp_db
    now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    sps.start_season(now=now)
    near = sps.MAX_XP - 100
    r1 = sps.add_timed_xp(db, steam_id=USER_STEAM, amount=near, map_id="ragnarok", cycle_key="c1")
    assert r1["applied"] is True
    assert r1["xp_after"] == near
    r2 = sps.add_timed_xp(db, steam_id=USER_STEAM, amount=200, map_id="ragnarok", cycle_key="c2")
    assert r2["applied"] is True
    assert r2["xp_after"] == sps.MAX_XP
    assert r2["xp_added"] == 100
    r3 = sps.add_timed_xp(db, steam_id=USER_STEAM, amount=100, map_id="aberration", cycle_key="c3")
    assert r3["applied"] is False
    assert r3.get("frozen") is True or r3.get("reason") == "xp_cap"
    prog = sps.get_progress(db, USER_STEAM, spcfg.load_config()["season_id"])
    assert prog["xp"] == sps.MAX_XP


def test_xp_progressive_curve_and_level_boundaries():
    """Curva +25%/Δ com B=3 → Free L28=6192 (≤7500), L30=9682; free ×4; boundaries."""
    assert spcfg.XP_BASE == 3
    assert spcfg.XP_GROWTH == 1.25
    thr = spcfg.build_xp_thresholds()
    assert len(thr) == 30
    assert thr == list(spcfg._XP_THRESHOLDS)
    assert thr[0] == 3
    assert thr[27] == 6192  # last Free
    assert thr[-1] == spcfg.MAX_XP == sps.MAX_XP == 9682
    assert thr[27] <= 7500  # finishable @ 30d × 5h × 25Â

    expected_deltas = [max(1, round(3 * (1.25 ** (n - 1)))) for n in range(1, 31)]
    for n, d in enumerate(expected_deltas, start=1):
        assert spcfg.xp_delta(n) == d
    running = 0
    for i, d in enumerate(expected_deltas):
        running += d
        assert thr[i] == running

    free_xp = {
        4: 18,
        8: 59,
        12: 162,
        16: 414,
        20: 1029,
        24: 2529,
        28: 6192,
    }
    for lv, xp in free_xp.items():
        assert thr[lv - 1] == xp
        assert spcfg.level_from_xp(xp, thr)["level"] == lv

    assert spcfg.level_from_xp(0, thr)["level"] == 0
    assert spcfg.level_from_xp(thr[0] - 1, thr)["level"] == 0
    assert spcfg.level_from_xp(thr[0], thr)["level"] == 1
    mid = thr[3] + 1  # past L4, before L5
    prog = spcfg.level_from_xp(mid, thr)
    assert prog["level"] == 4
    assert prog["next_level"] == 5
    assert prog["xp_to_next"] == thr[4] - mid
    top = spcfg.level_from_xp(thr[-1], thr)
    assert top["level"] == 30
    assert top["next_level"] is None
    assert top["xp_to_next"] == 0


def test_xp_idempotent_and_inactive(sp_db):
    db, _ = sp_db
    r = sps.add_timed_xp(db, steam_id=USER_STEAM, amount=25, map_id="m", cycle_key="k")
    assert r["applied"] is False
    assert "inactive" in r.get("reason", "")
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)
    a = sps.add_timed_xp(db, steam_id=USER_STEAM, amount=25, map_id="m", cycle_key="k")
    b = sps.add_timed_xp(db, steam_id=USER_STEAM, amount=25, map_id="m", cycle_key="k")
    assert a["applied"] is True
    assert b.get("duplicate") is True


def test_timed_outbox_consumer_applies_season_xp(sp_db):
    """Caminho produção: scheduler → process_timed_outbox → add_timed_xp."""
    from arkbank_service import (
        credit,
        enqueue_timed_outbox,
        get_balance,
        process_timed_outbox,
    )

    db, _ = sp_db
    now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    sps.start_season(now=now)
    credit(
        db,
        tx_type="catalog_spend",
        amount=1000,
        idempotency_key="arkbank:test:sp-seed",
        commit=True,
    )
    enqueue_timed_outbox(
        db,
        steam_id=USER_STEAM,
        amount=40,
        map_id="Ragnarok",
        cycle_key="cycle-sp-xp-1",
        commit=True,
    )
    out = process_timed_outbox(db, batch_size=50)
    assert out["processed"] == 1
    assert out.get("season_pass_xp") == 1
    assert get_balance(db) == 960
    season_id = spcfg.load_config()["season_id"]
    prog = sps.get_progress(db, USER_STEAM, season_id)
    assert prog["xp"] == 40
    # Reprocessar não duplica XP nem debito
    out2 = process_timed_outbox(db, batch_size=50)
    assert out2["processed"] == 0
    assert sps.get_progress(db, USER_STEAM, season_id)["xp"] == 40


def test_claim_eligibility():
    ok, _ = sps.claim_eligibility(
        status="active", track="free", level=4, player_level=4, premium=False, claimed=set()
    )
    assert ok is True
    ok, err = sps.claim_eligibility(
        status="active", track="premium", level=1, player_level=5, premium=False, claimed=set()
    )
    assert ok is False
    assert "Premium" in (err or "")
    ok, _ = sps.claim_eligibility(
        status="claim_window", track="free", level=4, player_level=10, premium=False, claimed=set()
    )
    assert ok is True
    ok, _ = sps.claim_eligibility(
        status="inactive", track="free", level=4, player_level=10, premium=False, claimed=set()
    )
    assert ok is False


def test_buy_premium_debits_and_arks(sp_db):
    db, _ = sp_db
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)
    before = int(db.execute(text("SELECT points FROM players WHERE steam_id=:s"), {"s": USER_STEAM}).scalar())
    result = sps.buy_premium(db, USER_STEAM)
    assert result["ok"] is True
    assert result["premium"] is True
    after = int(db.execute(text("SELECT points FROM players WHERE steam_id=:s"), {"s": USER_STEAM}).scalar())
    assert before - after == 15_000
    from arkbank_service import get_balance
    assert get_balance(db) == 15_000
    again = sps.buy_premium(db, USER_STEAM)
    assert again["already_owned"] is True


def test_claim_amber_free(sp_db):
    db, _ = sp_db
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)
    sid = spcfg.load_config()["season_id"]
    sps._upsert_progress(db, steam_id=USER_STEAM, season_id=sid, xp=_xp_at(4), premium=False, claimed=set())
    db.commit()
    before = int(db.execute(text("SELECT points FROM players WHERE steam_id=:s"), {"s": USER_STEAM}).scalar())
    result = sps.claim_reward(db, steam_id=USER_STEAM, track="free", level=4)
    assert result["ok"] is True
    assert result["in_game_delivered"] is True
    after = int(db.execute(text("SELECT points FROM players WHERE steam_id=:s"), {"s": USER_STEAM}).scalar())
    assert after - before == 500
    # UI usa new_balance/points_after para refrescar a pílula sem esperar cooldown.
    assert result["new_balance"] == after
    assert result["points_after"] == after


def test_preview_inactive_not_fake_active(client):
    r = client.get("/api/season-pass/preview")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["season"]["status"] == "inactive"
    assert data["premium"]["purchase_enabled"] is False
    free = data["tracks"]["free"]
    n4 = next(x for x in free if x["level"] == 4)
    assert n4["claimable"] is False


def test_admin_start_season_api(client):
    _login(client, ADMIN_STEAM)
    r = client.post("/api/admin/season-pass/start", json={})
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["ok"] is True
    assert body["season"]["status"] == "active"
    meta = client.get("/api/season-pass/meta").get_json()
    assert meta["status"] == "active"
    assert meta["days_remaining"] is not None


def test_admin_config_requires_admin(client):
    r = client.get("/api/admin/season-pass/config")
    assert r.status_code == 401
    _login(client, USER_STEAM)
    r2 = client.get("/api/admin/season-pass/config")
    assert r2.status_code == 403


def test_admin_get_put_config_preserves_calendar(client):
    _login(client, ADMIN_STEAM)
    client.post("/api/admin/season-pass/start", json={})
    season_id = client.get("/api/admin/season-pass/config").get_json()["config"]["season_id"]
    payload = {
        "current_tier": "Delta",
        "duration_days": 30,
        "premium_price_by_tier": {
            "Delta": 15_500,
            "Gamma": 18_000,
            "Beta": 22_000,
            "Alfa": 28_000,
            "Omega": 35_000,
            "Transcendente": 45_000,
        },
        "free_rewards": {
            "4": [{"type": "amber", "qty": 600, "label": "600 Â"}],
        },
        "premium_rewards": {
            "1": [{"type": "amber", "qty": 300}],
        },
    }
    put = client.put("/api/admin/season-pass/config", json=payload)
    assert put.status_code == 200, put.get_json()
    cfg = put.get_json()["config"]
    assert cfg["premium_price_by_tier"]["Delta"] == 15_500
    assert cfg["season_id"] == season_id
    assert cfg["starts_at"]


def test_player_has_higher_license():
    assert sps.player_has_higher_license([{"group": "Alfa"}], "Delta") is True
    assert sps.player_has_higher_license([{"group": "Delta"}], "Alfa") is False
    assert sps.player_has_higher_license([], "Delta") is False
    assert sps.player_has_higher_license(
        [{"group": "Delta"}, {"group": "Exotico"}], "Alfa",
    ) is True


def test_player_can_accept_license_unlimited_tiers():
    assert sps.player_can_accept_license([], "Delta") is True
    assert sps.player_can_accept_license([{"group": "Delta"}], "Gamma") is True
    assert sps.player_can_accept_license(
        [{"group": "Delta"}, {"group": "Gamma"}], "Alfa",
    ) is True
    assert sps.player_can_accept_license(
        [{"group": "Delta"}, {"group": "Gamma"}, {"group": "Beta"}], "Alfa",
    ) is True
    assert sps.player_can_accept_license(
        [{"group": "Delta"}, {"group": "Gamma"}], "Delta",
    ) is True


def test_third_tier_no_slots_full_choice():
    """Slots cheios deixam de forçar escolha; só tier superior exige licença↔Â."""
    alfa_grant = [{
        "type": "license",
        "id": "Alfa",
        "days": 30,
        "label": "Licença Alfa",
    }]
    assert sps.license_choice_needed(
        [{"group": "Delta"}, {"group": "Gamma"}], alfa_grant,
    ) is None
    assert sps.license_choice_needed(
        [{"group": "Delta"}, {"group": "Gamma"}, {"group": "Beta"}], alfa_grant,
    ) is None
    needed = sps.license_choice_needed(
        [{"group": "Alfa"}],
        [{"type": "license", "id": "Delta", "days": 30, "label": "Delta"}],
    )
    assert needed is not None
    assert needed["reason"] == "higher_tier"


def test_higher_license_choice_amber(sp_db):
    db, granted = sp_db
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)
    sid = spcfg.load_config()["season_id"]
    # bump XP to L29 + set premium
    sps._upsert_progress(db, steam_id=USER_STEAM, season_id=sid, xp=_xp_at(29), premium=True, claimed=set())
    db.commit()
    sps.configure_engine(get_entitlements=lambda sid, db=None: [{"group": "Alfa"}])
    before = int(db.execute(text("SELECT points FROM players WHERE steam_id=:s"), {"s": USER_STEAM}).scalar())
    with pytest.raises(ValueError, match="license_choice"):
        sps.claim_reward(db, steam_id=USER_STEAM, track="premium", level=29)
    db.rollback()
    result = sps.claim_reward(
        db, steam_id=USER_STEAM, track="premium", level=29, license_choice="amber"
    )
    assert result["ok"] is True
    after = int(db.execute(text("SELECT points FROM players WHERE steam_id=:s"), {"s": USER_STEAM}).scalar())
    assert after - before == 5000
    assert granted == []


def test_collective_meta_disabled_by_default():
    cfg = spcfg.load_config()
    assert int(cfg.get("meta_target_amber") or 0) == 0
    meta = sps.collective_meta_public(cfg, None, latch=False)
    assert meta["enabled"] is False
    assert meta["meta_reached"] is False
    assert meta["event_auto_fire"] is False


def test_collective_meta_progress_is_season_inflow_not_balance(sp_db):
    db, _ = sp_db
    now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    sps.start_season(now=now)
    spcfg.save_config({
        **spcfg.load_config(),
        "meta_target_amber": 20_000,
    })
    from arkbank_service import (
        TX_CATALOG_SPEND,
        TX_TIMED_REWARD,
        credit,
        debit,
        get_balance,
        season_meta_inflow,
    )

    # Inflow conta para meta
    credit(
        db,
        tx_type=TX_CATALOG_SPEND,
        amount=12_000,
        idempotency_key="test:meta:catalog",
        steam_id=USER_STEAM,
        commit=True,
    )
    # Outflow TimedPoints muda o saldo mas NÃO conta como progresso
    debit(
        db,
        tx_type=TX_TIMED_REWARD,
        amount=5_000,
        idempotency_key="test:meta:timed",
        steam_id=USER_STEAM,
        map_id="ragnarok",
        commit=True,
    )
    cfg = spcfg.load_config()
    starts = cfg["starts_at"]
    inflow = season_meta_inflow(db, since=starts)
    assert inflow["progress"] == 12_000
    assert get_balance(db) == 7_000  # 12k - 5k
    meta = sps.collective_meta_public(cfg, db, latch=True)
    assert meta["progress_amber"] == 12_000
    assert meta["vault_balance"] == 7_000
    assert meta["meta_reached"] is False
    assert meta["percent"] == 60

    # Mais inflow até atingir meta → latch
    credit(
        db,
        tx_type=TX_CATALOG_SPEND,
        amount=8_000,
        idempotency_key="test:meta:catalog2",
        steam_id=USER_STEAM,
        commit=True,
    )
    meta2 = sps.collective_meta_public(spcfg.load_config(), db, latch=True)
    assert meta2["progress_amber"] == 20_000
    assert meta2["meta_reached"] is True
    assert meta2["percent"] == 100
    assert meta2["status"] == "reached_pending_schedule"
    latched = spcfg.load_config()
    assert latched["meta_reached"] is True
    assert latched["meta_reached_at"]


def test_collective_meta_admin_schedules_event_no_autofire(client):
    _login(client, ADMIN_STEAM)
    client.post("/api/admin/season-pass/start", json={})
    put = client.put("/api/admin/season-pass/config", json={
        "meta_target_amber": 100_000,
        "meta_event_at": "2026-08-10 21:00 BRT",
        "meta_event_notes": "Boss fight Ragnarok",
    })
    assert put.status_code == 200, put.get_json()
    cfg = put.get_json()["config"]
    assert cfg["meta_target_amber"] == 100_000
    assert cfg["meta_event_at"] == "2026-08-10 21:00 BRT"
    assert "Boss fight" in cfg["meta_event_notes"]
    meta = put.get_json()["collective_meta"]
    assert meta["event_auto_fire"] is False
    assert meta["event_at"] == "2026-08-10 21:00 BRT"
    preview = client.get("/api/season-pass/preview").get_json()
    assert "collective_meta" in preview
    assert preview["collective_meta"]["target_amber"] == 100_000


def test_start_next_season_resets_meta_latch():
    now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    sps.start_season(now=now)
    spcfg.save_config({
        **spcfg.load_config(),
        "meta_target_amber": 50_000,
        "meta_reached": True,
        "meta_reached_at": "2026-07-20T12:00:00+00:00",
        "meta_event_at": "2026-07-25",
        "meta_event_notes": "evento velho",
    })
    later = now + timedelta(days=31)
    cfg2 = sps.start_season(advance_tier=True, now=later)
    assert cfg2["meta_reached"] is False
    assert cfg2["meta_reached_at"] is None
    assert cfg2["meta_event_at"] is None
    assert cfg2["meta_event_notes"] == ""
    # target pode persistir entre seasons
    assert int(cfg2.get("meta_target_amber") or 0) == 50_000


def test_higher_license_choice_license(sp_db):
    db, granted = sp_db
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)
    sid = spcfg.load_config()["season_id"]
    sps._upsert_progress(db, steam_id=USER_STEAM, season_id=sid, xp=_xp_at(29), premium=True, claimed=set())
    db.commit()
    sps.configure_engine(get_entitlements=lambda sid, db=None: [{"group": "Alfa"}])
    result = sps.claim_reward(
        db, steam_id=USER_STEAM, track="premium", level=29, license_choice="license"
    )
    assert result["ok"] is True
    assert len(granted) == 1
    assert granted[0]["group"] == "Delta"
    assert granted[0]["days"] == 30


def test_claim_window_ok_until_next_season(sp_db):
    db, _ = sp_db
    # Season no passado → wall-clock actual cai em claim_window
    started = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    sps.start_season(now=started)
    old_sid = spcfg.load_config()["season_id"]
    assert sps.compute_status(spcfg.load_config()) == "claim_window"
    sps._upsert_progress(db, steam_id=USER_STEAM, season_id=old_sid, xp=_xp_at(4), premium=False, claimed=set())
    db.commit()

    result = sps.claim_reward(db, steam_id=USER_STEAM, track="free", level=4)
    assert result["ok"] is True

    # Próxima season → season_id muda; progresso da anterior não conta
    next_at = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    sps.start_season(advance_tier=True, now=next_at)
    new_sid = spcfg.load_config()["season_id"]
    assert new_sid != old_sid
    with pytest.raises(ValueError, match="ainda não atingido"):
        sps.claim_reward(db, steam_id=USER_STEAM, track="free", level=4)


def test_sku_pending_blocks_before_side_effects(sp_db):
    db, _ = sp_db
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)
    sid = spcfg.load_config()["season_id"]
    sps._upsert_progress(db, steam_id=USER_STEAM, season_id=sid, xp=_xp_at(2), premium=True, claimed=set())
    db.commit()
    before = int(db.execute(text("SELECT points FROM players WHERE steam_id=:s"), {"s": USER_STEAM}).scalar())
    # Premium L2 seed is amber-ready; inject a pending kit alongside amber to force preflight
    with spcfg._lock:
        cfg = spcfg.load_config()
        cfg["premium_rewards"]["2"] = [
            {"type": "amber", "qty": 999},
            {"type": "kit", "id": None, "label": "Kit TBD"},
        ]
        spcfg.save_config(cfg)
    with pytest.raises(ValueError, match="sku_pending"):
        sps.claim_reward(db, steam_id=USER_STEAM, track="premium", level=2)
    db.rollback()
    after = int(db.execute(text("SELECT points FROM players WHERE steam_id=:s"), {"s": USER_STEAM}).scalar())
    assert after == before  # no partial amber credit


def test_claim_kit_item_dino_queue(sp_db):
    """Claim kit/item/dino com season_id longo (formato prod) — fila PENDENTE."""
    db, _ = sp_db
    from app import Order

    max_len = int(Order.original_order_id.type.length or 0)
    long_season = "season-delta-20240715032535"
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)
    with spcfg._lock:
        cfg = spcfg.load_config()
        cfg["season_id"] = long_season
        cfg["premium_rewards"]["3"] = [
            {"type": "kit", "id": "kit_test_sp", "qty": 1, "label": "Kit test"},
            {"type": "item", "id": "cryopod", "qty": 2, "label": "Cryo"},
            {"type": "dino", "id": "dino_spino", "qty": 1, "label": "Spino"},
        ]
        spcfg.save_config(cfg)
    sps._upsert_progress(
        db, steam_id=USER_STEAM, season_id=long_season, xp=_xp_at(3), premium=True, claimed=set()
    )
    db.commit()
    result = sps.claim_reward(db, steam_id=USER_STEAM, track="premium", level=3)
    assert result["ok"] is True
    # Fila ≠ entrega in-game — flag não pode mentir ao staff/UI.
    assert result["in_game_delivered"] is False
    assert result["queued_for_shop"] is True
    types = {d["type"] for d in result["delivery"]}
    assert types == {"kit", "item", "dino"}
    assert all(d.get("pending_order") for d in result["delivery"])
    rows = db.execute(
        text("SELECT item_type, item_id, amount, status, original_order_id FROM orders ORDER BY id")
    ).fetchall()
    assert len(rows) == 3
    assert {r[0] for r in rows} == {"kit", "shop"}
    assert all(r[3] == "PENDENTE" for r in rows)
    for orig in (str(r[4]) for r in rows):
        assert long_season in orig
        assert len(orig) <= max_len, orig
    # Idempotent re-queue via same original key should not duplicate after already claimed
    with pytest.raises(ValueError, match="Já resgatado"):
        sps.claim_reward(db, steam_id=USER_STEAM, track="premium", level=3)


def test_claim_long_season_id_kit_dino_no_data_error(sp_db):
    """Prod: season-delta-… + kit skip prefix > VARCHAR(64) → DataError 1406."""
    db, _ = sp_db
    from app import Order

    max_len = int(Order.original_order_id.type.length or 0)
    assert max_len >= 191

    long_season = "season-delta-20240715032535"
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)

    def queue_prod_shape(db_, *, steam_id, item_type, item_id, amount, original_order_id):
        # Espelha _season_pass_queue_catalog_order: kits guardam skip prefix.
        stored = (
            f"__admin_skip_kit_limit__|{original_order_id}"
            if item_type == "kit"
            else str(original_order_id)
        )
        if len(stored) > max_len:
            raise Exception(
                '(pymysql.err.DataError) (1406, "Data too long for column '
                "'original_order_id' at row 1\")"
            )
        assert len(stored) > 64, stored  # teria falhado no schema antigo
        oid = f"ord-{abs(hash(stored)) % 10_000_000}"
        db_.execute(
            text(
                "INSERT INTO orders (order_id, steam_id, server_id, item_type, item_id, amount, "
                "points_spent, status, original_order_id, created_at, updated_at) "
                "VALUES (:oid,:sid,'default',:it,:iid,:amt,0,'PENDENTE',:orig,'now','now')"
            ),
            {
                "oid": oid,
                "sid": steam_id,
                "it": item_type,
                "iid": item_id,
                "amt": amount,
                "orig": stored,
            },
        )
        return oid

    sps.configure_engine(
        subtract_points_tx=sps._cbs["subtract_points_tx"],
        add_points_tx=sps._cbs["add_points_tx"],
        credit_arkbank_premium=sps._cbs["credit_arkbank_premium"],
        queue_catalog_order=queue_prod_shape,
        grant_license=sps._cbs["grant_license"],
        get_entitlements=sps._cbs.get("get_entitlements") or (lambda sid, db=None: []),
        license_catalog_price=sps._cbs.get("license_catalog_price") or (lambda g: 5000),
    )

    with spcfg._lock:
        cfg = spcfg.load_config()
        cfg["season_id"] = long_season
        cfg["premium_rewards"]["8"] = [
            {
                "type": "dino",
                "id": "sb_crystal_ember_l200",
                "qty": 1,
                "label": "Crystal Ember",
            }
        ]
        cfg["premium_rewards"]["10"] = [
            {
                "type": "kit",
                "id": "noglin_pack10",
                "qty": 1,
                "label": "Noglin pack",
            }
        ]
        spcfg.save_config(cfg)

    sps._upsert_progress(
        db,
        steam_id=USER_STEAM,
        season_id=long_season,
        xp=_xp_at(10),
        premium=True,
        claimed=set(),
    )
    db.commit()

    dino = sps.claim_reward(db, steam_id=USER_STEAM, track="premium", level=8)
    assert dino["ok"] is True
    kit = sps.claim_reward(db, steam_id=USER_STEAM, track="premium", level=10)
    assert kit["ok"] is True

    origs = [
        str(r[0])
        for r in db.execute(text("SELECT original_order_id FROM orders ORDER BY id")).fetchall()
    ]
    assert len(origs) == 2
    assert origs[0] == (
        f"sp:{long_season}:premium:8:dino:sb_crystal_ember_l200"
    )
    assert origs[1] == (
        f"__admin_skip_kit_limit__|sp:{long_season}:premium:10:kit:noglin_pack10"
    )
    assert all(len(o) > 64 for o in origs)
    assert all(len(o) <= max_len for o in origs)
    prog = sps.get_progress(db, USER_STEAM, long_season)
    assert "premium:8" in prog["claimed"]
    assert "premium:10" in prog["claimed"]


def test_claim_queue_failure_does_not_mark_claimed(sp_db):
    """INSERT na fila falhou → claim NÃO fica marcado (evita estado parcial)."""
    db, _ = sp_db
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)
    sid = spcfg.load_config()["season_id"]

    def queue_boom(*_a, **_k):
        raise Exception(
            '(pymysql.err.DataError) (1406, "Data too long for column '
            "'original_order_id' at row 1\")"
        )

    sps.configure_engine(
        subtract_points_tx=sps._cbs["subtract_points_tx"],
        add_points_tx=sps._cbs["add_points_tx"],
        credit_arkbank_premium=sps._cbs["credit_arkbank_premium"],
        queue_catalog_order=queue_boom,
        grant_license=sps._cbs["grant_license"],
        get_entitlements=sps._cbs.get("get_entitlements") or (lambda sid, db=None: []),
        license_catalog_price=sps._cbs.get("license_catalog_price") or (lambda g: 5000),
    )
    with spcfg._lock:
        cfg = spcfg.load_config()
        cfg["premium_rewards"]["3"] = [
            {"type": "dino", "id": "sb_crystal_ember_l200", "qty": 1, "label": "X"},
        ]
        spcfg.save_config(cfg)
    sps._upsert_progress(
        db, steam_id=USER_STEAM, season_id=sid, xp=_xp_at(3), premium=True, claimed=set()
    )
    db.commit()
    with pytest.raises(Exception, match="Data too long"):
        sps.claim_reward(db, steam_id=USER_STEAM, track="premium", level=3)
    db.rollback()
    prog = sps.get_progress(db, USER_STEAM, sid)
    assert "premium:3" not in prog["claimed"]
    n = db.execute(text("SELECT COUNT(*) FROM orders")).scalar()
    assert int(n or 0) == 0


def test_premium_catchup_unlocks_1_to_n(sp_db):
    db, _ = sp_db
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)
    sid = spcfg.load_config()["season_id"]
    # Player already at L5 without premium
    sps._upsert_progress(db, steam_id=USER_STEAM, season_id=sid, xp=_xp_at(5), premium=False, claimed=set())
    db.commit()
    with pytest.raises(ValueError, match="Premium"):
        sps.claim_reward(db, steam_id=USER_STEAM, track="premium", level=1)
    db.rollback()
    bought = sps.buy_premium(db, USER_STEAM)
    assert bought["premium"] is True
    assert bought["catchup_to_level"] >= 5
    # Amber nodes that are grant_ready in seed
    for lv in (1, 2, 3, 4, 5):
        grants = spcfg.rewards_for(spcfg.load_config(), "premium", lv)
        ready = all(spcfg.normalize_grant(g).get("grant_ready") for g in grants) if grants else False
        if not ready:
            continue
        r = sps.claim_reward(db, steam_id=USER_STEAM, track="premium", level=lv)
        assert r["ok"] is True, lv
    # Free catch-up still available
    free = sps.claim_reward(db, steam_id=USER_STEAM, track="free", level=4)
    assert free["ok"] is True


def test_claimable_false_when_sku_pending_in_payload():
    cfg = spcfg.load_config()
    nodes = __import__("season_pass_routes", fromlist=["_track_nodes"])._track_nodes(
        {
            **cfg,
            "premium_rewards": {
                "1": [{"type": "kit", "id": None, "label": "TBD"}],
            },
        },
        "premium",
        10,
        unlocked=True,
        claimed=set(),
        claims_open=True,
    )
    n1 = next(x for x in nodes if x["level"] == 1)
    assert n1["claimable"] is False
    assert n1["delivery"]["grants_sku_pending"] >= 1
    assert "SKU" in (n1.get("block_reason") or "")


def _mark_claimed(db, steam_id: str, season_id: str, track: str, level: int, *, xp: int, premium: bool):
    prog = sps.get_progress(db, steam_id, season_id)
    claimed = set(prog["claimed"])
    claimed.add(sps.claimed_key(track, level))
    sps._upsert_progress(
        db,
        steam_id=steam_id,
        season_id=season_id,
        xp=xp,
        premium=premium,
        claimed=claimed,
    )
    db.commit()


def test_admin_resend_amber_only(sp_db):
    db, _ = sp_db
    audits: list[tuple] = []
    sps.configure_engine(audit_event=lambda et, **kw: audits.append((et, kw)))
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)
    sid = spcfg.load_config()["season_id"]
    sps._upsert_progress(
        db, steam_id=USER_STEAM, season_id=sid, xp=_xp_at(4), premium=False, claimed=set()
    )
    db.commit()
    sps.claim_reward(db, steam_id=USER_STEAM, track="free", level=4)
    before = int(db.execute(text("SELECT points FROM players WHERE steam_id=:s"), {"s": USER_STEAM}).scalar())
    with pytest.raises(ValueError, match="confirm_required"):
        sps.admin_resend_reward(
            db, steam_id=USER_STEAM, track="free", level=4, parts=["amber"], confirm=False
        )
    result = sps.admin_resend_reward(
        db,
        steam_id=USER_STEAM,
        track="free",
        level=4,
        parts=["amber"],
        confirm=True,
        admin_steam_id=ADMIN_STEAM,
        reason="felipe-like amber missing",
    )
    assert result["ok"] is True
    assert result["claimed_unchanged"] is True
    after = int(db.execute(text("SELECT points FROM players WHERE steam_id=:s"), {"s": USER_STEAM}).scalar())
    assert after - before == 500
    acts = [a for a in result["actions"] if a.get("action") == "regranted"]
    assert len(acts) == 1 and acts[0]["qty"] == 500
    # Ainda claimed
    prog = sps.get_progress(db, USER_STEAM, sid)
    assert sps.claimed_key("free", 4) in prog["claimed"]
    assert any(et == "season_pass_admin_resend" for et, _ in audits)


def test_admin_resend_catalog_entregue_to_pending(sp_db):
    db, _ = sp_db
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)
    sid = spcfg.load_config()["season_id"]
    with spcfg._lock:
        cfg = spcfg.load_config()
        cfg["premium_rewards"]["3"] = [
            {"type": "kit", "id": "kit_test_sp", "qty": 1, "label": "Kit"},
            {"type": "item", "id": "cryopod", "qty": 2, "label": "Cryo"},
        ]
        spcfg.save_config(cfg)
    sps._upsert_progress(
        db, steam_id=USER_STEAM, season_id=sid, xp=_xp_at(3), premium=True, claimed=set()
    )
    db.commit()
    claim = sps.claim_reward(db, steam_id=USER_STEAM, track="premium", level=3)
    assert claim["ok"] is True
    db.execute(text("UPDATE orders SET status='ENTREGUE'"))
    db.commit()
    result = sps.admin_resend_reward(
        db,
        steam_id=USER_STEAM,
        track="premium",
        level=3,
        parts=["catalog"],
        confirm=False,
        admin_steam_id=ADMIN_STEAM,
    )
    assert result["ok"] is True
    resets = [a for a in result["actions"] if a.get("action") == "reset_pending"]
    assert len(resets) == 2
    assert all(a.get("status_before") == "ENTREGUE" for a in resets)
    rows = db.execute(text("SELECT status FROM orders")).fetchall()
    assert all(r[0] == "PENDENTE" for r in rows)
    prog = sps.get_progress(db, USER_STEAM, sid)
    assert sps.claimed_key("premium", 3) in prog["claimed"]


def test_admin_resend_catalog_missing_creates_order(sp_db):
    db, _ = sp_db
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)
    sid = spcfg.load_config()["season_id"]
    with spcfg._lock:
        cfg = spcfg.load_config()
        cfg["premium_rewards"]["5"] = [
            {"type": "dino", "id": "dino_spino", "qty": 1, "label": "Spino"},
        ]
        spcfg.save_config(cfg)
    # Claimed sem pedido (caso Felipe: claim marcado, fila sumiu)
    _mark_claimed(db, USER_STEAM, sid, "premium", 5, xp=_xp_at(5), premium=True)
    assert db.execute(text("SELECT COUNT(*) FROM orders")).scalar() == 0
    result = sps.admin_resend_reward(
        db,
        steam_id=USER_STEAM,
        track="premium",
        level=5,
        parts=["catalog"],
        admin_steam_id=ADMIN_STEAM,
    )
    assert result["ok"] is True
    created = [a for a in result["actions"] if a.get("action") == "created"]
    assert len(created) == 1
    assert created[0]["type"] == "dino"
    row = db.execute(
        text("SELECT status, original_order_id FROM orders WHERE order_id=:oid"),
        {"oid": created[0]["order_id"]},
    ).fetchone()
    assert row[0] == "PENDENTE"
    assert row[1] == f"sp:{sid}:premium:5:dino:dino_spino"
    prog = sps.get_progress(db, USER_STEAM, sid)
    assert sps.claimed_key("premium", 5) in prog["claimed"]


def test_admin_resend_both_amber_and_catalog(sp_db):
    db, _ = sp_db
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)
    sid = spcfg.load_config()["season_id"]
    with spcfg._lock:
        cfg = spcfg.load_config()
        cfg["premium_rewards"]["7"] = [
            {"type": "amber", "qty": 250, "label": "250 Â"},
            {"type": "item", "id": "cryopod", "qty": 1, "label": "Cryo"},
        ]
        spcfg.save_config(cfg)
    sps._upsert_progress(
        db, steam_id=USER_STEAM, season_id=sid, xp=_xp_at(7), premium=True, claimed=set()
    )
    db.commit()
    sps.claim_reward(db, steam_id=USER_STEAM, track="premium", level=7)
    db.execute(text("UPDATE orders SET status='ERRO'"))
    db.commit()
    before = int(db.execute(text("SELECT points FROM players WHERE steam_id=:s"), {"s": USER_STEAM}).scalar())
    result = sps.admin_resend_reward(
        db,
        steam_id=USER_STEAM,
        track="premium",
        level=7,
        parts=["amber", "catalog"],
        confirm=True,
        admin_steam_id=ADMIN_STEAM,
    )
    assert result["ok"] is True
    after = int(db.execute(text("SELECT points FROM players WHERE steam_id=:s"), {"s": USER_STEAM}).scalar())
    assert after - before == 250
    assert any(a.get("action") == "regranted" for a in result["actions"])
    assert any(a.get("action") == "reset_pending" and a.get("status_before") == "ERRO" for a in result["actions"])
    assert db.execute(text("SELECT status FROM orders")).scalar() == "PENDENTE"
    prog = sps.get_progress(db, USER_STEAM, sid)
    assert sps.claimed_key("premium", 7) in prog["claimed"]


def test_audit_free_amber_claim(sp_db):
    db, _ = sp_db
    audits: list[dict] = []
    sps.configure_engine(audit_event=lambda et, **kw: audits.append({"event_type": et, **kw}))
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)
    sid = spcfg.load_config()["season_id"]
    sps._upsert_progress(db, steam_id=USER_STEAM, season_id=sid, xp=_xp_at(4), premium=False, claimed=set())
    db.commit()
    result = sps.claim_reward(db, steam_id=USER_STEAM, track="free", level=4)
    assert result["ok"] is True
    claim_audits = [a for a in audits if a["event_type"] == "season_pass_claim"]
    assert len(claim_audits) == 1
    ev = claim_audits[0]
    assert ev["actor_steam_id"] == USER_STEAM
    assert ev["target_steam_id"] == USER_STEAM
    assert ev["track"] == "free"
    assert ev["level"] == 4
    assert ev["season_id"] == sid
    assert ev["amber_amount"] == 500
    assert ev["amount"] == 500
    assert ev["new_balance"] == result["new_balance"]
    assert ev["item_id"] == "free:4"
    assert "500" in (ev.get("message") or "")


def test_audit_premium_kit_dino_claim(sp_db):
    db, _ = sp_db
    audits: list[dict] = []
    sps.configure_engine(audit_event=lambda et, **kw: audits.append({"event_type": et, **kw}))
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)
    sid = spcfg.load_config()["season_id"]
    cfg = spcfg.load_config()
    cfg["premium_rewards"]["8"] = [
        {"type": "dino", "id": "sb_crystal_ember_l200", "qty": 1, "label": "Crystal Ember"},
    ]
    cfg["premium_rewards"]["10"] = [
        {"type": "kit", "id": "noglin_pack10", "qty": 1, "label": "Noglin pack"},
    ]
    spcfg.save_config(cfg)
    sps._upsert_progress(
        db, steam_id=USER_STEAM, season_id=sid, xp=_xp_at(10), premium=True, claimed=set(),
    )
    db.commit()

    dino = sps.claim_reward(db, steam_id=USER_STEAM, track="premium", level=8)
    kit = sps.claim_reward(db, steam_id=USER_STEAM, track="premium", level=10)
    assert dino["ok"] and kit["ok"]

    claim_audits = [a for a in audits if a["event_type"] == "season_pass_claim"]
    assert len(claim_audits) == 2
    dino_ev = next(a for a in claim_audits if a["level"] == 8)
    kit_ev = next(a for a in claim_audits if a["level"] == 10)
    assert dino_ev["item_ids"] == ["sb_crystal_ember_l200"]
    assert kit_ev["item_ids"] == ["noglin_pack10"]
    assert dino_ev["order_ids"] and kit_ev["order_ids"]
    assert dino_ev["status_after"] == "queued"
    assert kit_ev["status_after"] == "queued"
    assert dino_ev["order_id"] == dino_ev["order_ids"][0]


def test_audit_premium_purchase(sp_db):
    db, _ = sp_db
    audits: list[dict] = []
    sps.configure_engine(audit_event=lambda et, **kw: audits.append({"event_type": et, **kw}))
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)
    result = sps.buy_premium(db, USER_STEAM)
    assert result["ok"] is True and not result.get("already_owned")
    purch = [a for a in audits if a["event_type"] == "season_pass_premium_purchase"]
    assert len(purch) == 1
    ev = purch[0]
    assert ev["amount"] == 15_000
    assert ev["actor_steam_id"] == USER_STEAM
    assert ev["new_balance"] == result["new_balance"]
    assert ev["status_after"] == "premium"
    # already_owned não gera segundo evento
    again = sps.buy_premium(db, USER_STEAM)
    assert again["already_owned"] is True
    assert len([a for a in audits if a["event_type"] == "season_pass_premium_purchase"]) == 1


def test_audit_claim_failed_on_delivery_error(sp_db):
    db, _ = sp_db
    audits: list[dict] = []
    sps.configure_engine(audit_event=lambda et, **kw: audits.append({"event_type": et, **kw}))
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)
    sid = spcfg.load_config()["season_id"]
    cfg = spcfg.load_config()
    cfg["premium_rewards"]["8"] = [
        {"type": "dino", "id": "sb_fail_dino", "qty": 1, "label": "Boom"},
    ]
    spcfg.save_config(cfg)
    sps._upsert_progress(
        db, steam_id=USER_STEAM, season_id=sid, xp=_xp_at(8), premium=True, claimed=set(),
    )
    db.commit()

    def boom_queue(*_a, **_k):
        raise RuntimeError("(pymysql.err.DataError) (1406, \"Data too long for column\")")

    sps.configure_engine(queue_catalog_order=boom_queue)
    with pytest.raises(RuntimeError, match="1406"):
        sps.claim_reward(db, steam_id=USER_STEAM, track="premium", level=8)
    failed = [a for a in audits if a["event_type"] == "season_pass_claim_failed"]
    assert len(failed) == 1
    ev = failed[0]
    assert ev["severity"] == "error"
    assert ev["track"] == "premium"
    assert ev["level"] == 8
    assert "1406" in (ev.get("error") or "")
    assert "1406" in (ev.get("message") or "")
    # ValueError de elegibilidade NÃO gera claim_failed
    audits.clear()
    db.rollback()
    sps._upsert_progress(
        db, steam_id=USER_STEAM, season_id=sid, xp=0, premium=False, claimed=set(),
    )
    db.commit()
    with pytest.raises(ValueError, match="ainda não atingido"):
        sps.claim_reward(db, steam_id=USER_STEAM, track="free", level=4)
    assert not any(a["event_type"] == "season_pass_claim_failed" for a in audits)
