"""Testes do módulo market_economy."""
from market_economy import (
    calculate_suggested_value,
    load_default_species_map,
    merge_species_from_catalog_item,
    normalize_stat_points,
    size_cap_for_class,
)


def test_ensure_catalog_species_in_defaults_adds_missing(tmp_path, monkeypatch):
    """Itens Type:dino L1 da loja sem defaults recebem stub econômico (BP do catálogo)."""
    import json
    from pathlib import Path

    import market_economy as me

    defaults_path = tmp_path / "market_species_defaults.json"
    defaults_path.write_text(
        json.dumps({
            "species": [{
                "species_key": "rex",
                "display_name": "Rex",
                "blueprint_path": "/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP",
                "catalog_item_id": "rex_femea",
                "catalog_item_ids": ["rex_femea"],
                "root_value": 5000,
                "premium_budget": 10000,
                "tier": "S",
                "dino_role": "ataque",
                "mod_source": "vanilla",
                "pricing_mode": "floor_quality",
                "commerce_channel": "market_p2p",
                "economy_stats": {"health": {"enabled": True}, "melee": {"enabled": True}},
            }],
            "global_stat_labels": {},
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(me, "_DEFAULTS_FILE", defaults_path)

    catalog = {
        "Items": {
            "rex_femea": {
                "Type": "dino",
                "Price": 5000,
                "Dinos": [{
                    "Blueprint": "/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP",
                    "Level": 1,
                }],
            },
            "meraxes_femea": {
                "Type": "dino",
                "Name": "Meraxes Fêmea Nível 1",
                "Price": 15000,
                "Dinos": [{
                    "Blueprint": "/Game/Mods/Meraxes/Dino/Meraxes_Character_BP.Meraxes_Character_BP",
                    "Level": 1,
                }],
            },
            "meraxes_snow_femea": {
                "Type": "dino",
                "Name": "Meraxes Snow Fêmea Nível 1",
                "Price": 15000,
                "Dinos": [{
                    "Blueprint": "/Game/Mods/Meraxes/Dino/texture/Varients/X-Snow/SnowMeraxes_Character_BP.SnowMeraxes_Character_BP",
                    "Level": 1,
                }],
            },
        }
    }
    missing = me.find_catalog_dinos_missing_from_defaults(catalog)
    assert {m[0] for m in missing} == {"meraxes_femea", "meraxes_snow_femea"}

    result = me.ensure_catalog_species_in_defaults(catalog, write=True)
    assert result["ok"] is True
    assert result["added"] == 1
    assert "meraxes" in result["species_keys"]

    data = me.load_defaults_file()
    keys = {s["species_key"] for s in data["species"]}
    assert "meraxes" in keys
    meraxes = next(s for s in data["species"] if s["species_key"] == "meraxes")
    assert set(meraxes["catalog_item_ids"]) == {"meraxes_femea", "meraxes_snow_femea"}
    assert meraxes["blueprint_path"].endswith("Meraxes_Character_BP.Meraxes_Character_BP")
    assert meraxes["premium_budget"] > 0
    assert me.find_catalog_dinos_missing_from_defaults(catalog) == []


def test_repo_defaults_cover_all_shop_l1_dinos(monkeypatch):
    """Após sync, nenhum Type:dino L1 do config.json fica de fora dos defaults."""
    import json
    from pathlib import Path

    import market_economy as me
    from market_economy import find_catalog_dinos_missing_from_defaults

    defaults_path = Path(__file__).resolve().parents[1] / "data" / "market_species_defaults.json"
    monkeypatch.setattr(me, "_DEFAULTS_FILE", defaults_path)

    cfg_path = Path(__file__).resolve().parents[2] / "CustomShop" / "configs" / "config.json"
    if not cfg_path.is_file() or not defaults_path.is_file():
        import pytest
        pytest.skip("config.json ou defaults ausente")
    catalog = json.loads(cfg_path.read_text(encoding="utf-8"))
    missing = find_catalog_dinos_missing_from_defaults(catalog)
    assert missing == [], f"Em falta nos defaults: {[m[0] for m in missing]}"


def test_defaults_cover_all_catalog_species_keys(monkeypatch):
    from pathlib import Path

    import market_economy as me
    from market_economy import build_catalog_economy_map

    monkeypatch.setattr(
        me,
        "_DEFAULTS_FILE",
        Path(__file__).resolve().parents[1] / "data" / "market_species_defaults.json",
    )

    catalog_map = build_catalog_economy_map()
    assert "rex_femea" in catalog_map
    assert catalog_map["rex_femea"]["species_key"] == "rex"
    # Bionic pode ser grupo próprio ou alias do rex — aceitar ambos.
    assert catalog_map["bionicrex_femea"]["species_key"] in ("rex", "bionicrex")
    assert catalog_map["bionicgigant_femea"]["species_key"] in ("giga", "bionicgigant")
    assert catalog_map["indominus_femea"]["species_key"] == "indominus"
    assert catalog_map["acrocanto_femea"]["species_key"] in ("acro", "acrocanto")
    defaults = load_default_species_map()
    assert "rex" in defaults
    assert "giga" in defaults
    assert "indominus" in defaults
    carcha = defaults.get("carcha") or catalog_map.get("carcha_femea")
    assert carcha is not None
    assert carcha["diet_class"] == "carnivore"
    assert carcha.get("size_class") in ("large", "medium", "small")
    assert carcha.get("pricing_mode") == "floor_quality"


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


def test_patch_economy_global_config_stat_weights(tmp_path, monkeypatch):
    from market_economy import (
        _defaults_file_path,
        load_stat_weights,
        patch_economy_global_config,
    )

    fake = tmp_path / "market_species_defaults.json"
    fake.write_text(
        __import__("json").dumps(
            {
                "species": [],
                "_stat_weights": {
                    "carnivore": {
                        "health": 0.55,
                        "melee": 0.45,
                        "weight": 0.0,
                        "stamina": 0.0,
                        "speed": 0.0,
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("market_economy._DEFAULTS_FILE", fake)

    patch_economy_global_config(
        {
            "stat_weights": {
                "carnivore": {
                    "health": 0.6,
                    "melee": 0.4,
                    "weight": 0.0,
                    "stamina": 0.0,
                    "speed": 0.0,
                }
            }
        }
    )

    saved = __import__("json").loads(fake.read_text(encoding="utf-8"))
    assert saved["_stat_weights"]["carnivore"]["health"] == 0.6
    assert saved["_stat_weights"]["carnivore"]["melee"] == 0.4
    weights = load_stat_weights()
    assert weights["carnivore"]["health"] == 0.6


def test_ensure_defaults_file_copies_bundled_to_writable(tmp_path, monkeypatch):
    from market_economy import _bundled_defaults_path, _ensure_defaults_file, load_defaults_file

    bundled = tmp_path / "bundle" / "data"
    bundled.mkdir(parents=True)
    bundled_file = bundled / "market_species_defaults.json"
    bundled_file.write_text(
        '{"species": [], "_stat_weights": {"carnivore": {"health": 0.99, "melee": 0.01, "weight": 0, "stamina": 0, "speed": 0}}}',
        encoding="utf-8",
    )
    writable_root = tmp_path / "writable"
    writable_root.mkdir()
    monkeypatch.setattr("market_economy._bundled_defaults_path", lambda: bundled_file)
    monkeypatch.setattr("market_economy._writable_data_dir", lambda: writable_root)
    monkeypatch.setattr("market_economy._DEFAULTS_FILE", None)

    path = _ensure_defaults_file()
    assert path == writable_root / "market_species_defaults.json"
    assert path.is_file()
    data = load_defaults_file()
    assert data["_stat_weights"]["carnivore"]["health"] == 0.99


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
