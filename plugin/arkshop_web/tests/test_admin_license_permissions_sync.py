"""Sync Permissions ao conceder/revogar licenças no painel admin."""
from __future__ import annotations

import json

import pytest

import app as _app_module
from app import app

ADMIN_STEAM = "76561198000000001"
TARGET_STEAM = "76561198000000099"


@pytest.fixture(autouse=True)
def _admin_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_WEB_SECRET", "test-secret")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]), encoding="utf-8")
    yield


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login(client, steam_id: str) -> None:
    with client.session_transaction() as sess:
        sess["steam_id"] = steam_id


def test_grant_keyvault_syncs_permissions_addtimed(client, monkeypatch):
    _login(client, ADMIN_STEAM)
    sync_calls: list[tuple] = []

    monkeypatch.setattr(_app_module, "_grant_player_entitlement", lambda *a, **k: None)
    monkeypatch.setattr(
        _app_module,
        "_get_player_entitlements",
        lambda sid: [{"group": "keyvault", "expires_at": "2099-01-01"}],
    )
    monkeypatch.setattr(
        _app_module,
        "_sync_license_permissions_all_servers",
        lambda sid, grp, grant, days=0: sync_calls.append((sid, grp, grant, days))
        or [{"server_id": "map1", "label": "Mapa", "ok": True}],
    )
    monkeypatch.setattr(_app_module, "_audit_event", lambda *a, **k: None)
    monkeypatch.setattr(_app_module, "_db_ready", lambda: True)

    r = client.post(
        f"/api/admin/players/{TARGET_STEAM}/licenses",
        json={"action": "grant", "group": "keyvault", "days": 30},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert sync_calls == [(TARGET_STEAM, "keyvault", True, 30)]
    assert body["permissions_sync"][0]["ok"] is True


def test_revoke_license_syncs_permissions_remove(client, monkeypatch):
    _login(client, ADMIN_STEAM)
    sync_calls: list[tuple] = []

    monkeypatch.setattr(_app_module, "_revoke_player_entitlement_by_group", lambda *a: None)
    monkeypatch.setattr(_app_module, "_get_player_entitlements", lambda sid: [])
    monkeypatch.setattr(
        _app_module,
        "_sync_license_permissions_all_servers",
        lambda sid, grp, grant, days=0: sync_calls.append((sid, grp, grant, days))
        or [{"server_id": "map1", "label": "Mapa", "ok": True}],
    )
    monkeypatch.setattr(_app_module, "_audit_event", lambda *a, **k: None)
    monkeypatch.setattr(_app_module, "_db_ready", lambda: True)

    r = client.post(
        f"/api/admin/players/{TARGET_STEAM}/licenses",
        json={"action": "revoke", "group": "keyvault"},
    )
    assert r.status_code == 200
    assert sync_calls == [(TARGET_STEAM, "keyvault", False, 0)]


def test_player_purchase_nuvem_syncs_permissions(client, monkeypatch):
    user_steam = "76561198000000002"
    _login(client, user_steam)
    sync_calls: list[tuple] = []

    monkeypatch.setattr(
        _app_module,
        "_auth_display_name_fields",
        lambda _sid, is_admin: {
            "market_display_name": "NuvemPlayer",
            "needs_display_name": False,
        },
    )
    monkeypatch.setattr(
        _app_module,
        "_safe_market_profile",
        lambda _db, _sid: type("P", (), {"market_display_name": "NuvemPlayer"})(),
    )
    monkeypatch.setattr(_app_module, "_get_player_points", lambda _sid: 10_000)
    monkeypatch.setattr(
        _app_module,
        "_catalog_entry",
        lambda _t, _i: {
            "Type": "license",
            "Price": 0,
            "LicenseGrant": {"Group": "keyvault", "Days": 30, "Redeemable": True},
        },
    )
    monkeypatch.setattr(_app_module, "_apply_entitlement_grant_tx", lambda *a, **k: None)

    class _FakeDb:
        def execute(self, *a, **k):
            return type("R", (), {"rowcount": 1})()

        def commit(self) -> None:
            return None

        def rollback(self) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(_app_module, "_SessionLocal", lambda: _FakeDb())
    monkeypatch.setattr(
        _app_module,
        "_create_order",
        lambda *a, **k: (
            type(
                "O",
                (),
                {
                    "order_id": "ord-nuvem",
                    "steam_id": user_steam,
                    "server_id": "default",
                    "status": "PENDENTE",
                },
            )(),
            None,
        ),
    )
    monkeypatch.setattr(
        _app_module,
        "_process_order_delivery",
        lambda _oid: {"ok": True, "queued": True},
    )
    monkeypatch.setattr(
        _app_module,
        "_sync_license_permissions_all_servers",
        lambda sid, grp, grant, days=0: sync_calls.append((sid, grp, grant, days))
        or [{"server_id": "map1", "label": "Mapa", "ok": True}],
    )

    r = client.post(
        "/api/player/purchase",
        json={"item_id": "licenca_nuvem", "item_type": "shop", "amount": 1},
    )
    assert r.status_code == 200
    assert sync_calls == [(user_steam, "keyvault", True, 30)]
