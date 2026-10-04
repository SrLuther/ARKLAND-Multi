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

    # Isola o arquivo de servidores para evitar leitura do arquivo real do ambiente
    servers_file = tmp_path / "servers.json"
    servers_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", servers_file)

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


def test_public_home_without_servers_does_not_resurrect_defaults(client):
    """Sem servidores syncados, a home não inventa a lista padrão antiga."""
    r = client.get("/api/public/home")
    assert r.status_code == 200
    data = r.get_json()
    names = [m["name"] for m in data.get("featured_maps", [])]
    assert names == []
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


def test_short_server_labels_still_get_map_descriptions():
    """Labels curtas (CRYSTAL/GEN2/VOLCANO) devem herdar o texto das FeaturedMaps."""
    servers = [
        {"server_id": "s1", "label": "CRYSTAL", "server_map": "CrystalIsles", "show_on_home": True},
        {"server_id": "s2", "label": "GEN2", "server_map": "Gen2_WP", "show_on_home": True},
        {"server_id": "s3", "label": "VOLCANO", "server_map": "TheVolcano", "show_on_home": True},
    ]
    catalog = {
        "FeaturedMaps": [
            {
                "id": "crystal_isles",
                "name": "Crystal Isles",
                "mod_map": True,
                "description": "Ilhas de cristal com biomas unicos.",
                "enabled": True,
            },
            {
                "id": "genesis_2",
                "name": "Genesis 2",
                "mod_map": True,
                "description": "Megastructure e mundos geneticos.",
                "enabled": True,
            },
            {
                "id": "the_volcano",
                "name": "The Volcano",
                "mod_map": True,
                "description": "Ilha vulcanica hostil e rica.",
                "enabled": True,
            },
        ],
    }
    maps = _app_module._load_featured_maps_public(servers=servers, catalog=catalog)
    by_desc = {m["description"] for m in maps}
    assert "Ilhas de cristal com biomas unicos." in by_desc
    assert "Megastructure e mundos geneticos." in by_desc
    assert "Ilha vulcanica hostil e rica." in by_desc
    assert all(str(m.get("description") or "").strip() for m in maps)


_DEAD_HOME_MAPS = ("Brighamia", "The Volcano", "Amissa", "Crystal Isles", "Genesis 2")


def _stale_featured_fixture() -> list[dict]:
    """Catálogo antigo: mapas que saíram do cluster + texto/badge dos que ficaram."""
    return [
        {
            "id": "brighamia",
            "name": "Brighamia",
            "mod_map": True,
            "description": "Texto de mapa que já saiu.",
            "sort_order": 0,
            "enabled": True,
        },
        {
            "id": "alps",
            "name": "Alps",
            "mod_map": True,
            "description": "Texto promo dos Alpes salvo pelo admin.",
            "sort_order": 1,
            "enabled": True,
            "server_id": "alps",
        },
        {
            "id": "the_volcano",
            "name": "The Volcano",
            "mod_map": True,
            "description": "Vulcão removido.",
            "sort_order": 2,
            "enabled": True,
        },
        {
            "id": "amissa",
            "name": "Amissa",
            "mod_map": True,
            "description": "Amissa removida.",
            "sort_order": 3,
            "enabled": True,
        },
        {
            "id": "ragnarok",
            "name": "Ragnarok",
            "mod_map": False,
            "description": "Texto promo de Ragnarok.",
            "sort_order": 4,
            "enabled": True,
            "server_id": "ragnarok",
        },
        {
            "id": "valhalla",
            "name": "Valhalla",
            "mod_map": False,
            "description": "Texto promo de Valhalla.",
            "sort_order": 5,
            "enabled": True,
        },
        {
            "id": "crystal_isles",
            "name": "Crystal Isles",
            "mod_map": False,
            "description": "Crystal saiu do cluster.",
            "sort_order": 6,
            "enabled": True,
        },
        {
            "id": "tunguska",
            "name": "Tunguska",
            "mod_map": True,
            "description": "Texto promo de Tunguska.",
            "sort_order": 7,
            "enabled": True,
            "server_id": "tunguska",
        },
        {
            "id": "genesis_2",
            "name": "Genesis 2",
            "mod_map": False,
            "description": "Genesis 2 saiu do cluster.",
            "sort_order": 8,
            "enabled": True,
        },
    ]


def _four_live_servers() -> list[dict]:
    return [
        {"server_id": "alps", "label": "Alps", "server_map": "Alps_WP", "show_on_home": True},
        {"server_id": "ragnarok", "label": "Ragnarok", "server_map": "Ragnarok", "show_on_home": True},
        {"server_id": "tunguska", "label": "Tunguska", "server_map": "Tunguska_WP", "show_on_home": True},
        {"server_id": "valhalla", "label": "Valhalla", "server_map": "Valhalla", "show_on_home": True},
    ]


def test_raw_featured_maps_do_not_resurrect_defaults():
    """Catálogo só com os mapas atuais não ganha Brighamia/Volcano/etc. na leitura."""
    catalog = {
        "FeaturedMaps": [
            {"id": "alps", "name": "Alps", "mod_map": True, "description": "a", "sort_order": 1, "enabled": True},
            {"id": "ragnarok", "name": "Ragnarok", "mod_map": False, "description": "r", "sort_order": 2, "enabled": True},
            {"id": "valhalla", "name": "Valhalla", "mod_map": True, "description": "v", "sort_order": 3, "enabled": True},
            {"id": "tunguska", "name": "Tunguska", "mod_map": True, "description": "t", "sort_order": 4, "enabled": True},
        ],
    }
    names = [m["name"] for m in _app_module._load_featured_maps_raw(catalog)]
    assert names == ["Alps", "Ragnarok", "Valhalla", "Tunguska"]
    assert _app_module._load_featured_maps_raw({"FeaturedMaps": []}) == []
    assert _app_module._load_featured_maps_raw({}) == []


def test_sync_drops_stale_maps_and_keeps_saved_copy(client, tmp_path, monkeypatch):
    """Sync com Alps, Ragnarok, Tunguska e Valhalla não ressuscita o fixture antigo."""
    catalog = {"Settings": {"HomeMapsTitle": "Mapas do cluster"}, "FeaturedMaps": _stale_featured_fixture()}
    catalog_path = tmp_path / "config.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    servers_file = tmp_path / "servers.json"
    servers_file.write_text(json.dumps(_four_live_servers()), encoding="utf-8")
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", servers_file)
    # O catálogo de teste não tem itens; sem este patch o app troca o path pelo mestre real.
    monkeypatch.setattr(
        _app_module,
        "_resolve_settings_catalog_path",
        lambda configured="", _c=str(catalog_path): _c,
    )
    _app_module._invalidate_shop_config_cache()

    dead = set(_DEAD_HOME_MAPS)
    reconciled = _app_module._reconcile_featured_maps(
        servers=_four_live_servers(),
        catalog=catalog,
    )
    names = [m["name"] for m in reconciled]
    assert set(names) == {"Alps", "Ragnarok", "Tunguska", "Valhalla"}
    assert dead.isdisjoint(names)

    by_name = {m["name"]: m for m in reconciled}
    assert by_name["Alps"]["description"] == "Texto promo dos Alpes salvo pelo admin."
    assert by_name["Alps"]["mod_map"] is True
    assert by_name["Ragnarok"]["description"] == "Texto promo de Ragnarok."
    assert by_name["Ragnarok"]["mod_map"] is False
    # Valhalla não é mapa oficial; o badge salvo (oficial) tem de vencer o palpite.
    assert by_name["Valhalla"]["mod_map"] is False
    assert by_name["Valhalla"]["description"] == "Texto promo de Valhalla."
    assert by_name["Tunguska"]["mod_map"] is True
    assert by_name["Tunguska"]["description"] == "Texto promo de Tunguska."

    _login_admin(client)
    admin = client.get("/api/featured-maps/admin")
    assert admin.status_code == 200
    admin_names = [m["name"] for m in admin.get_json()["maps"]]
    assert set(admin_names) == {"Alps", "Ragnarok", "Tunguska", "Valhalla"}
    assert dead.isdisjoint(admin_names)

    home = client.get("/api/public/home").get_json()
    home_names = [m["name"] for m in home["featured_maps"]]
    assert set(home_names) == {"Alps", "Ragnarok", "Tunguska", "Valhalla"}
    assert dead.isdisjoint(home_names)
    home_alps = next(m for m in home["featured_maps"] if m["name"] == "Alps")
    assert home_alps["description"] == "Texto promo dos Alpes salvo pelo admin."
    assert home_alps["mod_map"] is True


def test_disabled_synced_map_stays_off_public_home():
    servers = _four_live_servers()
    catalog = {
        "FeaturedMaps": [
            {
                "id": "alps",
                "name": "Alps",
                "mod_map": True,
                "description": "Continua salvo.",
                "enabled": False,
                "sort_order": 1,
                "server_id": "alps",
            },
        ],
    }
    admin_rows = _app_module._reconcile_featured_maps(servers=servers, catalog=catalog)
    alps = next(m for m in admin_rows if m["name"] == "Alps")
    assert alps["enabled"] is False
    assert alps["description"] == "Continua salvo."
    public_names = [
        m["name"] for m in _app_module._load_featured_maps_public(servers=servers, catalog=catalog)
    ]
    assert "Alps" not in public_names
    assert set(public_names) == {"Ragnarok", "Tunguska", "Valhalla"}
