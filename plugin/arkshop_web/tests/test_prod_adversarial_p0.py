"""Regressões adversariais P0 — otimizações Web Store (pool/bg/cache/waitress)."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")
os.environ.setdefault("ARKSHOP_RETRY_INTERVAL", "9999")

import background_tasks as _bg
import db_pool as pool
import waitress_config as wc


def test_bg_inline_ignored_in_production(monkeypatch):
    """P0: ARKSHOP_BG_INLINE=1 em production NÃO pode correr sync no caller."""
    monkeypatch.setenv("ARKSHOP_ENV", "production")
    _bg.set_inline_mode(True)
    try:
        assert _bg.is_inline_mode() is False
        seen: list[str] = []

        def work():
            import threading

            seen.append(threading.current_thread().name)

        assert _bg.submit(work, dedupe_key="prod-inline-p0") is True
        assert _bg.wait_idle(timeout=3)
        assert seen and seen[0] != "MainThread"
    finally:
        monkeypatch.delenv("ARKSHOP_ENV", raising=False)
        _bg.set_inline_mode(False)


def test_interval_worker_starts_in_production_despite_inline_env(monkeypatch):
    """P0: INLINE+production ainda arranca thread (schedulers não ficam mortos)."""
    monkeypatch.setenv("ARKSHOP_ENV", "production")
    _bg.set_inline_mode(True)
    name = "p0-interval-prod"
    ticks = {"n": 0}

    def tick():
        ticks["n"] += 1

    try:
        _bg.stop_interval_worker(name)
        t = _bg.start_interval_worker(tick, interval_sec=60.0, name=name, run_immediately=True)
        assert t.is_alive()
        assert _bg.is_interval_worker_alive(name)
        # run_immediately corre no loop da thread — dá-lhe um instante
        import time

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and ticks["n"] < 1:
            time.sleep(0.05)
        assert ticks["n"] >= 1
    finally:
        _bg.stop_interval_worker(name)
        monkeypatch.delenv("ARKSHOP_ENV", raising=False)
        _bg.set_inline_mode(False)


def test_auth_me_path_is_boot_skip_but_workers_must_boot_separately():
    """Documenta o chicken-egg: TEK pinga /api/auth/me (skip) — workers no boot."""
    import app as app_mod

    assert "/api/auth/me" in app_mod._BOOT_SKIP_PREFIXES or any(
        "/api/auth/me".startswith(p) for p in app_mod._BOOT_SKIP_PREFIXES
    )
    # O arranque em module-load chama _start_runtime_workers_once quando
    # SKIP_DB_BOOT!=1 — ver bloco no fim de app.py.
    src = open(app_mod.__file__, encoding="utf-8").read()
    assert "_start_runtime_workers_once()" in src
    boot_idx = src.find('os.environ.get("ARKSHOP_SKIP_DB_BOOT") != "1"')
    assert boot_idx > 0
    assert src.find("_start_runtime_workers_once()", boot_idx) > boot_idx


def test_diagnostics_threads_not_default_32(monkeypatch):
    """P0: probe NÃO pode reportar 32 threads quando o Waitress usa 4–8."""
    monkeypatch.delenv("ARKSHOP_HTTP_THREADS", raising=False)
    monkeypatch.delenv("ARKSHOP_HTTP_THREADS_FORCE", raising=False)
    from db_diagnostics import probe_database

    class _NoEngine:
        pass

    out = probe_database(_NoEngine(), None)  # type: ignore[arg-type]
    assert out["waitress_threads_configured"] <= 8
    assert out["waitress_threads_configured"] >= 4
    assert out["waitress_threads_configured"] != 32


def test_pool_peak_vs_mariadb_max_connections():
    """6× pico 30 = 180 — orçamento exacto; reserve deixa margem."""
    assert pool.pool_peak_connections() == 30
    # Com reserve=20: (180-20)//30 = 5 instâncias seguras
    assert pool.max_safe_app_instances(mariadb_max_connections=180, reserve=20) == 5
    # Sem reserve: 180//30 = 6 — no limite, perigoso
    assert pool.max_safe_app_instances(mariadb_max_connections=180, reserve=0) == 6


def test_threads_plus_bg_fit_pool_with_timeout_5(monkeypatch):
    """Waitress threads + headroom ≤ pool; overflow cobre bg (pool_timeout=5)."""
    monkeypatch.delenv("ARKSHOP_HTTP_THREADS", raising=False)
    monkeypatch.delenv("ARKSHOP_HTTP_THREADS_FORCE", raising=False)
    cfg = pool.resolve_pool_settings()
    http = wc.resolve_http_threads(pool_size=cfg["pool_size"], cpus=8)
    assert http["threads"] + http["pool_headroom"] <= cfg["pool_size"]
    bg = int(os.environ.get("ARKSHOP_BG_WORKERS", "4") or 4)
    # Pico HTTP+bg deve caber em pool+overflow sem FORCE
    assert http["threads"] + bg <= cfg["pool_size"] + cfg["max_overflow"]
    assert cfg["pool_timeout"] == 5
