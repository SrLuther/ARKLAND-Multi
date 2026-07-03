"""Testes de normalização de catálogo CustomShop."""
from __future__ import annotations

from src.shop_catalog_import import (
    _normalize_item_entry,
    build_item_detail_payload,
    extract_catalog,
    item_detail_source,
    merge_shop_item_entry,
    normalize_blueprint,
    sanitize_catalog_blueprints,
)

STONE = (
    "/Game/PrimalEarth/CoreBlueprints/Resources/"
    "PrimalItemResource_Stone.PrimalItemResource_Stone"
)


def test_item_detail_source_reads_nested_saddle_stats():
    saddle = {
        "Type": "item",
        "Price": 3200,
        "Description": "Sela de Allo",
        "Quality": 0,
        "Items": [{
            "Blueprint": (
                "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Saddles/"
                "PrimalItemArmor_AlloSaddle.PrimalItemArmor_AlloSaddle"
            ),
            "Quantity": 1,
            "Quality": 100,
            "Armor": 350,
        }],
        "Category": "Selas",
    }
    src = item_detail_source(saddle)
    assert src["Armor"] == 350
    assert src["Quality"] == 100
    assert "AlloSaddle" in src["Blueprint"]


def test_merge_shop_item_entry_writes_nested_saddle_stats():
    existing = {
        "Type": "item",
        "Price": 3200,
        "Description": "Sela de Allo",
        "Name": "Sela de Allo",
        "Category": "Selas",
        "Items": [{
            "Blueprint": "/Game/.../PrimalItemArmor_AlloSaddle.PrimalItemArmor_AlloSaddle",
            "Quantity": 1,
            "Quality": 100,
            "Armor": 350,
        }],
    }
    detail = build_item_detail_payload(
        blueprint="/Game/.../PrimalItemArmor_AlloSaddle.PrimalItemArmor_AlloSaddle",
        quantity=1,
        quality=100,
        force_blueprint=False,
        armor=400,
    )
    merged = merge_shop_item_entry(
        existing,
        item_type="item",
        price=3300,
        description="Sela de Allo atualizada",
        detail=detail,
    )
    assert merged["Price"] == 3300
    assert merged["Category"] == "Selas"
    assert merged["Items"][0]["Armor"] == 400
    assert "Blueprint" not in merged
    assert "Armor" not in merged


def test_extract_catalog_customshop_preserves_nested_armor():
    raw = {
        "Items": {
            "sela_allo": {
                "Type": "item",
                "Price": 3200,
                "Description": "Sela",
                "Items": [{
                    "Blueprint": (
                        "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Saddles/"
                        "PrimalItemArmor_AlloSaddle.PrimalItemArmor_AlloSaddle"
                    ),
                    "Quantity": 1,
                    "Quality": 100,
                    "Armor": 350,
                }],
            }
        }
    }
    items, _, _ = extract_catalog(raw)
    assert items["sela_allo"]["Items"][0]["Armor"] == 350


def test_normalize_blueprint_arkshop_wrapper():
    assert normalize_blueprint(f"Blueprint'{STONE}'") == STONE


def test_normalize_blueprint_malformed_json_fragment():
    malformed = f'"Blueprint": "{STONE}"'
    assert normalize_blueprint(malformed) == STONE


def test_normalize_item_entry_from_malformed_string():
    entry = _normalize_item_entry(f'"Blueprint": "{STONE}", "Amount": 100')
    assert entry["Blueprint"] == STONE
    assert entry["Quantity"] == 1


def test_normalize_item_entry_from_malformed_object():
    entry = _normalize_item_entry({"Blueprint": f'"Blueprint": "{STONE}"', "Amount": 50})
    assert entry["Blueprint"] == STONE
    assert entry["Quantity"] == 50


def test_normalize_item_entry_preserves_armor_damage_durability():
    entry = _normalize_item_entry({
        "Blueprint": STONE,
        "Amount": 1,
        "Quality": 100,
        "Armor": 350,
        "Damage": 300,
        "Durability": 250,
    })
    assert entry["Armor"] == 350
    assert entry["Damage"] == 300
    assert entry["Durability"] == 250
    assert entry["Quality"] == 100


def test_sanitize_catalog_blueprints_preserves_armor():
    data = {
        "Items": {
            "allo_saddle": {
                "Type": "item",
                "Price": 100,
                "Items": [{
                    "Blueprint": (
                        "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Saddles/"
                        "PrimalItemArmor_AlloSaddle.PrimalItemArmor_AlloSaddle"
                    ),
                    "Quantity": 1,
                    "Quality": 100,
                    "Armor": 350,
                }],
            }
        }
    }
    sanitize_catalog_blueprints(data)
    item = data["Items"]["allo_saddle"]["Items"][0]
    assert item["Armor"] == 350
    assert item["Quality"] == 100
    data = {
        "Kits": {
            "recursos": {
                "Price": 100,
                "Items": [
                    {"Blueprint": f'"Blueprint": "{STONE}"', "Amount": 100},
                    {"Blueprint": f'"Blueprint": "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Wood.PrimalItemResource_Wood"', "Amount": 200},
                ],
            }
        }
    }
    sanitize_catalog_blueprints(data)
    items = data["Kits"]["recursos"]["Items"]
    assert items[0]["Blueprint"] == STONE
    assert items[0]["Quantity"] == 100
    assert "Wood" in items[1]["Blueprint"]


def test_normalize_blueprint_fixes_raw_meat_resources_folder():
    wrong = (
        "/Game/PrimalEarth/CoreBlueprints/Resources/"
        "PrimalItemConsumable_RawMeat.PrimalItemConsumable_RawMeat"
    )
    right = (
        "/Game/PrimalEarth/CoreBlueprints/Items/Consumables/"
        "PrimalItemConsumable_RawMeat.PrimalItemConsumable_RawMeat"
    )
    assert normalize_blueprint(wrong) == right


def test_normalize_blueprint_fixes_hide_armor_folder():
    wrong = (
        "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Hide/"
        "PrimalItemArmor_HideHelmet.PrimalItemArmor_HideHelmet"
    )
    right = (
        "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Leather/"
        "PrimalItemArmor_HideHelmet.PrimalItemArmor_HideHelmet"
    )
    assert normalize_blueprint(wrong) == right


def test_normalize_blueprint_fixes_tek_armor_folder():
    wrong = (
        "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Tek/"
        "PrimalItemArmor_TekGloves.PrimalItemArmor_TekGloves"
    )
    right = (
        "/Game/PrimalEarth/CoreBlueprints/Items/Armor/TEK/"
        "PrimalItemArmor_TekGloves.PrimalItemArmor_TekGloves"
    )
    assert normalize_blueprint(wrong) == right


def test_normalize_blueprint_fixes_nameless_venom_folder():
    wrong = (
        "/Game/Aberration/CoreBlueprints/Resources/"
        "PrimalItemConsumable_NamelessVenom.PrimalItemConsumable_NamelessVenom"
    )
    right = (
        "/Game/Aberration/CoreBlueprints/Items/Consumables/"
        "PrimalItemConsumable_NamelessVenom.PrimalItemConsumable_NamelessVenom"
    )
    assert normalize_blueprint(wrong) == right


def test_normalize_blueprint_fixes_tek_structure_lowercase_folder():
    wrong = (
        "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/"
        "PrimalItemStructure_TekStairs.PrimalItemStructure_TekStairs"
    )
    right = (
        "/Game/PrimalEarth/CoreBlueprints/Items/Structures/tek/"
        "PrimalItemStructure_TekStairs.PrimalItemStructure_TekStairs"
    )
    assert normalize_blueprint(wrong) == right


def test_normalize_blueprint_fixes_tek_fence_foundation_casing():
    wrong = (
        "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/"
        "PrimalItemStructure_TekFenceFoundation.PrimalItemStructure_TekFenceFoundation"
    )
    right = (
        "/Game/PrimalEarth/CoreBlueprints/Items/Structures/tek/"
        "PrimalItemStructure_Tekfencefoundation.PrimalItemStructure_Tekfencefoundation"
    )
    assert normalize_blueprint(wrong) == right


def test_sanitize_catalog_blueprints_fixes_tekgrams_commands():
    from src.shop_catalog_import import sanitize_catalog_blueprints

    wrong_boots = (
        "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Tek/"
        "PrimalItemArmor_TekBoots.PrimalItemArmor_TekBoots"
    )
    right_boots = (
        "/Game/PrimalEarth/CoreBlueprints/Items/Armor/TEK/"
        "PrimalItemArmor_TekBoots.PrimalItemArmor_TekBoots"
    )
    data = {
        "Items": {
            "tekgrams": {
                "Type": "command",
                "Commands": [{
                    "Command": f'cheat UnlockEngram "Blueprint\'{wrong_boots}\'"',
                }],
            }
        }
    }
    sanitize_catalog_blueprints(data)
    assert right_boots in data["Items"]["tekgrams"]["Commands"][0]["Command"]
    assert wrong_boots not in data["Items"]["tekgrams"]["Commands"][0]["Command"]


def test_sanitize_catalog_blueprints_handles_arkshop_wrapper_with_trailing_quote():
    """Espelha o log de produção: Blueprint'...' ou fragmento JSON com aspas extras."""
    wrapped = f"'\"Blueprint\": \"{STONE}\"'"
    assert normalize_blueprint(wrapped) == STONE
