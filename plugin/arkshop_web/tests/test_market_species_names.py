"""Nomes de espécie: Comércio separado da loja + sync preserva edição."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as app_module
from market_service import sync_catalog_to_db, update_species_display_name


SAMPLE_CATALOG = {
    "Items": {
        "rex_femea": {
            "Type": "dino",
            "Name": "Rex Fêmea nível 1",
            "Price": 5000,
            "Dinos": [{"Blueprint": "/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP", "Level": 1}],
        }
    }
}


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'market_names.db'}"
    monkeypatch.setattr(app_module, "_DB_INITIALIZED", True)
    monkeypatch.setattr(app_module, "_ACTIVE_DATABASE_URL", "")
    app_module._configure_database(db_url)
    db = app_module._SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_sync_does_not_overwrite_commerce_display_name(db_session):
    sync_catalog_to_db(db_session, SAMPLE_CATALOG)
    update_species_display_name(db_session, "rex", "Rex Base")

    SAMPLE_CATALOG["Items"]["rex_femea"]["Name"] = "Rex Fêmea nível 1 — NOVO NA LOJA"
    sync_catalog_to_db(db_session, SAMPLE_CATALOG)

    from app import MarketSpecies

    row = db_session.query(MarketSpecies).filter(MarketSpecies.species_key == "rex").first()
    assert row is not None
    assert row.display_name == "Rex Base"
    assert row.root_value == 5000


def test_sync_reset_display_names_flag(db_session):
    sync_catalog_to_db(db_session, SAMPLE_CATALOG)
    update_species_display_name(db_session, "rex", "Rex")

    SAMPLE_CATALOG["Items"]["rex_femea"]["Name"] = "Rex Fêmea nível 1"
    sync_catalog_to_db(db_session, SAMPLE_CATALOG, reset_display_names=True)

    from app import MarketSpecies

    row = db_session.query(MarketSpecies).filter(MarketSpecies.species_key == "rex").first()
    assert row.display_name == "Rex"


def test_patch_species_display_name_http(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'market_names_http.db'}"
    monkeypatch.setattr(app_module, "_DB_INITIALIZED", True)
    monkeypatch.setattr(app_module, "_ACTIVE_DATABASE_URL", "")
    monkeypatch.setattr(app_module, "_is_admin_steamid", lambda sid: sid == "76561198000000001")
    app_module._configure_database(db_url)

    client = app_module.app.test_client()
    with app_module._SessionLocal() as db:
        sync_catalog_to_db(db, SAMPLE_CATALOG)

    with client.session_transaction() as sess:
        sess["steam_id"] = "76561198000000001"

    r = client.patch(
        "/api/market/admin/species/rex",
        json={"display_name": "Rex"},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["display_name"] == "Rex"
    assert "shop_catalog_name" in data


def test_filter_commerce_dino_rows_batch_aliases(db_session):
    """_filter_commerce_dino_rows carrega aliases num único SELECT."""
    sync_catalog_to_db(db_session, SAMPLE_CATALOG)
    from app import MarketSpecies

    rows = db_session.query(MarketSpecies).filter(MarketSpecies.status != "INACTIVE").all()
    assert rows

    alias_queries = {"n": 0}
    real_query = db_session.query

    def _counting_query(*args, **kwargs):
        q = real_query(*args, **kwargs)
        if args and getattr(args[0], "__name__", "") == "MarketSpeciesAlias":
            alias_queries["n"] += 1
        return q

    db_session.query = _counting_query  # type: ignore[method-assign]
    from market_service import _filter_commerce_dino_rows

    filtered, alias_map = _filter_commerce_dino_rows(db_session, rows)
    assert filtered
    assert alias_queries["n"] == 1
    assert isinstance(alias_map, dict)
