"""Testes — request_diagnostics (logs HTTP estruturados e snapshot admin)."""
from __future__ import annotations

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import request_diagnostics as rd


@pytest.fixture(autouse=True)
def _reset():
    rd.reset_for_tests()
    yield
    rd.reset_for_tests()


def test_finish_request_logs_slow(caplog):
    rd.REQUEST_LOG_MODE = "slow"
    rd.SLOW_REQUEST_MS = 100
    rd.begin_request(request_id="req1", route="/api/store/bootstrap", method="GET")
    rd._ctx.started -= 0.25  # simula 250ms
    with caplog.at_level(logging.INFO, logger="arkshop_web.request"):
        entry = rd.finish_request(status_code=200)
    assert entry is not None
    assert entry["outcome"] == "ok"
    assert entry["duration_ms"] >= 100
    assert any("http_request" in r.message for r in caplog.records)


def test_finish_request_skips_fast_ok_in_slow_mode(caplog):
    rd.REQUEST_LOG_MODE = "slow"
    rd.SLOW_REQUEST_MS = 5000
    rd.begin_request(request_id="fast", route="/api/health", method="GET")
    with caplog.at_level(logging.INFO, logger="arkshop_web.request"):
        rd.finish_request(status_code=200)
    assert not any("http_request" in r.message for r in caplog.records)


def test_api_error_marks_outcome_error():
    rd.begin_request(request_id="e1", route="/api/config", method="GET")
    rd.set_request_error(api_error="config.json em falta")
    entry = rd.finish_request(status_code=200)
    assert entry["outcome"] == "error"
    assert entry["api_error"] == "config.json em falta"
    slow = rd.recent_slow_requests()
    assert slow and slow[0]["request_id"] == "e1"


def test_record_event_counters_and_recent():
    rd.record_event("config_path_missing", config_path="C:\\ARK\\missing.json")
    rd.record_event("config_path_healed", config_path="C:\\ARK\\ok.json", items_count=10)
    counters = rd.event_counters()
    assert counters["config_path_missing"] == 1
    assert counters["config_path_healed"] == 1
    events = rd.recent_events()
    assert len(events) == 2
    assert events[0]["event"] == "config_path_healed"


def test_diagnostics_snapshot_shape():
    rd.begin_request(request_id="s1", route="/api/admin/diagnostics/database", method="GET")
    rd.set_request_error(http_error="timeout")
    rd.finish_request(status_code=504)
    snap = rd.diagnostics_snapshot()
    assert snap["log_mode"] == rd.REQUEST_LOG_MODE
    assert "recent_slow_requests" in snap
    assert "event_counters" in snap
    assert snap["recent_slow_requests"]


def test_db_wait_accumulates():
    rd.begin_request(request_id="db1", route="/api/test", method="GET")
    rd.add_db_wait_ms(120.0)
    rd.add_db_wait_ms(80.5)
    entry = rd.finish_request(status_code=200)
    assert entry["db_wait_ms"] == 200.5
