"""Testes — instrumentação DB (pool_wait_ms vs query_ms) e diagnóstico admin."""
from __future__ import annotations

import os
import sys
import time

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db_diagnostics as diag


@pytest.fixture(autouse=True)
def _reset_diag():
    diag.reset_stats_for_tests()
    yield
    diag.reset_stats_for_tests()


def test_sql_fingerprint_strips_literals():
    fp = diag.sql_fingerprint("SELECT * FROM users WHERE id = 42 AND name = 'griao'")
    assert "42" not in fp
    assert "griao" not in fp
    assert "?" in fp


def test_record_separates_pool_wait_and_query():
    diag.record_pool_wait_ms(1500.0)
    diag.record_query(statement="SELECT 1", duration_ms=5.0)
    diag.record_connect_ms(800.0)
    stats = diag.aggregate_stats()
    assert stats["pool_wait_max_ms"] == 1500.0
    assert stats["connect_max_ms"] == 800.0
    assert stats["queries_avg_ms"] == 5.0
    # Com DB vazio, prova: tempo está em pool/connect, não em query
    assert stats["pool_wait_max_ms"] > stats["queries_avg_ms"]
    assert stats["connect_max_ms"] > stats["queries_avg_ms"]


def test_slow_query_recorded_above_threshold():
    diag.set_request_context(endpoint="/api/admin/test", request_id="abc")
    diag.record_query(statement="SELECT * FROM orders WHERE steam_id = 'x'", duration_ms=1200.0)
    slow = diag.recent_slow_queries()
    assert slow
    assert slow[0]["duration_ms"] == 1200.0
    assert slow[0]["endpoint"] == "/api/admin/test"
    assert "steam_id" in slow[0]["fingerprint"]
    assert "'x'" not in slow[0]["fingerprint"]


def test_attach_engine_listeners_measures_query(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'diag.db'}", future=True)
    diag.attach_engine_listeners(engine)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        conn.commit()
    stats = diag.aggregate_stats()
    assert stats["queries_total"] >= 1


def test_pool_wait_via_mark_checkout(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'pw.db'}",
        future=True,
        pool_size=1,
        max_overflow=0,
    )
    diag.attach_engine_listeners(engine)
    Session = sessionmaker(bind=engine, future=True)

    diag.mark_checkout_started()
    time.sleep(0.05)  # simula espera antes do checkout
    db = Session()
    try:
        db.execute(text("SELECT 1"))
    finally:
        db.close()

    stats = diag.aggregate_stats()
    assert stats["pool_wait_samples"] >= 1
    assert (stats["pool_wait_max_ms"] or 0) >= 40


def test_probe_database_sqlite(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'probe.db'}", future=True)
    diag.attach_engine_listeners(engine)
    Session = sessionmaker(bind=engine, future=True)

    class _Scoped:
        def __call__(self):
            return Session()

        def remove(self):
            pass

    result = diag.probe_database(
        engine,
        _Scoped(),
        safe_db_fields=lambda u: {"host": "127.0.0.1", "database": "probe"},
        active_url="sqlite:///probe.db",
    )
    assert result["ok"] is True
    assert "ping_pooled_ms" in result
    assert result["ping_pooled_ms"] is not None
    assert "fresh_connect_ms" in result
    assert "pool" in result
    assert "aggregates" in result
    assert isinstance(result.get("diagnosis_hints"), list)
    assert "requests" in result
    assert "recent_slow_requests" in result["requests"]


def test_request_db_wait_accumulates_on_checkout(tmp_path):
    import request_diagnostics as rd

    rd.reset_for_tests()
    diag.set_request_context(endpoint="/api/test", request_id="pw2")
    engine = create_engine(
        f"sqlite:///{tmp_path / 'pw2.db'}",
        future=True,
        pool_size=1,
        max_overflow=0,
    )
    diag.attach_engine_listeners(engine)
    Session = sessionmaker(bind=engine, future=True)

    diag.mark_checkout_started()
    db = Session()
    try:
        db.execute(text("SELECT 1"))
    finally:
        db.close()
    assert diag.get_request_db_wait_ms() >= 0
    rd.reset_for_tests()


def test_record_pool_timeout_emits_event():
    import request_diagnostics as rd

    rd.reset_for_tests()
    diag.set_request_context(endpoint="/api/orders", request_id="to1")
    diag.record_pool_timeout(error="QueuePool limit reached")
    counters = rd.event_counters()
    assert counters.get("pool_timeout") == 1
    rd.reset_for_tests()


def test_circuit_opens_after_errors():
    for _ in range(diag._CIRCUIT_THRESHOLD):
        diag.record_query(statement="SELECT 1", duration_ms=0.0, error="gone away")
    assert diag.circuit_is_open() is True
    st = diag.circuit_status()
    assert st["open"] is True
    assert st["state"] == "open"
    diag.record_circuit_success()
    assert diag.circuit_is_open() is False
    assert diag.circuit_status()["state"] == "closed"


def test_successful_query_heals_circuit_failures():
    """Sucesso normal (não só ping diagnostics) zera falhas consecutivas."""
    for _ in range(diag._CIRCUIT_THRESHOLD - 1):
        diag.record_query(statement="SELECT 1", duration_ms=1.0, error="timeout")
    assert diag.circuit_is_open() is False
    assert diag.circuit_status()["failures"] == diag._CIRCUIT_THRESHOLD - 1
    diag.record_query(statement="SELECT 1", duration_ms=2.0)
    assert diag.circuit_status()["failures"] == 0
    assert diag.circuit_status()["state"] == "closed"


def test_half_open_probe_success_closes_circuit():
    for _ in range(diag._CIRCUIT_THRESHOLD):
        diag.record_query(statement="SELECT 1", duration_ms=0.0, error="gone away")
    assert diag.circuit_is_open() is True
    # Expira cooldown → half_open
    diag._circuit_open_until = time.monotonic() - 0.01
    assert diag.circuit_state() == "half_open"
    assert diag.circuit_allow_request() is True  # 1º probe
    assert diag.circuit_allow_request() is False  # restantes bloqueados
    # Probe bem-sucedido
    diag.record_query(statement="SELECT 1", duration_ms=3.0)
    assert diag.circuit_status()["state"] == "closed"
    assert diag.circuit_allow_request() is True


def test_half_open_probe_failure_reopens():
    for _ in range(diag._CIRCUIT_THRESHOLD):
        diag.record_query(statement="SELECT 1", duration_ms=0.0, error="gone away")
    diag._circuit_open_until = time.monotonic() - 0.01
    assert diag.circuit_allow_request() is True
    diag.record_query(statement="SELECT 1", duration_ms=0.0, error="still down")
    assert diag.circuit_is_open() is True
    assert diag.circuit_status()["state"] == "open"
    assert diag.circuit_status()["cooldown_remaining_s"] > 0


def test_circuit_status_does_not_consume_probe():
    for _ in range(diag._CIRCUIT_THRESHOLD):
        diag.record_query(statement="SELECT 1", duration_ms=0.0, error="gone away")
    diag._circuit_open_until = time.monotonic() - 0.01
    st1 = diag.circuit_status()
    st2 = diag.circuit_status()
    assert st1["state"] == "half_open"
    assert st2["state"] == "half_open"
    assert st1["probe_in_flight"] is False
    assert diag.circuit_allow_request() is True
    assert diag.circuit_status()["probe_in_flight"] is True
