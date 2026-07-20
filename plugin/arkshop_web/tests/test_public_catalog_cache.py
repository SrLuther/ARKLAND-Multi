"""Cache TTL de GET /api/catalog e parte partilhada do /api/store/bootstrap."""
from __future__ import annotations

import json

import pytest

import app as _app_module
from app import app, _configure_database


@pytest.fixture(autouse=True)
def fresh_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_API_KEY", "test-key")
    monkeypatch.setattr(_app_module, "_ARKSHOP_API_KEY", "test-key")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([]))

    catalog = tmp_path / "config.json"
    catalog.write_text(
        json.dumps({
            "Settings": {"ShopName": "ARKLAND DONATIONS"},
            "Items": {"stone": {"Type": "item", "Description": "Stone", "Price": 1}},
            "Kits": {"starter": {"Description": "Starter", "Price": 0}},
            "PointPackages": [
                {"id": "pkg1", "label": "100 Â", "points": 100, "price_brl": 10.0},
            ],
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
    _app_module._invalidate_public_catalog_cache()
    _app_module._invalidate_shop_config_cache()
    yield
    _app_module._invalidate_public_catalog_cache()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_catalog_cache_hit_on_second_request(client):
    r1 = client.get("/api/catalog")
    assert r1.status_code == 200
    assert r1.headers.get("X-Catalog-Cache") == "MISS"
    body1 = r1.get_json()
    assert "stone" in (body1.get("items") or {})
    assert body1.get("shop_name")

    r2 = client.get("/api/catalog")
    assert r2.status_code == 200
    assert r2.headers.get("X-Catalog-Cache") == "HIT"
    assert r2.get_json()["shop_name"] == body1["shop_name"]


def test_bootstrap_reuses_catalog_cache(client):
    r1 = client.get("/api/catalog")
    assert r1.headers.get("X-Catalog-Cache") == "MISS"

    r2 = client.get("/api/store/bootstrap")
    assert r2.status_code == 200
    assert r2.headers.get("X-Catalog-Cache") == "HIT"
    assert r2.headers.get("Cache-Control") == "private, no-store, max-age=0"
    d = r2.get_json()
    assert d["ok"] is True
    assert d["timing"].get("catalog_cache_hit") == 1
    assert d["catalog"].get("shop_name") == r1.get_json().get("shop_name")


def test_catalog_cache_miss_after_invalidate(client):
    assert client.get("/api/catalog").headers.get("X-Catalog-Cache") == "MISS"
    assert client.get("/api/catalog").headers.get("X-Catalog-Cache") == "HIT"
    _app_module._invalidate_public_catalog_cache()
    assert client.get("/api/catalog").headers.get("X-Catalog-Cache") == "MISS"


def test_catalog_cache_invalidates_on_shop_config_change(client, tmp_path):
    assert client.get("/api/catalog").headers.get("X-Catalog-Cache") == "MISS"
    assert client.get("/api/catalog").headers.get("X-Catalog-Cache") == "HIT"
    _app_module._invalidate_shop_config_cache()
    assert client.get("/api/catalog").headers.get("X-Catalog-Cache") == "MISS"


def test_bootstrap_anonymous_still_private_no_store(client):
    r = client.get("/api/store/bootstrap")
    assert r.status_code == 200
    assert r.headers.get("Cache-Control") == "private, no-store, max-age=0"
    assert r.headers.get("X-Catalog-Cache") in ("HIT", "MISS")
