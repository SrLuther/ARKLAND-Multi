"""Economia — Comércio lista só o catálogo da loja e não cola as colunas."""
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
    rows = {row["species_key"]: row for row in me.list_species_economy_meta(_catalog())}

    assert "ghost_only" not in rows
    rex = rows["rex"]
    assert rex["display_name"] == "Rex"
    assert rex["dino_role"] == "ataque"
    assert rex["tier"] == "S"
    assert rex["pricing_mode"] == "floor_quality"
    # R é o Price L1 do catálogo, não o root_value 1 do cache nem o L200.
    assert rex["root_value"] == 18000
    # Cache proportional sem B não zera o prêmio: volta o floor_quality do repo.
    assert rex["premium_budget"] == 90000
    assert rex["bonus_space"] == 90000
    assert rex["size_cap"] == 150_000
    bary = rows["baryonyx"]
    assert bary["root_value"] == 4242
    assert bary["bonus_space"] == 31500
    assert bary["dino_role"] == "ataque"
    assert bary["tier"] == "B"
    # Sem item L1 não se inventa piso a partir do preço 50.000.
    assert rows["solo_alto"]["root_value"] is None
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
