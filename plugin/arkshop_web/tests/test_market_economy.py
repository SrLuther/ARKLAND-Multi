"""Testes do módulo market_economy."""
from market_economy import (
    calculate_suggested_value,
    load_default_species_map,
    merge_species_from_catalog_item,
    normalize_stat_points,
    size_cap_for_class,
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
    assert defaults["carcha_femea"]["diet_class"] == "carnivore"
    assert defaults["carcha_femea"]["size_class"] == "large"


def test_carcha_zero_points_equals_root():
    entry = {
        "Type": "dino",
        "Name": "Carcha",
        "Price": 29994,
        "Dinos": [{"Blueprint": "/Game/.../Carcha", "Level": 1}],
    }
    species = merge_species_from_catalog_item("carcha_femea", entry)
    points = normalize_stat_points({})
    total, breakdown = calculate_suggested_value(species, points)
    assert total == 29994
    assert breakdown[0]["kind"] == "root"
    assert breakdown[-1]["subtotal"] == 29994


def test_carcha_moderate_stats():
    entry = {
        "Type": "dino",
        "Name": "Carcha",
        "Price": 29994,
        "Dinos": [{"Blueprint": "/Game/.../Carcha", "Level": 1}],
    }
    species = merge_species_from_catalog_item("carcha_femea", entry)
    points = normalize_stat_points(
        {
            "health": {"points_base": 78},
            "melee": {"points_base": 105},
        }
    )
    total, breakdown = calculate_suggested_value(species, points)
    assert total == 125_825
    stat_rows = [r for r in breakdown if r["kind"] == "stat"]
    assert len(stat_rows) == 2


def test_carcha_top_stats_hits_cap():
    entry = {
        "Type": "dino",
        "Name": "Carcha",
        "Price": 29994,
        "Dinos": [{"Blueprint": "/Game/.../Carcha", "Level": 1}],
    }
    species = merge_species_from_catalog_item("carcha_femea", entry)
    points = normalize_stat_points(
        {
            "health": {"points_base": 254},
            "melee": {"points_base": 254},
        }
    )
    total, _breakdown = calculate_suggested_value(species, points)
    assert total == size_cap_for_class("large")


def test_normalize_stat_points_aliases():
    pts = normalize_stat_points({"hp": 10, "damage": 5, "weight": 3})
    assert pts["health"] == 10
    assert pts["melee"] == 5
    assert pts["weight"] == 3


def test_normalize_prefers_points_base_over_total_points():
    pts = normalize_stat_points(
        {
            "health": {"points_base": 78, "points": 120},
            "melee": {"points_base": 12, "points": 40},
        }
    )
    assert pts["health"] == 78
    assert pts["melee"] == 12


def test_normalize_ignores_raw_value_without_points():
    pts = normalize_stat_points(
        {
            "health": {"value": 30470},
            "melee": {"value": 0},
            "weight": {"value": 1326},
        }
    )
    assert pts["health"] == 0
    assert pts["melee"] == 0
    assert pts["weight"] == 0


def test_patch_species_economy_meta(tmp_path, monkeypatch):
    from market_economy import (
        _defaults_file_path,
        load_default_species_map,
        patch_species_economy_meta,
        species_economy_meta_from_defaults,
    )

    src = _defaults_file_path()
    data = __import__("json").loads(src.read_text(encoding="utf-8"))
    fake = tmp_path / "defaults.json"
    fake.write_text(__import__("json").dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr("market_economy._DEFAULTS_FILE", fake)

    updated = patch_species_economy_meta(
        "carcha_femea",
        {
            "diet_class": "carnivore",
            "size_class": "medium",
            "economy_stats": {"health": True, "melee": False, "weight": True},
        },
    )
    assert updated is not None
    meta = species_economy_meta_from_defaults("carcha_femea")
    assert meta["size_class"] == "medium"
    assert meta["economy_stats"]["health"]["enabled"] is True
    assert meta["economy_stats"]["melee"]["enabled"] is False
    assert meta["economy_stats"]["weight"]["enabled"] is True


def test_deinonychus_weight_override_pricing():
    entry = {
        "Type": "dino",
        "Name": "Deinonychus",
        "Price": 8000,
        "Dinos": [{"Blueprint": "/Game/.../Deino", "Level": 1}],
    }
    species = merge_species_from_catalog_item("deinonychus_femea", entry)
    assert species.size_class == "small"
    points = normalize_stat_points(
        {"melee": {"points_base": 100}, "stamina": {"points_base": 50}}
    )
    total, breakdown = calculate_suggested_value(species, points)
    assert total > 8000
    stat_rows = [r for r in breakdown if r["kind"] == "stat"]
    assert len(stat_rows) == 2
    dm = next(r for r in stat_rows if r["stat_key"] == "melee")
    st = next(r for r in stat_rows if r["stat_key"] == "stamina")
    assert dm["subtotal"] > st["subtotal"]


def test_custom_pricing_mode(tmp_path, monkeypatch):
    from market_economy import _defaults_file_path, patch_species_economy_meta

    src = _defaults_file_path()
    data = __import__("json").loads(src.read_text(encoding="utf-8"))
    fake = tmp_path / "defaults.json"
    fake.write_text(__import__("json").dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr("market_economy._DEFAULTS_FILE", fake)

    patch_species_economy_meta(
        "carcha_femea",
        {
            "pricing_mode": "custom",
            "economy_stats": {
                "health": {"enabled": True, "rate_per_point": 100},
                "melee": {"enabled": True, "rate_per_point": 200},
            },
        },
    )

    entry = {
        "Type": "dino",
        "Name": "Carcha",
        "Price": 29994,
        "Dinos": [{"Blueprint": "/Game/.../Carcha", "Level": 1}],
    }
    species = merge_species_from_catalog_item("carcha_femea", entry)
    species.pricing_mode = "custom"
    species.economy_stats["health"] = {"enabled": True, "rate_per_point": 100}
    species.economy_stats["melee"] = {"enabled": True, "rate_per_point": 200}
    points = normalize_stat_points(
        {"health": {"points_base": 10}, "melee": {"points_base": 5}}
    )
    total, breakdown = calculate_suggested_value(species, points)
    assert total == 29994 + 10 * 100 + 5 * 200
    assert any(r.get("pricing_mode") == "custom" or r.get("kind") == "mode" for r in breakdown)


def test_legacy_multipliers_mode():
    entry = {
        "Type": "dino",
        "Name": "Rex",
        "Price": 5000,
        "Dinos": [{"Blueprint": "/Game/.../Rex", "Level": 1}],
    }
    species = merge_species_from_catalog_item("rex_femea", entry)
    species.pricing_mode = "legacy_multipliers"
    points = normalize_stat_points({"melee": {"points_base": 10}})
    total, breakdown = calculate_suggested_value(species, points)
    assert total == 5000 + 10 * species.multipliers["melee"].multiplier
    assert any(r.get("kind") == "mode" for r in breakdown)
