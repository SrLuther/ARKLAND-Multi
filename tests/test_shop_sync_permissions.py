"""Testes de diff de Permissions na sincronização CustomShop."""

import json
from types import SimpleNamespace

import pytest

from src.shop_integration import (
    _cross_chat_server_label,
    apply_shared_sections_to_plugin,
    build_cross_chat_settings,
    catalog_permission_diff,
    collect_groups_from_catalog,
    find_cross_chat_collisions,
    format_permission_sync_note,
    merge_catalog_into_plugin_config,
    merge_plugin_config,
    shared_config_fingerprint,
    sync_plugin_at_path,
)


@pytest.fixture(autouse=True)
def _fixed_mapas_cross_chat_ids(monkeypatch):
    from src import mapas_cross_chat_ids as mcc

    monkeypatch.setattr(
        mcc,
        "load_mapas_cross_chat_ids",
        lambda: dict(mcc.DEFAULT_MAPAS_CROSS_CHAT_IDS),
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


def test_apply_shared_sections_strips_server_id_for_per_map_sync():
    catalog = {
        "CrossChat": {"Enabled": True, "ServerId": "master", "Command": "/c"},
        "TimedPointsReward": {"Enabled": True, "Groups": {}},
    }
    existing = {"CrossChat": {"ServerId": "mapa-ragnarok"}}
    merged = {"Settings": {}}
    apply_shared_sections_to_plugin(merged, catalog, existing)
    assert "ServerId" not in merged["CrossChat"]
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
        install_dir=r"C:\ARKLAND SERVER\MAPAS\BR",
        id="uuid-brighamia",
    )
    assert _cross_chat_server_label(srv) == "BRIGHAMIA"


def test_cross_chat_server_label_prefers_install_dir_over_shop_server_id():
    srv = SimpleNamespace(
        name="ARK Server TEK",
        cross_chat_label="",
        shop_server_id="amissa",
        install_dir=r"C:\ARKLAND SERVER\MAPAS\BR",
        map="",
        id="brighamia-id",
    )
    assert _cross_chat_server_label(srv) == "BRIGHAMIA"


def test_cross_chat_server_label_uses_explicit_override():
    srv = SimpleNamespace(
        name="ARK Server TEK",
        cross_chat_label="CustomTag",
        shop_server_id="ARKLAND",
        install_dir=r"C:\ARK\ARK Server TEK",
        id="uuid-amissa",
    )
    assert _cross_chat_server_label(srv) == "CustomTag"


def test_cross_chat_server_label_mapas_folder_overrides_legacy_explicit():
    srv = SimpleNamespace(
        name="ARK Server TEK",
        cross_chat_label="Brighamia",
        shop_server_id="",
        install_dir=r"C:\ARKLAND SERVER\MAPAS\BR",
        customshop_config_path=(
            r"C:\ARKLAND SERVER\MAPAS\BR\ShooterGame\Binaries\Win64\ArkApi\Plugins\CustomShop\config.json"
        ),
        id="br-id",
    )
    assert _cross_chat_server_label(srv) == "BRIGHAMIA"


def test_cross_chat_server_label_ignores_shared_shop_server_id():
    srv = SimpleNamespace(
        name="ARK Server TEK",
        cross_chat_label="",
        shop_server_id="ARKLAND",
        install_dir=r"C:\ARK\ARK Server TEK",
        map="",
        id="uuid-unique-abc",
    )
    label = _cross_chat_server_label(srv)
    assert label != "ARKLAND"
    assert "unique" in label or label  # slugify do nome/id


def test_cross_chat_server_label_unique_fallback_when_same_name():
    a = SimpleNamespace(
        name="ARK Server TEK",
        cross_chat_label="",
        shop_server_id="ARKLAND",
        install_dir=r"C:\ARK\ARK Server TEK",
        map="",
        id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    )
    b = SimpleNamespace(
        name="ARK Server TEK",
        cross_chat_label="",
        shop_server_id="ARKLAND",
        install_dir=r"C:\ARK\ARK Server TEK",
        map="",
        id="ffffffff-bbbb-cccc-dddd-eeeeeeeeeeee",
    )
    la = _cross_chat_server_label(a)
    lb = _cross_chat_server_label(b)
    assert la != lb
    assert la != "ARKLAND"
    assert lb != "ARKLAND"


def test_find_cross_chat_collisions_detects_duplicate_labels():
    from types import SimpleNamespace as NS

    a = NS(name="Mapa A", cross_chat_label="ARKLAND", install_dir="", map="", id="a1")
    b = NS(name="Mapa B", cross_chat_label="ARKLAND", install_dir="", map="", id="b2")

    class _FakeCM:
        servers = [a]

    class _FakeAsm:
        servers = [b]

    errors = find_cross_chat_collisions(_FakeCM(), _FakeAsm())
    assert any("duplicado" in e.lower() for e in errors)
    assert any("ARKLAND" in e for e in errors)


def test_sync_plugin_disables_crosschat_by_default(tmp_path):
    catalog = {
        "Kits": {},
        "Items": {},
        "Settings": {"ShopName": "Cluster"},
        "CrossChat": {
            "Enabled": True,
            "ServerId": "Mapa1",
            "AutoCapture": True,
        },
    }
    shop = SimpleNamespace(cross_chat_enabled=False)
    srv = SimpleNamespace(
        name="Crystal",
        shop_server_id="crystal",
        install_dir=str(tmp_path / "MAPAS" / "CI"),
        id="crystal-id",
    )
    plugin_path = tmp_path / "config.json"
    plugin_path.write_text(
        '{"CrossChat":{"Enabled":true,"ServerId":"Crystal"}}',
        encoding="utf-8",
    )

    sync_plugin_at_path(
        catalog, plugin_path,
        "https://shop.test", "http://127.0.0.1:5177", "key", {},
        shop=shop,
        srv=srv,
    )
    saved = json.loads(plugin_path.read_text(encoding="utf-8"))
    assert saved["CrossChat"]["Enabled"] is False
    assert "ServerId" not in saved["CrossChat"]


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
        install_dir=str(tmp_path / "MAPAS" / "BR"),
        id="brighamia-id",
    )
    plugin_path = tmp_path / "MAPAS" / "BR" / "ShooterGame" / "Binaries" / "Win64" / "ArkApi" / "Plugins" / "CustomShop" / "config.json"
    plugin_path.parent.mkdir(parents=True, exist_ok=True)
    plugin_path.write_text('{"CrossChat":{"ServerId":"Mapa1"}}', encoding="utf-8")

    sync_plugin_at_path(
        catalog, plugin_path,
        "https://shop.test", "http://127.0.0.1:5177", "key", {},
        shop=shop,
        srv=srv,
    )
    saved = __import__("json").loads(plugin_path.read_text(encoding="utf-8"))
    assert saved["CrossChat"]["ServerId"] == "BRIGHAMIA"
    assert saved["CrossChat"]["UseWebApi"] is True
    assert saved["CrossChat"]["Enabled"] is True


def test_build_cross_chat_settings_unique_per_map():
    shop = SimpleNamespace(cross_chat_enabled=True)
    catalog_cc = {"Enabled": True, "ServerId": "Mapa1", "Command": "/cluster"}
    a = SimpleNamespace(name="ARK Server TEK", shop_server_id="", install_dir=r"C:\ARKLAND SERVER\MAPAS\BR", id="a")
    b = SimpleNamespace(name="ARK Server TEK", shop_server_id="", install_dir=r"C:\ARKLAND SERVER\MAPAS\AL", id="b")
    cc_a = build_cross_chat_settings(shop, a, catalog_cc=catalog_cc)
    cc_b = build_cross_chat_settings(shop, b, catalog_cc=catalog_cc)
    assert cc_a["ServerId"] == "BRIGHAMIA"
    assert cc_b["ServerId"] == "ALPS"
    assert cc_a["Command"] == "/cluster"
    assert cc_b["Command"] == "/cluster"


def test_build_cross_chat_disabled_keeps_server_id():
    """ServerId permanece com chat off — TribeSync (Minha Tribo) precisa do rótulo do mapa."""
    shop = SimpleNamespace(cross_chat_enabled=False)
    srv = SimpleNamespace(
        name="ARK Server TEK",
        shop_server_id="",
        install_dir=r"C:\ARKLAND SERVER\MAPAS\BR",
        id="br",
    )
    cc = build_cross_chat_settings(shop, srv)
    assert cc["Enabled"] is False
    assert cc["ServerId"] == "BRIGHAMIA"


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


def test_apply_shared_sections_crosschat_master_wins_without_server_id():
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
    assert "ServerId" not in merged["CrossChat"]
    assert merged["CrossChat"]["Command"] == "/cluster"
    assert merged["CrossChat"]["UseWebApi"] is True


def test_mapas_folder_from_plugin_path():
    from src.mapas_cross_chat_ids import mapas_folder_from_path

    path = r"C:\ARKLAND SERVER\MAPAS\BR\ShooterGame\Binaries\Win64\ArkApi\Plugins\CustomShop\config.json"
    assert mapas_folder_from_path(path) == "BR"


def test_cross_chat_server_label_prefers_mapas_folder_over_session_name():
    srv = SimpleNamespace(
        cross_chat_label="",
        install_dir=r"C:\ARKLAND SERVER\MAPAS\AL",
        customshop_config_path=(
            r"C:\ARKLAND SERVER\MAPAS\G2\ShooterGame\Binaries\Win64\ArkApi\Plugins\CustomShop\config.json"
        ),
        map="",
        session_name="ALPS",
        name="ARKLAND",
        id="g2-id",
    )
    assert _cross_chat_server_label(srv) == "GENESIS 2"


def test_repair_cross_chat_server_ids_on_disk(tmp_path):
    from src.shop_integration import repair_cross_chat_server_ids_on_disk

    for folder in ("BR", "AL"):
        cfg = tmp_path / folder / "ShooterGame/Binaries/Win64/ArkApi/Plugins/CustomShop"
        cfg.mkdir(parents=True)
        (cfg / "config.json").write_text(
            '{"CrossChat":{"Enabled":true,"ServerId":"Mapa1"}}',
            encoding="utf-8",
        )
    notes = repair_cross_chat_server_ids_on_disk(tmp_path)
    assert len(notes) == 2
    b = json.loads(
        (tmp_path / "BR/ShooterGame/Binaries/Win64/ArkApi/Plugins/CustomShop/config.json")
        .read_text(encoding="utf-8")
    )
    i = json.loads(
        (tmp_path / "AL/ShooterGame/Binaries/Win64/ArkApi/Plugins/CustomShop/config.json")
        .read_text(encoding="utf-8")
    )
    assert b["CrossChat"]["ServerId"] == "BRIGHAMIA"
    assert i["CrossChat"]["ServerId"] == "ALPS"


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


def test_collect_groups_from_catalog_excludes_vip_keeps_moderacao():
    catalog = {
        "Kits": {
            "vip_bronze": {"Permissions": "Admins,VIPBronze"},
        },
        "Items": {
            "licenca_vip_bronze": {"LicenseGrant": {"Group": "VIPBronze", "Days": 30}},
        },
        "TimedPointsReward": {
            "Groups": {
                "Default": {"Amount": 25},
                "VIPBronze": {"Amount": 20},
                "Moderacao": {"Amount": 500},
            },
        },
    }
    groups = collect_groups_from_catalog(catalog)
    assert "VIPBronze" not in groups
    assert "Moderacao" in groups
    assert "Default" in groups
