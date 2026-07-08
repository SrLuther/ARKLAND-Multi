"""Comércio P2P — somente dinos criopodáveis em market_species."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")

from ark_species_registry import (
    is_cryopodable_dino_blueprint,
    load_registry_overlay_raw,
    registry_entry_is_commerce_dino,
)
from market_economy import merge_species_from_registry_entry
from market_service import deactivate_non_dino_species, sync_registry_overlay_to_db

ABYSS_REX_BP = "/Game/Abyss/Dinos/Abyssal/Rex/Rex_Character_BP_Abyssal.Rex_Character_BP_Abyssal"
ABYSS_STEEL_BP = (
    "/Game/Abyss/CoreBlueprints/Resources/"
    "PrimalItemResource_HardenedSteelIngot.PrimalItemResource_HardenedSteelIngot"
)
NON_DINO_KEYS = {
    "abyss_seaweed",
    "abyss_manganese",
    "abyss_hardened_steel",
    "abyss_fish_scale",
    "abyss_crystallized_wood",
    "abyss_barnacle",
    "abyss_aqualyrium",
    "abyss_seed_plantspeciesw",
    "abyss_seed_rice",
    "abyss_seed_cucumis",
    "abyss_hover_sail",
    "abyss_hover_skiff",
}


@pytest.fixture()
def db_session(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app import Base
    from market_migrate import MARKET_TABLES

    engine = create_engine(f"sqlite:///{tmp_path / 'market_commerce.db'}", future=True)
    market_tables = [Base.metadata.tables[n] for n in MARKET_TABLES if n in Base.metadata.tables]
    Base.metadata.create_all(bind=engine, tables=market_tables)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def test_is_cryopodable_dino_blueprint():
    assert is_cryopodable_dino_blueprint(ABYSS_REX_BP)
    assert is_cryopodable_dino_blueprint(
        "/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP"
    )
    assert not is_cryopodable_dino_blueprint(ABYSS_STEEL_BP)
    assert not is_cryopodable_dino_blueprint(
        "/Game/Abyss/CoreBlueprints/Items/Consumables/Seeds/PrimalItemConsumable_Seed_Rice.PrimalItemConsumable_Seed_Rice"
    )
    assert not is_cryopodable_dino_blueprint(
        "/Game/Abyss/Dinos/Ships/HoverSkiff/"
        "PrimalItem_Spawner_ThalassianHoverSkiff.PrimalItem_Spawner_ThalassianHoverSkiff"
    )


def test_registry_overlay_filters_non_dinos():
    overlay = load_registry_overlay_raw()
    commerce = [e for e in overlay if registry_entry_is_commerce_dino(e)]
    keys = {str(e.get("species_key")) for e in commerce}
    assert "abyss_rex_abyssal" in keys
    assert "abyss_hardened_steel" not in keys
    assert "abyss_seaweed" not in keys
    assert len(keys) == 28
    assert NON_DINO_KEYS.isdisjoint(keys)


def test_sync_registry_skips_resources(db_session):
    from app import MarketSpecies

    result = sync_registry_overlay_to_db(db_session, only_missing=False)
    assert result["registry_filtered"] == 12
    assert set(result["registry_filtered_keys"]) == NON_DINO_KEYS

    row = db_session.query(MarketSpecies).filter(MarketSpecies.species_key == "abyss_rex_abyssal").first()
    assert row is not None

    steel = db_session.query(MarketSpecies).filter(MarketSpecies.species_key == "abyss_hardened_steel").first()
    assert steel is None


def test_deactivate_non_dino_species(db_session):
    from app import MarketSpecies

    overlay = {str(e["species_key"]): e for e in load_registry_overlay_raw()}
    steel_entry = overlay["abyss_hardened_steel"]
    species, _aliases = merge_species_from_registry_entry(steel_entry)
    row = MarketSpecies(
        species_key=species.species_key,
        catalog_item_id=species.catalog_item_id,
        display_name=species.display_name,
        blueprint_path=species.blueprint_path,
        root_value=species.root_value,
        tier=species.tier,
        status="ACTIVE",
    )
    db_session.add(row)
    db_session.commit()

    result = deactivate_non_dino_species(db_session)
    assert result["deactivated"] == 1
    assert "abyss_hardened_steel" in result["deactivated_keys"]
    db_session.refresh(row)
    assert row.status == "INACTIVE"
