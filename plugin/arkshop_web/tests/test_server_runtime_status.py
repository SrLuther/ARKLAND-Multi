"""Status runtime TEK → home pública."""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as _app_module
from app import _configure_database, app
from server_runtime_status import get_all_statuses, upsert_statuses

ADMIN_STEAM = "76561198000000001"


@pytest.fixture(autouse=True)
def fresh_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_API_KEY", "test-key")
    monkeypatch.setattr(_app_module, "_ARKSHOP_API_KEY", "test-key")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]))

    catalog = tmp_path / "config.json"
    catalog.write_text(json.dumps({"Settings": {}, "FeaturedMaps": []}), encoding="utf-8")
    (tmp_path / "settings.json").write_text(
        json.dumps({"config_path": str(catalog)}),
        encoding="utf-8",
    )
    store = tmp_path / "server_runtime_status.json"
    monkeypatch.setattr("server_runtime_status._store_path", lambda: store)
    _configure_database(f"sqlite:///{tmp_path / 't.db'}")
    _app_module._invalidate_public_home_cache()
    yield


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_upsert_and_public_endpoint(client):
    n = upsert_statuses([
        {
            "server_id": "brighamia",
            "status": "ONLINE",
            "display_name": "[ARKLAND BR] - Brighamia",
            "updated_at": "26/07/2026 23:00:00",
            "updated_at_unix": 9999999999,
            "players": 12,
            "max_players": 70,
        }
    ])
    assert n == 1
    row = get_all_statuses()["brighamia"]
    assert row["status"] == "ONLINE"
    assert row["players"] == 12
    assert row["max_players"] == 70

    r = client.get("/api/public/server-status")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    match = next(s for s in body["servers"] if s["server_id"] == "brighamia")
    assert match["status"] == "ONLINE"
    assert match["players"] == 12
    assert match["max_players"] == 70


def test_home_includes_runtime_status(client, tmp_path, monkeypatch):
    servers_file = tmp_path / "servers.json"
    servers_file.write_text(
        json.dumps([{
            "server_id": "brighamia",
            "label": "Brighamia",
            "show_on_home": True,
            "game_host": "203.0.113.20",
            "game_port": 7777,
            "rcon_host": "127.0.0.1",
            "rcon_password": "secret",
        }]),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", servers_file)
    upsert_statuses([{
        "server_id": "brighamia",
        "status": "INICIANDO",
        "updated_at_unix": 9999999999,
        "players": 0,
        "max_players": 70,
    }])
    _app_module._invalidate_public_home_cache()
    home = client.get("/api/public/home").get_json()
    srv = next(s for s in home["servers"] if s["server_id"] == "brighamia")
    assert srv["runtime_status"] == "INICIANDO"
    assert srv["join_address"] == "203.0.113.20:7777"
    assert srv["players"] == 0
    assert srv["max_players"] == 70


def test_upsert_omits_invalid_players(tmp_path, monkeypatch):
    store = tmp_path / "server_runtime_status.json"
    monkeypatch.setattr("server_runtime_status._store_path", lambda: store)
    n = upsert_statuses([
        {
            "server_id": "alps",
            "status": "PARADO",
            "updated_at_unix": 9999999999,
            "players": "nope",
            "max_players": None,
        }
    ])
    assert n == 1
    row = get_all_statuses()["alps"]
    assert row["status"] == "PARADO"
    assert "players" not in row
    assert "max_players" not in row
