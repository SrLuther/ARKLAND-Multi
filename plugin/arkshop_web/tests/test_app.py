"""Testes para ArkShop Web Manager."""
from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")
os.environ.setdefault("ARKSHOP_RETRY_INTERVAL", "9999")
os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")

import app as _app_module
from app import app, _configure_database, _now
from server_connect import ARK_ASE_STEAM_APP_ID

ADMIN_STEAM = "76561198000000001"
USER_STEAM  = "76561198000000002"
API_KEY = "test-api-key"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_API_KEY", API_KEY)
    monkeypatch.delenv("STEAM_API_KEY", raising=False)
    monkeypatch.setattr(_app_module, "_ARKSHOP_API_KEY", API_KEY)
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(_app_module, "_PLAYERS_FILE", tmp_path / "players.json")
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", tmp_path / "servers.json")
    monkeypatch.setattr(_app_module, "_migrate_schema", lambda _engine: None)

    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]))

    db_path = str(tmp_path / "test.db")
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    if _app_module._ENGINE is not None:
        from sqlalchemy import text

        _app_module.Base.metadata.create_all(bind=_app_module._ENGINE)
        with _app_module._ENGINE.connect() as conn:
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS players ("
                    "steam_id VARCHAR(20) PRIMARY KEY NOT NULL, "
                    "points INTEGER NOT NULL DEFAULT 0, "
                    "kits TEXT DEFAULT '{}'"
                    ")"
                )
            )
            conn.commit()
        db = _app_module._SessionLocal()
        try:
            _app_module._ensure_entitlements_schema(db)
            db.add(
                _app_module.MarketPlayerProfile(
                    steam_id=USER_STEAM,
                    market_display_name="TestPlayer",
                    commerce_enabled=True,
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
            from regulamento_config import REGULAMENTO_VERSION

            for sid, name in ((ADMIN_STEAM, "Admin"), (USER_STEAM, "TestPlayer")):
                db.add(
                    _app_module.StoreUser(
                        steam_id=sid,
                        display_name=name,
                        steam_persona=name,
                        regulamento_accepted_version=REGULAMENTO_VERSION,
                        regulamento_accepted_at=_now(),
                        last_login_at=_now(),
                    )
                )
            db.commit()
        finally:
            db.close()
    monkeypatch.setattr(_app_module, "_DB_INITIALIZED", True)
    yield
    _configure_database("")


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login(client, steam_id: str):
    with client.session_transaction() as sess:
        sess["steam_id"] = steam_id


def _write_settings(tmp_path, **overrides):
    data = {
        "delivery_mode": "plugin",
        "rcon_host": "127.0.0.1",
        "rcon_port": 27020,
        "rcon_password": "",
        "delivery_command_template": "Shop.Deliver {steam_id} {item_id} {amount}",
        "server_id": "default",
    }
    data.update(overrides)
    (tmp_path / "settings.json").write_text(json.dumps(data), encoding="utf-8")


def _create_order_direct(steam_id=USER_STEAM, item_id="sword", amount=1, status="PENDENTE", server_id="default", points_spent=0, item_type="shop", created_at=None):
    db = _app_module._SessionLocal()
    try:
        ts = created_at or _now()
        o = _app_module.Order(
            order_id=str(uuid.uuid4()),
            steam_id=steam_id,
            server_id=server_id,
            item_type=item_type,
            item_id=item_id,
            amount=amount,
            points_spent=max(0, int(points_spent)),
            status=status,
            created_at=ts,
            updated_at=ts,
        )
        db.add(o)
        db.commit()
        db.refresh(o)
        return o.order_id
    finally:
        db.close()


def _create_donation_direct(
    steam_id=USER_STEAM,
    points=100,
    amount_brl=10.0,
    credited=True,
    status="APROVADO",
    package_id="pkg_test",
    payment_method="pix",
):
    db = _app_module._SessionLocal()
    try:
        row = _app_module.PointPayment(
            payment_id=str(uuid.uuid4()),
            mp_payment_id="mp_test_1",
            steam_id=steam_id,
            package_id=package_id,
            amount_brl=amount_brl,
            points=points,
            status=status,
            credited=credited,
            payment_method=payment_method,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(row)
        db.commit()
        return row.payment_id
    finally:
        db.close()


# ── Auth ──────────────────────────────────────────────────────────────────────

class TestAuth:
    def test_me_unauthenticated(self, client):
        r = client.get("/api/auth/me")
        d = r.get_json()
        assert d["authenticated"] is False
        assert d["is_admin"] is False
        assert d.get("display_name") is None

    def test_me_authenticated_admin(self, client):
        _login(client, ADMIN_STEAM)
        r = client.get("/api/auth/me")
        d = r.get_json()
        assert d["authenticated"] is True
        assert d["is_admin"] is True
        assert d["steam_id"] == ADMIN_STEAM

    def test_auth_callback_creates_persistent_session(self, client, monkeypatch):
        monkeypatch.setattr(_app_module, "_verify_steam_openid", lambda _qp: True)
        monkeypatch.setattr(_app_module, "_touch_store_user_login", lambda _sid: None)
        claimed = f"https://steamcommunity.com/openid/id/{USER_STEAM}"
        r = client.get(
            "/api/auth/callback",
            query_string={
                "openid.mode": "id_res",
                "openid.claimed_id": claimed,
            },
        )
        assert r.status_code == 302
        cookie = r.headers.get("Set-Cookie", "")
        assert "Expires=" in cookie or "Max-Age=" in cookie
        with client.session_transaction() as sess:
            assert sess.get("steam_id") == USER_STEAM
            assert sess.permanent is True

    def test_me_includes_display_name_from_store_user(self, client, monkeypatch):
        monkeypatch.setenv("STEAM_API_KEY", "test-key")
        monkeypatch.setattr(
            _app_module,
            "_fetch_steam_persona_names_batch",
            lambda ids, **kw: {ADMIN_STEAM: "AdminNick"} if ADMIN_STEAM in ids else {},
        )
        _seed_store_user(ADMIN_STEAM, display_name="AdminNick", steam_persona="AdminNick")
        _login(client, ADMIN_STEAM)
        d = client.get("/api/auth/me").get_json()
        assert d["steam_persona"] == "AdminNick"
        assert d["display_name"] == "AdminNick"

    def test_me_display_name_from_steam_api_when_missing(self, client, monkeypatch):
        _seed_store_user(USER_STEAM, display_name=USER_STEAM)
        monkeypatch.setenv("STEAM_API_KEY", "test-key")
        monkeypatch.setattr(
            _app_module,
            "_fetch_steam_persona_names_batch",
            lambda ids, **kw: {USER_STEAM: "SteamPersona"} if USER_STEAM in ids else {},
        )
        _login(client, USER_STEAM)
        d = client.get("/api/auth/me").get_json()
        assert d["display_name"] == "SteamPersona"
        assert d["steam_persona"] == "SteamPersona"

    def test_me_display_name_null_when_unavailable(self, client, monkeypatch):
        _seed_store_user(USER_STEAM, display_name=USER_STEAM, steam_persona="")
        monkeypatch.delenv("STEAM_API_KEY", raising=False)
        monkeypatch.setattr(_app_module, "_fetch_steam_persona_names_batch", lambda _ids, **kw: {})
        _login(client, USER_STEAM)
        d = client.get("/api/auth/me").get_json()
        assert d.get("display_name") is None
        assert d.get("steam_persona") is None

    def test_me_display_name_ignores_market_vitrine_name(self, client, monkeypatch):
        _seed_store_user(USER_STEAM, display_name="Ciano_STAFF")
        db = _app_module._SessionLocal()
        try:
            prof = db.get(_app_module.MarketPlayerProfile, USER_STEAM)
            prof.market_display_name = "Ciano_STAFF"
            db.commit()
        finally:
            db.close()
        monkeypatch.setenv("STEAM_API_KEY", "test-key")
        monkeypatch.setattr(
            _app_module,
            "_fetch_steam_persona_names_batch",
            lambda ids, **kw: {USER_STEAM: "CianoSteam"} if USER_STEAM in ids else {},
        )
        _login(client, USER_STEAM)
        d = client.get("/api/auth/me").get_json()
        assert d["display_name"] == "CianoSteam"
        assert d["steam_persona"] == "CianoSteam"
        assert d.get("market_display_name") is None
        assert d.get("needs_display_name") is False

    def test_touch_login_stores_steam_persona_not_market_name(self, client, monkeypatch):
        _seed_store_user(USER_STEAM, display_name="Ciano_STAFF")
        monkeypatch.setenv("STEAM_API_KEY", "test-key")
        monkeypatch.setattr(
            _app_module,
            "_fetch_steam_persona_names_batch",
            lambda ids, **kw: {USER_STEAM: "CianoSteam"} if USER_STEAM in ids else {},
        )
        _app_module._touch_store_user_login(USER_STEAM)
        db = _app_module._SessionLocal()
        try:
            row = db.get(_app_module.StoreUser, USER_STEAM)
            assert row.steam_persona == "CianoSteam"
            assert row.display_name == "CianoSteam"
            prof = db.get(_app_module.MarketPlayerProfile, USER_STEAM)
            assert prof.market_display_name == "TestPlayer"
        finally:
            db.close()

    def test_health_reports_steam_api_configured(self, client, monkeypatch):
        monkeypatch.setenv("STEAM_API_KEY", "abc123")
        d = client.get("/api/health").get_json()
        assert d["steam_api_configured"] is True

    def test_health_steam_api_not_configured(self, client, monkeypatch):
        monkeypatch.delenv("STEAM_API_KEY", raising=False)
        d = client.get("/api/health").get_json()
        assert d["steam_api_configured"] is False

    def test_health_steam_api_configured_from_settings(self, client, monkeypatch, tmp_path):
        monkeypatch.delenv("STEAM_API_KEY", raising=False)
        monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
        (tmp_path / "settings.json").write_text(
            json.dumps({"steam_api_key": "settings-key"}), encoding="utf-8"
        )
        d = client.get("/api/health").get_json()
        assert d["steam_api_configured"] is True

    def test_me_authenticated_user(self, client):
        _login(client, USER_STEAM)
        r = client.get("/api/auth/me")
        d = r.get_json()
        assert d["authenticated"] is True
        assert d["is_admin"] is False
        assert d["needs_display_name"] is False
        assert d.get("market_display_name") is None

    def test_me_authenticated_user_with_steam_persona(self, client, monkeypatch):
        monkeypatch.setenv("STEAM_API_KEY", "test-key")
        monkeypatch.setattr(
            _app_module,
            "_fetch_steam_persona_names_batch",
            lambda ids, **kw: {USER_STEAM: "PlayerBR"} if USER_STEAM in ids else {},
        )
        _seed_store_user(USER_STEAM, steam_persona="PlayerBR")
        _login(client, USER_STEAM)
        d = client.get("/api/auth/me").get_json()
        assert d["needs_display_name"] is False
        assert d["steam_persona"] == "PlayerBR"

    def test_purchase_allowed_without_display_name_gate(self, client, monkeypatch):
        monkeypatch.setattr(_app_module, "_safe_market_profile", lambda _db, _sid: None)
        _login(client, USER_STEAM)
        monkeypatch.setattr(_app_module, "_catalog_entry", lambda _t, _i: {"Price": 0, "Type": "item"})
        r = client.post(
            "/api/player/purchase",
            json={"item_id": "sword", "item_type": "shop", "amount": 1},
        )
        assert r.status_code == 200

    def test_logout(self, client):
        _login(client, ADMIN_STEAM)
        r = client.post("/api/auth/logout")
        assert r.get_json()["ok"] is True
        r2 = client.get("/api/auth/me")
        assert r2.get_json()["authenticated"] is False

    def test_admin_required_blocks_unauthenticated(self, client):
        r = client.get("/api/settings")
        assert r.status_code == 401

    def test_admin_required_blocks_non_admin(self, client):
        _login(client, USER_STEAM)
        r = client.get("/api/settings")
        assert r.status_code == 403


class TestPointPackages:
    def _use_isolated_catalog(self, monkeypatch, config_path):
        monkeypatch.setattr(
            _app_module,
            "_resolve_settings_catalog_path",
            lambda configured="": str(config_path),
        )
        _app_module._invalidate_shop_config_cache()

    def test_get_config_empty_file_returns_error_not_silent_empty(self, client, tmp_path, monkeypatch):
        """Admin «Nenhum item cadastrado» — path existe mas sem Items/Kits → error explícito."""
        config_path = tmp_path / "shop_config.json"
        config_path.write_text(json.dumps({"Settings": {}, "Items": {}, "Kits": {}}), encoding="utf-8")
        _write_settings(tmp_path, config_path=str(config_path))
        self._use_isolated_catalog(monkeypatch, config_path)
        monkeypatch.setattr(
            _app_module,
            "_heal_empty_shop_config_path",
            lambda preferred: (preferred, {"Settings": {}, "Items": {}, "Kits": {}}, f"vazio: {preferred}"),
        )
        _login(client, ADMIN_STEAM)
        r = client.get("/api/config")
        d = r.get_json()
        assert r.status_code == 200
        assert d.get("ok") is False
        assert d.get("error")
        assert d.get("_items_count") == 0
        assert d.get("_kits_count") == 0

    def test_get_config_missing_path_heals_from_source(self, client, tmp_path, monkeypatch):
        missing = tmp_path / "missing_config.json"
        rich = tmp_path / "rich_config.json"
        rich.write_text(
            json.dumps({
                "Items": {"sword": {"Price": 10, "Description": "Espada"}},
                "Kits": {"starter": {"Price": 0, "Description": "Kit", "DefaultAmount": 1}},
            }),
            encoding="utf-8",
        )
        _write_settings(tmp_path, config_path=str(missing))
        self._use_isolated_catalog(monkeypatch, missing)

        def _fake_heal(preferred):
            return rich, json.loads(rich.read_text(encoding="utf-8")), f"recuperado de {rich}"

        monkeypatch.setattr(_app_module, "_heal_empty_shop_config_path", _fake_heal)
        _login(client, ADMIN_STEAM)
        r = client.get("/api/config")
        d = r.get_json()
        assert r.status_code == 200
        assert d.get("ok") is True
        assert "sword" in (d.get("ShopItems") or {})
        assert "starter" in (d.get("Kits") or {})
        assert d.get("_config_healed")

    def test_read_shop_config_uses_healed_source(self, client, tmp_path, monkeypatch):
        missing = tmp_path / "missing_config.json"
        rich = tmp_path / "rich_config.json"
        rich.write_text(
            json.dumps({"Items": {"a": {"Price": 1}}, "Kits": {"k": {"Price": 0}}}),
            encoding="utf-8",
        )
        _write_settings(tmp_path, config_path=str(missing))
        self._use_isolated_catalog(monkeypatch, missing)
        monkeypatch.setattr(
            _app_module,
            "_heal_empty_shop_config_path",
            lambda preferred: (rich, json.loads(rich.read_text(encoding="utf-8")), "healed"),
        )
        data = _app_module._read_shop_config()
        assert "a" in (data.get("Items") or {})
        assert "k" in (data.get("Kits") or {})

    def test_save_point_packages_persists_to_catalog(self, client, tmp_path, monkeypatch):
        config_path = tmp_path / "shop_config.json"
        config_path.write_text(
            json.dumps({"Settings": {}, "PointPackages": _app_module._DEFAULT_POINT_PACKAGES}),
            encoding="utf-8",
        )
        _write_settings(tmp_path, config_path=str(config_path))
        self._use_isolated_catalog(monkeypatch, config_path)

        custom = [
            {"id": "custom1", "label": "Pacote Teste", "points": 999, "price_brl": 9.99},
        ]
        _login(client, ADMIN_STEAM)
        r = client.post("/api/settings", json={"point_packages": custom})
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

        _app_module._CONFIG_CACHE.clear()
        r2 = client.get("/api/settings")
        assert r2.get_json()["point_packages"] == custom

        saved_cfg = json.loads(config_path.read_text(encoding="utf-8"))
        assert saved_cfg["PointPackages"] == custom

    def test_load_prefers_catalog_over_settings(self, client, tmp_path, monkeypatch):
        config_path = tmp_path / "shop_config.json"
        catalog_pkgs = [{"id": "from_cfg", "label": "Do catálogo", "points": 100, "price_brl": 1.0}]
        config_path.write_text(json.dumps({"PointPackages": catalog_pkgs}), encoding="utf-8")
        _write_settings(
            tmp_path,
            config_path=str(config_path),
            point_packages=[{"id": "from_settings", "label": "X", "points": 1, "price_brl": 1.0}],
        )
        self._use_isolated_catalog(monkeypatch, config_path)

        _login(client, ADMIN_STEAM)
        pkgs = client.get("/api/settings").get_json()["point_packages"]
        assert pkgs == catalog_pkgs

    def test_save_empty_point_packages_persists(self, client, tmp_path, monkeypatch):
        config_path = tmp_path / "shop_config.json"
        config_path.write_text(
            json.dumps({"Settings": {}, "PointPackages": _app_module._DEFAULT_POINT_PACKAGES}),
            encoding="utf-8",
        )
        _write_settings(tmp_path, config_path=str(config_path))
        self._use_isolated_catalog(monkeypatch, config_path)

        _login(client, ADMIN_STEAM)
        r = client.post("/api/settings", json={"point_packages": []})
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

        _app_module._CONFIG_CACHE.clear()
        assert client.get("/api/settings").get_json()["point_packages"] == []

        saved_cfg = json.loads(config_path.read_text(encoding="utf-8"))
        assert saved_cfg["PointPackages"] == []

    def test_save_point_packages_preserves_catalog_items(self, client, tmp_path, monkeypatch):
        config_path = tmp_path / "shop_config.json"
        config_path.write_text(
            json.dumps({
                "Settings": {"ShopName": "Test Shop"},
                "Items": {"item_x": {"Price": 99}},
                "PointPackages": _app_module._DEFAULT_POINT_PACKAGES,
            }),
            encoding="utf-8",
        )
        _write_settings(tmp_path, config_path=str(config_path))
        self._use_isolated_catalog(monkeypatch, config_path)

        custom = [{"id": "only_one", "label": "Único", "points": 5000, "price_brl": 25.0, "note": "Teste"}]
        _login(client, ADMIN_STEAM)
        r = client.post("/api/settings", json={"point_packages": custom})
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

        _app_module._CONFIG_CACHE.clear()
        saved_cfg = json.loads(config_path.read_text(encoding="utf-8"))
        assert saved_cfg["PointPackages"] == custom
        assert saved_cfg["Items"]["item_x"]["Price"] == 99
        assert saved_cfg["Settings"]["ShopName"] == "Test Shop"

    def test_save_point_packages_pushes_webstore_cache(self, client, tmp_path, monkeypatch):
        config_path = tmp_path / "shop_config.json"
        webstore_dir = tmp_path / "WEBSTORE"
        webstore_cfg = webstore_dir / "config.json"
        webstore_cfg.parent.mkdir(parents=True)
        webstore_cfg.write_text(
            json.dumps({"PointPackages": _app_module._DEFAULT_POINT_PACKAGES}),
            encoding="utf-8",
        )
        config_path.write_text(
            json.dumps({"Settings": {}, "PointPackages": _app_module._DEFAULT_POINT_PACKAGES}),
            encoding="utf-8",
        )
        _write_settings(tmp_path, config_path=str(config_path))
        self._use_isolated_catalog(monkeypatch, config_path)

        monkeypatch.setattr(
            "src.shop_integration.webstore_data_dir",
            lambda: webstore_dir,
        )
        monkeypatch.setattr(
            "src.arkland_environment.try_load_environment_paths",
            lambda: type("P", (), {"webstore": webstore_dir})(),
        )

        custom = [{"id": "ws_test", "label": "Webstore", "points": 1234, "price_brl": 12.34}]
        _login(client, ADMIN_STEAM)
        r = client.post("/api/settings", json={"point_packages": custom})
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

        ws_saved = json.loads(webstore_cfg.read_text(encoding="utf-8"))
        assert ws_saved["PointPackages"] == custom

    def test_save_engramas_command_price_via_config(self, client, tmp_path, monkeypatch):
        config_path = tmp_path / "shop_config.json"
        config_path.write_text(
            json.dumps({
                "Settings": {"ShopName": "Test Shop", "StartingPoints": 100},
                "Items": {},
                "Kits": {},
            }),
            encoding="utf-8",
        )
        _write_settings(tmp_path, config_path=str(config_path))
        self._use_isolated_catalog(monkeypatch, config_path)

        _login(client, ADMIN_STEAM)
        r = client.post(
            "/api/config",
            json={
                "Settings": {
                    "ShopName": "Test Shop",
                    "StartingPoints": 100,
                    "EngramasCommandPrice": 7500,
                },
                "Items": {},
                "Kits": {},
                "reload": False,
            },
        )
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

        _app_module._CONFIG_CACHE.clear()
        saved_cfg = json.loads(config_path.read_text(encoding="utf-8"))
        assert saved_cfg["Settings"]["EngramasCommandPrice"] == 7500

    def test_save_notas_command_settings_via_config(self, client, tmp_path, monkeypatch):
        config_path = tmp_path / "shop_config.json"
        config_path.write_text(
            json.dumps({
                "Settings": {"ShopName": "Test Shop", "StartingPoints": 100},
                "Items": {},
                "Kits": {},
            }),
            encoding="utf-8",
        )
        _write_settings(tmp_path, config_path=str(config_path))
        self._use_isolated_catalog(monkeypatch, config_path)

        _login(client, ADMIN_STEAM)
        r = client.post(
            "/api/config",
            json={
                "Settings": {
                    "ShopName": "Test Shop",
                    "StartingPoints": 100,
                    "NotasCommandPrice": 4200,
                    "NotasCommandEnabled": False,
                },
                "Items": {},
                "Kits": {},
                "reload": False,
            },
        )
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

        _app_module._CONFIG_CACHE.clear()
        saved_cfg = json.loads(config_path.read_text(encoding="utf-8"))
        assert saved_cfg["Settings"]["NotasCommandPrice"] == 4200
        assert saved_cfg["Settings"]["NotasCommandEnabled"] is False


class TestCatalogPathAlignment:
    """Admin/featured-maps/downloads devem usar o mesmo resolve/heal que /api/config."""

    def _use_isolated_catalog(self, monkeypatch, config_path):
        monkeypatch.setattr(
            _app_module,
            "_resolve_settings_catalog_path",
            lambda configured="": str(config_path),
        )
        _app_module._invalidate_shop_config_cache()

    def test_read_catalog_data_heals_missing_settings_path(self, tmp_path, monkeypatch):
        missing = tmp_path / "missing_config.json"
        rich = tmp_path / "rich_config.json"
        rich.write_text(
            json.dumps({
                "Items": {"sword": {"Price": 10}},
                "Kits": {},
                "FeaturedMaps": [{"id": "ragnarok", "name": "Ragnarok", "enabled": True}],
            }),
            encoding="utf-8",
        )
        _write_settings(tmp_path, config_path=str(missing))
        self._use_isolated_catalog(monkeypatch, missing)
        monkeypatch.setattr(
            _app_module,
            "_heal_empty_shop_config_path",
            lambda preferred: (rich, json.loads(rich.read_text(encoding="utf-8")), "healed"),
        )

        data = _app_module._read_catalog_data()
        assert "sword" in (data.get("Items") or {})
        maps = _app_module._load_featured_maps_raw()
        assert any(m.get("id") == "ragnarok" for m in maps)

    def test_write_featured_maps_persists_to_master(self, client, tmp_path, monkeypatch):
        config_path = tmp_path / "shop_config.json"
        config_path.write_text(
            json.dumps({
                "Settings": {"ShopName": "Test"},
                "Items": {"keep": {"Price": 1}},
                "Kits": {},
                "FeaturedMaps": [],
            }),
            encoding="utf-8",
        )
        _write_settings(tmp_path, config_path=str(config_path))
        self._use_isolated_catalog(monkeypatch, config_path)

        _login(client, ADMIN_STEAM)
        r = client.post(
            "/api/featured-maps",
            json={"name": "Aberration", "mod_map": True, "enabled": True},
        )
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

        saved = json.loads(config_path.read_text(encoding="utf-8"))
        assert saved["Items"]["keep"]["Price"] == 1
        assert any(m.get("name") == "Aberration" for m in saved.get("FeaturedMaps") or [])

    def test_build_catalog_payload_uses_resolved_path(self, tmp_path, monkeypatch):
        missing = tmp_path / "missing_config.json"
        rich = tmp_path / "rich_config.json"
        rich.write_text(
            json.dumps({
                "Items": {"sword": {"Price": 10, "Description": "Espada"}},
                "Kits": {"starter": {"Price": 0, "Description": "Kit"}},
            }),
            encoding="utf-8",
        )
        _write_settings(tmp_path, config_path=str(missing))
        self._use_isolated_catalog(monkeypatch, missing)
        monkeypatch.setattr(
            _app_module,
            "_heal_empty_shop_config_path",
            lambda preferred: (rich, json.loads(rich.read_text(encoding="utf-8")), f"healed:{rich}"),
        )
        payload = _app_module._build_catalog_payload()
        meta = payload.get("catalog_meta") or {}
        assert meta.get("items_count", 0) >= 1
        assert meta.get("catalog_empty") is False
        assert str(rich) in str(meta.get("config_path") or "")
        assert meta.get("catalog_note")


# ── Player summary & history ──────────────────────────────────────────────────

class TestPlayerHistory:
    def test_summary_empty(self, client):
        _login(client, USER_STEAM)
        r = client.get("/api/player/summary")
        d = r.get_json()
        assert d["ok"] is True
        assert d["stats"]["total_orders"] == 0

    def test_summary_counts(self, client):
        _login(client, USER_STEAM)
        _create_order_direct(status="ENTREGUE")
        _create_order_direct(status="PENDENTE")
        _create_order_direct(status="PENDENTE")
        r = client.get("/api/player/summary")
        d = r.get_json()
        assert d["stats"]["total_orders"] == 3
        assert d["stats"]["delivered"] == 1
        assert d["stats"]["pending"] == 2

    def test_history_pagination(self, client):
        _login(client, USER_STEAM)
        for _ in range(5):
            _create_order_direct()
        r = client.get("/api/player/history?limit=2&offset=0")
        d = r.get_json()
        assert d["total"] == 5
        assert len(d["items"]) == 2

    def test_history_filter_by_status(self, client):
        _login(client, USER_STEAM)
        _create_order_direct(status="ENTREGUE")
        _create_order_direct(status="PENDENTE")
        r = client.get("/api/player/history?status=ENTREGUE")
        d = r.get_json()
        assert d["total"] == 1
        assert d["items"][0]["status"] == "ENTREGUE"

    def test_history_requires_auth(self, client):
        r = client.get("/api/player/history")
        assert r.status_code == 401

    def test_donations_empty(self, client):
        _login(client, USER_STEAM)
        r = client.get("/api/player/donations")
        d = r.get_json()
        assert d["ok"] is True
        assert d["total"] == 0
        assert d["items"] == []

    def test_donations_lists_credited(self, client):
        _login(client, USER_STEAM)
        _create_donation_direct(points=500, amount_brl=25.0, payment_method="pix")
        _create_donation_direct(points=200, amount_brl=10.0, credited=False, status="PENDENTE", payment_method="card")
        r = client.get("/api/player/donations")
        d = r.get_json()
        assert d["total"] == 2
        points = {item["points"] for item in d["items"]}
        assert points == {500, 200}
        methods = {item["payment_method"] for item in d["items"]}
        assert methods == {"pix", "card"}
        credited = [item for item in d["items"] if item["credited"]]
        assert len(credited) == 1
        assert credited[0]["credited_at"] is not None
        assert credited[0]["payment_method"] == "pix"

    def test_summary_includes_donation_stats(self, client):
        _login(client, USER_STEAM)
        _create_donation_direct(points=100, credited=True)
        _create_donation_direct(points=50, credited=False, status="PENDENTE")
        r = client.get("/api/player/summary")
        d = r.get_json()
        assert d["stats"]["donations_total"] == 2
        assert d["stats"]["donations_credited"] == 1

    def test_donations_requires_auth(self, client):
        r = client.get("/api/player/donations")
        assert r.status_code == 401


# ── Order detail ──────────────────────────────────────────────────────────────

class TestOrderDetail:
    def test_detail_includes_attempts_and_disputes(self, client):
        _login(client, USER_STEAM)
        oid = _create_order_direct(status="ENTREGUE")
        db = _app_module._SessionLocal()
        try:
            db.add(_app_module.OrderAttempt(order_id=oid, success=True, command="cmd", response="ok", attempted_at=_now()))
            db.add(_app_module.Dispute(order_id=oid, steam_id=USER_STEAM, reason="teste", status="ABERTO", created_at=_now()))
            db.commit()
        finally:
            db.close()

        r = client.get(f"/api/player/orders/{oid}")
        d = r.get_json()
        assert d["ok"] is True
        assert len(d["attempts"]) == 1
        assert d["attempts"][0]["success"] is True
        assert len(d["disputes"]) == 1
        assert d["disputes"][0]["reason"] == "teste"

    def test_detail_not_found_for_other_user(self, client):
        _login(client, ADMIN_STEAM)
        oid = _create_order_direct(steam_id=USER_STEAM)
        r = client.get(f"/api/player/orders/{oid}")
        assert r.status_code == 404


# ── Contest ───────────────────────────────────────────────────────────────────

class TestContest:
    def test_contest_sets_status(self, client):
        _login(client, USER_STEAM)
        oid = _create_order_direct()
        r = client.post(
            f"/api/player/orders/{oid}/contest",
            json={"reason": "não recebi o item no servidor após várias tentativas"},
        )
        d = r.get_json()
        assert d["ok"] is True
        assert d["status"] == "CONTESTADO"
        assert d.get("ticket_id")

    def test_contest_requires_reason(self, client):
        _login(client, USER_STEAM)
        oid = _create_order_direct()
        r = client.post(f"/api/player/orders/{oid}/contest", json={"reason": "  "})
        assert r.status_code == 400

    def test_contest_requires_detailed_reason(self, client):
        _login(client, USER_STEAM)
        oid = _create_order_direct()
        r = client.post(f"/api/player/orders/{oid}/contest", json={"reason": "curto"})
        assert r.status_code == 400
        assert r.get_json().get("code") == "reason_too_short"

    def test_contest_creates_dispute_and_ticket(self, client):
        _login(client, USER_STEAM)
        oid = _create_order_direct()
        reason = "Item não entregue após inventário livre e várias tentativas de /shop"
        client.post(f"/api/player/orders/{oid}/contest", json={"reason": reason})
        db = _app_module._SessionLocal()
        try:
            dispute = db.query(_app_module.Dispute).filter(_app_module.Dispute.order_id == oid).first()
            assert dispute is not None
            assert dispute.reason == reason
            assert dispute.status == "ABERTO"
            ticket = (
                db.query(_app_module.SupportTicket)
                .filter(_app_module.SupportTicket.order_id == oid)
                .first()
            )
            assert ticket is not None
            assert ticket.category == "resgate"
        finally:
            db.close()


# ── Reemissão admin ───────────────────────────────────────────────────────────

class TestAdminReissue:
    def test_player_rebuy_forbidden(self, client):
        _login(client, USER_STEAM)
        oid = _create_order_direct(status="ERRO")
        r = client.post(f"/api/player/orders/{oid}/rebuy", json={})
        assert r.status_code == 403

    def test_admin_reissue_sets_original_to_reemitido(self, client):
        _login(client, ADMIN_STEAM)
        oid = _create_order_direct(status="ENTREGUE")
        r = client.post(
            f"/api/admin/orders/{oid}/reissue",
            json={"reason": "Teste reemissão", "force_reset": True},
        )
        d = r.get_json()
        assert d.get("ok") is True
        assert "new_order_id" in d

        db = _app_module._SessionLocal()
        try:
            original = db.query(_app_module.Order).filter(_app_module.Order.order_id == oid).first()
            assert original.status == "REEMITIDO"
            reissue = db.query(_app_module.AdminReissue).filter(
                _app_module.AdminReissue.original_order_id == oid
            ).first()
            assert reissue is not None
            assert reissue.admin_steam_id == ADMIN_STEAM
            assert reissue.reason == "Teste reemissão"
        finally:
            db.close()

    def test_admin_reissue_requires_reason(self, client):
        _login(client, ADMIN_STEAM)
        oid = _create_order_direct(status="ENTREGUE")
        r = client.post(f"/api/admin/orders/{oid}/reissue", json={})
        assert r.status_code == 400


class TestAudit:
    def test_audit_forbidden_for_player(self, client):
        _login(client, USER_STEAM)
        r = client.get("/api/admin/audit")
        assert r.status_code in (401, 403)

    def test_audit_list_for_admin(self, client):
        _login(client, ADMIN_STEAM)
        _create_order_direct()
        r = client.get("/api/admin/audit")
        d = r.get_json()
        assert d.get("ok") is True
        assert "items" in d

    def test_audit_filter_by_steam_id(self, client):
        db = _app_module._SessionLocal()
        try:
            db.add(
                _app_module.AuditEvent(
                    event_type="order_created",
                    severity="info",
                    target_steam_id=USER_STEAM,
                    order_id="ord-filter-test",
                    message="pedido de teste",
                    created_at=_now(),
                )
            )
            db.commit()
        finally:
            db.close()

        _login(client, ADMIN_STEAM)
        r = client.get(f"/api/admin/audit?steam_id={USER_STEAM}")
        d = r.get_json()
        assert d.get("ok") is True
        assert any(e.get("target_steam_id") == USER_STEAM for e in d["items"])

    def test_audit_filter_by_order_id(self, client):
        db = _app_module._SessionLocal()
        try:
            db.add(
                _app_module.AuditEvent(
                    event_type="order_delivered",
                    severity="info",
                    target_steam_id=USER_STEAM,
                    order_id="ord-by-id-test",
                    message="entrega de teste",
                    created_at=_now(),
                )
            )
            db.commit()
        finally:
            db.close()

        _login(client, ADMIN_STEAM)
        r = client.get("/api/admin/audit?order_id=ord-by-id-test")
        d = r.get_json()
        assert d.get("ok") is True
        assert any(e.get("order_id") == "ord-by-id-test" for e in d["items"])


# ── Idempotência ──────────────────────────────────────────────────────────────

class TestIdempotency:
    def test_delivered_order_skipped_on_retry(self, client):
        _login(client, ADMIN_STEAM)
        oid = _create_order_direct(status="ENTREGUE")
        result = _app_module._process_order_delivery(oid)
        assert result.get("skipped") is True
        assert result["status"] == "ENTREGUE"


# ── Servers CRUD ──────────────────────────────────────────────────────────────

class TestServers:
    def test_list_empty(self, client):
        _login(client, ADMIN_STEAM)
        r = client.get("/api/servers")
        d = r.get_json()
        assert d["ok"] is True
        assert d["items"] == []

    def test_upsert_and_list(self, client):
        _login(client, ADMIN_STEAM)
        r = client.post("/api/servers", json={
            "server_id": "pve1",
            "label": "PvE 1",
            "plugin_config_path": "C:\\ARK\\CustomShop\\config.json",
            "retry_max_attempts": 5,
        })
        assert r.get_json()["ok"] is True

        r2 = client.get("/api/servers")
        items = r2.get_json()["items"]
        assert len(items) == 1
        assert items[0]["server_id"] == "pve1"
        assert items[0]["plugin_config_path"] == "C:\\ARK\\CustomShop\\config.json"

    def test_delete_server(self, client):
        _login(client, ADMIN_STEAM)
        client.post("/api/servers", json={"server_id": "pvp1", "plugin_config_path": "C:\\cfg.json"})
        r = client.delete("/api/servers/pvp1")
        assert r.get_json()["ok"] is True
        r2 = client.get("/api/servers")
        assert r2.get_json()["items"] == []

    def test_sync_from_client_api_key(self, client):
        headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
        r = client.post(
            "/api/servers/sync",
            json={
                "machine_label": "Maquina-B",
                "servers": [{
                    "server_id": "volcano",
                    "label": "The Volcano",
                    "rcon_host": "127.0.0.1",
                    "rcon_port": 27020,
                    "game_host": "203.0.113.50",
                    "game_port": 7778,
                    "server_map": "The Volcano",
                    "arkland_ref": "tek:vol-1",
                    "show_on_home": True,
                }],
                "active_refs": ["tek:vol-1"],
            },
            headers=headers,
        )
        assert r.status_code == 200
        assert r.get_json()["ok"] is True
        home = client.get("/api/public/home").get_json()
        srv = next(s for s in home.get("servers", []) if s["server_id"] == "volcano")
        assert srv["can_connect"] is True
        assert srv["connect_url"] == f"steam://run/{ARK_ASE_STEAM_APP_ID}//+connect%20203.0.113.50:7778"
        assert srv["join_address"] == "203.0.113.50:7778"
        assert srv["map"] == "The Volcano"

    def test_upsert_server_preserves_game_host(self, client, tmp_path, monkeypatch):
        servers_file = tmp_path / "servers.json"
        servers_file.write_text(
            json.dumps([{
                "server_id": "pve1",
                "label": "PvE 1",
                "game_host": "203.0.113.60",
                "game_port": 7777,
                "rcon_host": "127.0.0.1",
                "rcon_port": 27020,
            }]),
            encoding="utf-8",
        )
        monkeypatch.setattr(_app_module, "_SERVERS_FILE", servers_file)
        _login(client, ADMIN_STEAM)
        r = client.post("/api/servers", json={
            "server_id": "pve1",
            "label": "PvE 1 atualizado",
            "rcon_host": "127.0.0.1",
            "rcon_port": 27020,
        })
        assert r.get_json()["ok"] is True
        saved = json.loads(servers_file.read_text(encoding="utf-8"))
        entry = next(s for s in saved if s["server_id"] == "pve1")
        assert entry["game_host"] == "203.0.113.60"
        assert entry["game_port"] == 7777

    def test_connect_status_endpoint(self, client, tmp_path, monkeypatch):
        servers_file = tmp_path / "servers.json"
        servers_file.write_text(
            json.dumps([
                {
                    "server_id": "ok_srv",
                    "label": "OK",
                    "show_on_home": True,
                    "join_host": "203.0.113.70",
                    "game_port": 7777,
                },
                {
                    "server_id": "bad_srv",
                    "label": "Bad",
                    "show_on_home": True,
                    "game_host": "127.0.0.1",
                    "game_port": 7777,
                },
            ]),
            encoding="utf-8",
        )
        monkeypatch.setattr(_app_module, "_SERVERS_FILE", servers_file)
        _login(client, ADMIN_STEAM)
        r = client.get("/api/servers/connect-status")
        d = r.get_json()
        assert d["ok"] is True
        assert d["summary"]["connectable"] == 1
        by_id = {i["server_id"]: i for i in d["items"]}
        assert by_id["ok_srv"]["can_connect"] is True
        assert by_id["bad_srv"]["can_connect"] is False
        assert by_id["bad_srv"]["blockers"]

    def test_connect_status_requires_admin(self, client):
        _login(client, USER_STEAM)
        r = client.get("/api/servers/connect-status")
        assert r.status_code == 403

    def test_sync_rejects_without_api_key(self, client):
        r = client.post("/api/servers/sync", json={"machine_label": "X", "servers": []})
        assert r.status_code == 401

    def test_server_required_fields(self, client):
        _login(client, ADMIN_STEAM)
        r = client.post("/api/servers", json={"label": "sem id"})
        assert r.status_code == 400

    def test_servers_requires_admin(self, client):
        _login(client, USER_STEAM)
        r = client.get("/api/servers")
        assert r.status_code == 403


# ── Entrega via fila do plugin ───────────────────────────────────────────────

class TestPluginDeliveryQueue:
    def test_process_order_queues_without_rcon(self, client):
        oid = _create_order_direct(status="PENDENTE")
        result = _app_module._process_order_delivery(oid)
        assert result["ok"] is True
        assert result["queued"] is True
        assert result["status"] == "PENDENTE"

        db = _app_module._SessionLocal()
        try:
            order = db.query(_app_module.Order).filter(_app_module.Order.order_id == oid).first()
            assert order.status == "PENDENTE"
        finally:
            db.close()

    def test_get_pending_returns_items(self, client):
        oid = _create_order_direct(item_id="metal_ingot_100", amount=2)
        r = client.get(
            f"/api/pending/{USER_STEAM}",
            headers={"X-API-Key": API_KEY},
        )
        d = r.get_json()
        assert d["ok"] is True
        assert len(d["items"]) == 1
        assert d["items"][0]["order_id"] == oid
        assert d["items"][0]["item_id"] == "metal_ingot_100"
        assert d["orders"] == d["items"]

    def test_mark_pending_delivered_batch(self, client):
        oid = _create_order_direct()
        r = client.post(
            "/api/pending/delivered",
            json={"steam_id": USER_STEAM, "order_ids": [oid]},
            headers={"X-API-Key": API_KEY},
        )
        assert r.get_json()["ok"] is True

        db = _app_module._SessionLocal()
        try:
            order = db.query(_app_module.Order).filter(_app_module.Order.order_id == oid).first()
            assert order.status == "ENTREGUE"
        finally:
            db.close()

    def test_pending_claim_reserves_orders(self, client):
        oid = _create_order_direct(item_id="Gamma", status="PENDENTE")
        r = client.post(
            "/api/pending/claim",
            json={"steam_id": USER_STEAM},
            headers={"X-API-Key": API_KEY},
        )
        d = r.get_json()
        assert d["ok"] is True
        assert len(d["items"]) == 1
        assert d["items"][0]["order_id"] == oid

        db = _app_module._SessionLocal()
        try:
            order = db.query(_app_module.Order).filter(_app_module.Order.order_id == oid).first()
            assert order.status == "ENTREGANDO"
        finally:
            db.close()

    def test_pending_claim_empty_queue_returns_json(self, client):
        r = client.post(
            "/api/pending/claim",
            json={"steam_id": USER_STEAM},
            headers={"X-API-Key": API_KEY},
        )
        assert r.status_code == 200
        assert r.data
        d = r.get_json()
        assert d["ok"] is True
        assert d["items"] == []
        assert d["orders"] == []

    def test_pending_claim_after_delivered_returns_empty_items(self, client):
        oid = _create_order_direct(item_id="metal_ingot_100", status="PENDENTE")
        claim = client.post(
            "/api/pending/claim",
            json={"steam_id": USER_STEAM},
            headers={"X-API-Key": API_KEY},
        )
        assert claim.get_json()["items"][0]["order_id"] == oid

        delivered = client.post(
            "/api/pending/delivered",
            json={"steam_id": USER_STEAM, "order_ids": [oid]},
            headers={"X-API-Key": API_KEY},
        )
        assert delivered.get_json()["ok"] is True

        again = client.post(
            "/api/pending/claim",
            json={"steam_id": USER_STEAM},
            headers={"X-API-Key": API_KEY},
        )
        assert again.status_code == 200
        assert again.data
        d = again.get_json()
        assert d["ok"] is True
        assert d["items"] == []
        assert d["orders"] == []

    def test_repair_license_grants_entitlement(self, client):
        _login(client, ADMIN_STEAM)
        oid = _create_order_direct(item_id="Gamma", status="ENTREGUE")
        fake_entitlements = [{"group": "Gamma", "timed_points_bonus": 25}]
        with patch.object(_app_module, "_ensure_license_entitlement_for_order", return_value=True), \
             patch.object(_app_module, "_get_player_entitlements", return_value=fake_entitlements):
            r = client.post(f"/api/admin/orders/{oid}/repair-license")
        d = r.get_json()
        assert d["ok"] is True
        assert d["repaired"] is True
        assert d["timed_points_total"] == 50
        assert "Gamma" in [e["group"] for e in d["entitlements"]]


class TestPendingDeliveries:
    def _write_license_catalog(self, tmp_path, monkeypatch) -> None:
        catalog = tmp_path / "license_catalog.json"
        catalog.write_text(
            json.dumps({
                "Items": {
                    "licenca_gamma": {
                        "Type": "license",
                        "Description": "Licença Gamma (30 dias)",
                    },
                },
                "Kits": {},
            }),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            _app_module,
            "_read_shop_config",
            lambda: json.loads(catalog.read_text(encoding="utf-8")),
        )
        _app_module._invalidate_shop_config_cache()

    def test_pending_claim_skips_already_licensed_order(self, client, tmp_path, monkeypatch):
        self._write_license_catalog(tmp_path, monkeypatch)
        oid = _create_order_direct(item_id="licenca_gamma", status="PENDENTE")

        # Fulfilled = entitlement deste pedido (source=order_id), não só grupo activo.
        monkeypatch.setattr(
            _app_module,
            "_get_player_entitlements",
            lambda sid: (
                [{"group": "Gamma", "source": oid, "expires_at": "2099-01-01T00:00:00+00:00"}]
                if sid == USER_STEAM
                else []
            ),
        )
        monkeypatch.setattr(
            _app_module,
            "_sync_license_permissions_all_servers",
            lambda *a, **k: [{"ok": True}],
        )

        r = client.post(
            "/api/pending/claim",
            json={"steam_id": USER_STEAM},
            headers={"X-API-Key": API_KEY},
        )
        d = r.get_json()
        assert d["ok"] is True
        assert d["items"] == []

        db = _app_module._SessionLocal()
        try:
            order = db.query(_app_module.Order).filter(_app_module.Order.order_id == oid).first()
            assert order.status == "ENTREGUE"
            assert order.last_error is None
        finally:
            db.close()

    def test_pending_release_fulfills_already_licensed_order(self, client, tmp_path, monkeypatch):
        self._write_license_catalog(tmp_path, monkeypatch)
        oid = _create_order_direct(item_id="licenca_gamma", status="ENTREGANDO")

        monkeypatch.setattr(
            _app_module,
            "_get_player_entitlements",
            lambda sid: (
                [{"group": "Gamma", "source": oid, "expires_at": "2099-01-01T00:00:00+00:00"}]
                if sid == USER_STEAM
                else []
            ),
        )
        monkeypatch.setattr(
            _app_module,
            "_sync_license_permissions_all_servers",
            lambda *a, **k: [{"ok": True}],
        )

        r = client.post(
            "/api/pending/release",
            json={"steam_id": USER_STEAM, "order_ids": [oid]},
            headers={"X-API-Key": API_KEY},
        )
        d = r.get_json()
        assert d["ok"] is True
        assert oid in d["fulfilled"]
        assert oid not in d["released"]

        db = _app_module._SessionLocal()
        try:
            order = db.query(_app_module.Order).filter(_app_module.Order.order_id == oid).first()
            assert order.status == "ENTREGUE"
            assert order.last_error is None
        finally:
            db.close()


# ── Delivery com RCON por servidor (modo legado) ─────────────────────────────

class TestServerRconRouting:
    def test_delivery_uses_server_specific_rcon(self, client, tmp_path):
        _write_settings(tmp_path, delivery_mode="rcon")
        _login(client, ADMIN_STEAM)
        client.post("/api/servers", json={
            "server_id": "pvp2",
            "rcon_host": "192.168.1.99",
            "rcon_port": 27050,
            "rcon_password": "pvp_secret",
        })

        calls = []
        def fake_rcon(host, port, password, command, timeout=5.0):
            calls.append({"host": host, "port": port, "password": password})
            return "ok"

        with patch.object(_app_module, "_rcon_command", side_effect=fake_rcon):
            oid = _create_order_direct(server_id="pvp2")
            _app_module._process_order_delivery(oid)

        assert calls[0]["host"] == "192.168.1.99"
        assert calls[0]["port"] == 27050
        assert calls[0]["password"] == "pvp_secret"


# ── Concorrência ──────────────────────────────────────────────────────────────

class TestConcurrency:
    def test_concurrent_delivery_does_not_duplicate(self, tmp_path):
        """
        WITH FOR UPDATE garante idempotência em MySQL/MariaDB.
        SQLite não suporta row-level lock, então este teste valida apenas
        que o status final é ENTREGUE (sem duplicatas de status, mesmo que
        múltiplas tentativas ocorram).
        """
        _write_settings(tmp_path, delivery_mode="rcon")
        oid = _create_order_direct(status="PENDENTE")

        def fake_rcon(host, port, password, command, timeout=5.0):
            return "ok"

        threads = []
        for _ in range(5):
            t = threading.Thread(
                target=lambda: _app_module._process_order_delivery(oid),
            )
            threads.append(t)

        with patch.object(_app_module, "_rcon_command", side_effect=fake_rcon):
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        db = _app_module._SessionLocal()
        try:
            order = db.query(_app_module.Order).filter(_app_module.Order.order_id == oid).first()
            assert order.status == "ENTREGUE"
        finally:
            db.close()


# ── RCON (reload + comandos in-game) ─────────────────────────────────────────

class TestRconScope:
    def test_rcon_blocks_shop_points(self, client):
        _login(client, ADMIN_STEAM)
        r = client.post("/api/rcon/command", json={"command": "Shop.AddPoints 76561198000000002 100"})
        assert r.status_code == 400
        assert "banco central" in r.get_json()["error"].lower()

    def test_rcon_status(self, client):
        _login(client, ADMIN_STEAM)
        with patch.object(_app_module, "_rcon_test_connection", return_value=(True, "No players")):
            r = client.get("/api/rcon/status")
        d = r.get_json()
        assert d["ok"] is True
        assert d["connected"] is True

    def test_rcon_reload_calls_plugin(self, client, tmp_path):
        _write_settings(tmp_path)
        _login(client, ADMIN_STEAM)
        with patch.object(_app_module, "_rcon_command", return_value="CustomShop reloaded") as mock:
            r = client.post("/api/rcon/reload")
        assert r.get_json()["ok"] is True
        mock.assert_called()
        assert mock.call_args.kwargs.get("connect_retries") == 5 or (
            len(mock.call_args) > 0 and mock.call_args[1].get("connect_retries") == 5
        )


# ── Admin gestão de jogadores ───────────────────────────────────────────────────

def _seed_store_user(
    steam_id: str,
    *,
    display_name: str = "Jogador Teste",
    steam_persona: str | None = None,
    blocked: bool = False,
    regulamento_accepted: bool = True,
) -> None:
    from regulamento_config import REGULAMENTO_VERSION

    persona = (
        steam_persona
        if steam_persona is not None
        else (display_name if display_name and display_name != steam_id else None)
    )
    db = _app_module._SessionLocal()
    try:
        row = db.get(_app_module.StoreUser, steam_id)
        if row is None:
            row = _app_module.StoreUser(
                steam_id=steam_id,
                display_name=display_name,
                steam_persona=persona,
                site_access_blocked=blocked,
                last_login_at=_now(),
            )
            db.add(row)
        else:
            row.display_name = display_name
            if steam_persona is not None:
                row.steam_persona = steam_persona if steam_persona else None
            elif persona is not None:
                row.steam_persona = persona
            elif display_name == steam_id:
                row.steam_persona = None
            row.site_access_blocked = blocked
            row.last_login_at = _now()
        if regulamento_accepted:
            row.regulamento_accepted_version = REGULAMENTO_VERSION
            row.regulamento_accepted_at = _now()
        else:
            row.regulamento_accepted_version = None
            row.regulamento_accepted_at = None
        db.commit()
    finally:
        db.close()


class TestAdminPlayers:
    def test_list_players_requires_admin(self, client):
        _seed_store_user(USER_STEAM)
        _login(client, USER_STEAM)
        r = client.get("/api/admin/players")
        assert r.status_code == 403

    def test_list_and_detail_players(self, client):
        _seed_store_user(USER_STEAM, display_name="Alpha Tester", steam_persona="Alpha Tester")
        _seed_player_points(USER_STEAM, 500)
        _login(client, ADMIN_STEAM)
        r = client.get("/api/admin/players?q=Alpha")
        d = r.get_json()
        assert d["ok"] is True
        assert d["total"] >= 1
        assert any(p["steam_id"] == USER_STEAM for p in d["items"])

        r2 = client.get(f"/api/admin/players/{USER_STEAM}")
        d2 = r2.get_json()
        assert d2["ok"] is True
        assert d2["player"]["points"] == 500
        assert d2["player"]["display_name"] == "Alpha Tester"

    def test_list_players_ignores_market_display_name(self, client):
        _seed_store_user(USER_STEAM, display_name=USER_STEAM)
        _login(client, ADMIN_STEAM)
        d = client.get("/api/admin/players").get_json()
        row = next(p for p in d["items"] if p["steam_id"] == USER_STEAM)
        assert row["display_name"] == USER_STEAM
        assert row["display_name"] != "TestPlayer"

    def test_adjust_points_via_player_endpoint(self, client):
        _seed_store_user(USER_STEAM)
        _login(client, ADMIN_STEAM)
        r = client.post(
            f"/api/admin/players/{USER_STEAM}/points",
            json={"mode": "add", "amount": 200, "reason": "teste"},
        )
        assert r.get_json()["ok"] is True
        assert r.get_json()["after"] == 200

        r2 = client.post(
            f"/api/admin/players/{USER_STEAM}/points",
            json={"mode": "subtract", "amount": 50, "reason": "ajuste"},
        )
        assert r2.get_json()["after"] == 150

    def test_ban_and_unban_player(self, client):
        _seed_store_user(USER_STEAM)
        _login(client, ADMIN_STEAM)
        r = client.post(
            f"/api/admin/players/{USER_STEAM}/ban",
            json={"blocked": True, "reason": "abuso"},
        )
        d = r.get_json()
        assert d["ok"] is True
        assert d["site_access_blocked"] is True

        _login(client, USER_STEAM)
        r2 = client.get("/api/player/points")
        assert r2.status_code == 403

        _login(client, ADMIN_STEAM)
        r3 = client.post(
            f"/api/admin/players/{USER_STEAM}/ban",
            json={"blocked": False},
        )
        assert r3.get_json()["ok"] is True

    def test_list_players_without_market_profile_table(self, client, monkeypatch):
        _seed_store_user(USER_STEAM, display_name="Alpha Tester")
        monkeypatch.setattr(
            _app_module,
            "_db_table_exists",
            lambda _engine, name: name != "market_player_profile",
        )
        _login(client, ADMIN_STEAM)
        r = client.get("/api/admin/players?q=Alpha")
        d = r.get_json()
        assert r.status_code == 200
        assert d["ok"] is True
        assert d["total"] >= 1

    def test_steam_id_join_uses_unicode_collation(self):
        prev = _app_module._STEAM_ID_COLLATION_NORMALIZED
        try:
            _app_module._STEAM_ID_COLLATION_NORMALIZED = False
            sql = _app_module._steam_id_on_sql("mp.steam_id", "su.steam_id", mysql=True)
            assert "COLLATE utf8mb4_unicode_ci" in sql
            assert sql.count("COLLATE utf8mb4_unicode_ci") == 2
            _app_module._STEAM_ID_COLLATION_NORMALIZED = True
            assert _app_module._steam_id_on_sql("mp.steam_id", "su.steam_id", mysql=True) == (
                "mp.steam_id = su.steam_id"
            )
            assert _app_module._steam_id_on_sql("a.steam_id", "b.steam_id", mysql=False) == (
                "a.steam_id = b.steam_id"
            )
        finally:
            _app_module._STEAM_ID_COLLATION_NORMALIZED = prev

    def test_steam_id_collation_modify_omits_pk_when_column_is_pk(self):
        sql = _app_module._build_steam_id_collation_modify_sql(
            "players",
            "steam_id",
            "varchar(20)",
            "NOT NULL",
            key_flag="PRI",
            is_pk_column=True,
        )
        assert "PRIMARY KEY" not in sql
        assert "utf8mb4_unicode_ci" in sql

    def test_steam_id_collation_modify_adds_pk_when_not_yet_pk(self):
        sql = _app_module._build_steam_id_collation_modify_sql(
            "legacy",
            "steam_id",
            "varchar(20)",
            "NOT NULL",
            key_flag="PRI",
            is_pk_column=False,
        )
        assert sql.endswith("NOT NULL PRIMARY KEY")

    def test_is_multiple_primary_key_error_detects_1068(self):
        class _Orig:
            args = (1068, "Multiple primary key defined")

        class _Err(Exception):
            orig = _Orig()

        assert _app_module._is_multiple_primary_key_error(_Err()) is True
        assert _app_module._is_multiple_primary_key_error(ValueError("other")) is False

class TestAdminPoints:
    def test_add_and_get_points(self, client):
        _login(client, ADMIN_STEAM)
        sid = USER_STEAM
        r = client.post("/api/admin/points", json={"action": "add", "steam_id": sid, "amount": 1000})
        d = r.get_json()
        assert d["ok"] is True
        assert d["points"] == 1000

        r2 = client.post("/api/admin/points", json={"action": "get", "steam_id": sid})
        assert r2.get_json()["points"] == 1000

    def test_set_points(self, client):
        _login(client, ADMIN_STEAM)
        sid = USER_STEAM
        client.post("/api/admin/points", json={"action": "set", "steam_id": sid, "amount": 250})
        r = client.post("/api/admin/points", json={"action": "get", "steam_id": sid})
        assert r.get_json()["points"] == 250

    def test_points_requires_admin(self, client):
        _login(client, USER_STEAM)
        r = client.post("/api/admin/points", json={"action": "get", "steam_id": USER_STEAM})
        assert r.status_code == 403


# ── Admin reprocess ───────────────────────────────────────────────────────────

class TestAdminReprocess:
    def test_reprocess_erro_order(self, client):
        _login(client, ADMIN_STEAM)
        oid = _create_order_direct(status="ERRO")
        with patch.object(_app_module, "_rcon_command", return_value="ok"):
            r = client.post(f"/api/admin/orders/{oid}/reprocess?force_rcon=1")
        d = r.get_json()
        assert d["ok"] is True
        assert d["status"] == "ENTREGUE"

    def test_reprocess_already_delivered_blocked(self, client):
        _login(client, ADMIN_STEAM)
        oid = _create_order_direct(status="ENTREGUE")
        r = client.post(f"/api/admin/orders/{oid}/reprocess")
        assert r.status_code == 400


# ── Admin orders list ─────────────────────────────────────────────────────────

class TestAdminOrdersList:
    def test_admin_orders_forbidden_for_player(self, client):
        _login(client, USER_STEAM)
        r = client.get("/api/admin/orders")
        assert r.status_code in (401, 403)

    def test_admin_orders_list_with_total(self, client):
        _login(client, ADMIN_STEAM)
        _create_order_direct(status="ENTREGUE")
        _create_order_direct(status="PENDENTE")
        r = client.get("/api/admin/orders")
        d = r.get_json()
        assert d.get("ok") is True
        assert "total" in d
        assert d["total"] >= 2
        assert "items" in d

    def test_admin_orders_pagination(self, client):
        _login(client, ADMIN_STEAM)
        for _ in range(5):
            _create_order_direct()
        r = client.get("/api/admin/orders?limit=2&offset=0")
        d = r.get_json()
        assert d["ok"] is True
        assert d["total"] >= 5
        assert len(d["items"]) == 2

        r2 = client.get("/api/admin/orders?limit=2&offset=2")
        d2 = r2.get_json()
        assert len(d2["items"]) == 2
        assert d2["items"][0]["order_id"] != d["items"][0]["order_id"]

    def test_admin_orders_filter_by_steam_id(self, client):
        _login(client, ADMIN_STEAM)
        other_steam = "76561198000000099"
        _create_order_direct(steam_id=USER_STEAM, status="ENTREGUE")
        _create_order_direct(steam_id=other_steam, status="ENTREGUE")
        r = client.get(f"/api/admin/orders?q={USER_STEAM}")
        d = r.get_json()
        assert d["ok"] is True
        assert all(o["steam_id"] == USER_STEAM for o in d["items"])

    def test_admin_orders_filter_by_status(self, client):
        _login(client, ADMIN_STEAM)
        _create_order_direct(status="ENTREGUE")
        _create_order_direct(status="PENDENTE")
        r = client.get("/api/admin/orders?status=PENDENTE")
        d = r.get_json()
        assert d["ok"] is True
        assert all(o["status"] == "PENDENTE" for o in d["items"])


# ── Admin order actions (refund / resend / cancel / details) ─────────────────

class TestAdminOrderActions:
    def test_admin_refund_credits_player(self, client):
        _login(client, ADMIN_STEAM)
        _seed_player_points(USER_STEAM, 100)
        oid = _create_order_direct(status="ENTREGUE", points_spent=50)
        r = client.post(
            f"/api/admin/orders/{oid}/refund",
            json={"reason": "Não entregue"},
        )
        d = r.get_json()
        assert d["ok"] is True
        assert d["status"] == "REEMBOLSADO"
        assert d["refunded"] == 50
        assert d["new_balance"] == 150

        db = _app_module._SessionLocal()
        try:
            order = db.query(_app_module.Order).filter(_app_module.Order.order_id == oid).first()
            assert order.status == "REEMBOLSADO"
        finally:
            db.close()

    def test_admin_refund_blocked_when_already_refunded(self, client):
        _login(client, ADMIN_STEAM)
        oid = _create_order_direct(status="REEMBOLSADO", points_spent=10)
        r = client.post(f"/api/admin/orders/{oid}/refund", json={})
        assert r.status_code == 409

    def test_admin_resend_sets_pending(self, client):
        _login(client, ADMIN_STEAM)
        oid = _create_order_direct(status="ERRO")
        r = client.post(f"/api/admin/orders/{oid}/resend", json={})
        d = r.get_json()
        assert d["ok"] is True
        assert d["status"] == "PENDENTE"
        assert d.get("queued") is True

        db = _app_module._SessionLocal()
        try:
            order = db.query(_app_module.Order).filter(_app_module.Order.order_id == oid).first()
            assert order.status == "PENDENTE"
            assert order.retry_count == 0
        finally:
            db.close()

    def test_admin_resend_blocked_when_already_pending(self, client):
        _login(client, ADMIN_STEAM)
        oid = _create_order_direct(status="PENDENTE")
        r = client.post(f"/api/admin/orders/{oid}/resend", json={})
        assert r.status_code == 409

    def test_admin_cancel_without_refund(self, client):
        _login(client, ADMIN_STEAM)
        _seed_player_points(USER_STEAM, 200)
        oid = _create_order_direct(status="ENTREGUE", points_spent=80)
        r = client.post(f"/api/admin/orders/{oid}/cancel", json={"reason": "Fraude"})
        d = r.get_json()
        assert d["ok"] is True
        assert d["status"] == "CANCELADO"
        assert d["refunded"] == 0

        db = _app_module._SessionLocal()
        try:
            order = db.query(_app_module.Order).filter(_app_module.Order.order_id == oid).first()
            assert order.status == "CANCELADO"
            row = db.execute(
                __import__("sqlalchemy").text("SELECT points FROM players WHERE steam_id = :sid"),
                {"sid": USER_STEAM},
            ).fetchone()
            assert int(row[0]) == 200
        finally:
            db.close()

    def test_admin_refund_closes_contest(self, client):
        _login(client, ADMIN_STEAM)
        _seed_player_points(USER_STEAM, 0)
        oid = _create_order_direct(status="CONTESTADO", points_spent=25)
        db = _app_module._SessionLocal()
        try:
            db.add(_app_module.Dispute(
                order_id=oid, steam_id=USER_STEAM, reason="bug", status="ABERTO", created_at=_now(),
            ))
            db.commit()
        finally:
            db.close()

        r = client.post(f"/api/admin/orders/{oid}/refund", json={})
        assert r.get_json()["ok"] is True

        db = _app_module._SessionLocal()
        try:
            dispute = db.query(_app_module.Dispute).filter(_app_module.Dispute.order_id == oid).first()
            assert dispute.status == "ENCERRADO"
            order = db.query(_app_module.Order).filter(_app_module.Order.order_id == oid).first()
            assert order.contested is False
        finally:
            db.close()

    def test_admin_order_details(self, client):
        _login(client, ADMIN_STEAM)
        oid = _create_order_direct(status="ENTREGUE", points_spent=10)
        r = client.get(f"/api/admin/orders/{oid}/details")
        d = r.get_json()
        assert d["ok"] is True
        assert d["order"]["order_id"] == oid
        assert d["order"]["points_spent"] == 10
        assert "audit_events" in d
        assert "attempts" in d

    def test_admin_resend_blocked_for_reemitido(self, client):
        _login(client, ADMIN_STEAM)
        oid = _create_order_direct(status="REEMITIDO")
        r = client.post(f"/api/admin/orders/{oid}/resend", json={})
        assert r.status_code == 409

    def test_admin_refund_blocked_when_amount_unknown(self, client):
        _login(client, ADMIN_STEAM)
        oid = _create_order_direct(status="ENTREGUE", points_spent=0, item_id="item_inexistente_xyz")
        r = client.post(f"/api/admin/orders/{oid}/refund", json={})
        assert r.status_code == 400
        db = _app_module._SessionLocal()
        try:
            order = db.query(_app_module.Order).filter(_app_module.Order.order_id == oid).first()
            assert order.status == "ENTREGUE"
        finally:
            db.close()

    def test_admin_refund_uses_audit_price_when_points_spent_zero(self, client):
        _login(client, ADMIN_STEAM)
        _seed_player_points(USER_STEAM, 100)
        oid = _create_order_direct(status="ENTREGUE", points_spent=0, item_id="sword")
        db = _app_module._SessionLocal()
        try:
            db.add(_app_module.AuditEvent(
                event_type="purchase_created",
                order_id=oid,
                target_steam_id=USER_STEAM,
                payload_json='{"price": 75}',
                created_at=_now(),
            ))
            db.commit()
        finally:
            db.close()
        r = client.post(f"/api/admin/orders/{oid}/refund", json={})
        d = r.get_json()
        assert d["ok"] is True
        assert d["refunded"] == 75
        assert d["new_balance"] == 175


# ── Licença Nuvem / entitlements ─────────────────────────────────────────────

def _seed_player_points(steam_id: str, points: int) -> None:
    from sqlalchemy import text

    db = _app_module._SessionLocal()
    try:
        db.execute(
            text(
                "INSERT INTO players (steam_id, points) VALUES (:sid, :pts) "
                "ON CONFLICT(steam_id) DO UPDATE SET points = :pts"
            ),
            {"sid": steam_id, "pts": points},
        )
        db.commit()
    finally:
        db.close()


def _mock_display_name_ok(monkeypatch):
    monkeypatch.setattr(
        _app_module,
        "_auth_display_name_fields",
        lambda _sid, is_admin: {
            "market_display_name": "TestPlayer",
            "needs_display_name": False,
        },
    )
    prof = MagicMock()
    prof.market_display_name = "TestPlayer"
    monkeypatch.setattr(_app_module, "_safe_market_profile", lambda _db, _sid: prof)


class TestCloudLicensePurchase:
    def test_debit_and_grant_keyvault_in_one_transaction(self, monkeypatch):
        _seed_player_points(USER_STEAM, 10_000)
        db = _app_module._SessionLocal()
        try:
            db.execute(
                __import__("sqlalchemy").text(
                    "UPDATE players SET points = MAX(points - :price, 0) "
                    "WHERE steam_id = :sid AND points >= :price"
                ),
                {"price": 5000, "sid": USER_STEAM},
            )
            _app_module._apply_entitlement_grant_tx(
                db, USER_STEAM, "keyvault", 30, source="test-order", notes="web:licenca_nuvem",
            )
            db.commit()
        finally:
            db.close()

        assert _app_module._get_player_points(USER_STEAM) == 5000
        ents = _app_module._get_player_entitlements(USER_STEAM)
        assert any(e["group"] == "keyvault" for e in ents)

    def test_keyvault_renewal_extends_expires_not_replace(self, monkeypatch):
        """Renovação de keyvault soma dias ao residual (spec: renovação soma)."""
        from datetime import datetime, timedelta, timezone

        db = _app_module._SessionLocal()
        try:
            # Residual ~17 dias
            past = (datetime.now(timezone.utc) - timedelta(days=13)).replace(tzinfo=None)
            future = (datetime.now(timezone.utc) + timedelta(days=17)).replace(tzinfo=None)
            db.execute(
                __import__("sqlalchemy").text(
                    "INSERT INTO player_entitlements "
                    "(steam_id, group_name, expires, source, notes, created_at) "
                    "VALUES (:sid, 'keyvault', :exp, 'old', 'residual', :created)"
                ),
                {"sid": USER_STEAM, "exp": future, "created": past},
            )
            db.commit()
            _app_module._apply_entitlement_grant_tx(
                db, USER_STEAM, "keyvault", 30, source="renew", notes="web:licenca_nuvem",
            )
            db.commit()
            row = db.execute(
                __import__("sqlalchemy").text(
                    "SELECT expires FROM player_entitlements "
                    "WHERE steam_id = :sid AND group_name = 'keyvault'"
                ),
                {"sid": USER_STEAM},
            ).fetchone()
        finally:
            db.close()

        assert row and row[0] is not None
        exp = row[0]
        if isinstance(exp, str):
            exp = datetime.fromisoformat(exp.replace("Z", "+00:00"))
        if getattr(exp, "tzinfo", None) is None:
            exp = exp.replace(tzinfo=timezone.utc)
        remaining = (exp - datetime.now(timezone.utc)).total_seconds()
        # ~17 + 30 = ~47 dias (±2 dias de tolerância)
        assert remaining >= 44 * 86400
        assert remaining <= 50 * 86400

    def test_purchase_license_failure_rolls_back_debit(self, monkeypatch):
        _seed_player_points(USER_STEAM, 10_000)
        db = _app_module._SessionLocal()
        try:
            db.execute(
                __import__("sqlalchemy").text(
                    "UPDATE players SET points = MAX(points - :price, 0) "
                    "WHERE steam_id = :sid AND points >= :price"
                ),
                {"price": 5000, "sid": USER_STEAM},
            )

            def _boom(*_a, **_kw):
                raise RuntimeError("grant failed")

            monkeypatch.setattr(_app_module, "_apply_entitlement_grant_tx", _boom)
            try:
                _app_module._apply_entitlement_grant_tx(
                    db, USER_STEAM, "keyvault", 30, source="x", notes="y",
                )
            except RuntimeError:
                db.rollback()
        finally:
            db.close()

        assert _app_module._get_player_points(USER_STEAM) == 10_000

    def test_entitlements_schema_bootstrap_once(self, monkeypatch):
        _app_module._ENTITLEMENTS_SCHEMA_READY = False
        ddl_calls: list[int] = []
        orig_execute = _app_module.text

        def _track_execute(sql):
            stmt = orig_execute(sql)
            if "player_entitlements" in str(sql) and "CREATE TABLE" in str(sql):
                ddl_calls.append(1)
            return stmt

        monkeypatch.setattr(_app_module, "text", _track_execute)
        db = _app_module._SessionLocal()
        try:
            _app_module._ensure_entitlements_schema(db)
            _app_module._ensure_entitlements_schema(db)
        finally:
            db.close()
        assert len(ddl_calls) == 1
        assert _app_module._ENTITLEMENTS_SCHEMA_READY is True


# ── Doações — cartão Mercado Pago ─────────────────────────────────────────────

class TestDonationPublicUrl:
    def test_shop_public_base_url_defaults_to_arkland(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
        assert _app_module._shop_public_base_url() == "https://arkland.com.br"

    def test_build_base_url_uses_public_url_behind_localhost_proxy(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
        with client.application.test_request_context(
            "/api/player/card/checkout",
            headers={
                "Host": "127.0.0.1:27199",
                "X-Forwarded-Proto": "https",
            },
            method="POST",
        ):
            assert _app_module._build_base_url() == "https://arkland.com.br"

    def test_get_mp_access_token_prefers_settings_over_env(self, tmp_path, monkeypatch):
        _write_settings(tmp_path, mp_access_token="SETTINGS_TOKEN")
        monkeypatch.setenv("MP_ACCESS_TOKEN", "ENV_TOKEN")
        assert _app_module._get_mp_access_token() == "SETTINGS_TOKEN"


class TestCardCheckout:
    def _enable_mp(self, tmp_path, monkeypatch):
        _write_settings(tmp_path, mp_access_token="TEST_MP_TOKEN", mp_sandbox=True)
        monkeypatch.setattr(_app_module, "_get_mp_access_token", lambda: "TEST_MP_TOKEN")
        monkeypatch.setattr(_app_module, "_mp_sandbox", lambda: True)
        monkeypatch.setattr(
            _app_module,
            "_auth_display_name_fields",
            lambda _sid, is_admin: {
                "market_display_name": "TestPlayer",
                "needs_display_name": False,
            },
        )

    def test_card_checkout_requires_auth(self, client):
        r = client.post("/api/player/card/checkout", json={"package_id": "p10000"})
        assert r.status_code == 401

    def test_card_checkout_creates_preference(self, client, tmp_path, monkeypatch):
        self._enable_mp(tmp_path, monkeypatch)
        _login(client, USER_STEAM)
        fake_pref = {
            "id": "pref_123",
            "sandbox_init_point": "https://sandbox.mercadopago.com.br/checkout/v1/redirect?pref_id=pref_123",
        }
        with patch.object(_app_module, "create_card_checkout_preference", return_value=fake_pref), \
             patch.object(_app_module, "extract_checkout_url", return_value=fake_pref["sandbox_init_point"]):
            r = client.post(
                "/api/player/card/checkout",
                json={
                    "package_id": "p10000",
                    "payer": {
                        "email": "player@example.com",
                        "full_name": "João Silva",
                        "cpf": "529.982.247-25",
                    },
                },
            )
        d = r.get_json()
        assert r.status_code == 200
        assert d["ok"] is True
        assert d["checkout_url"].startswith("https://sandbox.mercadopago")
        assert d["points"] == 10000
        assert d["amount_brl"] == 5.0

        db = _app_module._SessionLocal()
        try:
            row = db.query(_app_module.PointPayment).filter(
                _app_module.PointPayment.payment_id == d["payment_id"]
            ).first()
            assert row is not None
            assert row.package_id == "p10000"
            assert row.points == 10000
            assert row.status == "PENDENTE"
            assert row.credited is False
            assert row.mp_payment_id is None
            assert row.payment_method == "card"
        finally:
            db.close()

    def test_card_checkout_rejects_invalid_package(self, client, tmp_path, monkeypatch):
        self._enable_mp(tmp_path, monkeypatch)
        _login(client, USER_STEAM)
        r = client.post(
            "/api/player/card/checkout",
            json={
                "package_id": "invalid_pkg",
                "payer": {
                    "email": "player@example.com",
                    "full_name": "João Silva",
                    "cpf": "529.982.247-25",
                },
            },
        )
        assert r.status_code == 400

    def test_card_checkout_without_cpf_international(self, client, tmp_path, monkeypatch):
        self._enable_mp(tmp_path, monkeypatch)
        _login(client, USER_STEAM)
        fake_pref = {
            "id": "pref_intl",
            "sandbox_init_point": "https://sandbox.mercadopago.com.br/checkout/v1/redirect?pref_id=pref_intl",
        }
        with patch.object(_app_module, "create_card_checkout_preference", return_value=fake_pref) as mock_pref, \
             patch.object(_app_module, "extract_checkout_url", return_value=fake_pref["sandbox_init_point"]):
            r = client.post(
                "/api/player/card/checkout",
                json={
                    "package_id": "p10000",
                    "payer": {
                        "email": "international@example.com",
                        "full_name": "John Smith",
                    },
                },
            )
        assert r.status_code == 200
        assert r.get_json()["ok"] is True
        mock_pref.assert_called_once()
        payer_arg = mock_pref.call_args.kwargs["payer"]
        assert payer_arg["email"] == "international@example.com"
        assert "identification" not in payer_arg

    def test_card_payer_form_endpoint(self, client):
        _login(client, USER_STEAM)
        r = client.get("/api/player/card/payer-form")
        d = r.get_json()
        assert r.status_code == 200
        assert d["ok"] is True
        ids = [f["id"] for f in d["fields"]]
        assert "email" in ids and "full_name" in ids
        cpf_field = next(f for f in d["fields"] if f["id"] == "identification")
        assert cpf_field["required"] is False

    def test_public_exchange_rates(self, client):
        r = client.get("/api/public/exchange-rates")
        d = r.get_json()
        assert r.status_code == 200
        assert d["ok"] is True
        assert d["base"] == "BRL"
        assert "USD" in d["rates"] and "EUR" in d["rates"]

    def test_catalog_includes_exchange_estimates(self, client):
        r = client.get("/api/catalog")
        d = r.get_json()
        assert r.status_code == 200
        assert "exchange_rates" in d
        pkgs = d.get("point_packages") or []
        if pkgs:
            assert "estimate_usd" in pkgs[0]
            assert "estimate_eur" in pkgs[0]

    def test_webhook_credits_card_payment(self, client, tmp_path, monkeypatch):
        self._enable_mp(tmp_path, monkeypatch)
        payment_id = str(uuid.uuid4())
        db = _app_module._SessionLocal()
        try:
            db.add(
                _app_module.PointPayment(
                    payment_id=payment_id,
                    mp_payment_id=None,
                    steam_id=USER_STEAM,
                    package_id="p500",
                    amount_brl=5.0,
                    points=500,
                    status="PENDENTE",
                    credited=False,
                    payment_method="card",
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
            db.commit()
        finally:
            db.close()

        mp_resp = {
            "id": "mp_card_99",
            "status": "approved",
            "external_reference": payment_id,
            "payment_method_id": "visa",
        }
        with patch.object(_app_module, "fetch_payment", return_value=mp_resp), \
             patch.object(_app_module, "_add_player_points_tx", return_value=500) as credit_mock:
            r = client.post("/api/payments/webhook", json={"data": {"id": "mp_card_99"}})
        d = r.get_json()
        assert d["ok"] is True, d.get("error")
        credit_mock.assert_called_once()

        db = _app_module._SessionLocal()
        try:
            row = db.query(_app_module.PointPayment).filter(
                _app_module.PointPayment.payment_id == payment_id
            ).first()
            assert row.credited is True
            assert row.status == "APROVADO"
            assert row.mp_payment_id == "mp_card_99"
            assert row.payment_method == "card"
        finally:
            db.close()

    def test_status_accepts_mp_id_hint_for_card(self, client, tmp_path, monkeypatch):
        self._enable_mp(tmp_path, monkeypatch)
        _login(client, USER_STEAM)
        payment_id = str(uuid.uuid4())
        db = _app_module._SessionLocal()
        try:
            db.add(
                _app_module.PointPayment(
                    payment_id=payment_id,
                    mp_payment_id=None,
                    steam_id=USER_STEAM,
                    package_id="p500",
                    amount_brl=5.0,
                    points=500,
                    status="PENDENTE",
                    credited=False,
                    payment_method="card",
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
            db.commit()
        finally:
            db.close()

        mp_resp = {"id": "mp_card_hint", "status": "pending", "external_reference": payment_id}
        with patch.object(_app_module, "fetch_payment", return_value=mp_resp):
            r = client.get(f"/api/player/pix/{payment_id}/status?mp_id=mp_card_hint")
        d = r.get_json()
        assert d["ok"] is True
        db = _app_module._SessionLocal()
        try:
            row = db.query(_app_module.PointPayment).filter(
                _app_module.PointPayment.payment_id == payment_id
            ).first()
            assert row.mp_payment_id == "mp_card_hint"
        finally:
            db.close()

    def test_status_polls_mp_for_abandoned_pix_payment(self, client, tmp_path, monkeypatch):
        """ABANDONADO não deve bloquear reconciliação — jogador pode pagar após fechar o modal."""
        self._enable_mp(tmp_path, monkeypatch)
        _login(client, USER_STEAM)
        payment_id = str(uuid.uuid4())
        db = _app_module._SessionLocal()
        try:
            db.add(
                _app_module.PointPayment(
                    payment_id=payment_id,
                    mp_payment_id="mp_abandoned_pix",
                    steam_id=USER_STEAM,
                    package_id="p500",
                    amount_brl=5.0,
                    points=500,
                    status="ABANDONADO",
                    credited=False,
                    payment_method="pix",
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
            db.commit()
        finally:
            db.close()

        mp_resp = {"id": "mp_abandoned_pix", "status": "approved", "external_reference": payment_id}
        with patch.object(_app_module, "fetch_payment", return_value=mp_resp) as fetch_mock, \
             patch.object(_app_module, "_pix_mp_poll_allowed", return_value=True), \
             patch.object(_app_module, "_add_player_points_tx", return_value=500) as credit_mock:
            r = client.get(f"/api/player/pix/{payment_id}/status")
        d = r.get_json()
        assert d["ok"] is True, d.get("error")
        assert d["credited"] is True
        assert d["status"] == "APROVADO"
        fetch_mock.assert_called_once()
        credit_mock.assert_called_once()

        db = _app_module._SessionLocal()
        try:
            row = db.query(_app_module.PointPayment).filter(
                _app_module.PointPayment.payment_id == payment_id
            ).first()
            assert row.credited is True
            assert row.status == "APROVADO"
        finally:
            db.close()


class TestKitRedemptionLimit:
    def _mock_kit_catalog(self, monkeypatch, tmp_path):
        config = {
            "Kits": {
                "starter": {
                    "Price": 0,
                    "DefaultAmount": 3,
                    "Description": "Kit Inicial",
                    "Items": [{"Blueprint": "/Game/Test/Item", "Quantity": 1}],
                }
            }
        }
        config_path = tmp_path / "shop_config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        monkeypatch.setattr(
            _app_module,
            "_load_settings",
            lambda: {
                "config_path": str(config_path),
                "server_id": "default",
                "delivery_mode": "plugin",
            },
        )
        _app_module._CONFIG_CACHE.clear()

    def _seed_player_kits(self, steam_id: str, stash: dict) -> None:
        from sqlalchemy import text

        db = _app_module._SessionLocal()
        try:
            kits_json = json.dumps(stash, ensure_ascii=False)
            db.execute(
                text(
                    "INSERT INTO players (steam_id, points, kits) VALUES (:sid, 0, :kits) "
                    "ON CONFLICT(steam_id) DO UPDATE SET kits = :kits"
                ),
                {"sid": steam_id, "kits": kits_json},
            )
            db.commit()
        finally:
            db.close()

    def test_purchase_kit_allowed_with_remaining_uses(self, client, monkeypatch, tmp_path):
        _mock_display_name_ok(monkeypatch)
        self._mock_kit_catalog(monkeypatch, tmp_path)
        _login(client, USER_STEAM)
        r = client.post(
            "/api/player/purchase",
            json={"item_id": "starter", "item_type": "kit", "amount": 1},
        )
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_purchase_kit_rejects_when_limit_exhausted(self, client, monkeypatch, tmp_path):
        _mock_display_name_ok(monkeypatch)
        self._mock_kit_catalog(monkeypatch, tmp_path)
        self._seed_player_kits(USER_STEAM, {"starter": {"Amount": 0}})
        _login(client, USER_STEAM)
        r = client.post(
            "/api/player/purchase",
            json={"item_id": "starter", "item_type": "kit", "amount": 1},
        )
        assert r.status_code == 403
        d = r.get_json()
        assert d["ok"] is False
        assert d.get("kit_limit_reached") is True
        assert "starter" in d["error"].lower() or "Limite" in d["error"] or "resgates" in d["error"].lower()

    def test_purchase_kit_rejects_when_pending_orders_exhaust_limit(self, client, monkeypatch, tmp_path):
        _mock_display_name_ok(monkeypatch)
        self._mock_kit_catalog(monkeypatch, tmp_path)
        self._seed_player_kits(USER_STEAM, {"starter": {"Amount": 1}})
        _create_order_direct(
            steam_id=USER_STEAM,
            item_id="starter",
            item_type="kit",
            status="PENDENTE",
        )
        _login(client, USER_STEAM)
        r = client.post(
            "/api/player/purchase",
            json={"item_id": "starter", "item_type": "kit", "amount": 1},
        )
        assert r.status_code == 403
        assert r.get_json().get("kit_limit_reached") is True

    def test_player_kit_limits_shows_zero_when_exhausted(self, client, monkeypatch, tmp_path):
        _mock_display_name_ok(monkeypatch)
        self._mock_kit_catalog(monkeypatch, tmp_path)
        self._seed_player_kits(USER_STEAM, {"starter": {"Amount": 0}})
        _login(client, USER_STEAM)
        r = client.get("/api/player/kit-limits")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        starter = next(k for k in d["kits"] if k["kit_id"] == "starter")
        assert starter["limit"] == 3
        assert starter["remaining"] == 0
        assert starter["effective_remaining"] == 0

    def test_player_kit_limits_error_returns_partial_not_empty_success(self, client, monkeypatch, tmp_path):
        """Fail-open não deve marcar limites prontos quando a API falha (kits=[])."""
        _mock_display_name_ok(monkeypatch)
        self._mock_kit_catalog(monkeypatch, tmp_path)
        _login(client, USER_STEAM)
        monkeypatch.setattr(
            _app_module,
            "_build_player_kit_limits",
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("db timeout sim")),
        )
        r = client.get("/api/player/kit-limits")
        d = r.get_json()
        assert r.status_code == 503
        assert d.get("ok") is False
        assert d.get("partial") is True
        assert d.get("partial_reason") == "error"
        assert d.get("kits") == []

    def test_pending_kit_counts_survive_many_other_orders(self, tmp_path, monkeypatch):
        """GROUP BY não perde pendentes do kit alvo quando há milhares de outros pedidos."""
        catalog = tmp_path / "shop.json"
        kits = {
            "target_kit": {"Description": "Target", "DefaultAmount": 1, "Price": 0},
            **{
                f"filler_{i}": {"Description": f"F {i}", "DefaultAmount": 0, "Price": 0}
                for i in range(3)
            },
        }
        catalog.write_text(json.dumps({"Kits": kits}), encoding="utf-8")
        monkeypatch.setattr(_app_module, "_load_settings", lambda: {"config_path": str(catalog)})
        _app_module._invalidate_shop_config_cache()

        for i in range(520):
            _create_order_direct(
                steam_id=USER_STEAM,
                item_id=f"filler_{i % 3}",
                item_type="kit",
                status="PENDENTE",
                amount=1,
            )
        _create_order_direct(
            steam_id=USER_STEAM,
            item_id="target_kit",
            item_type="kit",
            status="PENDENTE",
            amount=1,
        )
        self._seed_player_kits(USER_STEAM, {"target_kit": {"Amount": 1}})

        db = _app_module._SessionLocal()
        try:
            counts = _app_module._pending_kit_order_counts(db, USER_STEAM)
            assert counts.get("target_kit") == 1
            limits = _app_module._build_player_kit_limits(db, USER_STEAM)
            target = next(row for row in limits if row["kit_id"] == "target_kit")
            assert target["pending_orders"] == 1
            assert target["effective_remaining"] == 0
        finally:
            _app_module._release_db_session(db)

    def test_purchase_kit_unlimited_when_default_amount_zero(self, client, monkeypatch, tmp_path):
        config = {
            "Kits": {
                "vip_free": {
                    "Price": 0,
                    "DefaultAmount": 0,
                    "Description": "VIP Free",
                    "Items": [{"Blueprint": "/Game/Test/Item", "Quantity": 1}],
                }
            }
        }
        config_path = tmp_path / "shop_config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        monkeypatch.setattr(
            _app_module,
            "_load_settings",
            lambda: {
                "config_path": str(config_path),
                "server_id": "default",
                "delivery_mode": "plugin",
            },
        )
        _app_module._CONFIG_CACHE.clear()
        _mock_display_name_ok(monkeypatch)
        self._seed_player_kits(USER_STEAM, {"vip_free": {"Amount": 0}})
        _login(client, USER_STEAM)
        r = client.post(
            "/api/player/purchase",
            json={"item_id": "vip_free", "item_type": "kit", "amount": 1},
        )
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_admin_revoke_kit_limit_resets_stash(self, client, monkeypatch, tmp_path):
        _mock_display_name_ok(monkeypatch)
        self._mock_kit_catalog(monkeypatch, tmp_path)
        self._seed_player_kits(USER_STEAM, {"starter": {"Amount": 0}})
        _login(client, ADMIN_STEAM)
        r = client.post(
            f"/api/admin/players/{USER_STEAM}/kit-limits/starter/revoke",
            json={"reason": "suporte"},
        )
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        assert d["remaining"] == 3
        assert d["stash"]["starter"]["Amount"] == 3

    def test_player_cancel_free_pending_order_succeeds_without_refund(self, client, monkeypatch, tmp_path):
        _mock_display_name_ok(monkeypatch)
        self._mock_kit_catalog(monkeypatch, tmp_path)
        _seed_player_points(USER_STEAM, 0)
        oid = _create_order_direct(
            steam_id=USER_STEAM,
            item_id="starter",
            item_type="kit",
            status="PENDENTE",
            points_spent=0,
            created_at=_now() - timedelta(hours=25),
        )
        _login(client, USER_STEAM)
        r = client.post(f"/api/player/orders/{oid}/cancel", json={})
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        assert d["status"] == "CANCELADO"
        assert d["refunded"] == 0
        assert d["new_balance"] == 0

    def test_player_cancel_free_limited_kit_restores_effective_availability(self, client, monkeypatch, tmp_path):
        _mock_display_name_ok(monkeypatch)
        self._mock_kit_catalog(monkeypatch, tmp_path)
        self._seed_player_kits(USER_STEAM, {"starter": {"Amount": 1}})
        oid = _create_order_direct(
            steam_id=USER_STEAM,
            item_id="starter",
            item_type="kit",
            status="PENDENTE",
            points_spent=0,
            created_at=_now() - timedelta(hours=25),
        )
        _login(client, USER_STEAM)

        blocked = client.post(
            "/api/player/purchase",
            json={"item_id": "starter", "item_type": "kit", "amount": 1},
        )
        assert blocked.status_code == 403
        assert blocked.get_json().get("kit_limit_reached") is True

        cancel = client.post(f"/api/player/orders/{oid}/cancel", json={})
        assert cancel.status_code == 200
        assert cancel.get_json()["ok"] is True

        retry = client.post(
            "/api/player/purchase",
            json={"item_id": "starter", "item_type": "kit", "amount": 1},
        )
        assert retry.status_code == 200
        assert retry.get_json()["ok"] is True


class TestLicenseRenewalKitReset:
    def _mock_license_kit_catalog(self, monkeypatch, tmp_path):
        config = {
            "Kits": {
                "kit_alfa": {
                    "Price": 0,
                    "DefaultAmount": 1,
                    "Permissions": "Admins,Alfa",
                    "Description": "Kit Alfa",
                    "Items": [{"Blueprint": "/Game/Test/Item", "Quantity": 1}],
                },
                "kit_beta": {
                    "Price": 0,
                    "DefaultAmount": 1,
                    "Permissions": "Admins,Beta",
                    "Description": "Kit Beta",
                    "Items": [{"Blueprint": "/Game/Test/Item", "Quantity": 1}],
                },
            },
            "Items": {
                "licenca_alfa": {
                    "Type": "license",
                    "Price": 0,
                    "LicenseGrant": {"Group": "Alfa", "Days": 30, "Redeemable": True},
                },
            },
        }
        config_path = tmp_path / "shop_config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        monkeypatch.setattr(
            _app_module,
            "_load_settings",
            lambda: {
                "config_path": str(config_path),
                "server_id": "default",
                "delivery_mode": "plugin",
            },
        )
        _app_module._CONFIG_CACHE.clear()

    def _seed_player_kits(self, steam_id: str, stash: dict) -> None:
        from sqlalchemy import text

        db = _app_module._SessionLocal()
        try:
            kits_json = json.dumps(stash, ensure_ascii=False)
            db.execute(
                text(
                    "INSERT INTO players (steam_id, points, kits) VALUES (:sid, 0, :kits) "
                    "ON CONFLICT(steam_id) DO UPDATE SET kits = :kits"
                ),
                {"sid": steam_id, "kits": kits_json},
            )
            db.commit()
        finally:
            db.close()

    def _read_player_kits(self, steam_id: str) -> dict:
        from sqlalchemy import text

        db = _app_module._SessionLocal()
        try:
            row = db.execute(
                text("SELECT kits FROM players WHERE steam_id = :sid"),
                {"sid": steam_id},
            ).fetchone()
            return json.loads(row[0]) if row and row[0] else {}
        finally:
            db.close()

    def _seed_player_license(self, steam_id: str, group: str, days: int = 30) -> None:
        db = _app_module._SessionLocal()
        try:
            _app_module._apply_entitlement_grant_tx(
                db, steam_id, group, days, source="test-seed", notes="test",
            )
            db.commit()
        finally:
            db.close()

    def test_license_grant_resets_dependent_kit_limits(self, monkeypatch, tmp_path):
        self._mock_license_kit_catalog(monkeypatch, tmp_path)
        self._seed_player_kits(USER_STEAM, {"kit_alfa": {"Amount": 0}, "kit_beta": {"Amount": 0}})
        db = _app_module._SessionLocal()
        try:
            _app_module._apply_entitlement_grant_tx(
                db, USER_STEAM, "Alfa", 30, source="renew-test", notes="web:licenca_alfa",
            )
            db.commit()
        finally:
            db.close()

        stash = self._read_player_kits(USER_STEAM)
        assert stash["kit_alfa"]["Amount"] == 1
        assert stash["kit_beta"]["Amount"] == 0

    def test_license_purchase_renewal_restores_kit(self, client, monkeypatch, tmp_path):
        _mock_display_name_ok(monkeypatch)
        self._mock_license_kit_catalog(monkeypatch, tmp_path)
        self._seed_player_license(USER_STEAM, "Alfa")
        self._seed_player_kits(USER_STEAM, {"kit_alfa": {"Amount": 0}})
        _seed_player_points(USER_STEAM, 0)
        _login(client, USER_STEAM)

        blocked = client.post(
            "/api/player/purchase",
            json={"item_id": "kit_alfa", "item_type": "kit", "amount": 1},
        )
        assert blocked.status_code == 403
        assert blocked.get_json().get("kit_limit_reached") is True

        renew = client.post(
            "/api/player/purchase",
            json={"item_id": "licenca_alfa", "item_type": "shop", "amount": 1},
        )
        assert renew.status_code == 200
        body = renew.get_json()
        assert body["ok"] is True
        assert "kit_alfa" in (body.get("kits_reset") or [])

        stash = self._read_player_kits(USER_STEAM)
        assert stash["kit_alfa"]["Amount"] == 1

        retry = client.post(
            "/api/player/purchase",
            json={"item_id": "kit_alfa", "item_type": "kit", "amount": 1},
        )
        assert retry.status_code == 200
        assert retry.get_json()["ok"] is True

    def test_license_renewal_restores_kit_despite_pending_order(
        self, client, monkeypatch, tmp_path,
    ):
        """Pedido PENDENTE antigo não deve bloquear o novo período pós-renovação."""
        _mock_display_name_ok(monkeypatch)
        self._mock_license_kit_catalog(monkeypatch, tmp_path)
        self._seed_player_license(USER_STEAM, "Alfa")
        self._seed_player_kits(USER_STEAM, {"kit_alfa": {"Amount": 0}})
        _create_order_direct(
            steam_id=USER_STEAM,
            item_id="kit_alfa",
            item_type="kit",
            status="PENDENTE",
            points_spent=0,
        )
        _seed_player_points(USER_STEAM, 0)
        _login(client, USER_STEAM)

        renew = client.post(
            "/api/player/purchase",
            json={"item_id": "licenca_alfa", "item_type": "shop", "amount": 1},
        )
        assert renew.status_code == 200
        assert renew.get_json()["ok"] is True

        stash = self._read_player_kits(USER_STEAM)
        # DefaultAmount(1) + 1 pending → effective_remaining = 1
        assert stash["kit_alfa"]["Amount"] == 2

        retry = client.post(
            "/api/player/purchase",
            json={"item_id": "kit_alfa", "item_type": "kit", "amount": 1},
        )
        assert retry.status_code == 200
        assert retry.get_json()["ok"] is True


class TestRegulamento:
    def test_meta_public(self, client):
        r = client.get("/api/regulamento/meta")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        assert d["version"] == "1.0"

    def test_content_public(self, client):
        r = client.get("/api/regulamento/content")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        assert d["html"]

    def test_accept_requires_login(self, client):
        r = client.post("/api/regulamento/accept", json={"version": "1.0"})
        assert r.status_code == 401

    def test_accept_persists(self, client):
        _seed_store_user(USER_STEAM, regulamento_accepted=False)
        _login(client, USER_STEAM)
        r = client.post("/api/regulamento/accept", json={"version": "1.0"})
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        assert d["needs_regulamento_accept"] is False
        me = client.get("/api/auth/me").get_json()
        assert me["needs_regulamento_accept"] is False
        assert me["regulamento_version_accepted"] == "1.0"

    def test_auth_me_flags_pending(self, client):
        _seed_store_user(USER_STEAM, regulamento_accepted=False)
        _login(client, USER_STEAM)
        me = client.get("/api/auth/me").get_json()
        assert me["needs_regulamento_accept"] is True

    def test_guard_blocks_ticket_if_pending(self, client):
        _seed_store_user(USER_STEAM, regulamento_accepted=False)
        _login(client, USER_STEAM)
        r = client.post(
            "/api/tickets",
            json={"category": "geral", "subject": "teste", "body": "mensagem de teste"},
        )
        assert r.status_code == 403
        assert r.get_json()["needs_regulamento_accept"] is True

    def test_ticket_after_accept(self, client):
        _seed_store_user(USER_STEAM, regulamento_accepted=False)
        _login(client, USER_STEAM)
        client.post("/api/regulamento/accept", json={"version": "1.0"})
        r = client.post(
            "/api/tickets",
            json={
                "category": "geral",
                "subject": "teste aceite",
                "body": "mensagem após regulamento",
            },
        )
        assert r.status_code == 201


class TestAdminPlayersSteamBackfill:
    def test_stale_display_name_overwritten_on_login(self, client, monkeypatch):
        """Ciano_STAFF em display_name/market_display_name deve ser substituído pelo nick Steam."""
        _seed_store_user(USER_STEAM, display_name="Ciano_STAFF")
        db = _app_module._SessionLocal()
        try:
            row = db.get(_app_module.StoreUser, USER_STEAM)
            row.steam_persona = "Ciano_STAFF"
            prof = db.get(_app_module.MarketPlayerProfile, USER_STEAM)
            prof.market_display_name = "Ciano_STAFF"
            db.commit()
        finally:
            db.close()
        monkeypatch.setenv("STEAM_API_KEY", "test-key")
        monkeypatch.setattr(
            _app_module,
            "_fetch_steam_persona_names_batch",
            lambda ids, timeout=12.0: {USER_STEAM: "Cyanø"} if USER_STEAM in ids else {},
        )
        _login(client, USER_STEAM)
        _app_module._touch_store_user_login(USER_STEAM)
        d = client.get("/api/auth/me").get_json()
        assert d["steam_persona"] == "Cyanø"
        assert d["display_name"] == "Cyanø"
        db = _app_module._SessionLocal()
        try:
            row = db.get(_app_module.StoreUser, USER_STEAM)
            assert row.steam_persona == "Cyanø"
            assert row.display_name == "Cyanø"
        finally:
            db.close()

    def test_batch_steam_persona_url_preserves_commas(self, monkeypatch):
        monkeypatch.setenv("STEAM_API_KEY", "test-key")
        captured: list[str] = []

        def _fake_urlopen(req, timeout=12):
            captured.append(req.full_url)
            body = json.dumps({
                "response": {
                    "players": [
                        {"steamid": ADMIN_STEAM, "personaname": "AdminNick"},
                        {"steamid": USER_STEAM, "personaname": "UserNick"},
                    ]
                }
            }).encode()
            mock_resp = MagicMock()
            mock_resp.read.return_value = body
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        monkeypatch.setattr(_app_module.urllib.request, "urlopen", _fake_urlopen)
        result = _app_module._fetch_steam_persona_names_batch([ADMIN_STEAM, USER_STEAM])
        assert result == {ADMIN_STEAM: "AdminNick", USER_STEAM: "UserNick"}
        assert captured
        assert f"steamids={ADMIN_STEAM},{USER_STEAM}" in captured[0]
        assert "%2C" not in captured[0]

    def test_list_players_uses_cached_persona_without_api(self, client, monkeypatch):
        _seed_store_user(USER_STEAM, display_name="Ciano_STAFF")
        db = _app_module._SessionLocal()
        try:
            row = db.get(_app_module.StoreUser, USER_STEAM)
            row.steam_persona = "Ciano_STAFF"
            db.commit()
        finally:
            db.close()
        _login(client, ADMIN_STEAM)
        monkeypatch.setenv("STEAM_API_KEY", "test-key")
        calls: list[list[str]] = []

        def _fake_fetch(ids, timeout=12.0):
            calls.append(list(ids))
            return {USER_STEAM: "Cyanø"} if USER_STEAM in ids else {}

        monkeypatch.setattr(_app_module, "_fetch_steam_persona_names_batch", _fake_fetch)
        d = client.get("/api/admin/players").get_json()
        row = next(p for p in d["items"] if p["steam_id"] == USER_STEAM)
        assert row["steam_persona"] == "Ciano_STAFF"
        assert row["display_name"] == "Ciano_STAFF"
        assert calls == []
        assert d.get("steam_persona_warning") in (None, "")

    def test_list_players_uses_cached_persona_without_sync(self, client, monkeypatch):
        """Lista NÃO chama Steam no request — só cache; backfill é background."""
        _seed_store_user(USER_STEAM, display_name=USER_STEAM, steam_persona="")
        _login(client, ADMIN_STEAM)
        monkeypatch.setenv("STEAM_API_KEY", "test-key")
        sync_calls: list[list[str]] = []
        scheduled: list[list[str]] = []

        def _fake_fetch(ids, timeout=12.0):
            sync_calls.append(list(ids))
            return {USER_STEAM: "SteamNickBR"} if USER_STEAM in ids else {}

        monkeypatch.setattr(_app_module, "_fetch_steam_persona_names_batch", _fake_fetch)
        monkeypatch.setattr(
            _app_module,
            "_schedule_steam_persona_backfill",
            lambda ids: scheduled.append(list(ids)),
        )
        d = client.get("/api/admin/players").get_json()
        row = next(p for p in d["items"] if p["steam_id"] == USER_STEAM)
        assert row["display_name"] == USER_STEAM
        assert sync_calls == []
        assert scheduled and USER_STEAM in scheduled[0]
        assert d.get("timing") is not None

    def test_list_players_slow_steam_does_not_block(self, client, monkeypatch):
        """Steam lento (15s+) não pode estourar o timeout do frontend na lista."""
        _seed_store_user(USER_STEAM, display_name=USER_STEAM, steam_persona="")
        _login(client, ADMIN_STEAM)
        monkeypatch.setenv("STEAM_API_KEY", "test-key")

        def _slow_fetch(ids, timeout=12.0):
            time.sleep(20)
            return {USER_STEAM: "TooLate"} if USER_STEAM in ids else {}

        monkeypatch.setattr(_app_module, "_fetch_steam_persona_names_batch", _slow_fetch)
        # Não agenda bg real — só prova que o path HTTP não chama fetch.
        monkeypatch.setattr(_app_module, "_schedule_steam_persona_backfill", lambda _ids: None)
        t0 = time.perf_counter()
        d = client.get("/api/admin/players").get_json()
        elapsed = time.perf_counter() - t0
        assert d["ok"] is True
        assert elapsed < 5.0
        row = next(p for p in d["items"] if p["steam_id"] == USER_STEAM)
        assert row["display_name"] == USER_STEAM

    def test_list_players_without_steam_api_keeps_steamid(self, client, monkeypatch):
        _seed_store_user(USER_STEAM, display_name=USER_STEAM, steam_persona="")
        _login(client, ADMIN_STEAM)
        monkeypatch.delenv("STEAM_API_KEY", raising=False)
        d = client.get("/api/admin/players").get_json()
        row = next(p for p in d["items"] if p["steam_id"] == USER_STEAM)
        assert row["display_name"] == USER_STEAM
        assert d.get("steam_api_configured") is False
        assert d.get("steam_persona_warning")

    def test_list_players_missing_persona_no_sync_warning_when_api_configured(self, client, monkeypatch):
        """Com API key, lista não espera fetch — sem warning de falha síncrona."""
        _seed_store_user(USER_STEAM, display_name=USER_STEAM, steam_persona="")
        _login(client, ADMIN_STEAM)
        monkeypatch.setenv("STEAM_API_KEY", "test-key")
        monkeypatch.setattr(_app_module, "_schedule_steam_persona_backfill", lambda _ids: None)
        d = client.get("/api/admin/players").get_json()
        assert d.get("steam_api_configured") is True
        assert d.get("steam_persona_warning") in (None, "")
        row = next(p for p in d["items"] if p["steam_id"] == USER_STEAM)
        assert row["display_name"] == USER_STEAM

    def test_refresh_steam_personas_returns_fetched_when_persist_fails(self, monkeypatch):
        monkeypatch.setenv("STEAM_API_KEY", "test-key")
        monkeypatch.setattr(
            _app_module,
            "_fetch_steam_persona_names_batch",
            lambda ids, timeout=12.0: {USER_STEAM: "NickBR"} if USER_STEAM in ids else {},
        )

        def _boom(_db, _m):
            raise RuntimeError("db down")

        monkeypatch.setattr(_app_module, "_persist_steam_personas", _boom)
        result = _app_module._refresh_steam_personas(None, [USER_STEAM])
        assert result == {USER_STEAM: "NickBR"}

    def test_admin_list_persona_uses_db_cache_normalized_id(self, client, monkeypatch):
        _seed_store_user(USER_STEAM, display_name=USER_STEAM, steam_persona="NickCached")
        _login(client, ADMIN_STEAM)
        monkeypatch.setenv("STEAM_API_KEY", "test-key")
        calls: list[list[str]] = []
        monkeypatch.setattr(
            _app_module,
            "_fetch_steam_persona_names_batch",
            lambda ids, timeout=12.0: calls.append(list(ids)) or {},
        )
        d = client.get("/api/admin/players").get_json()
        row = next(p for p in d["items"] if USER_STEAM in str(p["steam_id"]))
        assert row["display_name"] == "NickCached"
        assert row["steam_persona"] == "NickCached"
        assert calls == []

    def test_player_detail_uses_cached_persona_without_api(self, client, monkeypatch):
        _seed_store_user(USER_STEAM, display_name="Ciano_STAFF", steam_persona="Ciano_STAFF")
        _login(client, ADMIN_STEAM)
        monkeypatch.setenv("STEAM_API_KEY", "test-key")
        calls: list[list[str]] = []

        def _fake_fetch(ids, timeout=12.0):
            calls.append(list(ids))
            return {}

        monkeypatch.setattr(_app_module, "_fetch_steam_persona_names_batch", _fake_fetch)
        r = client.get(f"/api/admin/players/{USER_STEAM}")
        d = r.get_json()
        assert r.status_code == 200
        assert d["ok"] is True
        assert d["player"]["steam_persona"] == "Ciano_STAFF"
        assert d["player"]["display_name"] == "Ciano_STAFF"
        assert calls == []

    def test_player_detail_skips_steam_api_even_when_persona_missing(self, client, monkeypatch):
        """Detalhe nunca chama Steam — timeout 15s do frontend vs API lenta era a falha."""
        _seed_store_user(USER_STEAM, display_name=USER_STEAM, steam_persona="")
        _login(client, ADMIN_STEAM)
        monkeypatch.setenv("STEAM_API_KEY", "test-key")
        calls: list[list[str]] = []

        def _fake_fetch(ids, timeout=12.0):
            calls.append(list(ids))
            return {USER_STEAM: "SteamNickBR"}

        monkeypatch.setattr(_app_module, "_fetch_steam_persona_names_batch", _fake_fetch)
        d = client.get(f"/api/admin/players/{USER_STEAM}").get_json()
        assert d["ok"] is True
        assert calls == []
        assert d["player"]["steam_persona"] is None
        assert d["player"]["display_name"] == USER_STEAM

    def test_player_detail_survives_steam_fetch_failure(self, client, monkeypatch):
        _seed_store_user(USER_STEAM, display_name=USER_STEAM, steam_persona="")
        _login(client, ADMIN_STEAM)
        monkeypatch.setenv("STEAM_API_KEY", "test-key")
        monkeypatch.setattr(
            _app_module,
            "_fetch_steam_persona_names_batch",
            lambda _ids, timeout=12.0: (_ for _ in ()).throw(RuntimeError("steam down")),
        )
        r = client.get(f"/api/admin/players/{USER_STEAM}")
        d = r.get_json()
        assert r.status_code == 200
        assert d["ok"] is True
        assert d["player"]["steam_persona"] is None
        assert d["player"]["display_name"] == USER_STEAM

    def test_player_detail_essential_defers_heavy_sections(self, client, monkeypatch):
        """Essencial devolve o cartão barato + entitlements; pedidos/doações/kits/
        listings ficam para o /heavy (partial_reason='deferred')."""
        _seed_store_user(USER_STEAM, display_name="Rapido", steam_persona="Rapido")
        _login(client, ADMIN_STEAM)
        d = client.get(f"/api/admin/players/{USER_STEAM}").get_json()
        assert d["ok"] is True
        assert d.get("partial") is True
        assert d.get("partial_reason") == "deferred"
        assert d["player"]["steam_persona"] == "Rapido"
        # Secções pesadas vazias/adiadas no essencial.
        assert d["recent_orders"] == []
        assert d["recent_donations"] == []
        assert d["player"]["kit_limits"] == []
        assert d["player"]["listings_count"] is None
        assert set(d["partial_sections"]) == {
            "recent_orders",
            "recent_donations",
            "kit_limits",
            "listings_count",
        }

    def test_player_detail_essential_skips_big_tables(self, client, monkeypatch):
        """O essencial NUNCA varre orders/point_payments/market_listings — mesmo que
        essas queries falhem, o cartão do jogador pesado carrega <8s."""
        _seed_store_user(USER_STEAM, display_name="Pesado", steam_persona="Pesado")
        _login(client, ADMIN_STEAM)

        def _boom(*_a, **_k):
            raise AssertionError("essencial não pode tocar a tabela grande")

        monkeypatch.setattr(_app_module, "_build_player_kit_limits", _boom)
        t0 = time.perf_counter()
        d = client.get(f"/api/admin/players/{USER_STEAM}").get_json()
        assert time.perf_counter() - t0 < 8.0
        assert d["ok"] is True
        assert d["player"]["steam_persona"] == "Pesado"

    def test_player_detail_budget_returns_partial_when_slow(self, client, monkeypatch):
        """Detalhe lento além do budget → resposta parcial rápida, nunca 15s."""
        _seed_store_user(USER_STEAM, display_name="Lento", steam_persona="Lento")
        _login(client, ADMIN_STEAM)
        monkeypatch.setattr(_app_module, "_ADMIN_DETAIL_BUDGET_MS", 150)

        def _slow_detail(_sid, cancel=None):
            # Simula queries lentas; respeita cancel do budget para libertar o slot.
            for _ in range(30):
                if cancel is not None and cancel.is_set():
                    return {"ok": False, "error": "cancelled", "cancelled": True}
                time.sleep(0.1)
            return {"ok": True, "player": {"steam_id": _sid}, "recent_orders": []}

        monkeypatch.setattr(_app_module, "_get_admin_player_detail", _slow_detail)
        monkeypatch.setattr(
            _app_module,
            "_get_player_entitlements",
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("should not run")),
        )
        t0 = time.perf_counter()
        r = client.get(f"/api/admin/players/{USER_STEAM}")
        elapsed = time.perf_counter() - t0
        d = r.get_json()
        assert r.status_code == 200
        assert d["ok"] is True
        assert d.get("partial") is True
        assert elapsed < 3.0  # respondeu pelo path parcial, não esperou o lento
        # Campos essenciais presentes mesmo em modo parcial.
        assert d["player"]["steam_id"] == USER_STEAM
        assert d["player"]["steam_persona"] == "Lento"
        assert "license_catalog" in d

    def test_player_detail_missing_indexes_still_serves_essential(self, client, monkeypatch):
        """Índices ainda a criar NÃO degradam o essencial (ele já não toca as tabelas
        grandes): agenda o self-heal para o /heavy e devolve o cartão na hora."""
        _seed_store_user(USER_STEAM, display_name="DDL", steam_persona="DDL")
        _login(client, ADMIN_STEAM)
        monkeypatch.setattr(_app_module, "_HOT_PATH_INDEXES_READY", False)
        starts: list[str] = []
        monkeypatch.setattr(
            _app_module,
            "_hot_path_indexes_ready_or_schedule",
            lambda reason: starts.append(reason) or False,
        )

        t0 = time.perf_counter()
        d = client.get(f"/api/admin/players/{USER_STEAM}").get_json()
        assert time.perf_counter() - t0 < 8.0
        assert d["ok"] is True
        assert d["partial"] is True
        assert d["partial_reason"] == "deferred"
        # Cartão essencial servido mesmo com índices em falta.
        assert d["player"]["steam_persona"] == "DDL"
        # Self-heal agendado para o caminho pesado.
        assert starts == ["admin_player_detail"]

    def test_player_detail_heavy_endpoint_completes_sections(self, client):
        _seed_store_user(USER_STEAM, display_name="Heavy", steam_persona="Heavy")
        _create_order_direct(
            steam_id=USER_STEAM,
            item_id="kit_alpha",
            item_type="kit",
            status="PENDENTE",
            points_spent=25,
        )
        _create_donation_direct(steam_id=USER_STEAM, points=500)
        _login(client, ADMIN_STEAM)

        d = client.get(f"/api/admin/players/{USER_STEAM}/heavy").get_json()
        assert d["ok"] is True
        assert d.get("partial") is False
        assert d["recent_orders"][0]["item_id"] == "kit_alpha"
        assert d["recent_donations"][0]["points"] == 500

    def test_player_detail_budget_disabled_runs_inline(self, client, monkeypatch):
        """Budget<=0 corre o essencial direto (sem thread); ainda adia as secções
        pesadas para o /heavy (partial_reason='deferred')."""
        _seed_store_user(USER_STEAM, display_name="Inline", steam_persona="Inline")
        _login(client, ADMIN_STEAM)
        monkeypatch.setattr(_app_module, "_ADMIN_DETAIL_BUDGET_MS", 0)
        d = client.get(f"/api/admin/players/{USER_STEAM}").get_json()
        assert d["ok"] is True
        assert d.get("partial") is True
        assert d.get("partial_reason") == "deferred"
        assert d["player"]["steam_persona"] == "Inline"

    def test_auth_me_uses_cached_persona_without_steam_api(self, client, monkeypatch):
        _seed_store_user(USER_STEAM, display_name="CachedNick", steam_persona="CachedNick")
        _login(client, USER_STEAM)
        monkeypatch.setenv("STEAM_API_KEY", "test-key")
        calls: list[list[str]] = []

        def _fake_fetch(ids, timeout=12.0):
            calls.append(list(ids))
            return {}

        monkeypatch.setattr(_app_module, "_fetch_steam_persona_names_batch", _fake_fetch)
        d = client.get("/api/auth/me").get_json()
        assert d["authenticated"] is True
        assert d["steam_persona"] == "CachedNick"
        assert calls == []

    def test_catalog_license_options_cached_across_calls(self, tmp_path, monkeypatch):
        catalog = tmp_path / "shop.json"
        catalog.write_text(
            json.dumps({
                "Items": {
                    "licenca_gamma": {
                        "Type": "license",
                        "Description": "Gamma",
                        "LicenseGrant": {"Group": "Gamma", "Days": 30},
                    },
                },
                "Kits": {"kit_a": {"Description": "Kit A", "Price": 10}},
            }),
            encoding="utf-8",
        )
        monkeypatch.setattr(_app_module, "_load_settings", lambda: {"config_path": str(catalog)})
        monkeypatch.setattr(_app_module, "_collect_catalog_search_paths", lambda: [catalog])
        _app_module._invalidate_shop_config_cache()
        loads: list[str] = []
        real_load = _app_module.load_plugin_config

        def _counting_load(path):
            loads.append(str(path))
            return real_load(path)

        monkeypatch.setattr(_app_module, "load_plugin_config", _counting_load)
        first = _app_module._catalog_license_options()
        second = _app_module._catalog_license_options()
        kits_a = _app_module._catalog_kit_options()
        kits_b = _app_module._catalog_kit_options()
        assert first == second
        assert kits_a == kits_b
        assert any(e["group"] == "Gamma" for e in first)
        # 2ª chamada de license + kit options não reparseia candidatos.
        assert len(loads) <= 1

    def test_build_player_kit_limits_uses_single_pending_query(self, tmp_path, monkeypatch):
        """~40 kits com DefaultAmount não podem disparar N×SELECT em orders."""
        catalog = tmp_path / "shop.json"
        kits = {
            f"kit_{i}": {"Description": f"Kit {i}", "DefaultAmount": 1, "Price": 0}
            for i in range(12)
        }
        catalog.write_text(json.dumps({"Kits": kits}), encoding="utf-8")
        monkeypatch.setattr(_app_module, "_load_settings", lambda: {"config_path": str(catalog)})
        _app_module._invalidate_shop_config_cache()

        for i in range(3):
            _create_order_direct(
                steam_id=USER_STEAM,
                item_id=f"kit_{i}",
                item_type="kit",
                status="PENDENTE",
                amount=1,
            )

        db = _app_module._SessionLocal()
        try:
            real_execute = db.execute
            pending_selects = []

            def _counting_execute(stmt, *args, **kwargs):
                sql = str(getattr(stmt, "text", stmt) or stmt)
                if "item_type = 'kit'" in sql and "PENDENTE" in sql:
                    pending_selects.append(sql)
                    assert "GROUP BY item_id" in sql
                return real_execute(stmt, *args, **kwargs)

            db.execute = _counting_execute  # type: ignore[method-assign]
            limits = _app_module._build_player_kit_limits(db, USER_STEAM)
            assert len(limits) == 12
            assert len(pending_selects) == 1
            by_id = {row["kit_id"]: row for row in limits}
            assert by_id["kit_0"]["pending_orders"] == 1
            assert by_id["kit_5"]["pending_orders"] == 0
        finally:
            _app_module._release_db_session(db)

    def test_store_bootstrap_uses_single_session_no_ddl(self, client, monkeypatch, tmp_path):
        """Bootstrap autenticado: entitlements sem DDL; timing + kit_limits presentes."""
        catalog = tmp_path / "shop.json"
        catalog.write_text(
            json.dumps({
                "Kits": {
                    "starter": {"Description": "Starter", "DefaultAmount": 1, "Price": 0},
                },
                "Items": {},
            }),
            encoding="utf-8",
        )
        monkeypatch.setattr(_app_module, "_load_settings", lambda: {"config_path": str(catalog)})
        _app_module._invalidate_shop_config_cache()
        _seed_store_user(USER_STEAM, display_name="Boot", steam_persona="Boot")
        _login(client, USER_STEAM)

        ensure_calls: list[str] = []

        def _no_ddl(conn):
            ensure_calls.append("ddl")

        monkeypatch.setattr(_app_module, "_ensure_entitlements_schema", _no_ddl)
        _app_module._ENTITLEMENTS_SCHEMA_READY = True

        t0 = time.perf_counter()
        r = client.get("/api/store/bootstrap")
        elapsed = time.perf_counter() - t0
        d = r.get_json()
        assert r.status_code == 200
        assert d["ok"] is True
        assert d["me"]["authenticated"] is True
        assert isinstance(d.get("kit_limits"), list)
        assert "timing" in d
        assert ensure_calls == []
        assert elapsed < 3.0

    def test_entitlements_hot_path_queries_when_table_exists(self, monkeypatch):
        """Migrate async: flag False mas tabela existente → bootstrap NÃO devolve []."""
        _app_module._ENTITLEMENTS_SCHEMA_READY = False
        _app_module._clear_table_exists_cache()
        db = _app_module._SessionLocal()
        try:
            db.execute(
                _app_module.text(
                    "INSERT OR IGNORE INTO player_entitlements "
                    "(steam_id, group_name, expires, source) "
                    "VALUES (:sid, :grp, NULL, 'test')"
                ),
                {"sid": USER_STEAM, "grp": "Delta"},
            )
            db.commit()
            ents = _app_module._get_player_entitlements(
                USER_STEAM, db=db, allow_ddl=False,
            )
            assert any(e["group"] == "Delta" for e in ents)
            assert _app_module._ENTITLEMENTS_SCHEMA_READY is True
        finally:
            _app_module._release_db_session(db)

    def test_player_kit_limits_db_error_returns_503(self, client, monkeypatch):
        _login(client, USER_STEAM)
        monkeypatch.setattr(
            _app_module,
            "_build_player_kit_limits",
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("db timeout")),
        )
        r = client.get("/api/player/kit-limits")
        d = r.get_json()
        assert r.status_code == 503
        assert d["ok"] is False
        assert d["partial_reason"] == "error"
        assert d["kits"] == []

    def test_bootstrap_auth_me_reuses_shared_db_for_admin_check(self, client, monkeypatch):
        """Bootstrap com sessão partilhada não deve abrir 2.º checkout para ShopAdmin."""
        _seed_store_user(USER_STEAM, display_name="AdminBoot", steam_persona="AdminBoot")
        _login(client, USER_STEAM)
        db = _app_module._SessionLocal()
        try:
            db.merge(_app_module.ShopAdmin(steam_id=USER_STEAM))
            db.commit()
        finally:
            _app_module._release_db_session(db)

        merge_calls: list[float] = []

        def _no_extra_merge(*_a, **kwargs):
            merge_calls.append(kwargs.get("timeout", -1))
            return set()

        monkeypatch.setattr(_app_module, "_merge_admin_steamids_from_db", _no_extra_merge)
        monkeypatch.setattr(_app_module, "_ENTITLEMENTS_SCHEMA_READY", True)
        d = client.get("/api/store/bootstrap").get_json()
        assert d["ok"] is True
        assert d["me"]["is_admin"] is True
        assert merge_calls == []

    def test_build_player_kit_limits_accepts_preloaded_config(self, tmp_path, monkeypatch):
        """shop_config evita _read_shop_config enquanto a sessão DB está aberta."""
        catalog = tmp_path / "shop.json"
        catalog.write_text(
            json.dumps({
                "Kits": {
                    "starter": {"Description": "Starter", "DefaultAmount": 1, "Price": 0},
                },
            }),
            encoding="utf-8",
        )
        preloaded = json.loads(catalog.read_text(encoding="utf-8"))
        read_during_session: list[str] = []

        def _boom_read():
            read_during_session.append("read")
            raise AssertionError("catálogo não deve ser relido com shop_config")

        monkeypatch.setattr(_app_module, "_read_shop_config", _boom_read)
        db = _app_module._SessionLocal()
        try:
            limits = _app_module._build_player_kit_limits(
                db, USER_STEAM, shop_config=preloaded,
            )
            assert len(limits) == 1
            assert limits[0]["kit_id"] == "starter"
            assert read_during_session == []
        finally:
            _app_module._release_db_session(db)

    def test_ensure_store_users_schema_skips_after_ready(self, monkeypatch):
        """Lista admin não deve repetir SHOW COLUMNS / PRAGMA em cada request."""
        engine = _app_module._ENGINE
        assert engine is not None
        _app_module._STORE_USERS_SCHEMA_READY = False
        _app_module._ensure_store_users_schema(engine)
        assert _app_module._STORE_USERS_SCHEMA_READY is True
        calls = {"n": 0}
        real_connect = engine.connect

        def _counting_connect(*args, **kwargs):
            calls["n"] += 1
            return real_connect(*args, **kwargs)

        monkeypatch.setattr(engine, "connect", _counting_connect)
        _app_module._ensure_store_users_schema(engine)
        _app_module._ensure_store_users_schema(engine)
        assert calls["n"] == 0

    def test_db_table_exists_caches_positive(self, monkeypatch):
        engine = _app_module._ENGINE
        assert engine is not None
        _app_module._clear_table_exists_cache()
        assert _app_module._db_table_exists(engine, "store_users") is True
        inspect_calls = {"n": 0}
        import sqlalchemy as sa

        real_inspect = sa.inspect

        def _counting_inspect(bind):
            inspect_calls["n"] += 1
            return real_inspect(bind)

        monkeypatch.setattr(sa, "inspect", _counting_inspect)
        # Re-import path uses sqlalchemy.inspect inside function — patch where used.
        monkeypatch.setattr(
            "sqlalchemy.inspect",
            _counting_inspect,
        )
        assert _app_module._db_table_exists(engine, "store_users") is True
        assert inspect_calls["n"] == 0

    def test_ensure_hot_path_indexes_idempotent(self):
        engine = _app_module._ENGINE
        assert engine is not None
        _app_module._HOT_PATH_INDEXES_READY = False
        _app_module._ensure_hot_path_indexes(engine)
        assert _app_module._HOT_PATH_INDEXES_READY is True
        _app_module._ensure_hot_path_indexes(engine)
        assert _app_module._HOT_PATH_INDEXES_READY is True

    def test_ensure_hot_path_indexes_ready_only_when_all_present(self, monkeypatch):
        """P0: falha no CREATE NÃO marca READY — senão nunca re-tenta e detalhe full-scan."""
        engine = _app_module._ENGINE
        assert engine is not None
        _app_module._HOT_PATH_INDEXES_READY = False

        def _fail_all_present(*_a, **_k):
            return False

        monkeypatch.setattr(_app_module, "_hot_path_indexes_all_present", _fail_all_present)
        _app_module._ensure_hot_path_indexes(engine)
        assert _app_module._HOT_PATH_INDEXES_READY is False
        # Self-heal no detalhe: agenda DDL async e não bloqueia request.
        starts: list[str] = []
        monkeypatch.setattr(
            _app_module,
            "_start_hot_path_indexes_self_heal",
            lambda _eng, reason="": starts.append(reason) or False,
        )
        d = _app_module._get_admin_player_detail_budgeted(USER_STEAM)
        assert d["partial"] is True
        assert starts == ["admin_player_detail"]
        assert _app_module._HOT_PATH_INDEXES_READY is False

    def test_ddl_engine_omits_short_read_timeout(self, monkeypatch):
        """DDL MySQL não herda read_timeout=12s do pool HTTP; usa password real."""
        captured: dict[str, Any] = {}

        def _fake_create_engine(url, **kwargs):
            captured["url"] = (
                url.render_as_string(hide_password=False)
                if hasattr(url, "render_as_string")
                else str(url)
            )
            captured["raw_url"] = url
            captured["connect_args"] = dict(kwargs.get("connect_args") or {})
            return _app_module._ENGINE

        monkeypatch.setattr(_app_module, "create_engine", _fake_create_engine)
        monkeypatch.setattr(
            _app_module,
            "_ACTIVE_DATABASE_URL",
            "mysql+pymysql://arkland:s3%40cr%2Fet@127.0.0.1:3306/arkland_shop?charset=utf8mb4",
        )

        class _FakeEng:
            url = "mysql+pymysql://arkland:***@127.0.0.1:3306/arkland_shop"

        out = _app_module._ddl_engine_for(_FakeEng())
        assert out is _app_module._ENGINE
        assert "read_timeout" not in captured["connect_args"]
        assert "write_timeout" not in captured["connect_args"]
        assert "127.0.0.1" in captured["url"]
        assert "s3%40cr%2Fet" in captured["url"]
        assert "***" not in captured["url"].split("@", 1)[0]

    def test_ddl_engine_uses_render_not_masked_str(self, monkeypatch):
        """P0: str(engine.url) mascara password → 1045; render_as_string(False) corrige."""
        from sqlalchemy.engine import make_url

        captured: list[str] = []

        def _fake_create_engine(url, **kwargs):
            captured.append(
                url.render_as_string(hide_password=False)
                if hasattr(url, "render_as_string")
                else str(url)
            )
            return object()

        monkeypatch.setattr(_app_module, "create_engine", _fake_create_engine)
        monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
        monkeypatch.setattr(_app_module, "_DB_CONNECT_ARGS", {})

        class _FakeEng:
            url = make_url("mysql+pymysql://arkland:p%40ss%2Fw%3Ard@127.0.0.1:3306/shop?charset=utf8mb4")

        _app_module._ddl_engine_for(_FakeEng())
        assert captured
        assert "p%40ss%2Fw%3Ard" in captured[0]
        assert "127.0.0.1" in captured[0]
        assert "***" not in captured[0].split("@", 1)[0]

    def test_hot_path_indexes_backoff_on_auth_failure(self, monkeypatch):
        """Falha 1045 não spamma retry — agenda backoff."""
        engine = _app_module._ENGINE
        assert engine is not None
        _app_module._HOT_PATH_INDEXES_READY = False
        _app_module._HOT_PATH_INDEXES_FAIL_STREAK = 0
        _app_module._HOT_PATH_INDEXES_NEXT_TRY_AT = 0.0
        _app_module._HOT_PATH_INDEXES_LAST_ERROR = ""

        class _Boom:
            def connect(self):
                raise Exception(
                    '(pymysql.err.OperationalError) (1045, "Access denied for user '
                    "'arkland'@'localhost' (using password: YES)\")"
                )

        monkeypatch.setattr(_app_module, "_ddl_engine_for", lambda _e: _Boom())
        _app_module._ensure_hot_path_indexes(engine)
        assert _app_module._HOT_PATH_INDEXES_READY is False
        assert _app_module._HOT_PATH_INDEXES_FAIL_STREAK >= 1
        assert _app_module._HOT_PATH_INDEXES_NEXT_TRY_AT >= time.time() + 250
        # Segunda chamada imediata não re-tenta
        before = _app_module._HOT_PATH_INDEXES_FAIL_STREAK
        _app_module._ensure_hot_path_indexes(engine)
        assert _app_module._HOT_PATH_INDEXES_FAIL_STREAK == before

    def test_list_admin_players_count_skips_joins_without_q(self, monkeypatch):
        _seed_store_user(USER_STEAM, display_name="CountJoin")
        executes: list[str] = []
        orig_factory = _app_module._SessionLocal

        def _factory():
            inner = orig_factory()
            real_execute = inner.execute

            def _cap(stmt, *a, **k):
                sql = str(getattr(stmt, "text", stmt) or stmt)
                executes.append(sql)
                return real_execute(stmt, *a, **k)

            inner.execute = _cap  # type: ignore[method-assign]
            return inner

        # Preserva scoped_session.remove() para o teardown de fresh_db.
        _factory.remove = getattr(orig_factory, "remove", lambda: None)  # type: ignore[attr-defined]
        monkeypatch.setattr(_app_module, "_SessionLocal", _factory)
        d = _app_module._list_admin_players(q="", sort="last_login", limit=5)
        assert d["ok"] is True
        count_sqls = [s for s in executes if "COUNT(*)" in s.upper()]
        assert count_sqls, "esperava COUNT(*) na listagem"
        for sql in count_sqls:
            assert "JOIN players" not in sql
            assert "market_player_profile" not in sql

