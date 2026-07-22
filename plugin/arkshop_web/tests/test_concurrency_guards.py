"""Regressões de concorrência: limiter, rotas idempotentes, sync-all async, RCON/DB."""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")
os.environ.setdefault("ARKSHOP_RETRY_INTERVAL", "9999")

import app as _app_module
from app import app

ADMIN_STEAM = "76561198000000001"


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]), encoding="utf-8")
    (tmp_path / "settings.json").write_text("{}", encoding="utf-8")
    yield


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login(client, steam_id: str) -> None:
    with client.session_transaction() as sess:
        sess["steam_id"] = steam_id


def test_limiter_defaults_are_generous_for_spa():
    app_py = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")
    with open(app_py, encoding="utf-8") as fh:
        src = fh.read()
    assert 'default_limits=["6000 per day", "600 per hour"]' in src
    assert 'default_limits=["200 per day", "50 per hour"]' not in src


def test_auth_me_and_health_override_defaults(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    r2 = client.get("/api/auth/me")
    assert r2.status_code == 200
    assert r2.get_json().get("authenticated") is False


def test_tribe_routes_register_idempotent(monkeypatch):
    from tribe_routes import register_tribe_routes

    calls = {"n": 0}
    real_log = __import__("logging").getLogger("arkshop_web.tribe_routes").info

    def _counting_info(msg, *a, **k):
        if "já registradas" in str(msg):
            calls["n"] += 1
        return real_log(msg, *a, **k)

    monkeypatch.setattr(
        "tribe_routes.log.info",
        _counting_info,
    )
    # Já registadas no boot do app — segunda chamada deve skip.
    register_tribe_routes(
        app,
        db_ready=lambda: False,
        session_factory=lambda: None,
        login_required=lambda f: f,
        admin_required=lambda f: f,
        api_key_required=lambda **kw: (lambda f: f),
        steam_id_from_session=lambda: None,
        is_admin_steamid=lambda s: False,
    )
    assert calls["n"] >= 1
    assert "tribe_presence" in app.view_functions


def test_admin_sync_all_permissions_async_does_not_block(client, monkeypatch):
    _login(client, ADMIN_STEAM)
    started = threading.Event()
    release = threading.Event()

    def _slow_reconcile(dry_run=False):
        started.set()
        release.wait(timeout=5)
        return {"ok": True, "checked": 1, "irregular": 0, "synced": 0, "errors": []}

    monkeypatch.setattr(
        _app_module, "_reconcile_all_entitlements_to_permission_db", _slow_reconcile
    )
    monkeypatch.setattr(_app_module, "_require_db", lambda: None)

    t0 = time.monotonic()
    r = client.post("/api/admin/sync-all-permissions", json={})
    elapsed = time.monotonic() - t0
    assert r.status_code == 202
    data = r.get_json()
    assert data["ok"] is True
    assert data.get("accepted") is True
    assert elapsed < 1.0  # não espera o reconcile
    assert started.wait(timeout=2)

    # sync=true mantém caminho bloqueante p/ testes legados
    release.set()
    time.sleep(0.05)
    r2 = client.post("/api/admin/sync-all-permissions", json={"sync": True})
    assert r2.status_code == 200
    assert r2.get_json()["synced"] == 0


def test_admin_sync_all_permissions_sync_flag(client, monkeypatch):
    """Compat: body sync=true devolve resultado imediato (testes/scripts)."""
    _login(client, ADMIN_STEAM)
    monkeypatch.setattr(
        _app_module,
        "_reconcile_all_entitlements_to_permission_db",
        lambda dry_run=False: {
            "ok": True,
            "checked": 10,
            "irregular": 2,
            "synced": 2,
            "errors": [],
        },
    )
    monkeypatch.setattr(_app_module, "_require_db", lambda: None)
    r = client.post("/api/admin/sync-all-permissions", json={"sync": True})
    assert r.status_code == 200
    assert r.get_json()["synced"] == 2


def test_tribe_sync_releases_db_before_rcon(monkeypatch):
    """Sessão DB não pode ficar aberta durante RCON multi-mapa."""
    from tribe_routes import register_tribe_routes

    # Usa um Flask app isolado para não poluir rotas do app global.
    from flask import Flask

    mini = Flask("tribe_sync_test")
    mini.secret_key = "test"
    closed_before_rcon = {"ok": False}
    session_state = {"open": False}

    class _FakeDb:
        def close(self):
            session_state["open"] = False

    def _session_factory():
        session_state["open"] = True
        return _FakeDb()

    def _rcon():
        closed_before_rcon["ok"] = not session_state["open"]
        return [{"ok": True, "server_id": "map1"}]

    def _login_required(f):
        return f

    def _api_key_required(**_kw):
        def deco(f):
            return f
        return deco

    monkeypatch.setattr(
        "tribe_service.request_tribe_sync",
        lambda db, steam_id: {"id": 1},
    )
    monkeypatch.setattr(
        "tribe_service.sync_owner_maps",
        lambda db, steam_id: {"maps": [{"server_id": "map1"}], "presences": []},
    )
    # Import path usado dentro de register — patch no módulo após imports internos
    import tribe_service as ts

    monkeypatch.setattr(ts, "request_tribe_sync", lambda db, steam_id: {"id": 1})
    monkeypatch.setattr(
        ts, "sync_owner_maps", lambda db, steam_id: {"maps": [{"server_id": "map1"}], "presences": []}
    )

    register_tribe_routes(
        mini,
        db_ready=lambda: True,
        session_factory=_session_factory,
        login_required=_login_required,
        admin_required=_login_required,
        api_key_required=_api_key_required,
        steam_id_from_session=lambda: ADMIN_STEAM,
        is_admin_steamid=lambda s: True,
        trigger_tribe_sync_rcon=_rcon,
    )

    with mini.test_client() as c:
        with c.session_transaction() as sess:
            sess["steam_id"] = ADMIN_STEAM
        # login_required do mini é no-op; a rota tribe_sync usa steam_id_from_session
        r = c.post("/api/tribe/sync", json={})
        assert r.status_code == 200
        assert closed_before_rcon["ok"] is True


def test_runtime_workers_start_once(monkeypatch):
    _app_module._RUNTIME_WORKERS_STARTED = False
    calls = {"n": 0}

    def _count():
        calls["n"] += 1

    monkeypatch.setattr(_app_module, "_initialize_scheduler_if_needed", _count)
    monkeypatch.setattr(
        "catalog_feed_service.start_catalog_feed_scheduler_if_needed",
        lambda: None,
    )
    monkeypatch.setattr(
        "tribe_log_poller.start_tribe_log_poller_if_needed",
        lambda: None,
    )
    _app_module._start_runtime_workers_once()
    _app_module._start_runtime_workers_once()
    # Após o 1.º boot, _initialize_scheduler_if_needed continua a ser chamado
    # (retenta thread morta) — flag _RUNTIME_WORKERS_STARTED só muda 1×.
    assert calls["n"] == 2
    assert _app_module._RUNTIME_WORKERS_STARTED is True


def test_runtime_workers_retry_secondary_every_call(monkeypatch):
    """Após o 1.º boot, secondary workers continuam a ser re-tentados (thread morta / falha)."""
    _app_module._RUNTIME_WORKERS_STARTED = False
    secondary = {"n": 0}

    monkeypatch.setattr(_app_module, "_initialize_scheduler_if_needed", lambda: None)
    monkeypatch.setattr(
        _app_module,
        "_ensure_secondary_runtime_workers",
        lambda: secondary.__setitem__("n", secondary["n"] + 1),
    )
    _app_module._start_runtime_workers_once()
    _app_module._start_runtime_workers_once()
    _app_module._start_runtime_workers_once()
    assert secondary["n"] == 3


def test_retry_scheduler_restarts_dead_thread(monkeypatch):
    """P0: flag INITIALIZED True + thread morta → re-arranca arkshop-retry."""
    dead = threading.Thread(target=lambda: None, name="arkshop-retry-dead", daemon=True)
    dead.start()
    dead.join(timeout=2)
    assert not dead.is_alive()

    started = {"n": 0}

    def _counting_start():
        started["n"] += 1
        t = threading.Thread(
            target=lambda: time.sleep(30), name="arkshop-retry-test", daemon=True
        )
        t.start()
        _app_module._scheduler_thread = t

    _app_module._SCHEDULER_INITIALIZED = True
    _app_module._scheduler_thread = dead
    monkeypatch.setattr(_app_module, "_start_scheduler", _counting_start)
    _app_module._initialize_scheduler_if_needed()
    assert started["n"] == 1
    assert _app_module._scheduler_thread is not None
    assert _app_module._scheduler_thread.is_alive()
    _app_module._initialize_scheduler_if_needed()
    assert started["n"] == 1
    _app_module._scheduler_stop.set()
    _app_module._SCHEDULER_INITIALIZED = False
    _app_module._scheduler_thread = None


def test_ensure_pending_stale_clears_ok_flag_on_failure(monkeypatch):
    _app_module._PENDING_STALE_SCHEDULER_OK = True

    def _boom(*_a, **_k):
        raise RuntimeError("boot failed")

    monkeypatch.setattr("pending_jobs.start_pending_stale_scheduler", _boom)
    _app_module._ensure_pending_stale_scheduler()
    assert _app_module._PENDING_STALE_SCHEDULER_OK is False

    monkeypatch.setattr(
        "pending_jobs.start_pending_stale_scheduler",
        lambda **_k: None,
    )
    monkeypatch.setattr(
        "pending_jobs.is_pending_stale_scheduler_alive",
        lambda: True,
    )
    _app_module._ensure_pending_stale_scheduler()
    assert _app_module._PENDING_STALE_SCHEDULER_OK is True


def test_ensure_pending_stale_ok_false_when_thread_not_alive(monkeypatch):
    """P0: start 'sucesso' sem thread viva não pode marcar OK (INLINE / crash)."""
    _app_module._PENDING_STALE_SCHEDULER_OK = False
    monkeypatch.setattr(
        "pending_jobs.start_pending_stale_scheduler",
        lambda **_k: None,
    )
    monkeypatch.setattr(
        "pending_jobs.is_pending_stale_scheduler_alive",
        lambda: False,
    )
    _app_module._ensure_pending_stale_scheduler()
    assert _app_module._PENDING_STALE_SCHEDULER_OK is False


def test_catalog_feed_skips_when_busy(monkeypatch):
    from catalog_feed_service import _feed_run_lock, run_catalog_feed

    assert _feed_run_lock.acquire(blocking=False)
    try:
        out = run_catalog_feed(
            source="test",
            session_factory=MagicMock(),
            read_catalog=lambda: {},
        )
        assert out.get("skipped") is True
    finally:
        _feed_run_lock.release()


def test_scheduler_tick_skips_when_busy():
    assert _app_module._SCHEDULER_TICK_LOCK.acquire(blocking=False)
    try:
        assert not _app_module._SCHEDULER_TICK_LOCK.acquire(blocking=False)
    finally:
        _app_module._SCHEDULER_TICK_LOCK.release()


def test_scheduler_pool_busy_threshold(monkeypatch):
    class _FakePool:
        def checkedout(self):
            return 12

        def size(self):
            return 10

        _max_overflow = 5

    class _FakeEngine:
        pool = _FakePool()

    monkeypatch.setattr(_app_module, "_ENGINE", _FakeEngine())
    assert _app_module._scheduler_pool_busy(threshold=0.7) is True
    monkeypatch.setattr(_FakePool, "checkedout", lambda self: 1)
    assert _app_module._scheduler_pool_busy(threshold=0.7) is False
