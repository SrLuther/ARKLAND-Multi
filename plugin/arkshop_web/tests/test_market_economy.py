"""Testes do módulo market_economy."""
from market_economy import (
    calculate_suggested_value,
    load_default_species_map,
    merge_species_from_catalog_item,
    normalize_stat_points,
)


def test_defaults_cover_all_catalog_species_keys():
    from market_economy import build_catalog_economy_map

    catalog_map = build_catalog_economy_map()
    assert "rex_femea" in catalog_map
    assert catalog_map["rex_femea"]["species_key"] == "rex"
    assert catalog_map["bionicrex_femea"]["species_key"] == "rex"
    assert catalog_map["bionicgigant_femea"]["species_key"] == "giga"
    assert catalog_map["indominus_femea"]["species_key"] == "indominus"
    assert catalog_map["acrocanto_femea"]["species_key"] == "acro"
    defaults = load_default_species_map()
    assert "rex" in defaults
    assert "giga" in defaults
    assert "indominus" in defaults
    assert defaults["rex"]["multipliers"]["melee"] == 700


def test_calculate_suggested_value_with_breakdown():
    entry = {
        "Type": "dino",
        "Name": "Rex Fêmea",
        "Price": 5000,
        "Dinos": [{"Blueprint": "/Game/.../Rex", "Level": 1}],
    }
    species = merge_species_from_catalog_item("rex_femea", entry)
    assert species.species_key == "rex"
    points = normalize_stat_points(
        {
            "health": {"points": 80},
            "melee": {"points": 59},
            "weight": {"points": 42},
        }
    )
    total, breakdown = calculate_suggested_value(species, points)
    assert total == 5000 + 80 * 78 + 59 * 700 + 42 * 120
    assert breakdown[0]["kind"] == "root"
    assert breakdown[-1]["kind"] == "total"
    assert breakdown[-1]["subtotal"] == total


def test_normalize_stat_points_aliases():
    pts = normalize_stat_points({"hp": 10, "damage": 5, "weight": 3})
    assert pts["health"] == 10
    assert pts["melee"] == 5
    assert pts["weight"] == 3
