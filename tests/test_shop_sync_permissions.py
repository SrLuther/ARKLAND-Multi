"""Testes de diff de Permissions na sincronização CustomShop."""

from src.shop_integration import (
    apply_shared_sections_to_plugin,
    catalog_permission_diff,
    format_permission_sync_note,
    merge_catalog_into_plugin_config,
    merge_plugin_config,
    shared_config_fingerprint,
    sync_plugin_at_path,
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


def test_merge_settings_catalog_wins_over_plugin():
    catalog = {
        "Settings": {"ShopName": "Mestre NOVO", "StartingPoints": 200},
        "TimedPointsReward": {"Enabled": True, "Groups": {"Default": {"Amount": 25}}},
    }
    existing = {
        "Settings": {"ShopName": "Mapa ANTIGO", "StartingPoints": 50, "CustomFlag": True},
        "TimedPointsReward": {"Enabled": False, "Groups": {"VIPBronze": {"Amount": 20}}},
    }
    merged = merge_catalog_into_plugin_config(catalog, existing)
    assert merged["Settings"]["ShopName"] == "Mestre NOVO"
    assert merged["Settings"]["StartingPoints"] == 200
    assert merged["Settings"]["CustomFlag"] is True
    assert merged["TimedPointsReward"]["Enabled"] is True
    assert "VIPBronze" not in merged["TimedPointsReward"]["Groups"]


def test_shared_config_fingerprint_detects_timed_points_change():
    base = {
        "Items": {"a": {}},
        "Kits": {},
        "TimedPointsReward": {"Enabled": True, "Groups": {"Default": {"Amount": 25}}},
        "Settings": {"ShopName": "X"},
    }
    changed = {
        **base,
        "TimedPointsReward": {"Enabled": False, "Groups": {"VIPBronze": {"Amount": 20}}},
    }
    assert shared_config_fingerprint(base) != shared_config_fingerprint(changed)


def test_apply_shared_sections_preserves_crosschat_server_id():
    catalog = {
        "CrossChat": {"Enabled": True, "ServerId": "master", "Command": "/c"},
        "TimedPointsReward": {"Enabled": True, "Groups": {}},
    }
    existing = {"CrossChat": {"ServerId": "mapa-ragnarok"}}
    merged = {"Settings": {}}
    apply_shared_sections_to_plugin(merged, catalog, existing)
    assert merged["CrossChat"]["ServerId"] == "mapa-ragnarok"
    assert merged["CrossChat"]["Enabled"] is True


def test_sync_plugin_at_path_propagates_timed_points(tmp_path):
    catalog = {
        "Kits": {},
        "Items": {},
        "Settings": {"ShopName": "Cluster"},
        "TimedPointsReward": {
            "Enabled": True,
            "Interval": 30,
            "StackRewards": True,
            "Groups": {
                "Default": {"Amount": 25},
                "VIPBronze": {"Amount": 20},
                "VIPDiamante": {"Amount": 75},
            },
        },
    }
    plugin_path = tmp_path / "config.json"
    plugin_path.write_text(
        '{"TimedPointsReward":{"Enabled":false,"Groups":{"Alfa":{"Amount":75}}},"Settings":{"ShopName":"Old"}}',
        encoding="utf-8",
    )
    sync_plugin_at_path(
        catalog, plugin_path,
        "https://shop.test", "http://127.0.0.1:5177", "key", {},
    )
    saved = __import__("json").loads(plugin_path.read_text(encoding="utf-8"))
    assert saved["TimedPointsReward"]["Enabled"] is True
    assert "VIPBronze" in saved["TimedPointsReward"]["Groups"]
    assert "Alfa" not in saved["TimedPointsReward"]["Groups"]
    assert saved["Settings"]["ShopName"] == "Cluster"
