"""Cache curto em settings/servers/config (Fase 4) — headers X-Short-Cache."""
from __future__ import annotations

import json

import pytest

import app as _app_module
import ttl_cache as _ttl
from app import app, _configure_database

ADMIN_STEAM = "76561198000000001"


@pytest.fixture(autouse=True)
def fresh_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_API_KEY", "test-key")
    monkeypatch.setenv("ARKSHOP_WEB_SECRET", "test-secret")
    monkeypatch.setattr(_app_module, "_ARKSHOP_API_KEY", "test-key")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", tmp_path / "servers.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]), encoding="utf-8")
    (tmp_path / "servers.json").write_text("[]", encoding="utf-8")

    catalog = tmp_path / "config.json"
    catalog.write_text(
        json.dumps({
            "Settings": {"ShopName": "ARKLAND DONATIONS"},
            "Items": {"stone": {"Type": "item", "Description": "Stone", "Price": 1}},
            "Kits": {"starter": {"Description": "Starter", "Price": 0}},
        }),
        encoding="utf-8",
    )
    (tmp_path / "settings.json").write_text(
        json.dumps({"config_path": str(catalog)}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        _app_module,
        "_resolve_settings_catalog_path",
        lambda configured="", _c=str(catalog): str(configured or _c).strip() or _c,
    )
    monkeypatch.setattr(
        _app_module,
        "_heal_empty_shop_config_path",
        lambda preferred: (preferred, json.loads(catalog.read_text(encoding="utf-8")), None),
    )

    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    monkeypatch.setattr(_app_module, "_DB_INITIALIZED", True)
    from db_diagnostics import record_circuit_success

    record_circuit_success()
    _ttl.invalidate_all_short_caches()
    _app_module._invalidate_shop_config_cache()
    yield
    _ttl.invalidate_all_short_caches()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login(client) -> None:
    with client.session_transaction() as sess:
        sess["steam_id"] = ADMIN_STEAM


def test_settings_short_cache_hit(client):
    _login(client)
    r1 = client.get("/api/settings")
    assert r1.status_code == 200
    assert r1.headers.get("X-Short-Cache") == "MISS"
    r2 = client.get("/api/settings")
    assert r2.status_code == 200
    assert r2.headers.get("X-Short-Cache") == "HIT"


def test_servers_short_cache_hit(client):
    _login(client)
    r1 = client.get("/api/servers")
    assert r1.status_code == 200
    assert r1.headers.get("X-Short-Cache") == "MISS"
    r2 = client.get("/api/servers")
    assert r2.headers.get("X-Short-Cache") == "HIT"


def test_servers_cache_invalidates_on_upsert(client):
    _login(client)
    assert client.get("/api/servers").headers.get("X-Short-Cache") == "MISS"
    assert client.get("/api/servers").headers.get("X-Short-Cache") == "HIT"
    client.post("/api/servers", json={"server_id": "map1", "label": "Map 1"})
    assert client.get("/api/servers").headers.get("X-Short-Cache") == "MISS"


def test_config_short_cache_hit(client):
    _login(client)
    r1 = client.get("/api/config")
    assert r1.status_code == 200
    assert r1.get_json().get("ok") is True
    assert r1.headers.get("X-Short-Cache") == "MISS"
    r2 = client.get("/api/config")
    assert r2.headers.get("X-Short-Cache") == "HIT"


def test_pix_status_route_not_wired_to_short_cache():
    """Garantia estrutural: poll PIX não usa X-Short-Cache / ttl_cache."""
    import inspect
    src = inspect.getsource(_app_module.player_pix_status)
    assert "_ttl_cache" not in src
    assert "X-Short-Cache" not in src
    assert "NÃO cachear" in (inspect.getdoc(_app_module.player_pix_status) or "")
