"""HTTP do mercado — garante JSON (não HTML 500) após init lazy do DB."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as app_module


@pytest.fixture()
def market_client(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'market_http.db'}"
    monkeypatch.setattr(app_module, "_DB_INITIALIZED", True)
    monkeypatch.setattr(app_module, "_ACTIVE_DATABASE_URL", "")
    app_module._configure_database(db_url)
    return app_module.app.test_client()


def test_species_table_returns_json_not_html(market_client):
    """Regressão: session_factory não pode capturar _SessionLocal=None na importação."""
    r = market_client.get("/api/market/species-table")
    assert r.content_type.startswith("application/json")
    data = r.get_json()
    assert data is not None
    assert data.get("ok") is True
    assert "species" in data


def test_listings_returns_json_not_html(market_client):
    r = market_client.get("/api/market/listings?limit=5")
    assert r.content_type.startswith("application/json")
    data = r.get_json()
    assert data is not None
    assert data.get("ok") is True
    assert "listings" in data
