"""Testes de integração para cargos MOD/STAFF — sessão SQLAlchemy."""
from __future__ import annotations

import json
import os
import sys

import pytest
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as _app_module
from app import app, _configure_database, _now

ADMIN_STEAM = "76561198000000001"
TARGET_STEAM = "76561198000000099"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(_app_module, "_PLAYERS_FILE", tmp_path / "players.json")
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", tmp_path / "servers.json")
    monkeypatch.setattr(_app_module, "_migrate_schema", lambda _engine: None)
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]), encoding="utf-8")

    db_path = str(tmp_path / "test.db")
    _configure_database(f"sqlite:///{db_path}")
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
        db.add(_app_module.StoreUser(
            steam_id=TARGET_STEAM,
            display_name="Alvo",
            steam_persona="Alvo",
            last_login_at=_now(),
        ))
        db.commit()
    finally:
        _app_module._release_db_session(db)
    monkeypatch.setattr(_app_module, "_DB_INITIALIZED", True)
    monkeypatch.setattr(
        _app_module,
        "_sync_permissions_all_servers",
        lambda *a, **k: [{"server_id": "default", "label": "padrão", "ok": True}],
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


def test_grant_moderacao_staff_role_integration(client):
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

    ents = _app_module._get_player_entitlements(TARGET_STEAM)
    assert any(e["group"] == "Moderacao" for e in ents)


def test_admin_player_detail_after_entitlements(client):
    """Detalhe do jogador não pode acessar ORM após helpers fecharem a sessão."""
    _login(client, ADMIN_STEAM)
    r = client.get(f"/api/admin/players/{TARGET_STEAM}")
    body = r.get_json()
    assert r.status_code == 200, body
    assert body["ok"] is True
    assert body["player"]["display_name"] == "Alvo"


def test_legacy_db_close_still_works_for_staff_grant(client, monkeypatch):
    """Com sessão única no grant, legado db.close() não deve quebrar o fluxo."""

    def legacy_close(db):
        if db is not None:
            db.close()

    monkeypatch.setattr(_app_module, "_release_db_session", legacy_close)
    _login(client, ADMIN_STEAM)
    r = client.post(
        f"/api/admin/players/{TARGET_STEAM}/staff-roles",
        json={"action": "grant", "group": "Moderacao"},
    )
    body = r.get_json()
    assert body.get("ok") is True, body
    assert any(e["group"] == "Moderacao" for e in body.get("staff_roles", []))
