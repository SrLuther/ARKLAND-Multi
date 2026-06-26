"""Testes de preços VIP no catálogo."""
from __future__ import annotations

from src.catalog_vip_pricing import (
    apply_vip_pricing_to_catalog,
    catalog_has_placeholder_kit_prices,
)


def test_sanitize_placeholder_vip_kits():
    data = {
        "Items": {
            "licenca_vip_bronze": {
                "Type": "license",
                "Price": 3000,
                "LicenseGrant": {"Group": "VIPBronze", "Days": 30},
            },
            "licenca_vip_diamante": {
                "Type": "license",
                "Price": 11250,
                "LicenseGrant": {"Group": "VIPDiamante", "Days": 30},
            },
            "licenca_alfa": {
                "Type": "license",
                "Price": 100000,
                "LicenseGrant": {"Group": "Alfa", "Days": 30},
            },
        },
        "Kits": {
            "vip_bronze": {"Price": 99_999_999, "Permissions": "Admins,VIPBronze"},
            "diamante": {"Price": 1, "Permissions": "Admins,Alfa"},
            "kit_tek_padrao_alfa": {"Price": 99_999_999, "Permissions": "Admins,Alfa"},
        },
    }
    assert catalog_has_placeholder_kit_prices(data)
    cleared, _updates = apply_vip_pricing_to_catalog(data)
    assert "vip_bronze" in "".join(cleared)
    assert data["Kits"]["vip_bronze"]["Price"] == 300
    assert data["Kits"]["diamante"]["Price"] == 1125
    assert data["Kits"]["diamante"]["Permissions"] == "Admins,VIPDiamante"
    assert data["Kits"]["kit_tek_padrao_alfa"]["Price"] == 10000
    assert not catalog_has_placeholder_kit_prices(data)


def test_apply_vip_pricing_does_not_shrink_full_catalog():
    """Guarda: catálogo completo não perde itens/kits após apply_vip_pricing."""
    from src.shop_integration import catalog_entry_counts

    items = {f"item_{i}": {"Type": "item", "Price": 100} for i in range(210)}
    kits = {f"kit_{i}": {"Price": 500} for i in range(30)}
    data = {"Items": items, "Kits": kits}
    before_items, before_kits = catalog_entry_counts(data)
    apply_vip_pricing_to_catalog(data)
    after_items, after_kits = catalog_entry_counts(data)
    assert after_items >= before_items
    assert after_kits >= before_kits
    assert after_items >= 200
    assert after_kits >= 25
