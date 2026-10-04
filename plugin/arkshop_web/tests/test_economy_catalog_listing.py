"""Economia — Comércio lista só o catálogo da loja e calcula R por linha."""
from __future__ import annotations

import json
from pathlib import Path

import market_economy as me

_HTML = Path(__file__).resolve().parents[1] / "static" / "index.html"

_REX_BP = "/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP"
_GHOST_BP = "/Game/Mods/Ghost/Ghost_Character_BP.Ghost_Character_BP"
_BARY_BP = "/Game/PrimalEarth/Dinos/Baryonyx/Baryonyx_Character_BP.Baryonyx_Character_BP"


def _defaults() -> dict:
    return {
        "_floor_quality": {
            "enabled": True,
            "market_absolute_max": 150_000,
            "gamma": 0.82,
        },
        "species": [
            {
                "species_key": "ghost_only",
                "display_name": "Fantasma",
                "root_value": 9999,
                "premium_budget": 1111,
                "tier": "C",
                "dino_role": "utilitario",
                "pricing_mode": "floor_quality",
                "catalog_item_id": "ghost_only",
                "blueprint_path": _GHOST_BP,
            },
            {
                "species_key": "rex",
                "display_name": "Rex",
                "root_value": 1,
                "tier": "A",
                "dino_role": "utilitario",
                "pricing_mode": "proportional",
                "catalog_item_id": "rex_femea",
                "reference_catalog_item_id": "rex_femea",
                "blueprint_path": _REX_BP,
            },
        ],
    }


def _catalog() -> dict:
    return {
        "Items": {
            "rex_femea": {
                "Type": "dino",
                "Name": "Rex Fêmea Nível 1",
                "Price": 18000,
                "Dinos": [{"Blueprint": _REX_BP, "Level": 1}],
            },
            "rex_femea_l200": {
                "Type": "dino",
                "Name": "Rex Fêmea Nível 200",
                "Price": 72000,
                "Dinos": [{"Blueprint": _REX_BP, "Level": 200}],
            },
            "baryonyx": {
                "Type": "dino",
                "Name": "Baryonyx Fêmea Nível 1",
                "Price": 4242,
                "Dinos": [{"Blueprint": _BARY_BP, "Level": 1}],
            },
            "solo_alto": {
                "Type": "dino",
                "Name": "Só L200",
                "Price": 50000,
                "Dinos": [
                    {
                        "Blueprint": "/Game/Mods/Only/Only_Character_BP.Only_Character_BP",
                        "Level": 200,
                    }
                ],
            },
        }
    }


def _use_defaults(tmp_path, monkeypatch) -> None:
    path = tmp_path / "market_species_defaults.json"
    path.write_text(json.dumps(_defaults()), encoding="utf-8")
    monkeypatch.setattr(me, "_DEFAULTS_FILE", path)
    me.invalidate_defaults_cache()


def test_listing_excludes_defaults_only_and_keeps_catalog_species(tmp_path, monkeypatch):
    _use_defaults(tmp_path, monkeypatch)
    listed = me.list_species_economy_meta(_catalog())
    rows = {row["catalog_item_id"]: row for row in listed}

    assert "ghost_only" not in {row["species_key"] for row in listed}
    assert "ghost_only" not in rows
    rex = rows["rex_femea"]
    assert rex["display_name"] == "Rex Fêmea Nível 1"
    assert rex["species_key"] == "rex"
    assert rex["dino_role"] == "ataque"
    assert rex["tier"] == "S"
    assert rex["pricing_mode"] == "floor_quality"
    # R = preço da linha ÷ nível. L1: 18000/1. Não é o root_value 1 do cache.
    assert rex["shop_price"] == 18000
    assert rex["root_value"] == 18000
    assert rex["reference_level"] == 1
    # Cache proportional sem B não zera o prêmio: volta o floor_quality do repo.
    assert rex["premium_budget"] == 90000
    assert rex["bonus_space"] == 90000
    assert rex["size_cap"] == 600_000
    l200 = rows["rex_femea_l200"]
    assert l200["shop_price"] == 72000
    assert l200["reference_level"] == 200
    assert l200["root_value"] == 360
    assert l200["root_value"] != rex["root_value"]
    bary = rows["baryonyx"]
    assert bary["root_value"] == 4242
    assert bary["bonus_space"] == 31500
    assert bary["dino_role"] == "ataque"
    assert bary["tier"] == "B"
    assert bary["size_cap"] == 600_000
    # Nível 200 sem par L1: R = 50000/200. Não se usa média nem se descarta a linha.
    assert rows["solo_alto"]["root_value"] == 250
    assert rows["solo_alto"]["shop_price"] == 50000
    assert rows["solo_alto"]["dino_role"] == ""
    assert rows["solo_alto"]["bonus_space"] == 0


def test_listing_without_catalog_is_empty(tmp_path, monkeypatch):
    _use_defaults(tmp_path, monkeypatch)
    assert me.list_species_economy_meta(None) == []
    assert me.list_species_economy_meta({}) == []


def test_db_status_does_not_replace_floor_quality_prices():
    species = [
        {
            "species_key": "rex",
            "root_value": 18000,
            "bonus_space": 90000,
            "premium_budget": 90000,
            "size_cap": 150_000,
        }
    ]

    class _Row:
        status = "ACTIVE"
        root_value = 3000

    me.attach_economy_db_status(species, {"rex": _Row()})
    assert species[0]["db_status"] == "ACTIVE"
    assert species[0]["root_value"] == 18000
    assert species[0]["bonus_space"] == 90000
    assert species[0]["bonus_space"] != 150_000 - 3000


def test_economy_table_columns_do_not_collapse():
    html = _HTML.read_text(encoding="utf-8")
    start = html.find('id="page-market-economy-admin"')
    assert start > 0
    style_end = html.find("</style>", start)
    style = html[start:style_end]
    assert ".me-econ-scroll" in style
    assert "overflow-x: auto" in style
    assert ".me-econ-table th" in style
    assert ".me-econ-table td" in style
    assert "padding: 8px 14px" in style
    assert "white-space: nowrap" in style
    assert "border-collapse: separate" in style

    fn_start = html.find("function renderMarketEconomySpecies")
    fn_end = html.find("let _marketEconomyEditing", fn_start)
    fn = html[fn_start:fn_end]
    assert 'class="me-econ-scroll"' in fn
    assert 'class="me-econ-table"' in fn
    assert "data-table" not in fn
    assert "table-scroll" not in fn
    for cell in (
        "me-econ-role",
        "me-econ-tier",
        "me-econ-r",
        "me-econ-b",
        "me-econ-cap",
    ):
        assert f'class="{cell}"' in fn
    assert "renderMarketEconomySpecies(d.species" in html
    assert "renderMarketEconomySim(d.species" in html
    assert "Price do nível 1" not in fn
    assert "R (L1)" not in fn
    assert "preço ÷ nível" in fn
    assert "600.000" in fn


_ANKY_BP = "/Game/PrimalEarth/Dinos/Ankylosaurus/Ankylo_Character_BP.Ankylo_Character_BP"
_ARGENT_BP = "/Game/PrimalEarth/Dinos/Argentavis/Argent_Character_BP.Argent_Character_BP"
_BASILISK_BP = "/Game/Aberration/Dinos/Basilisk/Basilisk_Character_BP.Basilisk_Character_BP"

_VARIANT_IDS = (
    "pf_alpha_ankylo",
    "ab_ankylosaurus_aberrante",
    "pf_fabled_ankylo",
    "vn_ankylosaurus",
    "x_x_ankylosaurus",
)


def _family_defaults() -> dict:
    return {
        "_floor_quality": {"enabled": True, "market_absolute_max": 150_000, "gamma": 0.82},
        "species": [
            {
                "species_key": "ghost_only",
                "display_name": "Fantasma",
                "root_value": 9999,
                "premium_budget": 1111,
                "tier": "C",
                "dino_role": "utilitario",
                "mod_source": "vanilla",
                "pricing_mode": "floor_quality",
            },
            {
                "species_key": "ankylosaurus",
                "display_name": "Anquilossauro",
                "root_value": 2500,
                "premium_budget": 0,
                "tier": "C",
                "dino_role": "utilitario",
                "mod_source": "vanilla",
                "pricing_mode": "floor_quality",
                "blueprint_path": _ANKY_BP,
                "catalog_item_id": "ankylosaurus",
            },
            {
                "species_key": "pf_alpha_ankylo",
                "display_name": "Alpha Ankylo",
                "root_value": 1,
                "premium_budget": 0,
                "tier": "S",
                "dino_role": "ataque",
                "mod_source": "primal_fear",
                "pricing_mode": "floor_quality",
                "catalog_item_id": "pf_alpha_ankylo",
            },
            {
                "species_key": "argentavis",
                "display_name": "Argentavis",
                "root_value": 3500,
                "premium_budget": 24500,
                "tier": "B",
                "dino_role": "locomocao",
                "mod_source": "vanilla",
                "pricing_mode": "floor_quality",
                "blueprint_path": _ARGENT_BP,
                "catalog_item_id": "argentavis",
            },
            {
                "species_key": "basilisk",
                "display_name": "Basilisco",
                "root_value": 3500,
                "premium_budget": 42,
                "tier": "S",
                "dino_role": "sentinela",
                "mod_source": "aberration",
                "pricing_mode": "floor_quality",
                "blueprint_path": _BASILISK_BP,
                "catalog_item_id": "basilisk",
            },
        ],
    }


def _family_catalog() -> dict:
    items = {
        "linha_nivel_2": {
            "Type": "dino",
            "Name": "Linha Nível 2",
            "Price": 1000,
            "Dinos": [{"Blueprint": "/Game/Mods/Linha/Linha_Character_BP.Linha_Character_BP", "Level": 2}],
        },
        "linha_nivel_0": {
            "Type": "dino",
            "Name": "Linha Nível 0",
            "Price": 1000,
            "Dinos": [{"Blueprint": "/Game/Mods/Zero/Zero_Character_BP.Zero_Character_BP", "Level": 0}],
        },
        "linha_sem_nivel": {
            "Type": "dino",
            "Name": "Linha sem nível",
            "Price": 800,
            "Dinos": [{"Blueprint": "/Game/Mods/Sem/Sem_Character_BP.Sem_Character_BP"}],
        },
        "pf_alpha_ankylo": {
            "Type": "dino",
            "Name": "PF Alpha Ankylo Nível 2",
            "Price": 1000,
            "Dinos": [{"Blueprint": "/Game/Mods/PF/Ankylo_Character_BP.Ankylo_Character_BP", "Level": 2}],
        },
        "ab_ankylosaurus_aberrante": {
            "Type": "dino",
            "Name": "Ankylo Aberrante",
            "Price": 2000,
            "Dinos": [{"Blueprint": "/Game/Aberration/Dinos/Ankylosaurus/Ankylo_Character_BP_Aberrant.Ankylo_Character_BP_Aberrant", "Level": 1}],
        },
        "pf_fabled_ankylo": {
            "Type": "dino",
            "Name": "PF Fabled Ankylo",
            "Price": 3000,
            "Dinos": [{"Blueprint": "/Game/Mods/PF/Fabled_Ankylo_Character_BP.Fabled_Ankylo_Character_BP", "Level": 1}],
        },
        "vn_ankylosaurus": {
            "Type": "dino",
            "Name": "VN Ankylo",
            "Price": 4000,
            "Dinos": [{"Blueprint": _ANKY_BP, "Level": 4}],
        },
        "x_x_ankylosaurus": {
            "Type": "dino",
            "Name": "X Ankylo",
            "Price": 5000,
            "Dinos": [{"Blueprint": "/Game/Mods/X/Ankylo_Character_BP.Ankylo_Character_BP", "Level": 5}],
        },
        "pf_fabled_argentavis": {
            "Type": "dino",
            "Name": "PF Fabled Argentavis",
            "Price": 7000,
            "Dinos": [{"Blueprint": "/Game/Mods/PF/Argent_Character_BP.Argent_Character_BP", "Level": 1}],
        },
        "ab_argent_aberrante": {
            "Type": "dino",
            "Name": "Argent Aberrante",
            "Price": 8000,
            "Dinos": [{"Blueprint": "/Game/Aberration/Dinos/Argentavis/Argent_Character_BP_Aberrant.Argent_Character_BP_Aberrant", "Level": 2}],
        },
        "basilisk": {
            "Type": "dino",
            "Name": "Basilisco",
            "Price": 5000,
            "Dinos": [{"Blueprint": _BASILISK_BP, "Level": 1}],
        },
    }
    return {"Items": items}


def _use_family_defaults(tmp_path, monkeypatch) -> None:
    path = tmp_path / "market_species_defaults.json"
    path.write_text(json.dumps(_family_defaults()), encoding="utf-8")
    monkeypatch.setattr(me, "_DEFAULTS_FILE", path)
    monkeypatch.setattr(me, "_bundled_species_map", lambda: {})
    me.invalidate_defaults_cache()


def test_line_root_is_price_over_level_and_cap_is_600000(tmp_path, monkeypatch):
    _use_family_defaults(tmp_path, monkeypatch)
    rows = {row["catalog_item_id"]: row for row in me.list_species_economy_meta(_family_catalog())}

    nivel_2 = rows["linha_nivel_2"]
    assert nivel_2["shop_price"] == 1000
    assert nivel_2["reference_level"] == 2
    assert nivel_2["root_value"] == 500
    assert nivel_2["size_cap"] == 600_000
    assert me.ECONOMY_TABLE_CAP == 600_000

    assert rows["linha_nivel_0"]["reference_level"] == 1
    assert rows["linha_nivel_0"]["root_value"] == 1000
    assert rows["linha_sem_nivel"]["reference_level"] == 1
    assert rows["linha_sem_nivel"]["root_value"] == 800
    assert "ghost_only" not in rows
    assert "ghost_only" not in {row["species_key"] for row in rows.values()}


def test_ankylo_variants_inherit_utility_c_and_argentavis_locomotion_b(tmp_path, monkeypatch):
    _use_family_defaults(tmp_path, monkeypatch)
    rows = {row["catalog_item_id"]: row for row in me.list_species_economy_meta(_family_catalog())}

    expected_b = 8_000 - 2_500
    prices = {
        "pf_alpha_ankylo": (1000, 2, 500),
        "ab_ankylosaurus_aberrante": (2000, 1, 2000),
        "pf_fabled_ankylo": (3000, 1, 3000),
        "vn_ankylosaurus": (4000, 4, 1000),
        "x_x_ankylosaurus": (5000, 5, 1000),
    }
    roots = []
    for item_id in _VARIANT_IDS:
        row = rows[item_id]
        shop, level, root = prices[item_id]
        assert row["species_key"] == "ankylosaurus"
        assert row["dino_role"] == "utilitario"
        assert row["tier"] == "C"
        assert row["premium_budget"] == expected_b
        assert row["premium_budget"] != 0
        assert row["bonus_space"] == expected_b
        assert row["shop_price"] == shop
        assert row["reference_level"] == level
        assert row["root_value"] == root
        assert row["size_cap"] == 600_000
        roots.append(row["root_value"])
    assert len(set(roots)) > 1

    alpha = rows["pf_alpha_ankylo"]
    assert alpha["dino_role"] != "ataque"
    assert alpha["shop_price"] == 1000
    assert alpha["reference_level"] == 2
    assert alpha["root_value"] == 500

    for item_id in ("pf_fabled_argentavis", "ab_argent_aberrante"):
        row = rows[item_id]
        assert row["species_key"] == "argentavis"
        assert row["dino_role"] == "locomocao"
        assert row["tier"] == "B"
        assert row["premium_budget"] == 24500
        assert row["premium_budget"] != 0
        assert row["size_cap"] == 600_000
    assert rows["ab_argent_aberrante"]["root_value"] == 4000
    assert rows["pf_fabled_argentavis"]["root_value"] == 7000


def test_creature_without_vanilla_family_keeps_its_classification(tmp_path, monkeypatch):
    _use_family_defaults(tmp_path, monkeypatch)
    rows = {row["catalog_item_id"]: row for row in me.list_species_economy_meta(_family_catalog())}

    basilisk = rows["basilisk"]
    assert basilisk["dino_role"] == "sentinela"
    assert basilisk["tier"] == "S"
    assert basilisk["premium_budget"] == 42
    assert basilisk["species_key"] == "basilisk"
    assert basilisk["root_value"] == 5000

    assert rows["linha_nivel_2"]["dino_role"] == ""
    assert rows["linha_nivel_2"]["tier"] == "—"
    assert rows["linha_nivel_0"]["dino_role"] == ""
