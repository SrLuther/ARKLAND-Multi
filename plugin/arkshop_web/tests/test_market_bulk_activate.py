"""Ativar em massa espécies já PRE_REGISTERED e manter a listagem após sync 0/0."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as _app_module
from app import _configure_database

BP = "/Game/Mods/PFH/Dinos/Spirit/SpiritDragon_Character_BP.SpiritDragon_Character_BP"
BP_OFF = "/Game/Mods/PFH/Dinos/Reaper/EvilReaper_Character_BP.EvilReaper_Character_BP"

KEYS = (
    "pfh_spirit_dragon",
    "pfh_spirit_manticore",
    "pfh_evil_reaper_empress",
)


def _l200_catalog() -> dict:
    """Catálogo só com nível 200 — o feed L1 não cria nem atualiza nada."""
    items = {}
    for key in KEYS:
        items[key] = {
            "Type": "dino",
            "Name": key,
            "Price": 398000,
            "Dinos": [{"Blueprint": BP, "Level": 200}],
        }
    return {"ShopItems": items}


def _l1_catalog() -> dict:
    items = {}
    for key in KEYS:
        items[key] = {
            "Type": "dino",
            "Name": key,
            "Price": 398000,
            "Dinos": [{"Blueprint": BP, "Level": 1}],
        }
    return {"ShopItems": items}


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    monkeypatch.setattr(_app_module, "_DB_INITIALIZED", True)
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(f"sqlite:///{tmp_path / 'market_bulk_activate.db'}")
    db = _app_module._SessionLocal()
    try:
        yield db
    finally:
        db.close()
        _configure_database("")


def _noop_side_feeds(monkeypatch) -> None:
    import market_service as ms

    monkeypatch.setattr(
        ms,
        "ensure_catalog_species_in_defaults",
        lambda *a, **k: {"ok": True, "added": 0, "species_keys": []},
    )
    monkeypatch.setattr(ms, "sync_reference_species_to_db", lambda *a, **k: {})
    monkeypatch.setattr(ms, "sync_registry_overlay_to_db", lambda *a, **k: {})


def _seed(db) -> None:
    from app import MarketSpecies

    for key in KEYS:
        db.add(
            MarketSpecies(
                species_key=key,
                catalog_item_id=key,
                display_name=key,
                blueprint_path=BP,
                reference_level=200,
                root_value=398000,
                tier="S",
                status="PRE_REGISTERED",
            )
        )
    db.add(
        MarketSpecies(
            species_key="pfh_admin_off",
            catalog_item_id="pfh_admin_off",
            display_name="Desativado",
            blueprint_path=BP_OFF,
            reference_level=1,
            root_value=1000,
            tier="B",
            status="INACTIVE",
        )
    )
    db.commit()


def _status(db, key: str) -> str:
    from app import MarketSpecies

    row = db.query(MarketSpecies).filter(MarketSpecies.species_key == key).one()
    db.refresh(row)
    return row.status


def test_bulk_activate_pre_registered_and_listing_after_noop_sync(db_session, monkeypatch):
    from market_service import (
        bulk_pre_register_catalog_items,
        feed_catalog_to_market,
        list_admin_species,
    )

    _noop_side_feeds(monkeypatch)
    _seed(db_session)

    listed = list_admin_species(db_session, _l200_catalog())
    listed_keys = {row["species_key"] for row in listed}
    assert set(KEYS) <= listed_keys
    assert "pfh_admin_off" not in listed_keys

    # SYNC + ATIVAR TODAS com catálogo L200: nada muda no feed (0/0),
    # mas as pré-cadastradas passam a ACTIVE.
    sync = feed_catalog_to_market(
        db_session,
        _l200_catalog(),
        activate=True,
        level1_only=True,
        only_missing=False,
        include_reference_and_registry=True,
    )
    assert sync["created"] == 0
    assert sync["updated"] == 0
    assert sync["activated"] == len(KEYS)
    for key in KEYS:
        assert _status(db_session, key) == "ACTIVE"
    assert _status(db_session, "pfh_admin_off") == "INACTIVE"

    after_activate = list_admin_species(db_session, _l200_catalog())
    by_key = {row["species_key"]: row for row in after_activate}
    for key in KEYS:
        assert by_key[key]["status"] == "ACTIVE"

    # Volta ao pré-cadastro para o botão «Pré-cadastrar + ativar» (only_missing).
    from app import MarketSpecies

    for key in KEYS:
        row = db_session.query(MarketSpecies).filter(MarketSpecies.species_key == key).one()
        row.status = "PRE_REGISTERED"
    db_session.commit()

    bulk = bulk_pre_register_catalog_items(
        db_session,
        _l1_catalog(),
        only_missing=True,
        activate=True,
    )
    assert bulk["created"] == 0
    assert bulk["updated"] == 0
    assert bulk["activated"] == len(KEYS)
    for key in KEYS:
        assert _status(db_session, key) == "ACTIVE"
    assert _status(db_session, "pfh_admin_off") == "INACTIVE"

    # Sync seguinte sem mudança no catálogo não pode esvaziar a listagem.
    noop = feed_catalog_to_market(
        db_session,
        _l200_catalog(),
        activate=False,
        level1_only=True,
        only_missing=False,
        include_reference_and_registry=True,
    )
    assert noop["created"] == 0
    assert noop["updated"] == 0
    assert int(noop.get("activated") or 0) == 0

    still = list_admin_species(db_session, _l200_catalog())
    still_keys = {row["species_key"] for row in still}
    assert set(KEYS) <= still_keys
    assert len(still) >= len(KEYS)
    for key in KEYS:
        assert _status(db_session, key) == "ACTIVE"
