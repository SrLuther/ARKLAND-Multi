"""Doações Mercado Pago: pagamento tardio, reconciliação admin, webhook e valor pago."""
from __future__ import annotations

import json
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")
os.environ.setdefault("ARKSHOP_RETRY_INTERVAL", "9999")

import app as _app_module
import background_tasks as _bg
import payment_jobs as _pj
from app import app, _configure_database, _now
from pix_payments import (
    classify_mp_notification,
    is_public_https_url,
    mp_amount_covers_package,
    pick_best_payment,
)

ADMIN_STEAM = "76561198000000001"
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
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]), encoding="utf-8")
    (tmp_path / "settings.json").write_text(
        json.dumps({"mp_access_token": "TEST_MP_TOKEN", "mp_sandbox": True, "delivery_mode": "plugin"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _app_module.limiter.reset()
    _configure_database(f"sqlite:///{tmp_path / 'reconcile.db'}")
    if _app_module._ENGINE is not None:
        _app_module.Base.metadata.create_all(bind=_app_module._ENGINE)
    monkeypatch.setattr(_app_module, "_DB_INITIALIZED", True)
    monkeypatch.setattr(_app_module, "_get_mp_access_token", lambda: "TEST_MP_TOKEN")
    monkeypatch.setattr(_app_module, "_get_mp_webhook_secret", lambda: "")
    monkeypatch.setattr(_pj.time, "sleep", lambda *_a, **_k: None)
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


def _add_payment(*, status="PENDENTE", method="pix", mp_id="mp_1", amount=20.0, points=60000, credited=False) -> str:
    pid = str(uuid.uuid4())
    db = _app_module._SessionLocal()
    try:
        db.add(_app_module.PointPayment(
            payment_id=pid, mp_payment_id=mp_id, steam_id=USER_STEAM, package_id="p60000",
            amount_brl=amount, points=points, status=status, credited=credited,
            payment_method=method, created_at=_now(), updated_at=_now(),
        ))
        db.commit()
    finally:
        db.close()
    return pid


def _row(pid):
    db = _app_module._SessionLocal()
    try:
        r = db.query(_app_module.PointPayment).filter(_app_module.PointPayment.payment_id == pid).first()
        return {"status": r.status, "credited": bool(r.credited), "mp_id": r.mp_payment_id}
    finally:
        db.close()


def _events(event_type):
    db = _app_module._SessionLocal()
    try:
        return db.query(_app_module.AuditEvent).filter(_app_module.AuditEvent.event_type == event_type).all()
    finally:
        db.close()


class _Credit:
    def __init__(self):
        self.calls = 0

    def __call__(self, *_a, **_k):
        self.calls += 1
        return 60000


@pytest.fixture
def credit(monkeypatch):
    c = _Credit()
    monkeypatch.setattr(_app_module, "_add_player_points_tx", c)
    return c


# ── helpers puros ────────────────────────────────────────────────────────────

def test_classify_notification_variants():
    assert classify_mp_notification({"type": "payment", "data": {"id": 5}}, {}) == ("payment", "5")
    assert classify_mp_notification({}, {"topic": "merchant_order", "id": "77"}) == ("merchant_order", "77")
    assert classify_mp_notification({}, {"type": "payment", "data.id": "9"}) == ("payment", "9")
    assert classify_mp_notification({"data": {"id": "x"}}, {}) == ("payment", "x")  # legado sem tópico


def test_public_url_detection():
    assert is_public_https_url("https://arkland.com.br/api/payments/webhook")
    assert not is_public_https_url("http://arkland.com.br/x")
    assert not is_public_https_url("https://192.168.0.10/x")
    assert not is_public_https_url("https://localhost/x")
    assert not is_public_https_url("")


def test_amount_covers_package():
    assert mp_amount_covers_package({"transaction_amount": 20.0}, 20.0)
    assert mp_amount_covers_package({"transaction_amount": 25.5}, 20.0)
    assert not mp_amount_covers_package({"transaction_amount": 19.0}, 20.0)
    assert mp_amount_covers_package({}, 20.0)  # MP sempre informa; ausente (mock) não bloqueia


def test_pick_best_prefers_approved():
    r = pick_best_payment([{"id": 2, "status": "rejected"}, {"id": 1, "status": "approved"}])
    assert r["id"] == 1


# ── webhook / fluxo ──────────────────────────────────────────────────────────

def test_late_approved_after_abandoned_credits_once(client, monkeypatch, credit):
    pid = _add_payment(status="ABANDONADO")
    resp = {"id": "mp_1", "status": "approved", "external_reference": pid, "transaction_amount": 20.0}
    monkeypatch.setattr(_app_module, "fetch_payment", lambda *a, **k: resp)

    for _ in range(3):  # MP reenvia / duplicado — nunca credita 2x
        r = client.post("/api/payments/webhook", json={"type": "payment", "data": {"id": "mp_1"}})
        assert r.get_json()["ok"] is True

    assert credit.calls == 1
    assert _row(pid) == {"status": "APROVADO", "credited": True, "mp_id": "mp_1"}
    assert _events("mp_webhook_received")
    assert _events("mp_payment_checked")


def test_amount_below_package_is_not_credited(client, monkeypatch, credit):
    pid = _add_payment(amount=20.0)
    resp = {"id": "mp_1", "status": "approved", "external_reference": pid, "transaction_amount": 5.0}
    monkeypatch.setattr(_app_module, "fetch_payment", lambda *a, **k: resp)
    client.post("/api/payments/webhook", json={"type": "payment", "data": {"id": "mp_1"}})
    assert credit.calls == 0
    assert _row(pid)["credited"] is False
    assert _events("mp_amount_mismatch")


def test_merchant_order_topic_is_ignored(client, monkeypatch, credit):
    called = {"n": 0}

    def _fetch(*a, **k):
        called["n"] += 1
        return {}

    monkeypatch.setattr(_app_module, "fetch_payment", _fetch)
    r = client.post("/api/payments/webhook?topic=merchant_order&id=123", json={})
    assert r.get_json().get("ignored") is True
    assert called["n"] == 0
    assert _events("mp_webhook_ignored")


def test_fetch_is_retried_on_transient_failure(client, monkeypatch, credit):
    pid = _add_payment()
    attempts = {"n": 0}

    def _fetch(*a, **k):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("timeout")
        return {"id": "mp_1", "status": "approved", "external_reference": pid, "transaction_amount": 20.0}

    monkeypatch.setattr(_app_module, "fetch_payment", _fetch)
    client.post("/api/payments/webhook", json={"type": "payment", "data": {"id": "mp_1"}})
    assert attempts["n"] == 3
    assert credit.calls == 1


def test_fetch_failure_is_recorded(client, monkeypatch, credit):
    pid = _add_payment()

    def _boom(*a, **k):
        raise RuntimeError("mp offline")

    monkeypatch.setattr(_app_module, "fetch_payment", _boom)
    client.post("/api/payments/webhook", json={"type": "payment", "data": {"id": "mp_1"}})
    assert credit.calls == 0
    assert _events("mp_payment_fetch_failed")
    assert _row(pid)["credited"] is False


def test_bad_signature_processed_unless_strict(client, monkeypatch, credit):
    pid = _add_payment()
    monkeypatch.setattr(_app_module, "_get_mp_webhook_secret", lambda: "segredo")
    resp = {"id": "mp_1", "status": "approved", "external_reference": pid, "transaction_amount": 20.0}
    monkeypatch.setattr(_app_module, "fetch_payment", lambda *a, **k: resp)
    hdr = {"x-signature": "ts=1,v1=deadbeef", "x-request-id": "r1"}

    monkeypatch.setattr(_app_module, "_mp_webhook_strict_signature", lambda: True)
    r = client.post("/api/payments/webhook", json={"type": "payment", "data": {"id": "mp_1"}}, headers=hdr)
    assert r.status_code == 401
    assert credit.calls == 0
    assert _events("mp_webhook_rejected")

    monkeypatch.setattr(_app_module, "_mp_webhook_strict_signature", lambda: False)
    r = client.post("/api/payments/webhook", json={"type": "payment", "data": {"id": "mp_1"}}, headers=hdr)
    assert r.status_code == 200
    assert credit.calls == 1


def test_late_rejected_does_not_downgrade_credited(client, monkeypatch, credit):
    pid = _add_payment(status="APROVADO", credited=True)
    resp = {"id": "mp_old", "status": "rejected", "external_reference": pid}
    monkeypatch.setattr(_app_module, "fetch_payment", lambda *a, **k: resp)
    client.post("/api/payments/webhook", json={"type": "payment", "data": {"id": "mp_old"}})
    assert _row(pid)["status"] == "APROVADO"
    assert credit.calls == 0


# ── reconciliação admin ──────────────────────────────────────────────────────

def test_admin_reconcile_requires_admin_and_confirm(client, monkeypatch, credit):
    pid = _add_payment()
    r = client.post(f"/api/admin/pix/{pid}/reconcile", json={"confirm": True})
    assert r.status_code in (401, 403)
    _login(client, USER_STEAM)
    r = client.post(f"/api/admin/pix/{pid}/reconcile", json={"confirm": True})
    assert r.status_code == 403
    _login(client, ADMIN_STEAM)
    r = client.post(f"/api/admin/pix/{pid}/reconcile", json={})
    assert r.status_code == 400
    assert credit.calls == 0


def test_admin_reconcile_pix_credits_once_and_audits(client, monkeypatch, credit):
    pid = _add_payment(status="ABANDONADO")
    resp = {"id": "mp_1", "status": "approved", "external_reference": pid, "transaction_amount": 20.0}
    monkeypatch.setattr(_app_module, "fetch_payment", lambda *a, **k: resp)
    _login(client, ADMIN_STEAM)

    r = client.post(f"/api/admin/pix/{pid}/reconcile", json={"confirm": True})
    d = r.get_json()
    assert d["ok"] is True and d["result"] == "credited"
    assert credit.calls == 1
    assert _row(pid) == {"status": "APROVADO", "credited": True, "mp_id": "mp_1"}

    r2 = client.post(f"/api/admin/pix/{pid}/reconcile", json={"confirm": True})
    assert r2.get_json()["result"] == "already_credited"
    assert credit.calls == 1

    ev = _events("pix_admin_reconcile")
    assert ev and ev[0].actor_steam_id == ADMIN_STEAM
    assert _events("mp_payment_checked")[0].actor_type == "admin"


def test_admin_reconcile_card_without_mp_id_uses_search(client, monkeypatch, credit):
    pid = _add_payment(method="card", mp_id=None, amount=250.0, points=1375000)
    paid = {"id": 181748248168, "status": "approved", "external_reference": pid, "transaction_amount": 250.0}
    rejected = {"id": 1, "status": "rejected", "external_reference": pid}
    monkeypatch.setattr(
        "pix_payments.search_payments_by_external_reference",
        lambda tok, ref, **k: [rejected, paid],
    )
    _login(client, ADMIN_STEAM)
    r = client.post(f"/api/admin/pix/{pid}/reconcile", json={"confirm": True})
    assert r.get_json()["result"] == "credited"
    assert credit.calls == 1
    assert _row(pid)["mp_id"] == "181748248168"


def test_admin_reconcile_pending_at_mp_does_not_credit(client, monkeypatch, credit):
    pid = _add_payment()
    resp = {"id": "mp_1", "status": "pending", "external_reference": pid, "transaction_amount": 20.0}
    monkeypatch.setattr(_app_module, "fetch_payment", lambda *a, **k: resp)
    _login(client, ADMIN_STEAM)
    d = client.post(f"/api/admin/pix/{pid}/reconcile", json={"confirm": True}).get_json()
    assert d["credited"] is False
    assert credit.calls == 0


def test_audit_list_includes_last_mp_event(client, monkeypatch, credit):
    pid = _add_payment()
    resp = {"id": "mp_1", "status": "pending", "external_reference": pid, "transaction_amount": 20.0}
    monkeypatch.setattr(_app_module, "fetch_payment", lambda *a, **k: resp)
    client.post("/api/payments/webhook", json={"type": "payment", "data": {"id": "mp_1"}})
    _login(client, ADMIN_STEAM)
    d = client.get("/api/admin/pix/audit").get_json()
    item = next(i for i in d["items"] if i["payment_id"] == pid)
    assert item["last_mp_event"]["event_type"] == "mp_payment_checked"


def test_webhook_diagnostics_warns_when_not_public(client, monkeypatch):
    monkeypatch.setattr(_app_module, "_shop_public_base_url", lambda: "http://192.168.0.5:5000")
    _login(client, ADMIN_STEAM)
    d = client.get("/api/admin/pix/webhook-diagnostics").get_json()
    assert d["ok"] is True
    assert d["expected_webhook_url_public"] is False
    assert any("pública" in w for w in d["warnings"])
    assert "mp_access_token" not in json.dumps(d)


def test_notification_url_sent_only_when_public(monkeypatch):
    monkeypatch.setattr(_app_module, "_load_settings", lambda: {"mp_notification_url": "http://192.168.0.5/x"})
    assert _app_module._mp_notification_url() == ""
    monkeypatch.setattr(
        _app_module, "_load_settings",
        lambda: {"mp_notification_url": "https://arkland.com.br/api/payments/webhook"},
    )
    assert _app_module._mp_notification_url() == "https://arkland.com.br/api/payments/webhook"


def test_auto_reconcile_batch_credits_pending(client, monkeypatch, credit):
    pid = _add_payment(status="ABANDONADO")
    resp = {"id": "mp_1", "status": "approved", "external_reference": pid, "transaction_amount": 20.0}
    monkeypatch.setattr(_app_module, "fetch_payment", lambda *a, **k: resp)
    out = _pj.reconcile_pending_payments()
    assert out == {"checked": 1, "credited": 1}
    out2 = _pj.reconcile_pending_payments()
    assert out2["checked"] == 0
    assert credit.calls == 1


def test_auto_reconcile_tick_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(_app_module, "_mp_auto_reconcile_enabled", lambda: False)
    called = {"n": 0}
    monkeypatch.setattr(_pj, "reconcile_pending_payments", lambda **k: called.__setitem__("n", 1))
    _app_module._mp_auto_reconcile_tick()
    assert called["n"] == 0
