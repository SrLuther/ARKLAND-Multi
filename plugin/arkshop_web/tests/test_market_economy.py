"""Testes do módulo market_economy."""
from market_economy import (
    calculate_suggested_value,
    load_default_species_map,
    merge_species_from_catalog_item,
    normalize_stat_points,
)


def test_defaults_cover_all_catalog_species_keys():
    defaults = load_default_species_map()
    assert "rex_femea" in defaults
    assert "giga_femea" in defaults
    assert defaults["rex_femea"]["multipliers"]["melee"] == 700


def test_calculate_suggested_value_with_breakdown():
    entry = {
        "Type": "dino",
        "Name": "Rex Fêmea",
        "Price": 5000,
        "Dinos": [{"Blueprint": "/Game/.../Rex", "Level": 1}],
    }
    species = merge_species_from_catalog_item("rex_femea", entry)
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
