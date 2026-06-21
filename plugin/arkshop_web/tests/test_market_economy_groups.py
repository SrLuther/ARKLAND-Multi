"""Grupos econômicos — variantes Rex compartilham tabela."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")

from market_economy import load_default_species_map, merge_economy_group, normalize_blueprint
from market_listings import resolve_species
from market_service import sync_catalog_to_db

REX_BP = "/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP"
TEK_REX_BP = "/Game/PrimalEarth/Dinos/Rex/BionicRex_Character_BP.BionicRex_Character_BP"
VOLCANO_REX_BP = "/Game/Genesis2/Dinos/VolcanoRex/VolcanoRex_Character_BP.VolcanoRex_Character_BP"
GIGA_BP = "/Game/PrimalEarth/Dinos/Giganotosaurus/Gigant_Character_BP.Gigant_Character_BP"
BIONIC_GIGA_BP = "/Game/PrimalEarth/Dinos/Giganotosaurus/BionicGigant_Character_BP.BionicGigant_Character_BP"
INDOMINUS_BP = "/Game/Mods/IndominusRex/Models/IndominusRex_Character_BP.IndominusRex_Character_BP"
DOM_REX_BP = "/Game/Mods/Indominus/Dino/Indominus_Character_BP.Indominus_Character_BP"
DREAD_WYVERN_BP = "/Game/Mods/Funny_Creatures/DreadWyvern/Wyvern_Character_BP_Dread.Wyvern_Character_BP_Dread"
ACRO_BP = "/Game/Mods/Additions_Pack/Acrocanthosaurus/Dinos/Acrocanthosaurus_Character_BP.Acrocanthosaurus_Character_BP"
SCORCHED_ACRO_BP = "/Game/Mods/Additions_Pack/Acrocanthosaurus/Dinos/Scorched_Acrocanthosaurus_Character_BP.Scorched_Acrocanthosaurus_Character_BP"

CATALOG = {
    "Items": {
        "rex_femea": {
            "Type": "dino",
            "Name": "Rex Fêmea nível 1",
            "Price": 5000,
            "Dinos": [{"Blueprint": REX_BP, "Level": 1}],
        },
        "bionicrex_femea": {
            "Type": "dino",
            "Name": "Rex Tek Fêmea",
            "Price": 8000,
            "Dinos": [{"Blueprint": TEK_REX_BP, "Level": 1}],
        },
        "volcanorex_femea": {
            "Type": "dino",
            "Name": "Rex Volcano Fêmea",
            "Price": 7000,
            "Dinos": [{"Blueprint": VOLCANO_REX_BP, "Level": 1}],
        },
        "giga_femea": {
            "Type": "dino",
            "Name": "Giga Fêmea",
            "Price": 15000,
            "Dinos": [{"Blueprint": GIGA_BP, "Level": 1}],
        },
        "bionicgigant_femea": {
            "Type": "dino",
            "Name": "Bionic Giga Fêmea",
            "Price": 25000,
            "Dinos": [{"Blueprint": BIONIC_GIGA_BP, "Level": 1}],
        },
        "indominus_femea": {
            "Type": "dino",
            "Name": "Indominus Fêmea",
            "Price": 50000,
            "Dinos": [{"Blueprint": INDOMINUS_BP, "Level": 1}],
        },
        "acrocanto_femea": {
            "Type": "dino",
            "Name": "Acrocantossauro Fêmea",
            "Price": 8000,
            "Dinos": [{"Blueprint": ACRO_BP, "Level": 1}],
        },
    }
}


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    import app as app_module

    db_url = f"sqlite:///{tmp_path / 'market_groups.db'}"
    monkeypatch.setattr(app_module, "_DB_INITIALIZED", True)
    monkeypatch.setattr(app_module, "_ACTIVE_DATABASE_URL", "")
    app_module._configure_database(db_url)
    db = app_module._SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_merge_economy_group_rex_variants():
    items = [
        ("rex_femea", CATALOG["Items"]["rex_femea"]),
        ("bionicrex_femea", CATALOG["Items"]["bionicrex_femea"]),
        ("volcanorex_femea", CATALOG["Items"]["volcanorex_femea"]),
    ]
    defaults = load_default_species_map()["rex"]
    species, aliases = merge_economy_group("rex", items, defaults=defaults, catalog=CATALOG)
    assert species.species_key == "rex"
    assert species.display_name == "Rex"
    assert species.root_value == 5000
    assert len(aliases) == 3
    norms = {a["blueprint_norm"] for a in aliases}
    assert normalize_blueprint(TEK_REX_BP) in norms


def test_sync_creates_one_rex_row_with_aliases(db_session):
    sync_catalog_to_db(db_session, CATALOG)
    from app import MarketSpecies, MarketSpeciesAlias

    rows = db_session.query(MarketSpecies).filter(MarketSpecies.species_key == "rex").all()
    assert len(rows) == 1
    aliases = db_session.query(MarketSpeciesAlias).filter(MarketSpeciesAlias.species_id == rows[0].id).all()
    assert len(aliases) == 3


def test_resolve_tek_rex_blueprint_to_rex_economy(db_session):
    sync_catalog_to_db(db_session, CATALOG, activate=True)
    row = resolve_species(db_session, blueprint=TEK_REX_BP)
    assert row is not None
    assert row.species_key == "rex"
    assert row.root_value == 5000


def test_merge_giga_group():
    defaults = load_default_species_map()["giga"]
    items = [
        ("giga_femea", CATALOG["Items"]["giga_femea"]),
        ("bionicgigant_femea", CATALOG["Items"]["bionicgigant_femea"]),
    ]
    species, aliases = merge_economy_group("giga", items, defaults=defaults, catalog=CATALOG)
    assert species.species_key == "giga"
    assert species.root_value == 15000
    assert len(aliases) >= 2


def test_indominus_includes_domination_rex_alias(db_session):
    sync_catalog_to_db(db_session, CATALOG, activate=True)
    row = resolve_species(db_session, blueprint=DOM_REX_BP)
    assert row is not None
    assert row.species_key == "indominus"
    assert row.root_value == 50000


def test_acro_includes_scorched_variant_alias(db_session):
    sync_catalog_to_db(db_session, CATALOG, activate=True)
    row = resolve_species(db_session, blueprint=SCORCHED_ACRO_BP)
    assert row is not None
    assert row.species_key == "acro"
    assert row.root_value == 8000


def test_sync_registers_reference_mod_species(db_session):
    result = sync_catalog_to_db(db_session, CATALOG)
    assert "dread_wyvern" in result.get("reference_keys", [])
    from app import MarketSpecies

    dread = db_session.query(MarketSpecies).filter(MarketSpecies.species_key == "dread_wyvern").first()
    assert dread is not None
    assert dread.root_value == 42000
    row = resolve_species(db_session, blueprint=DREAD_WYVERN_BP)
    assert row is not None
    assert row.species_key == "dread_wyvern"
