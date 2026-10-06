"""Referência secundária do Primal Fear na tabela Economia — Comércio."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import market_economy as me
from primal_fear_secondary import (
    primal_fear_roster,
    primal_fear_roster_counts,
    primal_fear_secondary_fields,
)

_HTML = Path(__file__).resolve().parents[1] / "static" / "index.html"
_ANKY_BP = "/Game/PrimalEarth/Dinos/Ankylosaurus/Ankylo_Character_BP.Ankylo_Character_BP"
_REX_BP = "/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP"


def _defaults() -> dict:
    return {
        "_floor_quality": {"enabled": True, "market_absolute_max": 150_000, "gamma": 0.82},
        "species": [
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
            },
            {
                "species_key": "rex",
                "display_name": "Rex",
                "root_value": 100_000,
                "premium_budget": 0,
                "tier": "S",
                "dino_role": "ataque",
                "mod_source": "vanilla",
                "pricing_mode": "floor_quality",
                "blueprint_path": _REX_BP,
            },
        ],
    }


def _dino(name: str, price: int, blueprint: str, level: int = 1) -> dict:
    return {
        "Type": "dino",
        "Name": name,
        "Price": price,
        "Dinos": [{"Blueprint": blueprint, "Level": level}],
    }


def _catalog() -> dict:
    return {
        "Items": {
            "pf_alpha_ankylo": _dino(
                "PF Alpha Ankylo Nível 2",
                1000,
                "/Game/Mods/Primal_Fear/Dinos/Alpha/Ankylo_Character_BP.Ankylo_Character_BP",
                2,
            ),
            "pf_apex_ankylo": _dino(
                "PF Apex Ankylo",
                4000,
                "/Game/Mods/Primal_Fear/Dinos/Apex/Ankylo_Character_BP.Ankylo_Character_BP",
            ),
            "pf_fabled_ankylo": _dino(
                "PF Fabled Ankylo",
                3000,
                "/Game/Mods/Primal_Fear/Dinos/Fabled/Ankylo_Character_BP.Ankylo_Character_BP",
            ),
            "pf_chaos_ankylo": _dino(
                "PF Chaos Ankylo",
                9000,
                "/Game/Mods/Primal_Fear/Dinos/Chaos/Ankylo_Character_BP.Ankylo_Character_BP",
            ),
            "pf_chaos_rex": _dino("PF Chaos Rex", 8000, _REX_BP),
            "pf_chaos_fantasma": _dino(
                "PF Chaos Fantasma",
                1500,
                "/Game/Mods/Primal_Fear/Dinos/Chaos/Fantasma_Character_BP.Fantasma_Character_BP",
            ),
            "pf_buffoon_ankylo": _dino("PF Buffoon Ankylo", 1100, _ANKY_BP),
            "pf_black_omega_rex": _dino("PF Black Omega Rex", 1600, _REX_BP),
            "pf_apex_corrupt": _dino(
                "PF Apex Ankylo Corrupt",
                4200,
                "/Game/Mods/Primal_Fear/Dinos/Apex/Corrupted/Ankylo_Character_BP.Ankylo_Character_BP",
            ),
            "alpha_rex": _dino("Alpha Rex", 5000, _REX_BP),
            "primal_tek_rex": _dino(
                "Primal Tek Rex",
                2400,
                "/Game/Mods/Primal_Fear/Dinos/PrimalTek/Rex_Character_BP.Rex_Character_BP",
            ),
        }
    }


def _use_defaults(tmp_path, monkeypatch) -> None:
    path = tmp_path / "market_species_defaults.json"
    path.write_text(json.dumps(_defaults()), encoding="utf-8")
    monkeypatch.setattr(me, "_DEFAULTS_FILE", path)
    monkeypatch.setattr(me, "_bundled_species_map", lambda: {})
    me.invalidate_defaults_cache()


def _rows(tmp_path, monkeypatch) -> dict:
    _use_defaults(tmp_path, monkeypatch)
    return {row["catalog_item_id"]: row for row in me.list_species_economy_meta(_catalog())}


def test_alpha_apex_fabled_and_chaos_indexes_keep_the_current_floor(tmp_path, monkeypatch):
    rows = _rows(tmp_path, monkeypatch)
    alpha = rows["pf_alpha_ankylo"]
    assert alpha["shop_price"] == 1000
    assert alpha["reference_level"] == 2
    assert alpha["root_value"] == 500
    assert alpha["dino_role"] == "utilitario"
    assert alpha["tier"] == "C"
    assert alpha["premium_budget"] == 8_000 - 2_500
    assert alpha["size_cap"] == 600_000
    assert alpha["pf_band"] == "Alpha"
    assert alpha["pf_index"] == 1
    assert alpha["pf_mod"] == "Primal Fear"
    assert alpha["pf_reference"] == 2_500
    assert alpha["pf_reference"] != alpha["root_value"]
    assert alpha["pf_reference"] != alpha["root_value"] + alpha["premium_budget"]

    apex = rows["pf_apex_ankylo"]
    assert apex["root_value"] == 4000
    assert apex["pf_band"] == "Apex"
    assert apex["pf_index"] == 2
    assert apex["pf_reference"] == 5_000
    assert apex["dino_role"] == "utilitario"
    assert apex["premium_budget"] == 5_500

    fabled = rows["pf_fabled_ankylo"]
    assert fabled["root_value"] == 3000
    assert fabled["pf_band"] == "Fabled"
    assert fabled["pf_index"] == 3.2
    assert fabled["pf_reference"] == 8_000

    chaos = rows["pf_chaos_ankylo"]
    assert chaos["root_value"] == 9000
    assert chaos["pf_band"] == "Chaos"
    assert chaos["pf_index"] == 8
    assert chaos["pf_reference"] == 20_000

    corrupt = rows["pf_apex_corrupt"]
    assert corrupt["pf_band"] == "Apex"
    assert corrupt["pf_index"] == 2
    assert corrupt["pf_reference"] == 5_000
    assert corrupt["root_value"] == 4200
    assert "Corrupção" in (corrupt["pf_note"] or "")


def test_reference_caps_at_600000(tmp_path, monkeypatch):
    rows = _rows(tmp_path, monkeypatch)
    chaos_rex = rows["pf_chaos_rex"]
    assert chaos_rex["species_key"] == "rex"
    assert chaos_rex["root_value"] == 8000
    assert chaos_rex["pf_index"] == 8
    assert chaos_rex["pf_reference"] == 600_000
    assert chaos_rex["size_cap"] == 600_000
    assert chaos_rex["pf_reference"] != chaos_rex["root_value"] * 8


def test_without_vanilla_family_reference_stays_empty(tmp_path, monkeypatch):
    rows = _rows(tmp_path, monkeypatch)
    ghost = rows["pf_chaos_fantasma"]
    assert ghost["dino_role"] == ""
    assert ghost["tier"] == "—"
    assert ghost["premium_budget"] == 0
    assert ghost["root_value"] == 1500
    assert ghost["pf_band"] == "Chaos"
    assert ghost["pf_index"] == 8
    assert ghost["pf_mod"] == "Primal Fear"
    assert ghost["pf_reference"] is None

    vanilla_alpha = rows["alpha_rex"]
    assert vanilla_alpha["root_value"] == 5000
    assert vanilla_alpha["pf_band"] is None
    assert vanilla_alpha["pf_index"] is None
    assert vanilla_alpha["pf_reference"] is None
    assert vanilla_alpha["pf_mod"] is None


def test_unpriced_bands_and_distinct_multipliers(tmp_path, monkeypatch):
    rows = _rows(tmp_path, monkeypatch)
    buffoon = rows["pf_buffoon_ankylo"]
    assert buffoon["species_key"] == "ankylosaurus"
    assert buffoon["pf_band"] == "Buffoon"
    assert buffoon["pf_index"] is None
    assert buffoon["pf_reference"] is None
    assert buffoon["root_value"] == 1100
    assert "multiplicador" in (buffoon["pf_note"] or "").lower()

    black = rows["pf_black_omega_rex"]
    assert black["pf_band"] == "Black Omega"
    assert black["pf_index"] == 3.2
    assert black["pf_reference"] == 320_000

    tek = rows["primal_tek_rex"]
    assert tek["pf_band"] == "Primal Tek"
    assert tek["pf_index"] == 2.4
    assert tek["pf_mod"] == "Primal Fear"
    assert tek["pf_reference"] == 240_000
    assert tek["root_value"] == 2400

    light = primal_fear_secondary_fields(
        item_id="pf_light_griffin",
        entry={
            "Dinos": [
                {
                    "Blueprint": (
                        "/Game/Mods/Primal_Fear/Dinos/Elemental/Griffin/Light/"
                        "LightGriffin_Character_BP.LightGriffin_Character_BP"
                    )
                }
            ]
        },
        display_name="Light Griffin",
        family_root=1000,
        cap=600_000,
    )
    assert light["pf_band"] == "Elemental Advanced"
    assert light["pf_index"] == 2.8
    assert light["pf_reference"] == 2800

    fire = primal_fear_secondary_fields(
        item_id="pf_fire_griffin",
        entry={
            "Dinos": [
                {
                    "Blueprint": (
                        "/Game/Mods/Primal_Fear/Dinos/Elemental/Griffin/Fire/"
                        "FireGriffin_Character_BP.FireGriffin_Character_BP"
                    )
                }
            ]
        },
        display_name="Fire Griffin",
        family_root=1000,
        cap=600_000,
    )
    assert fire["pf_band"] == "Elemental Basic"
    assert fire["pf_index"] == 1.5
    assert fire["pf_reference"] == 1500

    celestial = primal_fear_secondary_fields(
        item_id="pf_celestial_rex",
        entry={"Dinos": [{"Blueprint": "/Game/Mods/Primal_Fear/Dinos/Celestial/Rex_Character_BP.Rex_Character_BP"}]},
        display_name="PF Celestial Rex",
        family_root=1000,
        cap=600_000,
    )
    assert celestial["pf_index"] == 5.5
    assert celestial["pf_reference"] == 5500


def test_noxious_and_boss_creatures_from_the_ficha(tmp_path, monkeypatch):
    counts = primal_fear_roster_counts()
    assert counts["Primal Fear"] > 0
    assert counts["Noxious Creatures"] > 0
    assert counts["Primal Fear Boss Expansion"] > 0
    for missing in (
        "Primal Fear Scorched Earth Expansion",
        "Primal Fear Extinction Expansion",
        "Primal Fear Aberration Expansion",
        "Primal Fear Genesis Expansion",
        "Primal Fear Fey Expansion",
        "Primal Fear Dodo Expansion",
        "Primal Fear | Unofficial Extras",
    ):
        assert counts[missing] == 0

    creatures = primal_fear_roster()["creatures"]
    noxious = next(
        creature
        for creature in creatures
        if creature["mod"] == "Noxious Creatures" and "ankylo" in creature["blueprint"].lower()
    )
    boss = next(
        creature
        for creature in creatures
        if creature["mod"] == "Primal Fear Boss Expansion" and "/alpha/" in creature["blueprint"].lower()
    )
    _use_defaults(tmp_path, monkeypatch)
    catalog = {
        "Items": {
            "pf_ankylo": _dino(noxious["name"] or "Anky", 2200, noxious["blueprint"], 2),
            boss["tag"] or "pfb_alpha_dodo": _dino(
                boss["name"] or "Dodo Rex",
                3000,
                boss["blueprint"],
            ),
        }
    }
    rows = {row["catalog_item_id"]: row for row in me.list_species_economy_meta(catalog)}
    nox = rows["pf_ankylo"]
    assert nox["species_key"] == "ankylosaurus"
    assert nox["dino_role"] == "utilitario"
    assert nox["root_value"] == 1100
    assert nox["premium_budget"] == 5_500
    assert nox["pf_mod"] == "Noxious Creatures"
    assert nox["pf_band"] is None
    assert nox["pf_index"] is None
    assert nox["pf_reference"] is None

    boss_id = boss["tag"] or "pfb_alpha_dodo"
    boss_row = rows[boss_id]
    assert boss_row["pf_mod"] == "Primal Fear Boss Expansion"
    assert boss_row["pf_band"] == "Alpha"
    assert boss_row["pf_index"] == 1
    assert boss_row["pf_reference"] is None
    assert boss_row["root_value"] == 3000


def test_economy_page_shows_pf_columns_beside_the_floor():
    html = _HTML.read_text(encoding="utf-8")
    start = html.find("function renderMarketEconomySpecies")
    end = html.find("let _marketEconomyEditing", start)
    fn = html[start:end]
    for label in ("Faixa PF", "Índice", "Referência PF", "Mod de origem"):
        assert label in fn
    for cell in ("me-econ-pf-band", "me-econ-pf-index", "me-econ-pf-ref", "me-econ-pf-mod", "me-econ-r", "me-econ-b"):
        assert f'class="{cell}"' in fn
    assert "preço ÷ nível" in fn
    assert "600.000" in fn
    assert "Não multiplica o piso" in html
