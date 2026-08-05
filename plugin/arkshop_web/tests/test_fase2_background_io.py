"""Fase 2: I/O externo fora do worker HTTP (fila threading mínima)."""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")
os.environ.setdefault("ARKSHOP_RETRY_INTERVAL", "9999")

import app as _app_module
import background_tasks as _bg
import payment_jobs as _pj
import pending_jobs as _pend
from app import app, _configure_database, _now

USER_STEAM = "76561198000000002"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_API_KEY", "test-api-key")
    monkeypatch.setattr(_app_module, "_ARKSHOP_API_KEY", "test-api-key")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(_app_module, "_PLAYERS_FILE", tmp_path / "players.json")
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", tmp_path / "servers.json")
    monkeypatch.setattr(_app_module, "_migrate_schema", lambda _engine: None)
    (tmp_path / "admin_steamids.json").write_text("[]", encoding="utf-8")
    (tmp_path / "settings.json").write_text(
        json.dumps({
            "mp_access_token": "TEST_MP_TOKEN",
            "mp_sandbox": True,
            "delivery_mode": "plugin",
            "shop_stale_entregando_minutes": 5,
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(f"sqlite:///{tmp_path / 'fase2.db'}")
    if _app_module._ENGINE is not None:
        _app_module.Base.metadata.create_all(bind=_app_module._ENGINE)
        from sqlalchemy import text

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
    monkeypatch.setattr(_app_module, "_DB_INITIALIZED", True)
    monkeypatch.setattr(_app_module, "_get_mp_access_token", lambda: "TEST_MP_TOKEN")
    from db_diagnostics import record_circuit_success

    record_circuit_success()
    _bg.set_inline_mode(True)
    yield
    _bg.set_inline_mode(False)
    _configure_database("")


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login(client, steam_id: str) -> None:
    with client.session_transaction() as sess:
        sess["steam_id"] = steam_id


def test_submit_dedupe_skips_second(monkeypatch):
    _bg.set_inline_mode(False)
    started = threading.Event()
    release = threading.Event()
    calls = {"n": 0}

    def slow():
        calls["n"] += 1
        started.set()
        release.wait(timeout=2)

    assert _bg.submit(slow, dedupe_key="k1") is True
    assert started.wait(timeout=2)
    assert _bg.submit(slow, dedupe_key="k1") is False
    release.set()
    assert _bg.wait_idle(timeout=3)
    assert calls["n"] == 1
    _bg.set_inline_mode(True)


def test_pix_status_returns_without_waiting_mp(client, monkeypatch):
    """HTTP responde do DB; fetch MP não corre no thread do request (sem inline)."""
    _login(client, USER_STEAM)
    payment_id = str(uuid.uuid4())
    db = _app_module._SessionLocal()
    try:
        db.add(
            _app_module.PointPayment(
                payment_id=payment_id,
                mp_payment_id="mp-slow",
                steam_id=USER_STEAM,
                package_id="p500",
                amount_brl=5.0,
                points=500,
                status="PENDENTE",
                credited=False,
                payment_method="pix",
                created_at=_now(),
                updated_at=_now(),
            )
        )
        db.commit()
    finally:
        db.close()

    request_thread = threading.current_thread().name
    seen_threads: list[str] = []
    release = threading.Event()

    def slow_fetch(*_a, **_k):
        seen_threads.append(threading.current_thread().name)
        release.wait(timeout=2)
        return {"id": "mp-slow", "status": "pending", "external_reference": payment_id}

    _bg.set_inline_mode(False)
    monkeypatch.setattr(_app_module, "fetch_payment", slow_fetch)
    monkeypatch.setattr(_app_module, "_pix_mp_poll_allowed", lambda _pid: True)

    t0 = time.perf_counter()
    r = client.get(f"/api/player/pix/{payment_id}/status")
    elapsed = time.perf_counter() - t0
    release.set()
    _bg.wait_idle(timeout=3)
    _bg.set_inline_mode(True)

    d = r.get_json()
    assert d["ok"] is True
    assert d["status"] == "PENDENTE"
    assert d.get("mp_poll_queued") is True
    assert elapsed < 1.0, f"status bloqueou no MP: {elapsed:.2f}s"
    assert seen_threads and seen_threads[0] != request_thread


def test_pix_status_inline_credits_abandoned(client, monkeypatch):
    _login(client, USER_STEAM)
    payment_id = str(uuid.uuid4())
    db = _app_module._SessionLocal()
    try:
        db.add(
            _app_module.PointPayment(
                payment_id=payment_id,
                mp_payment_id="mp_abandoned_pix",
                steam_id=USER_STEAM,
                package_id="p500",
                amount_brl=5.0,
                points=500,
                status="ABANDONADO",
                credited=False,
                payment_method="pix",
                created_at=_now(),
                updated_at=_now(),
            )
        )
        db.commit()
    finally:
        db.close()

    mp_resp = {
        "id": "mp_abandoned_pix",
        "status": "approved",
        "external_reference": payment_id,
    }
    monkeypatch.setattr(_app_module, "fetch_payment", lambda *a, **k: mp_resp)
    monkeypatch.setattr(_app_module, "_pix_mp_poll_allowed", lambda _pid: True)
    monkeypatch.setattr(_app_module, "_add_player_points_tx", lambda *a, **k: 500)

    r = client.get(f"/api/player/pix/{payment_id}/status")
    d = r.get_json()
    assert d["ok"] is True
    # 1.º poll só enfileira; com inline o crédito corre antes do return do job,
    # mas a resposta HTTP usa snapshot pré-job — 2.º poll vê APROVADO.
    r2 = client.get(f"/api/player/pix/{payment_id}/status")
    d2 = r2.get_json()
    assert d2["credited"] is True
    assert d2["status"] == "APROVADO"


def test_webhook_acks_and_credits_inline(client, monkeypatch):
    payment_id = str(uuid.uuid4())
    db = _app_module._SessionLocal()
    try:
        db.add(
            _app_module.PointPayment(
                payment_id=payment_id,
                mp_payment_id=None,
                steam_id=USER_STEAM,
                package_id="p500",
                amount_brl=5.0,
                points=500,
                status="PENDENTE",
                credited=False,
                payment_method="card",
                created_at=_now(),
                updated_at=_now(),
            )
        )
        db.commit()
    finally:
        db.close()

    mp_resp = {
        "id": "mp_card_99",
        "status": "approved",
        "external_reference": payment_id,
        "payment_method_id": "visa",
    }
    monkeypatch.setattr(_app_module, "fetch_payment", lambda *a, **k: mp_resp)
    monkeypatch.setattr(_app_module, "_add_player_points_tx", lambda *a, **k: 500)

    r = client.post("/api/payments/webhook", json={"data": {"id": "mp_card_99"}})
    d = r.get_json()
    assert d["ok"] is True
    assert d.get("queued") is True

    db = _app_module._SessionLocal()
    try:
        row = db.query(_app_module.PointPayment).filter(
            _app_module.PointPayment.payment_id == payment_id
        ).first()
        assert row.credited is True
        assert row.status == "APROVADO"
        assert row.mp_payment_id == "mp_card_99"
    finally:
        db.close()


def test_tribe_sync_rcon_runs_in_parallel(monkeypatch):
    servers = [
        {"server_id": f"map{i}", "label": f"Mapa {i}", "rcon_host": "127.0.0.1",
         "rcon_port": 27020 + i, "rcon_password": "pw"}
        for i in range(6)
    ]
    monkeypatch.setattr(_app_module, "_load_settings", lambda: {})
    monkeypatch.setattr(_app_module, "_resolve_rcon_reload_targets", lambda s: servers)

    def slow_rcon(host, port, password, cmd, **k):
        time.sleep(0.15)
        return "ok"

    monkeypatch.setattr(_app_module, "_rcon_command", slow_rcon)
    t0 = time.perf_counter()
    results = _app_module._trigger_tribe_sync_rcon_all()
    elapsed = time.perf_counter() - t0
    assert len(results) == 6
    assert all(r["ok"] for r in results)
    assert elapsed < 0.7, f"tribe sync sequencial: {elapsed:.2f}s"


def test_claim_does_not_call_recover_stale(client, monkeypatch):
    """Com scheduler vivo e fila PENDENTE, claim NÃO faz recover (hot path).

    Empty-claim pode reabrir ENTREGANDO stale (ver test_claim_reopens_…);
    este teste cobre o caminho com trabalho real na fila.
    """
    calls = {"n": 0}

    def boom(*_a, **_k):
        calls["n"] += 1
        return 0

    oid = str(uuid.uuid4())
    db = _app_module._SessionLocal()
    try:
        db.add(
            _app_module.Order(
                order_id=oid,
                steam_id=USER_STEAM,
                server_id="default",
                item_type="shop",
                item_id="sword",
                amount=1,
                points_spent=0,
                status="PENDENTE",
                created_at=_now(),
                updated_at=_now(),
            )
        )
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(_app_module, "recover_stale_entregando_shop_orders", boom)
    monkeypatch.setattr(_app_module, "_pending_stale_scheduler_healthy", lambda: True)
    monkeypatch.setattr(_app_module, "_ARKSHOP_API_KEY", "test-api-key")
    r = client.post(
        "/api/pending/claim",
        headers={"X-API-Key": "test-api-key", "Content-Type": "application/json"},
        data=json.dumps({"steam_id": USER_STEAM}),
    )
    assert r.status_code == 200
    assert len(r.get_json()["items"]) == 1
    assert calls["n"] == 0


def test_claim_recovers_stale_when_scheduler_dead(client, monkeypatch):
    """P0: sem scheduler, claim tem de reabrir ENTREGANDO (senão entrega morre)."""
    from datetime import timedelta

    oid = str(uuid.uuid4())
    db = _app_module._SessionLocal()
    try:
        old = _now() - timedelta(minutes=30)
        db.add(
            _app_module.Order(
                order_id=oid,
                steam_id=USER_STEAM,
                server_id="default",
                item_type="shop",
                item_id="sword",
                amount=1,
                points_spent=0,
                status="ENTREGANDO",
                created_at=old,
                updated_at=old,
            )
        )
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(_app_module, "_pending_stale_scheduler_healthy", lambda: False)
    monkeypatch.setattr(_app_module, "_ARKSHOP_API_KEY", "test-api-key")
    r = client.post(
        "/api/pending/claim",
        headers={"X-API-Key": "test-api-key", "Content-Type": "application/json"},
        data=json.dumps({"steam_id": USER_STEAM}),
    )
    assert r.status_code == 200
    d = r.get_json()
    assert len(d["items"]) == 1
    assert d["items"][0]["item_id"] == "sword"


def test_pending_stale_global_recovers(monkeypatch):
    oid = str(uuid.uuid4())
    db = _app_module._SessionLocal()
    try:
        from datetime import timedelta

        old = _now() - timedelta(minutes=30)
        db.add(
            _app_module.Order(
                order_id=oid,
                steam_id=USER_STEAM,
                server_id="default",
                item_type="shop",
                item_id="sword",
                amount=1,
                points_spent=0,
                status="ENTREGANDO",
                created_at=old,
                updated_at=old,
            )
        )
        db.commit()
    finally:
        db.close()

    n = _pend.recover_stale_entregando_global()
    assert n >= 1
    db = _app_module._SessionLocal()
    try:
        row = db.query(_app_module.Order).filter(_app_module.Order.order_id == oid).first()
        assert row.status == "PENDENTE"
    finally:
        db.close()


def test_pending_stale_global_recovers_multiple_players(monkeypatch):
    """Sessão por steam_id + commit: 2.º jogador não pode falhar por scoped remove."""
    from datetime import timedelta

    steam_b = "76561198000000099"
    old = _now() - timedelta(minutes=30)
    ids = []
    db = _app_module._SessionLocal()
    try:
        for sid, item in ((USER_STEAM, "sword"), (steam_b, "pike")):
            oid = str(uuid.uuid4())
            ids.append(oid)
            db.add(
                _app_module.Order(
                    order_id=oid,
                    steam_id=sid,
                    server_id="default",
                    item_type="shop",
                    item_id=item,
                    amount=1,
                    points_spent=0,
                    status="ENTREGANDO",
                    created_at=old,
                    updated_at=old,
                )
            )
        db.commit()
    finally:
        db.close()

    n = _pend.recover_stale_entregando_global()
    assert n >= 2
    db = _app_module._SessionLocal()
    try:
        for oid in ids:
            row = db.query(_app_module.Order).filter(_app_module.Order.order_id == oid).first()
            assert row is not None
            assert row.status == "PENDENTE", oid
    finally:
        db.close()


def test_enqueue_shop_reload_does_not_block(monkeypatch):
    started = threading.Event()
    release = threading.Event()

    def slow_reload(_s):
        started.set()
        release.wait(timeout=2)
        return [{"ok": True}]

    monkeypatch.setattr(_app_module, "_reload_all_plugins", slow_reload)
    _bg.set_inline_mode(False)
    t0 = time.perf_counter()
    out = _app_module._enqueue_shop_reload({})
    elapsed = time.perf_counter() - t0
    assert out and out[0].get("queued") is True
    assert elapsed < 0.5
    assert started.wait(timeout=2)
    release.set()
    _bg.wait_idle(timeout=3)
    _bg.set_inline_mode(True)
