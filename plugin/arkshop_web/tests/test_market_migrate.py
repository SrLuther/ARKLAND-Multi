"""Testes de migração automática do mercado."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as _app_module
from app import _configure_database
from market_migrate import MARKET_TABLES, ensure_market_schema, schema_status


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'migrate_test.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    yield
    _configure_database("")


def test_ensure_market_schema_creates_tables():
    engine = _app_module._ENGINE
    assert engine is not None
    result = ensure_market_schema(engine, bootstrap=False)
    assert result["ok"] is True
    assert result["still_missing"] == []
    status = schema_status(engine)
    assert status["ok"] is True
    for name in MARKET_TABLES:
        assert status["tables"][name] is True
