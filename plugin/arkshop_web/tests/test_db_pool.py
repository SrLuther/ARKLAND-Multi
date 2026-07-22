"""Fase 1 — defaults e helpers do pool SQLAlchemy."""
from __future__ import annotations

import db_pool as pool


def test_default_pool_settings_within_plan_ranges():
    cfg = pool.resolve_pool_settings()
    assert pool.POOL_SIZE_MIN <= cfg["pool_size"] <= pool.POOL_SIZE_MAX
    assert pool.MAX_OVERFLOW_MIN <= cfg["max_overflow"] <= pool.MAX_OVERFLOW_MAX
    assert cfg["pool_recycle"] == 1800
    assert cfg["pool_timeout"] >= 2
    assert cfg["pool_size"] == 20
    assert cfg["max_overflow"] == 10


def test_pool_peak_and_safe_instances():
    assert pool.pool_peak_connections() == 30
    assert pool.max_safe_app_instances(mariadb_max_connections=180, reserve=20) == 5
    assert pool.DEFAULT_MARIADB_MAX_CONNECTIONS == 180


def test_env_override_pool_size(monkeypatch):
    monkeypatch.setenv("ARKSHOP_DB_POOL_SIZE", "12")
    monkeypatch.setenv("ARKSHOP_DB_MAX_OVERFLOW", "8")
    monkeypatch.setenv("ARKSHOP_DB_POOL_RECYCLE", "1800")
    cfg = pool.resolve_pool_settings()
    assert cfg["pool_size"] == 12
    assert cfg["max_overflow"] == 8
    assert cfg["pool_recycle"] == 1800


def test_db_session_releases_even_on_error():
    closed: list[str] = []

    class FakeSession:
        def commit(self) -> None:
            pass

        def rollback(self) -> None:
            closed.append("rollback")

        def close(self) -> None:
            closed.append("close")

    def factory():
        return FakeSession()

    def release(db, force=False):
        closed.append(f"release:{force}")
        db.close()

    try:
        with pool.db_session(factory, release=release, commit=False):
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert "rollback" in closed
    assert "release:True" in closed
    assert "close" in closed


def test_release_before_external_io_force():
    calls: list[tuple] = []

    def release(db=None, force=False):
        calls.append((db, force))

    pool.release_before_external_io(release, "sess")
    assert calls == [("sess", True)]
