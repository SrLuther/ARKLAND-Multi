"""Testes admin sync-all-permissions."""
from __future__ import annotations

import json

import pytest

import app as _app_module
from app import app

ADMIN_STEAM = "76561198000000001"


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


def test_admin_sync_all_permissions(client, monkeypatch):
    _login(client, ADMIN_STEAM)
    monkeypatch.setattr(
        _app_module,
        "_reconcile_all_entitlements_to_permission_db",
        lambda dry_run=False: {
            "ok": True,
            "checked": 10,
            "irregular": 2,
            "synced": 2,
            "errors": [],
        },
    )
    monkeypatch.setattr(_app_module, "_require_db", lambda: None)
    r = client.post("/api/admin/sync-all-permissions", json={})
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["synced"] == 2
