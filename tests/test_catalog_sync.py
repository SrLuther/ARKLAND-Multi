"""Testes de manutenção do catálogo no sync TEK."""
from __future__ import annotations

from src.catalog_sync import (
    apply_catalog_sync,
    catalog_has_placeholder_kit_prices,
)


def test_purge_retired_licenses_and_kits_on_sync():
    data = {
        "Items": {
            "licenca_vip_bronze": {
                "Type": "license",
                "Price": 3000,
                "LicenseGrant": {"Group": "VIPBronze", "Days": 30},
            },
            "licenca_alfa": {
                "Type": "license",
                "Price": 100000,
                "LicenseGrant": {"Group": "Alfa", "Days": 30},
            },
            "struct_generatortek": {"Type": "item", "Price": 90},
        },
        "Kits": {
            "vip_bronze": {"Price": 300, "Permissions": "Admins,VIPBronze"},
            "prata": {"Price": 450, "Permissions": "Admins,VIPPrata"},
            "kit_tek_padrao_alfa": {"Price": 99_999_999, "Permissions": "Admins,Alfa"},
        },
    }
    cleared, updates = apply_catalog_sync(data)
    assert "licenca_vip_bronze" not in data["Items"]
    assert "vip_bronze" not in data["Kits"]
    assert "prata" not in data["Kits"]
    assert "licenca_alfa" in data["Items"]
    assert any("removed:item:licenca_vip_bronze" in c for c in cleared)
    assert any("removed:kit:vip_bronze" in c for c in cleared)
    assert data["Kits"]["kit_tek_padrao_alfa"]["Price"] == 50000
    assert "kit_tek_padrao_alfa" in "".join(updates)


def test_sanitize_placeholder_tier_kits():
    data = {
        "Items": {
            "licenca_alfa": {
                "Type": "license",
                "Price": 100000,
                "LicenseGrant": {"Group": "Alfa", "Days": 30},
            },
        },
        "Kits": {
            "kit_tek_padrao_alfa": {"Price": 99_999_999, "Permissions": "Admins,Alfa"},
        },
    }
    assert catalog_has_placeholder_kit_prices(data)
    cleared, _ = apply_catalog_sync(data)
    assert "kit_tek_padrao_alfa" in "".join(cleared)
    assert data["Kits"]["kit_tek_padrao_alfa"]["Price"] == 50000
    assert not catalog_has_placeholder_kit_prices(data)


def test_catalog_sync_does_not_shrink_full_catalog():
    from src.shop_integration import catalog_entry_counts

    items = {f"item_{i}": {"Type": "item", "Price": 100} for i in range(210)}
    kits = {f"kit_{i}": {"Price": 500} for i in range(30)}
    data = {"Items": items, "Kits": kits}
    before_items, before_kits = catalog_entry_counts(data)
    apply_catalog_sync(data)
    after_items, after_kits = catalog_entry_counts(data)
    assert after_items >= before_items
    assert after_kits >= before_kits
    assert after_items >= 200
    assert after_kits >= 25


def test_does_not_inject_licenses_or_rewrite_items():
    data = {
        "Items": {
            "struct_generatortek": {"Type": "item", "Price": 90},
            "struct_transmitter": {"Type": "item", "Price": 90},
        },
        "Kits": {},
    }
    apply_catalog_sync(data)
    assert "licenca_vip_bronze" not in data["Items"]
    assert data["Items"]["struct_generatortek"]["Price"] == 90
    assert "Permissions" not in data["Items"]["struct_generatortek"]


def test_purge_vip_and_moderacao_from_timed_points():
    data = {
        "Items": {},
        "Kits": {},
        "TimedPointsReward": {
            "Groups": {
                "Default": {"Amount": 25},
                "VIPBronze": {"Amount": 20},
                "Moderacao": {"Amount": 500},
            },
        },
    }
    cleared, _ = apply_catalog_sync(data)
    groups = data["TimedPointsReward"]["Groups"]
    assert "VIPBronze" not in groups
    assert "Moderacao" not in groups
    assert "Mod" in groups
    assert groups["Mod"]["Amount"] == 500
    assert any("timed:VIPBronze" in c for c in cleared)
