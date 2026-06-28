"""Sync Permissions ao conceder/revogar licenças no painel admin."""
from __future__ import annotations

import json

import pytest

import app as _app_module
from app import app

ADMIN_STEAM = "76561198000000001"
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


def test_grant_keyvault_syncs_permissions_addtimed(client, monkeypatch):
    _login(client, ADMIN_STEAM)
    sync_calls: list[tuple] = []

    monkeypatch.setattr(_app_module, "_grant_player_entitlement", lambda *a, **k: None)
    monkeypatch.setattr(
        _app_module,
        "_get_player_entitlements",
        lambda sid: [{"group": "keyvault", "expires_at": "2099-01-01"}],
    )
    monkeypatch.setattr(
        _app_module,
        "_sync_license_permissions_all_servers",
        lambda sid, grp, grant, days=0: sync_calls.append((sid, grp, grant, days))
        or [{"server_id": "map1", "label": "Mapa", "ok": True}],
    )
    monkeypatch.setattr(_app_module, "_audit_event", lambda *a, **k: None)
    monkeypatch.setattr(_app_module, "_db_ready", lambda: True)

    r = client.post(
        f"/api/admin/players/{TARGET_STEAM}/licenses",
        json={"action": "grant", "group": "keyvault", "days": 30},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert sync_calls == [(TARGET_STEAM, "keyvault", True, 30)]
    assert body["permissions_sync"][0]["ok"] is True


def test_revoke_license_syncs_permissions_remove(client, monkeypatch):
    _login(client, ADMIN_STEAM)
    sync_calls: list[tuple] = []

    monkeypatch.setattr(_app_module, "_revoke_player_entitlement_by_group", lambda *a: None)
    monkeypatch.setattr(_app_module, "_get_player_entitlements", lambda sid: [])
    monkeypatch.setattr(
        _app_module,
        "_sync_license_permissions_all_servers",
        lambda sid, grp, grant, days=0: sync_calls.append((sid, grp, grant, days))
        or [{"server_id": "map1", "label": "Mapa", "ok": True}],
    )
    monkeypatch.setattr(_app_module, "_audit_event", lambda *a, **k: None)
    monkeypatch.setattr(_app_module, "_db_ready", lambda: True)

    r = client.post(
        f"/api/admin/players/{TARGET_STEAM}/licenses",
        json={"action": "revoke", "group": "keyvault"},
    )
    assert r.status_code == 200
    assert sync_calls == [(TARGET_STEAM, "keyvault", False, 0)]
