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
    assert "tier_legend" in data
    assert "S+" in data["tier_legend"]


def test_listings_returns_json_not_html(market_client):
    r = market_client.get("/api/market/listings?limit=5")
    assert r.content_type.startswith("application/json")
    data = r.get_json()
    assert data is not None
    assert data.get("ok") is True
    assert "listings" in data


USER_STEAM = "76561197960287930"


def _login(client, steam_id: str = USER_STEAM) -> None:
    with client.session_transaction() as sess:
        sess["steam_id"] = steam_id


def test_market_display_name_persists_without_prior_migration(market_client):
    """Regressão: salvar nome cria market_player_profile mesmo se migrate ainda não rodou."""
    _login(market_client)
    r = market_client.patch(
        "/api/market/profile/display-name",
        json={"market_display_name": "SellerBR"},
    )
    assert r.content_type.startswith("application/json")
    data = r.get_json()
    assert data is not None
    assert data.get("ok") is True
    assert data.get("market_display_name") == "SellerBR"

    r2 = market_client.get("/api/market/profile")
    assert r2.status_code == 200
    prof = r2.get_json()
    assert prof.get("ok") is True
    assert prof["profile"]["market_display_name"] == "SellerBR"

    r3 = market_client.get("/api/auth/me")
    me = r3.get_json()
    assert me.get("market_display_name") == "SellerBR"
    assert me.get("needs_display_name") is False


def test_market_display_name_rejects_invalid_chars(market_client):
    _login(market_client)
    r = market_client.patch(
        "/api/market/profile/display-name",
        json={"market_display_name": "Nome Com Espaco"},
    )
    assert r.status_code == 400
    data = r.get_json()
    assert data.get("ok") is False
