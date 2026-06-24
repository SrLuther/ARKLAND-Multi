"""Testes do log de auditoria PIX (admin)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

import app as _app_module
from app import PointPayment, app, _configure_database

ADMIN_STEAM = "76561198000000001"
USER_STEAM = "76561198000000002"


@pytest.fixture(autouse=True)
def fresh_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_API_KEY", "test-key")
    monkeypatch.setenv("MP_ACCESS_TOKEN", "test-mp-token")
    monkeypatch.setattr(_app_module, "_ARKSHOP_API_KEY", "test-key")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(_app_module, "_PLAYERS_FILE", tmp_path / "players.json")
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", tmp_path / "servers.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]))

    catalog = tmp_path / "config.json"
    catalog.write_text(json.dumps({"Settings": {}, "PointPackages": []}), encoding="utf-8")
    (tmp_path / "settings.json").write_text(
        json.dumps({"config_path": str(catalog)}),
        encoding="utf-8",
    )

    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
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


def _seed_payment(db_session, *, payment_id="pay-test-001", steam_id=USER_STEAM, status="PENDENTE", credited=False):
    row = PointPayment(
        payment_id=payment_id,
        mp_payment_id=f"mp-{payment_id}",
        steam_id=steam_id,
        package_id="pkg_1000",
        amount_brl=10.0,
        points=1000,
        status=status,
        credited=credited,
        payer_email="player@example.com",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(row)
    db_session.commit()


def test_pix_audit_forbidden_for_player(client):
    _login(client, USER_STEAM)
    r = client.get("/api/admin/pix/audit")
    assert r.status_code in (401, 403)


def test_pix_audit_lists_payments(client):
    db = _app_module._SessionLocal()
    try:
        _seed_payment(db, status="PENDENTE")
        _seed_payment(db, payment_id="pay-test-002", steam_id="76561198000000003", status="APROVADO", credited=True)
    finally:
        db.close()

    _login(client, ADMIN_STEAM)
    r = client.get("/api/admin/pix/audit")
    d = r.get_json()
    assert d.get("ok") is True
    assert d["stats"]["total"] >= 2
    assert d["stats"]["concluidas"] >= 1
    assert any(i["steam_id"] == USER_STEAM for i in d["items"])


def test_pix_abandon_creates_audit_event(client):
    db = _app_module._SessionLocal()
    try:
        _seed_payment(db, status="PENDENTE")
    finally:
        db.close()

    _login(client, USER_STEAM)
    r = client.post("/api/player/pix/pay-test-001/abandon")
    assert r.status_code == 200
    assert r.get_json().get("status") == "ABANDONADO"

    _login(client, ADMIN_STEAM)
    audit = client.get("/api/admin/audit?event_type=pix_abandoned").get_json()
    assert audit.get("ok") is True
    assert any(e["event_type"] == "pix_abandoned" for e in audit["items"])
