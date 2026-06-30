"""Cargos MOD/STAFF no painel Gerenciar Jogadores."""
from __future__ import annotations

import json

import pytest

import app as _app_module
from app import app

ADMIN_STEAM = "76561198000000001"
USER_STEAM = "76561198000000002"
TARGET_STEAM = "76561198000000099"


@pytest.fixture(autouse=True)
def _admin_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_WEB_SECRET", "test-secret")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]), encoding="utf-8")
    yield


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login(client, steam_id: str) -> None:
    with client.session_transaction() as sess:
        sess["steam_id"] = steam_id


def test_staff_role_catalog(client):
    _login(client, ADMIN_STEAM)
    r = client.get("/api/admin/staff-roles")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    groups = {item["group"] for item in data["items"]}
    assert groups == {"Moderacao", "Mod", "STAFF"}
    labels = {item["label"] for item in data["items"]}
    assert "MOD" in labels


def test_grant_and_revoke_staff_role(client, monkeypatch):
    _login(client, ADMIN_STEAM)
    monkeypatch.setattr(
        _app_module,
        "_grant_player_entitlement",
        lambda sid, grp, days, **kw: None,
    )
    monkeypatch.setattr(
        _app_module,
        "_revoke_player_entitlement_by_group",
        lambda sid, grp: None,
    )
    monkeypatch.setattr(
        _app_module,
        "_get_player_staff_roles",
        lambda sid: [{"group": "STAFF"}],
    )
    monkeypatch.setattr(
        _app_module,
        "_sync_permissions_all_servers",
        lambda sid, grp, grant: [{"server_id": "map1", "label": "Mapa", "ok": True}],
    )
    monkeypatch.setattr(_app_module, "_audit_event", lambda *a, **k: None)
    monkeypatch.setattr(_app_module, "_db_ready", lambda: True)

    r = client.post(
        f"/api/admin/players/{TARGET_STEAM}/staff-roles",
        json={"action": "grant", "group": "STAFF", "reason": "teste"},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["group"] == "STAFF"
    assert body["permissions_sync"][0]["ok"] is True

    r2 = client.post(
        f"/api/admin/players/{TARGET_STEAM}/staff-roles",
        json={"action": "revoke", "group": "STAFF"},
    )
    assert r2.status_code == 200


def test_staff_role_rejected_as_license(client, monkeypatch):
    _login(client, ADMIN_STEAM)
    monkeypatch.setattr(_app_module, "_db_ready", lambda: True)
    r = client.post(
        f"/api/admin/players/{TARGET_STEAM}/licenses",
        json={"action": "grant", "group": "STAFF", "days": 30},
    )
    assert r.status_code == 400
    assert "Cargos" in (r.get_json() or {}).get("error", "")


def test_staff_roles_require_admin(client):
    _login(client, USER_STEAM)
    r = client.get("/api/admin/staff-roles")
    assert r.status_code in (401, 403)
