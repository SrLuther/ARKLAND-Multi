"""Regressões: cache de fila vazia, GET pending, batch status, recover stale."""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")
os.environ.setdefault("ARKSHOP_RETRY_INTERVAL", "9999")

import app as _app_module
from app import app, _configure_database, _now

USER_STEAM = "76561198000000002"
USER_B = "76561198000000003"
API_KEY = "test-pending-opt-key"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_API_KEY", API_KEY)
    monkeypatch.setattr(_app_module, "_ARKSHOP_API_KEY", API_KEY)
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(_app_module, "_PLAYERS_FILE", tmp_path / "players.json")
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", tmp_path / "servers.json")
    monkeypatch.setattr(_app_module, "_migrate_schema", lambda _engine: None)
    (tmp_path / "admin_steamids.json").write_text("[]", encoding="utf-8")
    (tmp_path / "settings.json").write_text(
        json.dumps({"shop_stale_entregando_minutes": 5}),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(f"sqlite:///{tmp_path / 'pending_opt.db'}")
    if _app_module._ENGINE is not None:
        _app_module.Base.metadata.create_all(bind=_app_module._ENGINE)
    monkeypatch.setattr(_app_module, "_DB_INITIALIZED", True)
    _app_module._invalidate_pending_delivery_cache()
    yield
    _configure_database("")


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _headers():
    return {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def _mk_order(*, steam_id=USER_STEAM, status="PENDENTE", item_id="sword", **extra):
    oid = str(uuid.uuid4())
    db = _app_module._SessionLocal()
    try:
        order = _app_module.Order(
            order_id=oid,
            steam_id=steam_id,
            server_id="default",
            item_type=extra.get("item_type", "shop"),
            item_id=item_id,
            amount=int(extra.get("amount", 1)),
            points_spent=0,
            status=status,
            created_at=_now(),
            updated_at=extra.get("updated_at", _now()),
        )
        db.add(order)
        db.commit()
    finally:
        db.close()
    _app_module._invalidate_pending_delivery_cache(steam_id)
    return oid


def test_claim_empty_cache_skips_db(client, monkeypatch):
    db_calls = {"n": 0}
    real_get = _app_module._get_db_session

    def _counting():
        db_calls["n"] += 1
        return real_get()

    monkeypatch.setattr(_app_module, "_get_db_session", _counting)

    r1 = client.post(
        "/api/pending/claim",
        headers=_headers(),
        data=json.dumps({"steam_id": USER_STEAM}),
    )
    assert r1.status_code == 200
    assert r1.get_json()["items"] == []
    assert r1.headers.get("X-Pending-Cache") == "MISS"
    assert db_calls["n"] == 1

    r2 = client.post(
        "/api/pending/claim",
        headers=_headers(),
        data=json.dumps({"steam_id": USER_STEAM}),
    )
    assert r2.status_code == 200
    assert r2.get_json()["items"] == []
    assert r2.headers.get("X-Pending-Cache") == "EMPTY"
    assert db_calls["n"] == 1  # cache hit — sem DB


def test_create_order_invalidates_empty_cache(client):
    r1 = client.post(
        "/api/pending/claim",
        headers=_headers(),
        data=json.dumps({"steam_id": USER_STEAM}),
    )
    assert r1.get_json()["items"] == []
    assert _app_module._pending_empty_cache_hit(USER_STEAM)

    order, err = _app_module._create_order(USER_STEAM, "shop", "sword", 1)
    assert err is None and order is not None
    assert not _app_module._pending_empty_cache_hit(USER_STEAM)

    r2 = client.post(
        "/api/pending/claim",
        headers=_headers(),
        data=json.dumps({"steam_id": USER_STEAM}),
    )
    d = r2.get_json()
    assert len(d["items"]) == 1
    assert d["items"][0]["item_id"] == "sword"


def test_get_pending_empty_then_hit(client):
    r1 = client.get(f"/api/pending/{USER_STEAM}", headers=_headers())
    assert r1.status_code == 200
    assert r1.get_json()["items"] == []
    assert r1.headers.get("X-Pending-Cache") == "MISS"

    r2 = client.get(f"/api/pending/{USER_STEAM}", headers=_headers())
    assert r2.status_code == 200
    assert r2.headers.get("X-Pending-Cache") == "EMPTY"


def test_pending_batch_status(client):
    _mk_order(steam_id=USER_STEAM, item_id="metal")
    r = client.post(
        "/api/pending/batch",
        headers=_headers(),
        data=json.dumps({
            "steam_ids": [USER_STEAM, USER_B],
            "include_items": True,
        }),
    )
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True
    assert d["results"][USER_STEAM]["empty"] is False
    assert d["results"][USER_STEAM]["count"] == 1
    assert d["results"][USER_STEAM]["items"][0]["item_id"] == "metal"
    assert d["results"][USER_B]["empty"] is True
    assert "plugin C++" in (d.get("note") or "")


def test_recover_stale_fast_path_and_reopen(client):
    oid = _mk_order(status="ENTREGANDO", updated_at=_now() - timedelta(minutes=10))
    db = _app_module._SessionLocal()
    try:
        n = _app_module.recover_stale_entregando_shop_orders(db, USER_STEAM, minutes=5)
        db.commit()
    finally:
        db.close()
    assert n == 1

    row = _app_module._SessionLocal()
    try:
        st = row.execute(
            text("SELECT status FROM orders WHERE order_id = :o"),
            {"o": oid},
        ).fetchone()
        assert st[0] == "PENDENTE"
    finally:
        row.close()

    # Sem stale: fast-path SELECT 1 → 0
    db2 = _app_module._SessionLocal()
    try:
        assert _app_module.recover_stale_entregando_shop_orders(db2, USER_STEAM) == 0
    finally:
        db2.close()
