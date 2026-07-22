"""Garantias pré-release — gaps das otimizações Flask/MySQL (Fases 1–5).

Cobre: race de schedulers, retry após falha de boot, sessão libertada antes
de I/O, PIX sem cache, pool vs Waitress, circuit breaker isolation,
double-start locks, e carga leve (pool leak).
"""
from __future__ import annotations

import ast
import json
import os
import py_compile
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")
os.environ.setdefault("ARKSHOP_RETRY_INTERVAL", "9999")

import app as _app_module
import background_tasks as _bg
import db_diagnostics as _diag
import db_pool as _pool
import payment_jobs as _pj
import pending_jobs as _pend
import ttl_cache as _ttl
import waitress_config as _wc
from app import app, _configure_database
from sqlalchemy import text

_WEB_ROOT = Path(__file__).resolve().parents[1]
_TOUCHED_PY = [
    "db_pool.py",
    "background_tasks.py",
    "payment_jobs.py",
    "pending_jobs.py",
    "ttl_cache.py",
    "waitress_config.py",
    "db_diagnostics.py",
]
_TOUCHED_JSON = [
    # catalog examples under CustomShop (se existirem no repo)
]


# ── Static checks ─────────────────────────────────────────────────────────────


def test_static_py_compile_touched_modules():
    errors: list[str] = []
    for name in _TOUCHED_PY:
        path = _WEB_ROOT / name
        assert path.is_file(), f"missing {name}"
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"{name}: {exc}")
    # app.py é grande — ast.parse + compile parcial via import já validado; ainda assim py_compile
    app_path = _WEB_ROOT / "app.py"
    try:
        py_compile.compile(str(app_path), doraise=True)
    except py_compile.PyCompileError as exc:
        errors.append(f"app.py: {exc}")
    assert not errors, "py_compile failed:\n" + "\n".join(errors)


def test_static_ast_parse_touched_modules():
    for name in _TOUCHED_PY + ["app.py"]:
        src = (_WEB_ROOT / name).read_text(encoding="utf-8")
        ast.parse(src, filename=name)


def test_static_anti_pattern_pix_no_ttl_cache():
    """Poll PIX não pode importar/usar ttl_cache nem X-Short-Cache."""
    src = (_WEB_ROOT / "app.py").read_text(encoding="utf-8")
    # Isola a função player_pix_status via AST
    tree = ast.parse(src)
    found = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "player_pix_status":
            found = node
            break
    assert found is not None, "player_pix_status não encontrado"
    body = ast.get_source_segment(src, found) or ""
    assert "_ttl_cache" not in body
    assert "X-Short-Cache" not in body
    assert "ttl_cache" not in body


def test_static_payment_jobs_fetches_mp_before_db():
    """MP HTTP deve ocorrer ANTES de abrir sessão DB (ordem no source)."""
    src = (_WEB_ROOT / "payment_jobs.py").read_text(encoding="utf-8")
    fetch_pos = src.find("fetch_payment(")
    session_pos = src.find("_SessionLocal()")
    assert fetch_pos > 0 and session_pos > 0
    assert fetch_pos < session_pos, "fetch_payment deve preceder _SessionLocal"


def test_static_pending_jobs_releases_before_per_player_loop():
    """Lista steam_ids com sessão curta; loop por jogador abre sessão nova."""
    src = (_WEB_ROOT / "pending_jobs.py").read_text(encoding="utf-8")
    assert "force=True" in src
    assert "for sid in steam_ids" in src
    # Duas aberturas: SELECT DISTINCT + por jogador
    assert src.count("_SessionLocal()") >= 2


def test_static_json_touched_valid():
    candidates = [
        _WEB_ROOT.parent / "CustomShop" / "catalog.json",
        _WEB_ROOT.parent / "CustomShop" / "catalog.json.example",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as fh:
            json.load(fh)


def test_static_db_local_server_mysql_flags():
    """MariaDB portable: max_connections + wait_timeout alinhados à Fase 1."""
    path = Path(__file__).resolve().parents[3] / "src" / "pages" / "db_local_server.py"
    if not path.is_file():
        pytest.skip("db_local_server.py fora do layout esperado")
    src = path.read_text(encoding="utf-8")
    assert "--max-connections=180" in src
    assert "--wait-timeout=600" in src


# ── Double-start / race locks ─────────────────────────────────────────────────


def test_interval_worker_double_start_same_thread():
    name = f"pre-release-interval-{time.time()}"
    calls = {"n": 0}
    stop = threading.Event()

    def tick():
        calls["n"] += 1
        stop.wait(timeout=0.05)

    t1 = _bg.start_interval_worker(tick, interval_sec=60.0, name=name)
    t2 = _bg.start_interval_worker(tick, interval_sec=60.0, name=name)
    assert t1 is t2
    _bg.stop_interval_worker(name)


def test_pending_stale_scheduler_double_start_idempotent():
    calls = {"n": 0}

    def recover():
        calls["n"] += 1
        return 0

    t1 = _pend.start_pending_stale_scheduler(interval_sec=60.0, recover_fn=recover)
    t2 = _pend.start_pending_stale_scheduler(interval_sec=60.0, recover_fn=recover)
    assert t1 is t2
    _bg.stop_interval_worker("arkshop-pending-stale")


def test_catalog_feed_scheduler_double_start(monkeypatch):
    import catalog_feed_service as cfs

    monkeypatch.setenv("MARKET_CATALOG_FEED_INTERVAL_MINUTES", "60")
    monkeypatch.setenv("MARKET_CATALOG_FEED_ON_BOOT", "0")
    # Reset thread state for isolação
    with cfs._scheduler_start_lock:
        cfs._scheduler_stop.set()
        cfs._scheduler_thread = None
    cfs._scheduler_stop.clear()

    cfs.start_catalog_feed_scheduler_if_needed()
    t_before = cfs._scheduler_thread
    assert t_before is not None and t_before.is_alive()
    cfs.start_catalog_feed_scheduler_if_needed()
    assert cfs._scheduler_thread is t_before
    cfs._scheduler_stop.set()


def test_concurrent_runtime_workers_start_once(monkeypatch):
    _app_module._RUNTIME_WORKERS_STARTED = False
    barrier = threading.Barrier(8)
    calls = {"sched": 0, "sec": 0}
    lock = threading.Lock()

    def _sched():
        with lock:
            calls["sched"] += 1

    def _sec():
        with lock:
            calls["sec"] += 1

    monkeypatch.setattr(_app_module, "_initialize_scheduler_if_needed", _sched)
    monkeypatch.setattr(_app_module, "_ensure_secondary_runtime_workers", _sec)

    def worker():
        barrier.wait(timeout=5)
        _app_module._start_runtime_workers_once()

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    # Flag só liga 1× no path locked; chamadas pós-flag ainda invocam sched+sec
    assert _app_module._RUNTIME_WORKERS_STARTED is True
    assert calls["sched"] >= 1
    assert calls["sec"] >= 1


# ── Circuit breaker isolation ─────────────────────────────────────────────────


@pytest.fixture
def _reset_circuit():
    _diag.record_circuit_success()
    yield
    _diag.record_circuit_success()


def test_health_ok_while_circuit_open(_reset_circuit):
    for _ in range(_diag._CIRCUIT_THRESHOLD):
        _diag.record_query(statement="SELECT 1", duration_ms=0.0, error="gone away")
    assert _diag.circuit_is_open() is True
    c = app.test_client()
    r = c.get("/api/health")
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True


def test_require_db_blocks_when_circuit_open(monkeypatch, _reset_circuit):
    monkeypatch.setattr(_app_module, "_db_ready", lambda: True)
    for _ in range(_diag._CIRCUIT_THRESHOLD):
        _diag.record_query(statement="SELECT 1", duration_ms=0.0, error="gone away")
    assert _diag.circuit_is_open() is True
    with app.test_request_context("/api/admin/orders"):
        err = _app_module._require_db()
    assert err is not None
    resp, code = err
    assert code == 503
    payload = resp.get_json()
    assert payload.get("error") == "db_circuit_open"


def test_auth_me_is_boot_skip_workers_must_boot_separately():
    """/api/auth/me está em BOOT_SKIP — workers têm de subir no boot DB (P0 adversarial)."""
    assert "/api/auth/me" in _app_module._BOOT_SKIP_PREFIXES or any(
        "/api/auth/me".startswith(p) for p in _app_module._BOOT_SKIP_PREFIXES
    )
    src = (_WEB_ROOT / "app.py").read_text(encoding="utf-8")
    boot_idx = src.find('os.environ.get("ARKSHOP_SKIP_DB_BOOT") != "1"')
    assert boot_idx > 0
    assert src.find("_start_runtime_workers_once()", boot_idx) > boot_idx


def test_bg_inline_ignored_in_production_aligns_with_adversarial(monkeypatch):
    """Alinhamento com test_prod_adversarial_p0: INLINE morto em production."""
    monkeypatch.setenv("ARKSHOP_ENV", "production")
    _bg.set_inline_mode(True)
    try:
        assert _bg.is_inline_mode() is False
    finally:
        monkeypatch.delenv("ARKSHOP_ENV", raising=False)
        _bg.set_inline_mode(False)


# ── Session released before external I/O (payment_jobs) ───────────────────────


def test_payment_confirm_releases_session_even_on_error(monkeypatch):
    released = {"force": None}

    class _FakeDb:
        def query(self, *_a, **_k):
            raise RuntimeError("db boom")

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(_app_module, "_get_mp_access_token", lambda: "tok")
    monkeypatch.setattr(
        _app_module,
        "fetch_payment",
        lambda *a, **k: {"id": "1", "status": "approved", "external_reference": "p1"},
    )
    monkeypatch.setattr(_app_module, "_SessionLocal", lambda: _FakeDb())
    monkeypatch.setattr(
        _app_module,
        "_release_db_session",
        lambda db, force=False: released.__setitem__("force", force),
    )
    _pj._confirm_mp_payment("1", payment_id="p1", source="test")
    assert released["force"] is True


# ── Pool vs Waitress ──────────────────────────────────────────────────────────


def test_waitress_threads_never_exceed_pool_capacity():
    pool = _pool.resolve_pool_settings()
    http = _wc.resolve_http_threads(pool_size=pool["pool_size"], cpus=16)
    capacity = pool["pool_size"] + pool["max_overflow"]
    assert http["threads"] <= pool["pool_size"]
    assert http["threads"] + http["pool_headroom"] <= pool["pool_size"] or http["threads"] <= 8
    assert http["threads"] < capacity


# ── PIX response headers (runtime) ────────────────────────────────────────────


@pytest.fixture
def pix_client(tmp_path, monkeypatch):
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    (tmp_path / "admin_steamids.json").write_text("[]", encoding="utf-8")
    (tmp_path / "settings.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    monkeypatch.setattr(_app_module, "_migrate_schema", lambda _e: None)
    _configure_database(f"sqlite:///{tmp_path / 'pix.db'}")
    if _app_module._ENGINE is not None:
        _app_module.Base.metadata.create_all(bind=_app_module._ENGINE)
    monkeypatch.setattr(_app_module, "_DB_INITIALIZED", True)
    _diag.record_circuit_success()
    _ttl.invalidate_all_short_caches()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
    _configure_database("")


def test_pix_status_response_has_no_short_cache_header(pix_client, monkeypatch):
    steam = "76561198000000002"
    with pix_client.session_transaction() as sess:
        sess["steam_id"] = steam
    import uuid

    pid = str(uuid.uuid4())
    db = _app_module._SessionLocal()
    try:
        db.add(
            _app_module.PointPayment(
                payment_id=pid,
                mp_payment_id="mp-x",
                steam_id=steam,
                package_id="p1",
                amount_brl=1.0,
                points=100,
                status="PENDENTE",
                credited=False,
                payment_method="pix",
                created_at=_app_module._now(),
                updated_at=_app_module._now(),
            )
        )
        db.commit()
    finally:
        db.close()
    monkeypatch.setattr(_app_module, "_pix_mp_poll_allowed", lambda _p: False)
    r = pix_client.get(f"/api/player/pix/{pid}/status")
    assert r.status_code == 200
    assert "X-Short-Cache" not in r.headers
    assert "X-Catalog-Cache" not in r.headers


# ── Carga leve — pool leak ────────────────────────────────────────────────────


def test_concurrent_health_no_pool_exhaustion(tmp_path, monkeypatch):
    """Muitas requests concorrentes ao test client não devem esgotar QueuePool."""
    monkeypatch.setenv("ARKSHOP_DB_POOL_SIZE", "5")
    monkeypatch.setenv("ARKSHOP_DB_MAX_OVERFLOW", "2")
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    monkeypatch.setattr(_app_module, "_migrate_schema", lambda _e: None)
    _configure_database(f"sqlite:///{tmp_path / 'load.db'}")
    if _app_module._ENGINE is not None:
        _app_module.Base.metadata.create_all(bind=_app_module._ENGINE)
    monkeypatch.setattr(_app_module, "_DB_INITIALIZED", True)
    _diag.record_circuit_success()

    client = app.test_client()
    errors: list[str] = []

    def one(_i: int) -> int:
        r = client.get("/api/health")
        if r.status_code != 200:
            errors.append(f"health:{r.status_code}")
        return r.status_code

    with ThreadPoolExecutor(max_workers=20) as ex:
        futs = [ex.submit(one, i) for i in range(80)]
        codes = [f.result(timeout=10) for f in as_completed(futs)]

    assert all(c == 200 for c in codes), errors
    with _app_module._ENGINE.connect() as conn:
        conn.execute(text("SELECT 1"))
    _configure_database("")


def test_concurrent_short_db_sessions_release(tmp_path, monkeypatch):
    """db_session + release sob concorrência — checkedout volta a 0."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import QueuePool

    engine = create_engine(
        f"sqlite:///{tmp_path / 'pool.db'}",
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=2,
        connect_args={"check_same_thread": False},
    )
    Session = sessionmaker(bind=engine)
    errors: list[str] = []

    def work(_i: int) -> None:
        try:
            with _pool.db_session(Session, commit=False) as db:
                db.execute(text("SELECT 1"))
        except Exception as exc:
            errors.append(str(exc))

    with ThreadPoolExecutor(max_workers=12) as ex:
        list(ex.map(work, range(60)))

    assert not errors, errors
    assert engine.pool.checkedout() == 0
    engine.dispose()
