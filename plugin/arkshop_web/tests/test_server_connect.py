"""Testes de conexão direta aos servidores (home pública)."""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as _app_module
from app import _configure_database, app
from server_connect import (
    build_join_address,
    build_steam_connect_url,
    diagnose_server_connect,
    public_server_connect_view,
    resolve_join_host,
)

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

    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    yield


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_resolve_join_host_prefers_game_host_over_local_rcon():
    srv = {
        "rcon_host": "127.0.0.1",
        "game_host": "203.0.113.10",
        "game_port": 7777,
    }
    assert resolve_join_host(srv, {}) == "203.0.113.10"


def test_resolve_join_host_explicit_join_host():
    srv = {
        "join_host": "play.arkland.example",
        "game_host": "203.0.113.10",
        "rcon_host": "10.0.0.1",
    }
    assert resolve_join_host(srv, {}) == "play.arkland.example"


def test_resolve_join_host_falls_back_to_settings_public_ip():
    srv = {"rcon_host": "127.0.0.1", "game_host": "127.0.0.1"}
    assert resolve_join_host(srv, {"public_ip": "198.51.100.5"}) == "198.51.100.5"


def test_resolve_join_host_falls_back_to_settings_join_host():
    srv = {"rcon_host": "127.0.0.1", "game_host": "127.0.0.1"}
    assert resolve_join_host(srv, {"join_host": "play.example.com"}) == "play.example.com"


def test_resolve_join_host_uses_public_rcon_host():
    srv = {"rcon_host": "203.0.113.99", "game_host": "127.0.0.1"}
    assert resolve_join_host(srv, {}) == "203.0.113.99"


def test_build_steam_connect_url_and_join_address():
    assert build_steam_connect_url("203.0.113.10", 7777) == "steam://connect/203.0.113.10:7777"
    assert build_join_address("203.0.113.10", 7777) == "203.0.113.10:7777"


def test_public_server_connect_view_includes_map():
    view = public_server_connect_view(
        {
            "game_host": "203.0.113.10",
            "game_port": 7778,
            "server_map": "The Island",
        },
        {},
    )
    assert view["can_connect"] is True
    assert view["connect_url"] == "steam://connect/203.0.113.10:7778"
    assert view["join_address"] == "203.0.113.10:7778"
    assert view["map"] == "The Island"


def test_public_home_includes_connect_fields(client, tmp_path, monkeypatch):
    servers_file = tmp_path / "servers.json"
    servers_file.write_text(
        json.dumps([{
            "server_id": "brighamia",
            "label": "Brighamia",
            "show_on_home": True,
            "game_host": "203.0.113.20",
            "game_port": 7777,
            "server_map": "Brighamia",
            "rcon_host": "127.0.0.1",
            "rcon_password": "secret",
        }]),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", servers_file)

    home = client.get("/api/public/home").get_json()
    srv = next(s for s in home["servers"] if s["server_id"] == "brighamia")

    assert srv["can_connect"] is True
    assert srv["connect_url"] == "steam://connect/203.0.113.20:7777"
    assert srv["join_address"] == "203.0.113.20:7777"
    assert srv["map"] == "Brighamia"
    assert "rcon_password" not in srv


def test_public_home_can_connect_false_without_public_host(client, tmp_path, monkeypatch):
    servers_file = tmp_path / "servers.json"
    servers_file.write_text(
        json.dumps([{
            "server_id": "local_only",
            "label": "Local",
            "show_on_home": True,
            "game_host": "127.0.0.1",
            "rcon_host": "127.0.0.1",
            "game_port": 7777,
        }]),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", servers_file)

    home = client.get("/api/public/home").get_json()
    srv = next(s for s in home["servers"] if s["server_id"] == "local_only")

    assert srv["can_connect"] is False
    assert srv["connect_url"] == ""
    assert srv["join_address"] == ""


def test_public_home_uses_settings_join_host_fallback(client, tmp_path, monkeypatch):
    servers_file = tmp_path / "servers.json"
    servers_file.write_text(
        json.dumps([{
            "server_id": "needs_fallback",
            "label": "Needs Fallback",
            "show_on_home": True,
            "game_host": "127.0.0.1",
            "rcon_host": "127.0.0.1",
            "game_port": 7779,
        }]),
        encoding="utf-8",
    )
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps({
            "config_path": str(tmp_path / "config.json"),
            "join_host": "play.arkland.example",
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", servers_file)
    monkeypatch.setattr(_app_module, "_STATE_FILE", settings_file)

    home = client.get("/api/public/home").get_json()
    srv = next(s for s in home["servers"] if s["server_id"] == "needs_fallback")

    assert srv["can_connect"] is True
    assert srv["join_address"] == "play.arkland.example:7779"


def test_diagnose_server_connect_lists_blockers():
    view = diagnose_server_connect(
        {"server_id": "x", "show_on_home": False, "game_host": "127.0.0.1", "game_port": 7777},
        {},
    )
    assert view["can_connect"] is False
    assert any("show_on_home" in b for b in view["blockers"])
    assert any("host público" in b for b in view["blockers"])
