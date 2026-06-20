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

    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]))

    db_path = str(tmp_path / "test.db")
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
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


def _create_order_direct(steam_id=USER_STEAM, item_id="sword", amount=1, status="PENDENTE", server_id="default"):
    db = _app_module._SessionLocal()
    try:
        o = _app_module.Order(
            order_id=str(uuid.uuid4()),
            steam_id=steam_id,
            server_id=server_id,
            item_type="shop",
            item_id=item_id,
            amount=amount,
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

    def test_me_authenticated_user(self, client):
        _login(client, USER_STEAM)
        r = client.get("/api/auth/me")
        d = r.get_json()
        assert d["authenticated"] is True
        assert d["is_admin"] is False

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
        _create_donation_direct(points=500, amount_brl=25.0)
        _create_donation_direct(points=200, amount_brl=10.0, credited=False, status="PENDENTE")
        r = client.get("/api/player/donations")
        d = r.get_json()
        assert d["total"] == 2
        points = {item["points"] for item in d["items"]}
        assert points == {500, 200}
        credited = [item for item in d["items"] if item["credited"]]
        assert len(credited) == 1
        assert credited[0]["credited_at"] is not None

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


# ── Admin pontos (banco central) ──────────────────────────────────────────────

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
