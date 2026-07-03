"""Testes de detecção de selas e aplicação de Armor no catálogo."""
from __future__ import annotations

from src.shop_catalog_import import _normalize_item_entry, sanitize_catalog_blueprints
from tools.apply_saddle_armor import apply_saddle_armor, is_saddle_blueprint

ALLO_SADDLE = (
    "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Saddles/"
    "PrimalItemArmor_AlloSaddle.PrimalItemArmor_AlloSaddle"
)
TEK_HELMET = (
    "/Game/PrimalEarth/CoreBlueprints/Items/Armor/TEK/"
    "PrimalItemArmor_TekHelmet.PrimalItemArmor_TekHelmet"
)
SEAFIN_GLIDER = (
    "/Game/Abyss/CoreBlueprints/Items/Armor/SeafinGlider/"
    "PrimalItemArmor_SeafinGlider.PrimalItemArmor_SeafinGlider"
)
SB_DRAGON = (
    "/Game/Mods/SmallBosses/SmallDragon/"
    "PrimalItemArmor_DragonArmor.PrimalItemArmor_DragonArmor"
)
GALLIMIMUS = (
    "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Saddles/"
    "PrimalItemArmor_Gallimimus.PrimalItemArmor_Gallimimus"
)


def test_is_saddle_blueprint_vanilla_saddle():
    assert is_saddle_blueprint(ALLO_SADDLE)


def test_is_saddle_blueprint_mod_saddle():
    assert is_saddle_blueprint(
        "/Game/Mods/GrandHunt/Monsters/Armaedron/"
        "PrimalItemArmor_ArmaeSaddle.PrimalItemArmor_ArmaeSaddle"
    )


def test_is_saddle_blueprint_smallbosses_armor():
    assert is_saddle_blueprint(SB_DRAGON)


def test_is_saddle_blueprint_gallimimus():
    assert is_saddle_blueprint(GALLIMIMUS)


def test_is_saddle_blueprint_rejects_player_armor():
    assert not is_saddle_blueprint(TEK_HELMET)
    assert not is_saddle_blueprint(
        "/Game/Mods/VISOUSMod/Blindado/Alfa/"
        "PrimalItemArmor_MetalHelmet_Alfa.PrimalItemArmor_MetalHelmet_Alfa"
    )


def test_is_saddle_blueprint_rejects_glider():
    assert not is_saddle_blueprint(SEAFIN_GLIDER)


def test_apply_saddle_armor_sets_armor_on_items_and_kits():
    data = {
        "Items": {
            "sela_allo": {
                "Type": "item",
                "Price": 100,
                "Items": [{"Blueprint": ALLO_SADDLE, "Quantity": 1, "Quality": 100}],
            },
            "tek_helmet": {
                "Type": "item",
                "Price": 50,
                "Items": [{"Blueprint": TEK_HELMET, "Quantity": 1}],
            },
        },
        "Kits": {
            "starter": {
                "Price": 0,
                "Items": [
                    {"Blueprint": ALLO_SADDLE, "Quantity": 1},
                    {"Blueprint": TEK_HELMET, "Quantity": 1},
                ],
            }
        },
    }
    count, paths = apply_saddle_armor(data, armor=350)
    assert count == 2
    assert data["Items"]["sela_allo"]["Items"][0]["Armor"] == 350
    assert "Armor" not in data["Items"]["tek_helmet"]["Items"][0]
    assert data["Kits"]["starter"]["Items"][0]["Armor"] == 350
    assert "Armor" not in data["Kits"]["starter"]["Items"][1]
    assert any("sela_allo" in p for p in paths)
    assert any("starter" in p for p in paths)


def test_sanitize_catalog_preserves_saddle_armor():
    data = {
        "Items": {
            "sela_allo": {
                "Type": "item",
                "Price": 100,
                "Items": [{
                    "Blueprint": ALLO_SADDLE,
                    "Quantity": 1,
                    "Quality": 100,
                    "Armor": 350,
                    "ForceBlueprint": True,
                }],
            }
        }
    }
    apply_saddle_armor(data, armor=350)
    sanitize_catalog_blueprints(data)
    item = data["Items"]["sela_allo"]["Items"][0]
    assert item["Armor"] == 350
    assert item["Quality"] == 100
    assert item["ForceBlueprint"] is True


def test_normalize_item_entry_preserves_armor_on_saddle():
    entry = _normalize_item_entry({
        "Blueprint": ALLO_SADDLE,
        "Quantity": 1,
        "Armor": 350,
        "Damage": 0,
    })
    assert entry["Armor"] == 350
