"""Testes para ArkShop Web Manager."""
from __future__ import annotations

import json
import threading
import uuid
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

ADMIN_STEAM = "76561198000000001"
USER_STEAM  = "76561198000000002"
API_KEY = "test-api-key"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_API_KEY", API_KEY)
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


def _create_order_direct(steam_id=USER_STEAM, item_id="sword", amount=1, status="PENDENTE", server_id="default", points_spent=0, item_type="shop"):
    db = _app_module._SessionLocal()
    try:
        o = _app_module.Order(
            order_id=str(uuid.uuid4()),
            steam_id=steam_id,
            server_id=server_id,
            item_type=item_type,
            item_id=item_id,
            amount=amount,
            points_spent=max(0, int(points_spent)),
            status=status,
            created_at=_now(),
            updated_at=_now(),
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

    def test_me_authenticated_admin(self, client):
        _login(client, ADMIN_STEAM)
        r = client.get("/api/auth/me")
        d = r.get_json()
        assert d["authenticated"] is True
        assert d["is_admin"] is True
        assert d["steam_id"] == ADMIN_STEAM

    def test_me_authenticated_user(self, client, monkeypatch):
        monkeypatch.setattr(
            _app_module,
            "_auth_display_name_fields",
            lambda _sid, is_admin: {
                "market_display_name": None,
                "needs_display_name": not is_admin,
            },
        )
        _login(client, USER_STEAM)
        r = client.get("/api/auth/me")
        d = r.get_json()
        assert d["authenticated"] is True
        assert d["is_admin"] is False
        assert d["needs_display_name"] is True
        assert d["market_display_name"] is None

    def test_me_authenticated_user_with_display_name(self, client, monkeypatch):
        monkeypatch.setattr(
            _app_module,
            "_auth_display_name_fields",
            lambda _sid, is_admin: {
                "market_display_name": "PlayerBR",
                "needs_display_name": False,
            },
        )
        _login(client, USER_STEAM)
        d = client.get("/api/auth/me").get_json()
        assert d["needs_display_name"] is False
        assert d["market_display_name"] == "PlayerBR"

    def test_purchase_rejects_without_display_name(self, client, monkeypatch):
        monkeypatch.setattr(_app_module, "_safe_market_profile", lambda _db, _sid: None)
        _login(client, USER_STEAM)
        monkeypatch.setattr(_app_module, "_catalog_entry", lambda _t, _i: {"Price": 0, "Type": "item"})
        r = client.post(
            "/api/player/purchase",
            json={"item_id": "sword", "item_type": "shop", "amount": 1},
        )
        assert r.status_code == 403
        d = r.get_json()
        assert d["needs_display_name"] is True

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
        r = client.post(f"/api/player/orders/{oid}/contest",
                        json={"reason": "não recebi o item"})
        d = r.get_json()
        assert d["ok"] is True
        assert d["status"] == "CONTESTADO"

    def test_contest_requires_reason(self, client):
        _login(client, USER_STEAM)
        oid = _create_order_direct()
        r = client.post(f"/api/player/orders/{oid}/contest", json={"reason": "  "})
        assert r.status_code == 400

    def test_contest_creates_dispute_record(self, client):
        _login(client, USER_STEAM)
        oid = _create_order_direct()
        client.post(f"/api/player/orders/{oid}/contest", json={"reason": "bug"})
        db = _app_module._SessionLocal()
        try:
            dispute = db.query(_app_module.Dispute).filter(_app_module.Dispute.order_id == oid).first()
            assert dispute is not None
            assert dispute.reason == "bug"
            assert dispute.status == "ABERTO"
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
                    "rcon_host": "10.0.0.2",
                    "rcon_port": 27020,
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
        names = [s["label"] for s in home.get("servers", [])]
        assert "The Volcano" in names

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

def _seed_store_user(steam_id: str, *, display_name: str = "Jogador Teste", blocked: bool = False) -> None:
    db = _app_module._SessionLocal()
    try:
        row = db.get(_app_module.StoreUser, steam_id)
        if row is None:
            row = _app_module.StoreUser(
                steam_id=steam_id,
                display_name=display_name,
                site_access_blocked=blocked,
                last_login_at=_now(),
            )
            db.add(row)
        else:
            row.display_name = display_name
            row.site_access_blocked = blocked
            row.last_login_at = _now()
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
        _seed_store_user(USER_STEAM, display_name="Alpha Tester")
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
        sql = _app_module._steam_id_on_sql("mp.steam_id", "su.steam_id", mysql=True)
        assert "COLLATE utf8mb4_unicode_ci" in sql
        assert sql.count("COLLATE utf8mb4_unicode_ci") == 2
        assert _app_module._steam_id_on_sql("a.steam_id", "b.steam_id", mysql=False) == (
            "a.steam_id = b.steam_id"
        )

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
        r = client.post("/api/player/card/checkout", json={"package_id": "p500"})
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
                    "package_id": "p500",
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
        assert d["points"] == 500
        assert d["amount_brl"] == 5.0

        db = _app_module._SessionLocal()
        try:
            row = db.query(_app_module.PointPayment).filter(
                _app_module.PointPayment.payment_id == d["payment_id"]
            ).first()
            assert row is not None
            assert row.package_id == "p500"
            assert row.points == 500
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
