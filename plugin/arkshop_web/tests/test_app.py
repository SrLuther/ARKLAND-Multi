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


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
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


# ── Rebuy ─────────────────────────────────────────────────────────────────────

class TestRebuy:
    def test_rebuy_sets_original_to_reemitido(self, client):
        _login(client, USER_STEAM)
        oid = _create_order_direct(status="ERRO")
        with patch.object(_app_module, "_rcon_command", return_value="ok"):
            r = client.post(f"/api/player/orders/{oid}/rebuy", json={})
        d = r.get_json()
        assert "order_id" in d

        db = _app_module._SessionLocal()
        try:
            original = db.query(_app_module.Order).filter(_app_module.Order.order_id == oid).first()
            assert original.status == "REEMITIDO"
        finally:
            db.close()

    def test_rebuy_creates_new_order(self, client):
        _login(client, USER_STEAM)
        oid = _create_order_direct(status="ERRO")
        with patch.object(_app_module, "_rcon_command", return_value="ok"):
            r = client.post(f"/api/player/orders/{oid}/rebuy", json={})
        new_oid = r.get_json()["order_id"]
        assert new_oid != oid

        db = _app_module._SessionLocal()
        try:
            new_order = db.query(_app_module.Order).filter(_app_module.Order.order_id == new_oid).first()
            assert new_order is not None
            assert new_order.original_order_id == oid
            rebuy = db.query(_app_module.Rebuy).filter(_app_module.Rebuy.original_order_id == oid).first()
            assert rebuy is not None
        finally:
            db.close()

    def test_rebuy_not_found(self, client):
        _login(client, USER_STEAM)
        r = client.post("/api/player/orders/nonexistent/rebuy", json={})
        assert r.status_code == 404


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
            "rcon_host": "10.0.0.1",
            "rcon_port": 27020,
            "rcon_password": "secret",
            "retry_max_attempts": 5,
        })
        assert r.get_json()["ok"] is True

        r2 = client.get("/api/servers")
        items = r2.get_json()["items"]
        assert len(items) == 1
        assert items[0]["server_id"] == "pve1"
        assert items[0]["rcon_password_set"] is True
        assert "rcon_password" not in items[0]

    def test_delete_server(self, client):
        _login(client, ADMIN_STEAM)
        client.post("/api/servers", json={"server_id": "pvp1", "rcon_host": "127.0.0.1", "rcon_port": 27020})
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


# ── Delivery com RCON por servidor ────────────────────────────────────────────

class TestServerRconRouting:
    def test_delivery_uses_server_specific_rcon(self, client, tmp_path):
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
    def test_concurrent_delivery_does_not_duplicate(self):
        """
        WITH FOR UPDATE garante idempotência em MySQL/MariaDB.
        SQLite não suporta row-level lock, então este teste valida apenas
        que o status final é ENTREGUE (sem duplicatas de status, mesmo que
        múltiplas tentativas ocorram).
        """
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


# ── Admin reprocess ───────────────────────────────────────────────────────────

class TestAdminReprocess:
    def test_reprocess_erro_order(self, client):
        _login(client, ADMIN_STEAM)
        oid = _create_order_direct(status="ERRO")
        with patch.object(_app_module, "_rcon_command", return_value="ok"):
            r = client.post(f"/api/admin/orders/{oid}/reprocess")
        d = r.get_json()
        assert d["ok"] is True
        assert d["status"] == "ENTREGUE"

    def test_reprocess_already_delivered_blocked(self, client):
        _login(client, ADMIN_STEAM)
        oid = _create_order_direct(status="ENTREGUE")
        r = client.post(f"/api/admin/orders/{oid}/reprocess")
        assert r.status_code == 400
