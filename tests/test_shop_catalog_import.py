"""Testes de normalização de catálogo CustomShop."""
from __future__ import annotations

from src.shop_catalog_import import (
    _normalize_item_entry,
    normalize_blueprint,
    sanitize_catalog_blueprints,
)

STONE = (
    "/Game/PrimalEarth/CoreBlueprints/Resources/"
    "PrimalItemResource_Stone.PrimalItemResource_Stone"
)


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


def test_sanitize_catalog_blueprints_fixes_recursos_kit():
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


def test_sanitize_catalog_blueprints_handles_arkshop_wrapper_with_trailing_quote():
    """Espelha o log de produção: Blueprint'...' ou fragmento JSON com aspas extras."""
    wrapped = f"'\"Blueprint\": \"{STONE}\"'"
    assert normalize_blueprint(wrapped) == STONE
