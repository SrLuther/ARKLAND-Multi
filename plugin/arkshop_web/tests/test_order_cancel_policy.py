"""Regras de desistência: licenças irrevogáveis, cooldown 24h, auto-cancel 48h."""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")
os.environ.setdefault("ARKSHOP_RETRY_INTERVAL", "9999")
os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")

import app as _app_module
from app import app, _configure_database, _now, expire_stale_pending_orders

ADMIN_STEAM = "76561198000000001"
USER_STEAM = "76561198000000002"
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
    monkeypatch.setattr(_app_module, "_start_scheduler", lambda: None)

    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]))

    db_path = str(tmp_path / "cancel_policy_test.db")
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


def _mock_shop_catalog(monkeypatch, tmp_path):
    config = {
        "Items": {
            "sword": {"Type": "item", "Price": 100, "Description": "Espada"},
            "licenca_alfa": {
                "Type": "license",
                "Price": 5000,
                "Description": "Licença Alfa",
                "LicenseGrant": {"Days": 30, "Group": "Alfa", "Redeemable": True},
                "Category": "Licenças",
            },
        },
        "Kits": {},
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


def _create_order(*, item_id="sword", item_type="shop", status="PENDENTE", points_spent=100, created_at=None):
    db = _app_module._SessionLocal()
    try:
        ts = created_at or _now()
        o = _app_module.Order(
            order_id=str(uuid.uuid4()),
            steam_id=USER_STEAM,
            server_id="default",
            item_type=item_type,
            item_id=item_id,
            amount=1,
            points_spent=points_spent,
            status=status,
            created_at=ts,
            updated_at=ts,
        )
        db.add(o)
        db.commit()
        return o.order_id
    finally:
        db.close()


def _order_status(order_id: str) -> str:
    db = _app_module._SessionLocal()
    try:
        row = db.query(_app_module.Order).filter(_app_module.Order.order_id == order_id).first()
        return row.status
    finally:
        db.close()


def _player_points(steam_id: str) -> int:
    from sqlalchemy import text

    db = _app_module._SessionLocal()
    try:
        row = db.execute(
            text("SELECT points FROM players WHERE steam_id = :sid"),
            {"sid": steam_id},
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        db.close()


class TestPlayerCancelPolicy:
    def test_blocks_license_cancel(self, client, monkeypatch, tmp_path):
        _mock_display_name_ok(monkeypatch)
        _mock_shop_catalog(monkeypatch, tmp_path)
        _seed_player_points(USER_STEAM, 0)
        oid = _create_order(
            item_id="licenca_alfa",
            points_spent=5000,
            created_at=_now() - timedelta(hours=50),
        )
        _login(client, USER_STEAM)
        r = client.post(f"/api/player/orders/{oid}/cancel", json={})
        assert r.status_code == 403
        d = r.get_json()
        assert d["ok"] is False
        assert d["code"] == "license_irrevocable"
        assert _order_status(oid) == "PENDENTE"

    def test_blocks_cancel_within_24h(self, client, monkeypatch, tmp_path):
        _mock_display_name_ok(monkeypatch)
        _mock_shop_catalog(monkeypatch, tmp_path)
        _seed_player_points(USER_STEAM, 0)
        oid = _create_order(created_at=_now() - timedelta(hours=2))
        _login(client, USER_STEAM)
        r = client.post(f"/api/player/orders/{oid}/cancel", json={})
        assert r.status_code == 403
        d = r.get_json()
        assert d["ok"] is False
        assert d["code"] == "cooldown_24h"
        assert "24" in d["error"]
        assert _order_status(oid) == "PENDENTE"

    def test_allows_cancel_after_24h_with_refund(self, client, monkeypatch, tmp_path):
        _mock_display_name_ok(monkeypatch)
        _mock_shop_catalog(monkeypatch, tmp_path)
        _seed_player_points(USER_STEAM, 50)
        oid = _create_order(points_spent=100, created_at=_now() - timedelta(hours=25))
        _login(client, USER_STEAM)
        r = client.post(f"/api/player/orders/{oid}/cancel", json={})
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        assert d["refunded"] == 80
        assert d["paid_amount"] == 100
        assert d["refund_factor"] == 0.8
        assert d["new_balance"] == 130
        assert _order_status(oid) == "CANCELADO"

    def test_available_flags_can_cancel(self, client, monkeypatch, tmp_path):
        _mock_display_name_ok(monkeypatch)
        _mock_shop_catalog(monkeypatch, tmp_path)
        fresh = _create_order(item_id="sword", created_at=_now() - timedelta(hours=1))
        aged = _create_order(item_id="sword", created_at=_now() - timedelta(hours=30))
        lic = _create_order(
            item_id="licenca_alfa",
            points_spent=5000,
            created_at=_now() - timedelta(hours=50),
        )
        _login(client, USER_STEAM)
        r = client.get("/api/player/available")
        d = r.get_json()
        assert d["ok"] is True
        by_id = {p["order_id"]: p for p in d["pending"]}
        assert by_id[fresh]["can_cancel"] is False
        assert by_id[fresh]["cancel_blocked_code"] == "cooldown_24h"
        assert by_id[aged]["can_cancel"] is True
        assert by_id[lic]["can_cancel"] is False
        assert by_id[lic]["is_license"] is True
        assert d["cancel_policy"]["cooldown_hours"] == 24
        assert d["cancel_policy"]["auto_cancel_hours"] == 48


class TestAdminLicenseBlocked:
    def test_admin_refund_license_blocked(self, client, monkeypatch, tmp_path):
        _mock_shop_catalog(monkeypatch, tmp_path)
        oid = _create_order(item_id="licenca_alfa", status="ENTREGUE", points_spent=5000)
        _login(client, ADMIN_STEAM)
        r = client.post(f"/api/admin/orders/{oid}/refund", json={})
        assert r.status_code == 403
        assert r.get_json()["code"] == "license_irrevocable"

    def test_admin_cancel_license_blocked(self, client, monkeypatch, tmp_path):
        _mock_shop_catalog(monkeypatch, tmp_path)
        oid = _create_order(item_id="licenca_alfa", status="PENDENTE", points_spent=5000)
        _login(client, ADMIN_STEAM)
        r = client.post(f"/api/admin/orders/{oid}/cancel", json={})
        assert r.status_code == 403
        assert r.get_json()["code"] == "license_irrevocable"


class TestAutoCancel48h:
    def test_expires_pending_non_license_and_refunds(self, monkeypatch, tmp_path):
        _mock_shop_catalog(monkeypatch, tmp_path)
        _seed_player_points(USER_STEAM, 10)
        oid = _create_order(points_spent=200, created_at=_now() - timedelta(hours=49))
        lic = _create_order(
            item_id="licenca_alfa",
            points_spent=5000,
            created_at=_now() - timedelta(hours=72),
        )
        young = _create_order(points_spent=50, created_at=_now() - timedelta(hours=10))

        db = _app_module._SessionLocal()
        try:
            first = expire_stale_pending_orders(db)
            second = expire_stale_pending_orders(db)
        finally:
            db.close()

        assert first["processed"] == 1
        assert first["skipped_license"] >= 1
        assert first["cancelled"][0]["order_id"] == oid
        assert first["cancelled"][0]["refunded"] == 160
        assert second["processed"] == 0
        assert _order_status(oid) == "CANCELADO"
        assert _order_status(lic) == "PENDENTE"
        assert _order_status(young) == "PENDENTE"
        assert _player_points(USER_STEAM) == 170
