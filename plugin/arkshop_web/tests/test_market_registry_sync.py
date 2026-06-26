"""Sync do overlay ark_species_registry.json → market_species."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")

from ark_species_registry import load_registry_overlay_raw
from market_service import sync_registry_overlay_to_db

ABYSS_REX_BP = "/Game/Abyss/Dinos/Rex/Rex_Character_BP_Abyssal.Rex_Character_BP_Abyssal"


@pytest.fixture()
def db_session(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app import Base
    from market_migrate import MARKET_TABLES

    engine = create_engine(f"sqlite:///{tmp_path / 'market_registry.db'}", future=True)
    market_tables = [Base.metadata.tables[n] for n in MARKET_TABLES if n in Base.metadata.tables]
    Base.metadata.create_all(bind=engine, tables=market_tables)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def test_registry_overlay_has_abyss_entries():
    overlay = load_registry_overlay_raw()
    keys = {str(e.get("species_key")) for e in overlay}
    assert "abyss_rex_abyssal" in keys
    assert "abyss_seaweed" in keys
    assert len(overlay) >= 40


def test_sync_registry_overlay_creates_species(db_session):
    from app import MarketSpecies, MarketSpeciesAlias

    result = sync_registry_overlay_to_db(db_session, only_missing=True)
    assert result["registry_created"] >= 1 or result["registry_updated"] >= 1

    row = (
        db_session.query(MarketSpecies)
        .filter(MarketSpecies.species_key == "abyss_rex_abyssal")
        .first()
    )
    assert row is not None
    assert row.display_name
    assert row.root_value > 0
    assert row.status == "PRE_REGISTERED"

    alias = (
        db_session.query(MarketSpeciesAlias)
        .filter(MarketSpeciesAlias.blueprint_norm.isnot(None))
        .join(MarketSpecies, MarketSpecies.id == MarketSpeciesAlias.species_id)
        .filter(MarketSpecies.species_key == "abyss_rex_abyssal")
        .first()
    )
    assert alias is not None
    assert ABYSS_REX_BP.split(".")[-1].lower() in (alias.blueprint_path or "").lower()


def test_sync_registry_only_missing_skips_existing(db_session):
    first = sync_registry_overlay_to_db(db_session, only_missing=True)
    second = sync_registry_overlay_to_db(db_session, only_missing=True)
    assert second["registry_created"] == 0
    assert second["registry_skipped"] >= first["registry_created"] + first["registry_updated"]
