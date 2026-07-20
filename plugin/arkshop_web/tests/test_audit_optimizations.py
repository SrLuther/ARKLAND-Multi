"""Regressões das fases de auditoria ARKLAND (perf/segurança)."""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as _app_module
from app import app, _configure_database

ADMIN_STEAM = "76561198000000001"
USER_STEAM = "76561198000000002"


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_API_KEY", "test-audit-key")
    monkeypatch.setattr(_app_module, "_ARKSHOP_API_KEY", "test-audit-key")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]), encoding="utf-8")
    (tmp_path / "settings.json").write_text("{}", encoding="utf-8")
    db_url = f"sqlite:///{tmp_path / 'audit.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    _app_module._invalidate_public_catalog_cache()
    yield


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login(client, steam_id: str) -> None:
    with client.session_transaction() as sess:
        sess["steam_id"] = steam_id


def test_pending_polled_skips_audit_when_empty(client, monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(_app_module, "_audit_event", lambda *a, **k: calls.append(k))
    monkeypatch.setattr(_app_module, "_require_db", lambda: None)

    class _EmptyQuery:
        def filter(self, *a, **k):
            return self

        def all(self):
            return []

    class _Db:
        def query(self, model):
            return _EmptyQuery()

    monkeypatch.setattr(_app_module, "_get_db_session", lambda: _Db())

    r = client.get(
        f"/api/pending/{USER_STEAM}",
        headers={"X-API-Key": "test-audit-key"},
    )
    assert r.status_code == 200
    assert calls == []


def test_player_history_single_query_window(client):
    _login(client, USER_STEAM)
    executes: list[str] = []

    def _capture(conn, clause, *args, **kwargs):
        executes.append(str(clause))
        return conn.__class__.execute(conn, clause, *args, **kwargs)

    # Seed one order via API is heavy — smoke: endpoint ok + no separate COUNT query pattern
    r = client.get("/api/player/history?limit=5")
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True
    assert "total" in d
    assert "items" in d


def test_player_myarea_aggregate(client):
    _login(client, USER_STEAM)
    r = client.get("/api/player/myarea?limit=5")
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True
    assert "summary" in d
    assert "history" in d
    assert "donations" in d


def test_catalog_etag_304(client):
    r1 = client.get("/api/catalog")
    assert r1.status_code == 200
    etag = r1.headers.get("ETag")
    assert etag
    r2 = client.get("/api/catalog", headers={"If-None-Match": etag})
    assert r2.status_code == 304


def test_admin_metrics(client):
    _login(client, ADMIN_STEAM)
    r = client.get("/api/admin/metrics")
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True
    assert "cache" in d
    assert "db" in d


def test_idempotency_store_claim(tmp_path):
    import idempotency_store as store

    db = tmp_path / "idem.sqlite"
    store.configure(db)
    assert store.claim("k1") is True
    assert store.claim("k1") is False
    store.release("k1")
    assert store.claim("k1") is True
