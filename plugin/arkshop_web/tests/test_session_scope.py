"""Regressão: scoped_session não deve desanexar ORM durante request Flask."""
from __future__ import annotations

import json
import os
import sys
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as _app_module
from app import app, _configure_database, _now

ADMIN_STEAM = "76561198000000001"
USER_STEAM = "76561198000000002"
TARGET_STEAM = "76561198000000099"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_API_KEY", "test-api-key")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(_app_module, "_PLAYERS_FILE", tmp_path / "players.json")
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", tmp_path / "servers.json")
    monkeypatch.setattr(_app_module, "_migrate_schema", lambda _engine: None)

    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]), encoding="utf-8")
    (tmp_path / "settings.json").write_text(
        json.dumps({
            "mp_access_token": "TEST_MP_TOKEN",
            "mp_sandbox": True,
            "delivery_mode": "plugin",
            "server_id": "default",
        }),
        encoding="utf-8",
    )

    db_path = str(tmp_path / "test.db")
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    if _app_module._ENGINE is not None:
        _app_module.Base.metadata.create_all(bind=_app_module._ENGINE)
        with _app_module._ENGINE.connect() as conn:
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS players ("
                    "steam_id VARCHAR(20) PRIMARY KEY NOT NULL, "
                    "points INTEGER NOT NULL DEFAULT 0, "
                    "kits TEXT DEFAULT '{}'"
                    ")"
                )
            )
            conn.commit()
        db = _app_module._SessionLocal()
        try:
            _app_module._ensure_entitlements_schema(db)
            db.add(
                _app_module.MarketPlayerProfile(
                    steam_id=USER_STEAM,
                    market_display_name="PixPlayer",
                    commerce_enabled=True,
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
            from regulamento_config import REGULAMENTO_VERSION

            db.add(
                _app_module.StoreUser(
                    steam_id=USER_STEAM,
                    display_name="PixPlayer",
                    regulamento_accepted_version=REGULAMENTO_VERSION,
                    regulamento_accepted_at=_now(),
                    last_login_at=_now(),
                )
            )
            db.commit()
        finally:
            _app_module._release_db_session(db)
    monkeypatch.setattr(_app_module, "_DB_INITIALIZED", True)
    monkeypatch.setattr(_app_module, "_get_mp_access_token", lambda: "TEST_MP_TOKEN")
    monkeypatch.setattr(_app_module, "_mp_sandbox", lambda: True)
    monkeypatch.setattr(
        _app_module,
        "_auth_display_name_fields",
        lambda _sid, is_admin: {
            "market_display_name": "PixPlayer",
            "needs_display_name": False,
        },
    )
    monkeypatch.setattr(
        _app_module,
        "_sync_permissions_all_servers",
        lambda sid, grp, grant: [{"server_id": "default", "label": "padrão", "ok": True}],
    )
    yield
    _configure_database("")


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login(client, steam_id: str) -> None:
    with client.session_transaction() as sess:
        sess["steam_id"] = steam_id


def test_audit_event_keeps_orm_attached_during_request(client):
    with client.application.test_request_context("/"):
        db = _app_module._SessionLocal()
        row = _app_module.PointPayment(
            payment_id=str(uuid.uuid4()),
            mp_payment_id="mp_test",
            steam_id=USER_STEAM,
            package_id="p10000",
            amount_brl=5.0,
            points=10000,
            status="PENDENTE",
            payment_method="pix",
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(row)
        db.commit()
        _app_module._audit_event("pix_checkout_created", order_id=row.payment_id, persist=True)
        assert row.status == "PENDENTE"
        assert row.points == 10000


def test_pix_checkout_after_donor_data(client, monkeypatch):
    _login(client, USER_STEAM)
    monkeypatch.setattr(
        _app_module,
        "_load_point_packages",
        lambda: _app_module._DEFAULT_POINT_PACKAGES,
    )
    fake_mp = {
        "id": "mp_pix_001",
        "status": "pending",
        "point_of_interaction": {
            "transaction_data": {
                "qr_code_base64": "abc123",
                "qr_code": "00020126580014br.gov.bcb.pix",
            }
        },
    }
    with patch.object(_app_module, "create_pix_payment", return_value=fake_mp):
        r = client.post(
            "/api/player/pix/checkout",
            json={
                "package_id": "p10000",
                "payer": {
                    "email": "player@example.com",
                    "full_name": "João Silva",
                    "cpf": "529.982.247-25",
                    "phone": "(11) 98765-4321",
                },
            },
        )
    body = r.get_json()
    assert r.status_code == 200, body
    assert body["ok"] is True
    assert body["status"] == "PENDENTE"
    assert body["pix_copy_paste"] == "00020126580014br.gov.bcb.pix"
    assert body["points"] == 10000

    db = _app_module._SessionLocal()
    try:
        row = db.query(_app_module.PointPayment).filter(
            _app_module.PointPayment.payment_id == body["payment_id"]
        ).first()
        assert row is not None
        assert row.payer_email == "player@example.com"
    finally:
        _app_module._release_db_session(db)


def test_grant_moderacao_staff_role_no_detach(client):
    _login(client, ADMIN_STEAM)
    r = client.post(
        f"/api/admin/players/{TARGET_STEAM}/staff-roles",
        json={"action": "grant", "group": "Moderacao", "reason": "teste integração"},
    )
    body = r.get_json()
    assert r.status_code == 200, body
    assert body["ok"] is True
    assert body["group"] == "Moderacao"
    assert any(e["group"] == "Moderacao" for e in body["staff_roles"])

    detail = client.get(f"/api/admin/players/{TARGET_STEAM}").get_json()
    assert detail["ok"] is True
    assert any(e["group"] == "Moderacao" for e in detail["player"]["staff_roles"])
