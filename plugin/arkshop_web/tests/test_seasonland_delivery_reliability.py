"""SeasonLand delivery reliability — Phase A (stale/ERRO/flags) + Phase B (partial/SKU/metrics)."""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")
os.environ.setdefault("ARKSHOP_RETRY_INTERVAL", "9999")
os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")

import app as _app_module
from app import app, _configure_database, _now
import season_pass_config as spcfg
import season_pass_routes as sproutes
import season_pass_service as sps

ADMIN_STEAM = "76561198000000001"
USER_STEAM = "76561198000000002"
API_KEY = "test-api-key"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_API_KEY", API_KEY)
    monkeypatch.setattr(_app_module, "_ARKSHOP_API_KEY", API_KEY)
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(_app_module, "_PLAYERS_FILE", tmp_path / "players.json")
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", tmp_path / "servers.json")
    monkeypatch.setattr(_app_module, "_migrate_schema", lambda _engine: None)
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]), encoding="utf-8")
    (tmp_path / "settings.json").write_text(
        json.dumps({
            "shop_stale_entregando_minutes": 5,
            "shop_identical_fail_max": 3,
        }),
        encoding="utf-8",
    )
    cfg_path = tmp_path / "season_pass_config.json"
    claims_path = tmp_path / "season_pass_claims.json"
    monkeypatch.setattr(_app_module, "_SEASON_PASS_CONFIG_FILE", cfg_path)
    monkeypatch.setattr(_app_module, "_SEASON_PASS_CLAIMS_FILE", claims_path)
    spcfg.configure_season_pass(config_file=cfg_path, claims_file=claims_path)

    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(f"sqlite:///{db_path}")
    if _app_module._ENGINE is not None:
        _app_module.Base.metadata.create_all(bind=_app_module._ENGINE)
        with _app_module._ENGINE.connect() as conn:
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS players ("
                    "steam_id VARCHAR(20) PRIMARY KEY NOT NULL, "
                    "points INTEGER NOT NULL DEFAULT 0, "
                    "kits TEXT DEFAULT '{}')"
                )
            )
            conn.commit()
        db = _app_module._SessionLocal()
        try:
            _app_module._ensure_entitlements_schema(db)
            from regulamento_config import REGULAMENTO_VERSION

            for sid, name in ((ADMIN_STEAM, "Admin"), (USER_STEAM, "TestPlayer")):
                db.add(
                    _app_module.StoreUser(
                        steam_id=sid,
                        display_name=name,
                        steam_persona=name,
                        regulamento_accepted_version=REGULAMENTO_VERSION,
                        regulamento_accepted_at=_now(),
                        last_login_at=_now(),
                    )
                )
            db.commit()
        finally:
            db.close()
    monkeypatch.setattr(_app_module, "_DB_INITIALIZED", True)
    yield
    _configure_database("")


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login(client, steam_id: str):
    with client.session_transaction() as sess:
        sess["steam_id"] = steam_id


def _mk_order(
    *,
    item_type="shop",
    item_id="cryopod",
    status="PENDENTE",
    original_order_id=None,
    updated_at=None,
    retry_count=0,
    last_error=None,
):
    db = _app_module._SessionLocal()
    try:
        oid = str(uuid.uuid4())
        now = _now()
        order = _app_module.Order(
            order_id=oid,
            steam_id=USER_STEAM,
            server_id="default",
            item_type=item_type,
            item_id=item_id,
            amount=1,
            points_spent=0,
            status=status,
            original_order_id=original_order_id,
            retry_count=retry_count,
            last_error=last_error,
            created_at=now,
            updated_at=updated_at or now,
        )
        db.add(order)
        db.commit()
        return oid
    finally:
        db.close()


# ── Phase A ──────────────────────────────────────────────────────────────────


def test_a1_stale_recovery_shop_order(client):
    """Phase A: shop ENTREGANDO stale → PENDENTE + last_error + reclaimable."""
    stale = _now() - timedelta(minutes=10)
    if getattr(stale, "tzinfo", None):
        stale = stale.replace(tzinfo=None)
    oid = _mk_order(item_type="shop", item_id="metal_ingot", status="ENTREGANDO", updated_at=stale)

    db = _app_module._SessionLocal()
    try:
        n = _app_module.recover_stale_entregando_shop_orders(db, USER_STEAM, minutes=5)
        db.commit()
        assert n == 1
        row = db.query(_app_module.Order).filter_by(order_id=oid).first()
        assert row.status == "PENDENTE"
        assert "expirou" in (row.last_error or "").lower() or "timeout" in (row.last_error or "").lower()
        assert int(row.retry_count or 0) >= 1
    finally:
        db.close()

    r = client.post(
        "/api/pending/claim",
        json={"steam_id": USER_STEAM},
        headers={"X-API-Key": API_KEY},
    )
    d = r.get_json()
    assert d["ok"] is True
    assert any(i["order_id"] == oid for i in d["items"])


def test_a2_stale_recovery_kit_seasonland_sp(client):
    """Phase A: kit SeasonLand sp: ENTREGANDO stale → PENDENTE."""
    stale = _now() - timedelta(minutes=15)
    if getattr(stale, "tzinfo", None):
        stale = stale.replace(tzinfo=None)
    oid = _mk_order(
        item_type="kit",
        item_id="kit_test_sp",
        status="ENTREGANDO",
        original_order_id="__admin_skip_kit_limit__|sp:season-delta:premium:3:kit:kit_test_sp",
        updated_at=stale,
    )
    db = _app_module._SessionLocal()
    try:
        n = _app_module.recover_stale_entregando_shop_orders(db, USER_STEAM, minutes=5)
        db.commit()
        assert n == 1
        row = db.query(_app_module.Order).filter_by(order_id=oid).first()
        assert row.status == "PENDENTE"
        assert "sp:" in (row.original_order_id or "")
    finally:
        db.close()


def test_a3_erro_after_n_identical_releases(client):
    """Phase A: N releases com mesmo fail_reason → ERRO (não silent forever)."""
    oid = _mk_order(item_type="shop", item_id="ghost_sku", status="ENTREGANDO")
    headers = {"X-API-Key": API_KEY}

    for i in range(2):
        r = client.post(
            "/api/pending/release",
            json={
                "steam_id": USER_STEAM,
                "order_ids": [oid],
                "errors": [{"order_id": oid, "fail_reason": "item_desconhecido"}],
            },
            headers=headers,
        )
        d = r.get_json()
        assert d["ok"] is True
        assert oid in d["released"]
        assert oid not in (d.get("errored") or [])
        # Reclaim to ENTREGANDO for next release
        client.post(
            "/api/pending/claim",
            json={"steam_id": USER_STEAM, "order_ids": [oid]},
            headers=headers,
        )

    r = client.post(
        "/api/pending/release",
        json={
            "steam_id": USER_STEAM,
            "order_ids": [oid],
            "errors": [{"order_id": oid, "fail_reason": "item_desconhecido"}],
        },
        headers=headers,
    )
    d = r.get_json()
    assert d["ok"] is True
    assert oid in (d.get("errored") or [])
    db = _app_module._SessionLocal()
    try:
        row = db.query(_app_module.Order).filter_by(order_id=oid).first()
        assert row.status == "ERRO"
        assert row.last_error == "item_desconhecido"
        assert int(row.retry_count or 0) >= 3
    finally:
        db.close()


def test_a4_claim_api_flags_queued_for_shop(tmp_path, monkeypatch):
    """Phase A: claim com kit → queued_for_shop + delivery_state partial/queued."""
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
            "original_order_id TEXT, retry_count INTEGER DEFAULT 0,"
            "last_error TEXT, created_at TEXT, updated_at TEXT)"
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
    from arkbank_service import ensure_arkbank_schema, credit_season_pass_premium
    ensure_arkbank_schema(engine)
    Session = sessionmaker(bind=engine, future=True)
    db = Session()
    db.execute(text("INSERT INTO players (steam_id, points) VALUES (:s, 100000)"), {"s": USER_STEAM})
    db.commit()

    def add(db_, sid, amt):
        db_.execute(text("UPDATE players SET points = points + :a WHERE steam_id=:s"), {"a": amt, "s": sid})
        return int(db_.execute(text("SELECT points FROM players WHERE steam_id=:s"), {"s": sid}).scalar())

    def queue(db_, *, steam_id, item_type, item_id, amount, original_order_id):
        oid = f"ord-{original_order_id[-24:]}"
        db_.execute(
            text(
                "INSERT INTO orders (order_id, steam_id, server_id, item_type, item_id, amount, "
                "points_spent, status, original_order_id, created_at, updated_at) "
                "VALUES (:oid,:sid,'default',:it,:iid,:amt,0,'PENDENTE',:orig,'now','now')"
            ),
            {"oid": oid, "sid": steam_id, "it": item_type, "iid": item_id, "amt": amount, "orig": original_order_id},
        )
        return oid

    sps.configure_engine(
        add_points_tx=add,
        subtract_points_tx=lambda *a, **k: 0,
        credit_arkbank_premium=lambda db_, **kw: credit_season_pass_premium(db_, **kw),
        queue_catalog_order=queue,
        grant_license=lambda *a, **k: None,
        get_entitlements=lambda *a, **k: [],
        license_catalog_price=lambda g: 5000,
    )
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)
    sid = spcfg.load_config()["season_id"]
    with spcfg._lock:
        cfg = spcfg.load_config()
        cfg["premium_rewards"]["2"] = [
            {"type": "amber", "qty": 100},
            {"type": "kit", "id": "kit_q", "qty": 1, "label": "Kit Q"},
        ]
        spcfg.save_config(cfg)
    sps._upsert_progress(db, steam_id=USER_STEAM, season_id=sid, xp=spcfg.build_xp_thresholds()[1], premium=True, claimed=set())
    db.commit()
    result = sps.claim_reward(db, steam_id=USER_STEAM, track="premium", level=2)
    assert result["queued_for_shop"] is True
    assert result["in_game_delivered"] is False
    assert result["delivery_state"] in ("queued", "partial")
    assert "forçar" in (result["message"] or "").lower() or "/shop" in (result["message"] or "")
    db.close()


def test_a5_available_shows_entregando_erro_delivery_state(client):
    """Phase A: /api/player/available expõe ENTREGANDO/ERRO + delivery_state."""
    oid_e = _mk_order(item_type="shop", item_id="cryo_a", status="ENTREGANDO")
    oid_f = _mk_order(
        item_type="kit",
        item_id="kit_fail",
        status="ERRO",
        last_error="kit_desconhecido",
        original_order_id="sp:season-x:free:4:kit:kit_fail",
    )
    _login(client, USER_STEAM)
    r = client.get("/api/player/available")
    d = r.get_json()
    assert d["ok"] is True
    by_id = {p["order_id"]: p for p in d["pending"]}
    assert oid_e in by_id
    assert by_id[oid_e]["delivery_state"] == "delivering"
    assert oid_f in by_id
    assert by_id[oid_f]["delivery_state"] == "failed"
    assert by_id[oid_f]["last_error"] == "kit_desconhecido"
    assert by_id[oid_f].get("is_season_pass") is True


# ── Phase B ──────────────────────────────────────────────────────────────────


def test_b1_partial_amber_plus_kit_state():
    """Phase B: nó claimed com Â settled + kit PENDENTE → delivery_state partial."""
    grants = [
        {"type": "amber", "qty": 500},
        {"type": "kit", "id": "kit_x", "qty": 1, "label": "Kit"},
    ]
    orders = {
        "sp:season1:premium:5:kit:kit_x": {
            "order_id": "o1",
            "status": "PENDENTE",
            "delivery_state": "queued",
        }
    }
    annotated, state = sps.annotate_claimed_grants(
        grants,
        season_id="season1",
        track="premium",
        level=5,
        orders_by_idem=orders,
    )
    assert state == "partial"
    amber = next(g for g in annotated if g["type"] == "amber")
    kit = next(g for g in annotated if g["type"] == "kit")
    assert amber["settled"] is True
    assert amber["delivery_state"] == "delivered"
    assert kit["settled"] is False
    assert kit["delivery_state"] == "queued"


def test_b2_sku_missing_sync_check_blocks_warn():
    """Phase B: SKU sync detecta id fantasma via catalog_lookup."""
    cfg = {
        "free_rewards": {},
        "premium_rewards": {
            "1": [{"type": "kit", "id": "exists_kit", "qty": 1}],
            "2": [{"type": "item", "id": "ghost_item", "qty": 1}],
            "3": [{"type": "dino", "id": None, "label": "TBD"}],
        },
    }
    def lookup(item_type, item_id):
        return item_id == "exists_kit"

    result = sps.check_season_pass_sku_sync(cfg, catalog_lookup=lookup)
    assert result["warn"] is True
    assert result["missing_count"] >= 1
    assert result["pending_count"] >= 1
    assert any(m["id"] == "ghost_item" for m in result["sku_missing"])
    assert result["block_claims"] is True


def test_b3_delivery_metrics_endpoint(client):
    """Phase B: GET /api/admin/season-pass/delivery-metrics."""
    stale = _now() - timedelta(hours=2)
    if getattr(stale, "tzinfo", None):
        stale = stale.replace(tzinfo=None)
    _mk_order(
        item_type="kit",
        item_id="k1",
        status="PENDENTE",
        original_order_id="sp:season-m:premium:1:kit:k1",
        updated_at=stale,
        last_error="kit_desconhecido",
    )
    _mk_order(
        item_type="shop",
        item_id="i1",
        status="ENTREGANDO",
        original_order_id="sp:season-m:premium:2:item:i1",
    )
    _login(client, ADMIN_STEAM)
    r = client.get("/api/admin/season-pass/delivery-metrics")
    d = r.get_json()
    assert d["ok"] is True
    assert d["pending"] >= 1
    assert d["entregando"] >= 1
    assert any("kit_desconhecido" in (f.get("fail_reason") or "") for f in d.get("top_fail_reasons") or [])


def test_b4_reclaim_missing_only_skips_entregue_and_amber(tmp_path):
    """Phase B: missing_only reenvia só catálogo em falta/ERRO — não mexe ENTREGUE nem Â."""
    path = tmp_path / "sp2.db"
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
            "original_order_id TEXT, retry_count INTEGER DEFAULT 0,"
            "last_error TEXT, created_at TEXT, updated_at TEXT)"
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
    from arkbank_service import ensure_arkbank_schema, credit_season_pass_premium
    ensure_arkbank_schema(engine)
    Session = sessionmaker(bind=engine, future=True)
    db = Session()
    db.execute(text("INSERT INTO players (steam_id, points) VALUES (:s, 50000)"), {"s": USER_STEAM})
    db.commit()

    points_calls = []

    def add(db_, sid, amt):
        points_calls.append(amt)
        db_.execute(text("UPDATE players SET points = points + :a WHERE steam_id=:s"), {"a": amt, "s": sid})
        return 50000 + sum(points_calls)

    created = []

    def queue(db_, *, steam_id, item_type, item_id, amount, original_order_id):
        oid = f"new-{item_id}"
        created.append(oid)
        db_.execute(
            text(
                "INSERT INTO orders (order_id, steam_id, server_id, item_type, item_id, amount, "
                "points_spent, status, original_order_id, created_at, updated_at) "
                "VALUES (:oid,:sid,'default',:it,:iid,:amt,0,'PENDENTE',:orig,'now','now')"
            ),
            {"oid": oid, "sid": steam_id, "it": item_type, "iid": item_id, "amt": amount, "orig": original_order_id},
        )
        return oid

    def reset(db_, oid):
        db_.execute(text("UPDATE orders SET status='PENDENTE' WHERE order_id=:o"), {"o": oid})

    sps.configure_engine(
        add_points_tx=add,
        subtract_points_tx=lambda *a, **k: 0,
        credit_arkbank_premium=lambda db_, **kw: credit_season_pass_premium(db_, **kw),
        queue_catalog_order=queue,
        reset_order_to_pending=reset,
        grant_license=lambda *a, **k: None,
        get_entitlements=lambda *a, **k: [],
        license_catalog_price=lambda g: 5000,
    )
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    sps.start_season(now=now)
    sid = spcfg.load_config()["season_id"]
    with spcfg._lock:
        cfg = spcfg.load_config()
        cfg["premium_rewards"]["7"] = [
            {"type": "amber", "qty": 999},
            {"type": "kit", "id": "kit_ok", "qty": 1},
            {"type": "item", "id": "item_fail", "qty": 1},
        ]
        spcfg.save_config(cfg)

    # ENTREGUE kit + ERRO item
    db.execute(
        text(
            "INSERT INTO orders (order_id, steam_id, server_id, item_type, item_id, amount, "
            "points_spent, status, original_order_id, created_at, updated_at) VALUES "
            "('o-kit',:sid,'default','kit','kit_ok',1,0,'ENTREGUE',:a,'now','now'),"
            "('o-item',:sid,'default','shop','item_fail',1,0,'ERRO',:b,'now','now')"
        ),
        {
            "sid": USER_STEAM,
            "a": f"sp:{sid}:premium:7:kit:kit_ok",
            "b": f"sp:{sid}:premium:7:item:item_fail",
        },
    )
    sps._upsert_progress(
        db, steam_id=USER_STEAM, season_id=sid, xp=spcfg.build_xp_thresholds()[6],
        premium=True, claimed={"premium:7"},
    )
    db.commit()

    result = sps.admin_resend_reward(
        db,
        steam_id=USER_STEAM,
        track="premium",
        level=7,
        parts=["amber", "catalog"],
        confirm=True,
        missing_only=True,
    )
    assert result["ok"] is True
    assert result["missing_only"] is True
    assert not points_calls  # Â skipped
    assert any(
        a.get("part") == "amber" and a.get("action") == "skipped"
        and a.get("reason") == "missing_only_skips_amber"
        for a in result["actions"]
    )
    assert any(a.get("type") == "kit" and a.get("action") == "skipped" and a.get("reason") == "already_delivered" for a in result["actions"])
    assert any(a.get("type") == "item" and a.get("action") == "reset_pending" for a in result["actions"])
    row = db.execute(text("SELECT status FROM orders WHERE order_id='o-item'")).fetchone()
    assert row[0] == "PENDENTE"
    kit_row = db.execute(text("SELECT status FROM orders WHERE order_id='o-kit'")).fetchone()
    assert kit_row[0] == "ENTREGUE"
    db.close()


def test_b5_admin_sku_health_endpoint(client, monkeypatch, tmp_path):
    """Phase B: GET /api/admin/season-pass/sku-health para staff."""
    catalog = tmp_path / "config.json"
    catalog.write_text(json.dumps({
        "Kits": {"real_kit": {"Price": 0}},
        "Items": {"cryopod": {"Price": 10}},
    }), encoding="utf-8")
    monkeypatch.setattr(_app_module, "_read_shop_config", lambda: json.loads(catalog.read_text(encoding="utf-8")))

    with spcfg._lock:
        cfg = spcfg.load_config()
        cfg["premium_rewards"]["9"] = [
            {"type": "kit", "id": "real_kit", "qty": 1},
            {"type": "item", "id": "no_such_item", "qty": 1},
        ]
        spcfg.save_config(cfg)

    _login(client, ADMIN_STEAM)
    r = client.get("/api/admin/season-pass/sku-health")
    d = r.get_json()
    assert d["ok"] is True or "ready_count" in d
    assert d.get("missing_count", 0) >= 1 or any(
        m.get("id") == "no_such_item" for m in (d.get("sku_missing") or [])
    )


# ── SeasonLand Ops — list endpoint ────────────────────────────────────────────


def test_ops_list_season_pass_orders_filters(client):
    """GET /api/admin/season-pass/orders — só sp: / skip-kit|sp:, filtros track/level."""
    shop_oid = _mk_order(item_type="shop", item_id="sword", status="PENDENTE")
    sp_prem = _mk_order(
        item_type="shop",
        item_id="cryopod",
        status="PENDENTE",
        original_order_id="sp:season-ops:premium:5:item:cryopod",
    )
    sp_kit = _mk_order(
        item_type="kit",
        item_id="kit_ops",
        status="ERRO",
        original_order_id="__admin_skip_kit_limit__|sp:season-ops:free:4:kit:kit_ops",
    )
    _mk_order(
        item_type="shop",
        item_id="other",
        status="PENDENTE",
        original_order_id="sp:season-ops:premium:12:item:other",
    )

    _login(client, USER_STEAM)
    assert client.get("/api/admin/season-pass/orders").status_code in (401, 403)

    _login(client, ADMIN_STEAM)
    r = client.get("/api/admin/season-pass/orders")
    d = r.get_json()
    assert d["ok"] is True
    ids = {o["order_id"] for o in d["items"]}
    assert sp_prem in ids
    assert sp_kit in ids
    assert shop_oid not in ids
    assert all(o.get("is_season_pass") for o in d["items"])
    prem5 = next(o for o in d["items"] if o["order_id"] == sp_prem)
    assert prem5["track"] == "premium"
    assert prem5["level"] == 5
    assert prem5["grant_type"] == "item"

    r2 = client.get("/api/admin/season-pass/orders?track=free&level=4&status=ERRO")
    d2 = r2.get_json()
    assert d2["ok"] is True
    assert d2.get("has_more") is False
    assert len(d2["items"]) == 1
    assert d2["items"][0]["order_id"] == sp_kit
    assert d2["items"][0]["track"] == "free"
    assert d2["items"][0]["level"] == 4

    r3 = client.get(f"/api/admin/season-pass/orders?steam_id={USER_STEAM}")
    d3 = r3.get_json()
    assert d3["ok"] is True
    assert len(d3["items"]) >= 3


def test_ops_admin_orders_hides_seasonland_by_default(client):
    """Pedidos admin: SeasonLand oculto por omissão; include_season_pass=1 mostra."""
    shop_oid = _mk_order(item_type="shop", item_id="sword", status="PENDENTE")
    sp_oid = _mk_order(
        item_type="shop",
        item_id="cryopod",
        status="PENDENTE",
        original_order_id="sp:season-hide:premium:1:item:cryopod",
    )
    _login(client, ADMIN_STEAM)
    r = client.get("/api/admin/orders")
    d = r.get_json()
    assert d["ok"] is True
    ids = {o["order_id"] for o in d["items"]}
    assert shop_oid in ids
    assert sp_oid not in ids
    assert d.get("include_season_pass") is False

    r2 = client.get("/api/admin/orders?include_season_pass=1")
    d2 = r2.get_json()
    ids2 = {o["order_id"] for o in d2["items"]}
    assert shop_oid in ids2
    assert sp_oid in ids2
    assert d2.get("include_season_pass") is True

    r3 = client.get("/api/admin/orders?season_pass_only=1")
    d3 = r3.get_json()
    ids3 = {o["order_id"] for o in d3["items"]}
    assert sp_oid in ids3
    assert shop_oid not in ids3


def test_parse_season_pass_idem():
    p = sps.parse_season_pass_idem(
        "__admin_skip_kit_limit__|sp:season-x:premium:3:kit:kit_a"
    )
    assert p is not None
    assert p["season_id"] == "season-x"
    assert p["track"] == "premium"
    assert p["level"] == 3
    assert p["grant_type"] == "kit"
    assert p["grant_id"] == "kit_a"
    assert sps.parse_season_pass_idem("shop-order-xyz") is None
