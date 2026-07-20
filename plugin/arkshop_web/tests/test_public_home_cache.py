"""Cache TTL de GET /api/public/home — evita rebuild sob saturação Waitress."""
from __future__ import annotations

import json
import threading
import time

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
    catalog.write_text(
        json.dumps({
            "Settings": {"ShopName": "ARKLAND DONATIONS"},
            "Items": {"stone": {"Type": "item", "Description": "Stone"}},
            "Kits": {"starter": {"Description": "Starter"}},
            "FeaturedMaps": [],
            "Downloads": [],
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
    # Evita heal do catálogo real (tmp parece «truncado» vs mestre do ambiente).
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
    servers_file = tmp_path / "servers.json"
    servers_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", servers_file)

    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    _app_module._invalidate_public_home_cache()
    _app_module._invalidate_shop_config_cache()
    yield
    _app_module._invalidate_public_home_cache()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_public_home_cache_hit_on_second_request(client):
    r1 = client.get("/api/public/home")
    assert r1.status_code == 200
    assert r1.headers.get("X-Home-Cache") == "MISS"
    body1 = r1.get_json()
    assert body1["ok"] is True
    assert body1["stats"]["items"] == 1
    assert body1["stats"]["kits"] == 1

    r2 = client.get("/api/public/home")
    assert r2.status_code == 200
    assert r2.headers.get("X-Home-Cache") == "HIT"
    assert r2.get_json()["shop_name"] == body1["shop_name"]
    assert "public, max-age=" in (r2.headers.get("Cache-Control") or "")


def test_public_home_build_not_under_lock(monkeypatch):
    """Regressão saturação: build dentro do lock empilhava Waitress (fila 70+)."""
    builds: list[float] = []
    lock_held_during_build = {"bad": False}
    real_build = _app_module._build_public_home_payload

    def _slow_build():
        builds.append(time.monotonic())
        if _app_module._PUBLIC_HOME_CACHE_LOCK.locked():
            lock_held_during_build["bad"] = True
        time.sleep(0.15)
        return real_build()

    monkeypatch.setattr(_app_module, "_build_public_home_payload", _slow_build)
    _app_module._invalidate_public_home_cache()

    statuses: list[str] = []
    errors: list[BaseException] = []

    def _worker():
        try:
            _payload, status = _app_module._get_cached_public_home_payload()
            statuses.append(status)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, errors
    assert not lock_held_during_build["bad"]
    assert len(builds) == 1  # single-flight
    assert "MISS" in statuses
    assert all(s in ("HIT", "STALE", "MISS") for s in statuses)


def test_public_home_cache_miss_after_invalidate(client):
    assert client.get("/api/public/home").headers.get("X-Home-Cache") == "MISS"
    assert client.get("/api/public/home").headers.get("X-Home-Cache") == "HIT"

    _app_module._invalidate_public_home_cache()
    assert client.get("/api/public/home").headers.get("X-Home-Cache") == "MISS"


def test_public_home_cache_invalidates_on_catalog_change(client, tmp_path):
    assert client.get("/api/public/home").headers.get("X-Home-Cache") == "MISS"
    assert client.get("/api/public/home").headers.get("X-Home-Cache") == "HIT"

    catalog = tmp_path / "config.json"
    data = json.loads(catalog.read_text(encoding="utf-8"))
    data["Items"]["wood"] = {"Type": "item", "Description": "Wood"}
    catalog.write_text(json.dumps(data), encoding="utf-8")
    _app_module._invalidate_shop_config_cache()

    r = client.get("/api/public/home")
    assert r.headers.get("X-Home-Cache") == "MISS"
    assert r.get_json()["stats"]["items"] == 2


def test_admin_home_card_invalidates_public_home_cache(client):
    assert client.get("/api/public/home").headers.get("X-Home-Cache") == "MISS"
    assert client.get("/api/public/home").headers.get("X-Home-Cache") == "HIT"

    with client.session_transaction() as sess:
        sess["steam_id"] = ADMIN_STEAM
    created = client.post(
        "/api/admin/home-cards",
        json={"title": "Novo card", "body": "Texto", "active": True},
    )
    assert created.status_code == 201

    r = client.get("/api/public/home")
    assert r.headers.get("X-Home-Cache") == "MISS"
    cards = r.get_json().get("home_cards") or []
    assert any(c.get("title") == "Novo card" for c in cards)


def test_build_skips_rcon_decrypt(client, tmp_path, monkeypatch):
    """Home pública não deve desencriptar rcon_password de todos os servidores."""
    servers_file = tmp_path / "servers.json"
    servers_file.write_text(
        json.dumps([{
            "server_id": "map1",
            "label": "Map One",
            "show_on_home": True,
            "rcon_password": "enc:fake",
            "config_snapshot": {"xp_multiplier": 2},
        }]),
        encoding="utf-8",
    )
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", servers_file)
    _app_module._invalidate_public_home_cache()

    calls: list[str] = []

    def _spy(value: str) -> str:
        calls.append(value)
        return value

    monkeypatch.setattr(_app_module, "_decrypt_value", _spy)
    r = client.get("/api/public/home")
    assert r.status_code == 200
    assert not any(c == "enc:fake" for c in calls)
    names = [m["name"] for m in r.get_json()["featured_maps"]]
    assert "Map One" in names
