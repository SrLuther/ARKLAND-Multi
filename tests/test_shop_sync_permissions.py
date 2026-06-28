"""Testes de diff de Permissions na sincronização CustomShop."""

import json
from types import SimpleNamespace

from src.shop_integration import (
    _cross_chat_server_label,
    apply_shared_sections_to_plugin,
    build_cross_chat_settings,
    catalog_permission_diff,
    collect_groups_from_catalog,
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


def test_merge_partial_point_packages_preserves_items():
    catalog = {
        "PointPackages": [{"id": "p1", "label": "Novo", "points": 100, "price_brl": 5.0}],
    }
    existing = {
        "Items": {"item_a": {"Price": 10}},
        "Kits": {"kit_a": {}},
        "PointPackages": [{"id": "p_old", "label": "Antigo", "points": 50, "price_brl": 5.0}],
        "Settings": {"ShopName": "Mapa"},
    }
    merged = merge_catalog_into_plugin_config(catalog, existing)
    assert merged["Items"] == existing["Items"]
    assert merged["Kits"] == existing["Kits"]
    assert merged["Settings"]["ShopName"] == "Mapa"
    assert merged["PointPackages"] == catalog["PointPackages"]


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


def test_apply_shared_sections_does_not_copy_master_server_id():
    catalog = {
        "CrossChat": {"Enabled": True, "ServerId": "Mapa1", "UseWebApi": True},
        "TimedPointsReward": {"Enabled": True, "Groups": {}},
    }
    merged = {"Settings": {}}
    apply_shared_sections_to_plugin(merged, catalog, {})
    assert "ServerId" not in merged["CrossChat"]
    assert merged["CrossChat"]["UseWebApi"] is True


def test_apply_shared_sections_ignores_existing_master_duplicate_server_id():
    catalog = {
        "CrossChat": {"Enabled": True, "ServerId": "Mapa1"},
        "TimedPointsReward": {"Enabled": True, "Groups": {}},
    }
    existing = {"CrossChat": {"ServerId": "Mapa1"}}
    merged = {"Settings": {}}
    apply_shared_sections_to_plugin(merged, catalog, existing)
    assert "ServerId" not in merged["CrossChat"]


def test_cross_chat_server_label_prefers_install_dir_over_generic_name():
    srv = SimpleNamespace(
        name="ARK Server TEK",
        shop_server_id="",
        install_dir=r"C:\ARK\Brighamia",
        id="uuid-brighamia",
    )
    assert _cross_chat_server_label(srv) == "Brighamia"


def test_cross_chat_server_label_uses_shop_server_id_when_install_dir_generic():
    srv = SimpleNamespace(
        name="ARK Server TEK",
        shop_server_id="Ragnarok-PVP",
        install_dir=r"C:\ARK\ARK Server TEK",
        id="uuid-rag",
    )
    assert _cross_chat_server_label(srv) == "Ragnarok-PVP"


def test_cross_chat_server_label_prefers_install_dir_over_shop_server_id():
    srv = SimpleNamespace(
        name="ARK Server TEK",
        shop_server_id="amissa",
        install_dir=r"C:\ARK\Brighamia",
        id="brighamia-id",
    )
    assert _cross_chat_server_label(srv) == "Brighamia"


def test_sync_plugin_at_path_sets_unique_crosschat_server_id(tmp_path):
    catalog = {
        "Kits": {},
        "Items": {},
        "Settings": {"ShopName": "Cluster"},
        "CrossChat": {
            "Enabled": True,
            "ServerId": "Mapa1",
            "AutoCapture": True,
            "UseWebApi": True,
        },
    }
    shop = SimpleNamespace(cross_chat_enabled=True)
    srv = SimpleNamespace(
        name="ARK Server TEK",
        shop_server_id="",
        install_dir=str(tmp_path / "Brighamia"),
        id="brighamia-id",
    )
    plugin_path = tmp_path / "Brighamia" / "config.json"
    plugin_path.parent.mkdir(parents=True, exist_ok=True)
    plugin_path.write_text('{"CrossChat":{"ServerId":"Mapa1"}}', encoding="utf-8")

    sync_plugin_at_path(
        catalog, plugin_path,
        "https://shop.test", "http://127.0.0.1:5177", "key", {},
        shop=shop,
        srv=srv,
    )
    saved = __import__("json").loads(plugin_path.read_text(encoding="utf-8"))
    assert saved["CrossChat"]["ServerId"] == "Brighamia"
    assert saved["CrossChat"]["UseWebApi"] is True
    assert saved["CrossChat"]["Enabled"] is True


def test_build_cross_chat_settings_unique_per_map():
    shop = SimpleNamespace(cross_chat_enabled=True)
    catalog_cc = {"Enabled": True, "ServerId": "Mapa1", "Command": "/cluster"}
    a = SimpleNamespace(name="ARK Server TEK", shop_server_id="", install_dir=r"C:\ARK\Brighamia", id="a")
    b = SimpleNamespace(name="ARK Server TEK", shop_server_id="", install_dir=r"C:\ARK\TheIsland", id="b")
    cc_a = build_cross_chat_settings(shop, a, catalog_cc=catalog_cc)
    cc_b = build_cross_chat_settings(shop, b, catalog_cc=catalog_cc)
    assert cc_a["ServerId"] == "Brighamia"
    assert cc_b["ServerId"] == "TheIsland"
    assert cc_a["Command"] == "/cluster"
    assert cc_b["Command"] == "/cluster"


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


def test_sync_plugin_at_path_propagates_new_kit_from_master(tmp_path):
    catalog = {
        "Kits": {
            "recursos": {"Price": 0, "Description": "Recursos", "Items": []},
            "vip": {"Price": 100, "Description": "VIP", "Items": []},
        },
        "Items": {},
        "Settings": {"ShopName": "Mestre"},
    }
    plugin_path = tmp_path / "config.json"
    plugin_path.write_text(
        json.dumps({
            "Kits": {
                "vip": {"Price": 50, "Description": "VIP antigo", "Items": []},
                "somente_mapa": {"Price": 1, "Description": "Local", "Items": []},
            },
            "Items": {},
            "Settings": {"ShopName": "Mapa"},
            "CrossChat": {"ServerId": "Mapa1"},
        }),
        encoding="utf-8",
    )
    sync_plugin_at_path(
        catalog, plugin_path,
        "https://shop.test", "http://127.0.0.1:5177", "key", {},
    )
    saved = json.loads(plugin_path.read_text(encoding="utf-8"))
    assert "recursos" in saved["Kits"]
    assert saved["Kits"]["recursos"]["Description"] == "Recursos"
    assert saved["Kits"]["vip"]["Price"] == 100
    assert "somente_mapa" not in saved["Kits"]


def test_apply_shared_sections_crosschat_master_wins_except_server_id():
    catalog = {
        "CrossChat": {
            "Enabled": True,
            "ServerId": "Mapa1",
            "Command": "/cluster",
            "UseWebApi": True,
        },
    }
    existing = {
        "CrossChat": {
            "ServerId": "Ragnarok",
            "Command": "/c",
            "UseWebApi": False,
        },
    }
    merged: dict = {}
    apply_shared_sections_to_plugin(merged, catalog, existing)
    assert merged["CrossChat"]["ServerId"] == "Ragnarok"
    assert merged["CrossChat"]["Command"] == "/cluster"
    assert merged["CrossChat"]["UseWebApi"] is True


def test_collect_groups_from_catalog_includes_license_grant_keyvault():
    catalog = {
        "Kits": {},
        "Items": {
            "licenca_nuvem": {
                "LicenseGrant": {"Group": "keyvault", "Days": 30},
            },
            "licenca_alfa": {
                "LicenseGrant": {"Group": "Alfa", "Days": 30},
            },
        },
    }
    groups = collect_groups_from_catalog(catalog)
    assert "keyvault" in groups
    assert "Alfa" in groups
