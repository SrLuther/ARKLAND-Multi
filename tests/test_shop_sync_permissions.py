"""Testes de diff de Permissions na sincronização CustomShop."""

from src.shop_integration import (
    catalog_permission_diff,
    format_permission_sync_note,
    merge_plugin_config,
)


def test_catalog_permission_diff_detects_kit_change():
    existing = {
        "Kits": {
            "diamante": {"Permissions": "Admins,VIPDiamante"},
            "alga_kit": {"Permissions": ""},
        },
        "Items": {},
    }
    catalog = {
        "Kits": {
            "diamante": {"Permissions": "Admins"},
            "alga_kit": {"Permissions": "Alga"},
        },
        "Items": {
            "licenca_alga": {"Permissions": "Alga", "Type": "license"},
        },
    }
    changes = catalog_permission_diff(existing, catalog)
    assert ("Kits", "diamante", "Admins,VIPDiamante", "Admins") in changes
    assert ("Kits", "alga_kit", "", "Alga") in changes
    assert ("Items", "licenca_alga", "", "Alga") in changes


def test_catalog_permission_diff_ignores_unchanged():
    catalog = {"Kits": {"vip": {"Permissions": "Alga"}}, "Items": {}}
    assert catalog_permission_diff(catalog, catalog) == []


def test_format_permission_sync_note():
    note = format_permission_sync_note("Kits", "vip", "", "Alga")
    assert note == "Kits/vip Permissions: (vazio) → Alga"


def test_merge_plugin_config_replaces_kits_from_catalog():
    catalog = {
        "Kits": {"vip": {"Permissions": "Alga", "Price": 100}},
        "Items": {},
        "Settings": {},
    }
    merged = merge_plugin_config(catalog, "https://shop.test", "http://127.0.0.1:5177", "key", {})
    assert merged["Kits"]["vip"]["Permissions"] == "Alga"
