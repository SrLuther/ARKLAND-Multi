"""Testes da seção Mapas da Home (FeaturedMaps)."""
from __future__ import annotations

import json

import pytest

import app as _app_module
from app import app, _configure_database

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


def _login_admin(client):
    with client.session_transaction() as sess:
        sess["steam_id"] = ADMIN_STEAM


def test_public_home_includes_map_stats(client, tmp_path, monkeypatch):
    servers_file = tmp_path / "servers.json"
    servers_file.write_text(
        json.dumps([{
            "server_id": "brighamia",
            "label": "Brighamia",
            "config_snapshot": {
                "xp_multiplier": 44,
                "taming_speed_multiplier": 20,
                "harvest_amount_multiplier": 15,
                "baby_mature_speed_multiplier": 1,
                "max_player_level": 180,
                "max_dino_level": 150,
            },
        }]),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", servers_file)

    home = client.get("/api/public/home").get_json()
    brighamia = next(m for m in home["featured_maps"] if m["name"] == "Brighamia")
    assert brighamia.get("stats", {}).get("xp") == "44x"
    assert brighamia["stats"]["max_dino_level"] == 150


def test_public_home_auto_maps_from_servers(client, tmp_path, monkeypatch):
    """Com servidores syncados, a home lista mapas do ASM — sem FeaturedMaps manual."""
    servers_file = tmp_path / "servers.json"
    servers_file.write_text(
        json.dumps([
            {
                "server_id": "alps",
                "label": "Alps",
                "server_map": "Alps_WP",
                "show_on_home": True,
                "config_snapshot": {
                    "xp_multiplier": 5,
                    "taming_speed_multiplier": 5,
                    "harvest_amount_multiplier": 5,
                    "max_player_level": 180,
                    "max_dino_level": 150,
                },
            },
            {
                "server_id": "crystal",
                "label": "Crystal Isles",
                "server_map": "CrystalIsles",
                "show_on_home": True,
                "config_snapshot": {"xp_multiplier": 3},
            },
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", servers_file)

    home = client.get("/api/public/home").get_json()
    names = [m["name"] for m in home["featured_maps"]]
    assert names == ["Alps", "Crystal Isles"]
    alps = next(m for m in home["featured_maps"] if m["name"] == "Alps")
    assert alps["stats"]["xp"] == "5x"
    assert alps["mod_map"] is True
    crystal = next(m for m in home["featured_maps"] if m["name"] == "Crystal Isles")
    assert crystal["mod_map"] is False


def test_public_home_default_featured_maps(client):
    r = client.get("/api/public/home")
    assert r.status_code == 200
    data = r.get_json()
    names = [m["name"] for m in data.get("featured_maps", [])]
    assert "Brighamia" in names
    assert "The Volcano" in names
    assert "Amissa" in names
    assert "Crystal Isles" in names
    assert "Genesis 2" in names
    assert len(names) == 6
    assert data.get("featured_maps_section", {}).get("title")


def test_featured_map_crud_and_hide(client):
    _login_admin(client)
    r = client.post(
        "/api/featured-maps",
        json={"name": "Test Map", "description": "Desc", "mod_map": True},
    )
    assert r.status_code == 200
    map_id = r.get_json()["map"]["id"]

    r2 = client.put(
        f"/api/featured-maps/{map_id}",
        json={"name": "Test Map", "description": "Desc", "enabled": False},
    )
    assert r2.status_code == 200

    home = client.get("/api/public/home").get_json()
    assert all(m["name"] != "Test Map" for m in home["featured_maps"])

    r3 = client.delete(f"/api/featured-maps/{map_id}")
    assert r3.status_code == 200


def test_featured_maps_section_settings(client):
    _login_admin(client)
    r = client.put(
        "/api/featured-maps/settings",
        json={"title": "Meus Mapas", "intro": "Intro customizada."},
    )
    assert r.status_code == 200
    home = client.get("/api/public/home").get_json()
    sec = home.get("featured_maps_section", {})
    assert sec.get("title") == "Meus Mapas"
    assert sec.get("intro") == "Intro customizada."
