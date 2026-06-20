"""Testes stat_points_asb."""
from __future__ import annotations

from stat_points_asb import calculate_value, get_species_data, invert_stat_levels, load_asb_subset


def test_asb_subset_loaded():
    data = load_asb_subset()
    species = data.get("species") or {}
    assert len(species) >= 10


def test_calculate_value_rex_health_level_zero():
    species = get_species_data("rex_femea")
    if not species:
        return
    v = calculate_value(species, 0, 0, 0, 0, dom=True, imprint_bonus=1.0)
    assert v > 1000


def test_invert_rex_melee_roundtrip():
    species = get_species_data("rex_femea")
    if not species:
        return
    target = calculate_value(species, 8, 20, 10, 15, dom=True, imprint_bonus=1.0)
    levels = invert_stat_levels("rex_femea", "melee", target, imprint_pct=1.0)
    assert levels is not None
    lw, lm, ld = levels
    again = calculate_value(species, 8, lw, lm, ld, dom=True, imprint_bonus=1.0)
    assert abs(again - target) <= 0.5
