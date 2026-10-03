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
    ARK_ASE_STEAM_APP_ID,
    build_join_address,
    build_steam_connect_url,
    diagnose_server_connect,
    public_server_connect_view,
    resolve_game_port,
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
    assert build_steam_connect_url("203.0.113.10", 7777) == (
        f"steam://run/{ARK_ASE_STEAM_APP_ID}//+connect%20203.0.113.10:7777"
    )
    assert build_join_address("203.0.113.10", 7777) == "203.0.113.10:7777"


def test_resolve_game_port_ignores_query_port():
    assert resolve_game_port({"query_port": 7790}) == 7777
    assert resolve_game_port({"game_port": 7788, "query_port": 7790}) == 7788
    assert resolve_game_port({"server_port": 7789, "query_port": 7791}) == 7789


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
    assert view["connect_url"] == f"steam://run/{ARK_ASE_STEAM_APP_ID}//+connect%20203.0.113.10:7778"
    assert view["join_address"] == "203.0.113.10:7778"
    assert view["map"] == "The Island"
    assert view["steam_app_id"] == ARK_ASE_STEAM_APP_ID


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
    assert srv["connect_url"] == f"steam://run/{ARK_ASE_STEAM_APP_ID}//+connect%20203.0.113.20:7777"
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


# ── IP:QueryPort na home ─────────────────────────────────────────────────────

def test_resolve_query_port_valid_and_invalid():
    from server_connect import resolve_query_port

    assert resolve_query_port({"query_port": 27015}) == 27015
    assert resolve_query_port({"query_port": "27017"}) == 27017
    for bad in (None, "", 0, -1, "abc", 70000):
        assert resolve_query_port({"query_port": bad}) is None
    assert resolve_query_port({}) is None


def test_resolve_display_port_prefers_query_with_fallback():
    from server_connect import resolve_display_port

    assert resolve_display_port({"game_port": 7777, "query_port": 27015}) == (27015, "query")
    assert resolve_display_port({"game_port": 7779}) == (7779, "game_fallback")
    assert resolve_display_port({"server_port": 7781, "query_port": ""}) == (7781, "game_fallback")
    assert resolve_display_port({}) == (7777, "game_fallback")


def test_public_view_uses_query_port_for_join_address():
    view = public_server_connect_view(
        {"game_host": "179.185.19.88", "game_port": 7777, "query_port": 27015}, {},
    )
    assert view["join_address"] == "179.185.19.88:27015"
    assert view["connect_url"].endswith("%20179.185.19.88:27015")
    assert view["game_address"] == "179.185.19.88:7777"
    assert view["game_port"] == 7777
    assert view["query_port"] == 27015
    assert view["display_port_source"] == "query"


def test_public_view_fallback_to_game_port_without_query(caplog):
    with caplog.at_level("WARNING"):
        view = public_server_connect_view(
            {"server_id": "legacy_x", "game_host": "179.185.19.88", "game_port": 7779}, {},
        )
    assert view["join_address"] == "179.185.19.88:7779"
    assert view["query_port"] is None
    assert view["display_port_source"] == "game_fallback"
    assert any("sem query_port" in r.getMessage() for r in caplog.records)


def test_diagnose_warns_when_query_port_missing():
    view = diagnose_server_connect(
        {"server_id": "x", "game_host": "203.0.113.5", "game_port": 7777}, {},
    )
    assert view["display_port_source"] == "game_fallback"
    assert any("query_port" in w for w in view["warnings"])
    ok = diagnose_server_connect(
        {"server_id": "y", "game_host": "203.0.113.5", "game_port": 7777, "query_port": 27015}, {},
    )
    assert ok["warnings"] == []
    assert ok["resolved_port"] == 27015


def test_public_home_api_returns_query_port(client, tmp_path, monkeypatch):
    servers_file = tmp_path / "servers.json"
    servers_file.write_text(
        json.dumps([{
            "server_id": "alps",
            "label": "01 ALPS",
            "show_on_home": True,
            "game_host": "179.185.19.88",
            "game_port": 7777,
            "query_port": 27015,
            "rcon_host": "127.0.0.1",
            "rcon_password": "secret",
        }]),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", servers_file)

    home = client.get("/api/public/home").get_json()
    srv = next(s for s in home["servers"] if s["server_id"] == "alps")
    assert srv["join_address"] == "179.185.19.88:27015"
    assert srv["query_port"] == 27015
    assert srv["game_port"] == 7777
    assert srv["game_address"] == "179.185.19.88:7777"


def test_sync_endpoint_persists_query_port(client):
    r = client.post(
        "/api/servers/sync",
        json={
            "machine_label": "Maquina-Q",
            "servers": [{
                "server_id": "ragnarok",
                "label": "02 RAGNAROK",
                "rcon_host": "127.0.0.1",
                "game_host": "179.185.19.88",
                "game_port": 7779,
                "query_port": 27017,
                "arkland_ref": "tek:rag-1",
            }],
            "active_refs": ["tek:rag-1"],
        },
        headers={"X-API-Key": "test-key", "Content-Type": "application/json"},
    )
    assert r.status_code == 200
    home = client.get("/api/public/home").get_json()
    srv = next(s for s in home["servers"] if s["server_id"] == "ragnarok")
    assert srv["join_address"] == "179.185.19.88:27017"
    assert srv["query_port"] == 27017
