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


def test_market_my_history_includes_buyer_for_seller(market_client):
    """Vendedor deve ver quem comprou no histórico da Minha Loja."""
    from datetime import datetime, timezone

    from app import MarketCryopodVault, MarketListing, MarketPlayerProfile, MarketSpecies

    seller = "76561198000000001"
    buyer = "76561198000000002"
    db = app_module._SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        db.add(
            MarketSpecies(
                species_key="rex_femea",
                catalog_item_id="rex_femea",
                display_name="Rex Fêmea",
                blueprint_path="/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP",
                reference_level=1,
                root_value=5000,
                tier="A",
                status="ACTIVE",
                created_at=now,
                updated_at=now,
            )
        )
        for sid, name in ((seller, "SellerBR"), (buyer, "BuyerBR")):
            db.add(
                MarketPlayerProfile(
                    steam_id=sid,
                    market_display_name=name,
                    commerce_enabled=True,
                    created_at=now,
                    updated_at=now,
                )
            )
        vault = MarketCryopodVault(
            seller_steam_id=seller,
            item_blob=b"\x01",
            blob_hash="histhash1",
            metadata_json="{}",
            species_key="rex_femea",
            uploaded_at=now,
        )
        db.add(vault)
        db.flush()
        listing = MarketListing(
            vault_id=vault.id,
            seller_steam_id=seller,
            species_key="rex_femea",
            status="ACTIVE",
            computed_base_value=5000,
            effective_price=5000,
            custom_name="RexClone",
            metadata_json='{"admin_classification_approved": true}',
            created_at=now,
            updated_at=now,
        )
        db.add(listing)
        db.commit()
        listing_id = listing.id
        db.execute(
            __import__("sqlalchemy").text(
                "INSERT INTO players (steam_id, points) VALUES (:sid, :pts)"
            ),
            {"sid": buyer, "pts": 10000},
        )
        db.commit()
    finally:
        db.close()

    _login(market_client, buyer)
    pr = market_client.post(f"/api/market/listings/{listing_id}/purchase")
    assert pr.status_code == 200
    assert pr.get_json().get("ok") is True

    _login(market_client, seller)
    hr = market_client.get("/api/market/my/history")
    assert hr.status_code == 200
    data = hr.get_json()
    assert data.get("ok") is True
    assert len(data["sales"]) == 1
    assert data["sales"][0]["buyer_steam_id"] == buyer
    assert data["sales"][0]["buyer_display_name"] == "BuyerBR"
    assert data["sales"][0]["delivery_status"] == "aguardando_resgate"
