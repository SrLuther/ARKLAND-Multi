"""Equipe de suporte — acesso à fila de tickets sem permissões de admin."""
from __future__ import annotations

import json

import pytest

import app as _app_module
from app import app

ADMIN_STEAM = "76561198000000001"
SUPPORT_STEAM = "76561198000000003"
USER_STEAM = "76561198000000002"


@pytest.fixture(autouse=True)
def _role_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_WEB_SECRET", "test-secret")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_SUPPORT_FILE", tmp_path / "support_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]), encoding="utf-8")
    (tmp_path / "support_steamids.json").write_text(json.dumps([SUPPORT_STEAM]), encoding="utf-8")
    _app_module._invalidate_support_steamids_cache()
    _app_module._ADMIN_STEAMIDS_CACHE["ids"] = None
    _app_module._ADMIN_STEAMIDS_CACHE["expires"] = 0.0
    yield


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login(client, steam_id: str) -> None:
    with client.session_transaction() as sess:
        sess["steam_id"] = steam_id


def test_auth_me_support_flags(client):
    _login(client, SUPPORT_STEAM)
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    body = r.get_json()
    assert body["authenticated"] is True
    assert body["is_admin"] is False
    assert body["is_support"] is True
    assert body["can_manage_tickets"] is True


def test_auth_me_admin_not_marked_support(client):
    _login(client, ADMIN_STEAM)
    body = client.get("/api/auth/me").get_json()
    assert body["is_admin"] is True
    assert body["is_support"] is False
    assert body["can_manage_tickets"] is True


def test_support_staff_crud_requires_admin(client):
    _login(client, USER_STEAM)
    assert client.get("/api/admin/support-staff").status_code == 403
    assert client.post("/api/admin/support-staff", json={"steam_id": USER_STEAM}).status_code == 403


def test_admin_lists_and_adds_support_staff(client, tmp_path, monkeypatch):
    monkeypatch.setattr(_app_module, "_db_ready", lambda: False)
    new_sid = "76561198000000099"
    _login(client, ADMIN_STEAM)

    listed = client.get("/api/admin/support-staff").get_json()
    assert listed["ok"] is True
    assert SUPPORT_STEAM in listed["items"]

    added = client.post("/api/admin/support-staff", json={"steam_id": new_sid}).get_json()
    assert added["ok"] is True

    listed2 = client.get("/api/admin/support-staff").get_json()
    assert new_sid in listed2["items"]

    removed = client.delete(f"/api/admin/support-staff/{new_sid}").get_json()
    assert removed["ok"] is True
    assert new_sid not in client.get("/api/admin/support-staff").get_json()["items"]

    if not _app_module._db_ready():
        data = json.loads((tmp_path / "support_steamids.json").read_text(encoding="utf-8"))
        assert SUPPORT_STEAM in data
        assert new_sid not in data


def test_cannot_add_admin_as_support(client):
    _login(client, ADMIN_STEAM)
    r = client.post("/api/admin/support-staff", json={"steam_id": ADMIN_STEAM})
    assert r.status_code == 400
    assert "administrador" in r.get_json().get("error", "").lower()


def test_can_manage_tickets_helpers():
    assert _app_module._can_manage_tickets(ADMIN_STEAM) is True
    assert _app_module._can_manage_tickets(SUPPORT_STEAM) is True
    assert _app_module._can_manage_tickets(USER_STEAM) is False
    assert _app_module._is_support_steamid(SUPPORT_STEAM) is True
    assert _app_module._is_support_steamid(ADMIN_STEAM) is False


def test_regular_user_cannot_access_ticket_queue(client, monkeypatch):
    _login(client, USER_STEAM)
    monkeypatch.setattr(_app_module, "_db_ready", lambda: True)
    r = client.get("/api/admin/tickets")
    assert r.status_code == 403


def test_support_cannot_access_settings(client):
    _login(client, SUPPORT_STEAM)
    assert client.get("/api/settings").status_code == 403
