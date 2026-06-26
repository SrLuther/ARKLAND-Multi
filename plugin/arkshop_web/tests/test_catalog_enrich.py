"""Testes de enriquecimento do catálogo público."""
from catalog_enrich import enrich_kit, enrich_shop_item


def test_enrich_dino_uses_species_registry():
    entry = {
        "Type": "dino",
        "Price": 15000,
        "Description": "Giganotosaurus Fêmea Nível 1",
        "Dinos": [{
            "Blueprint": "/Game/PrimalEarth/Dinos/Giganotosaurus/Gigant_Character_BP.Gigant_Character_BP",
            "Level": 1,
        }],
    }
    meta = enrich_shop_item("giga", entry)
    assert meta["display_category"] == "Dinos"
    assert meta["thumbnail_url"].startswith("/species/icons/")
    assert meta["tier"] in ("S+", "S", "A", "B", "C")
    assert "giga" in meta["search_text"]
    assert "gigant" in meta["search_text"] or "giganoto" in meta["search_text"]


def test_enrich_item_category_icon():
    entry = {
        "Type": "item",
        "Category": "Ferramentas",
        "Name": "Metal Pick",
        "Description": "Picareta de metal",
        "Price": 100,
    }
    meta = enrich_shop_item("pick", entry)
    assert meta["thumbnail_url"] == "/catalog/tool.svg"
    assert meta["display_category"] == "Ferramentas"
    assert "picareta" in meta["search_text"]


def test_enrich_license_metadata():
    entry = {
        "Type": "license",
        "Category": "Licenças",
        "Name": "Licença Gamma",
        "Description": "Licença Gamma (30 dias)",
        "LicenseGrant": {"Group": "Gamma", "Days": 30},
        "Price": 50000,
    }
    meta = enrich_shop_item("licenca_gamma", entry)
    assert meta["thumbnail_url"] == "/catalog/license.svg"
    assert meta["license_days"] == 30
    assert meta["license_group"] == "Gamma"


def test_enrich_kit_contents_and_tier():
    entry = {
        "Description": "Kit Iniciante",
        "Price": 3000,
        "Items": [
            {"Blueprint": "/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponMetalPick.PrimalItem_WeaponMetalPick", "Amount": 1},
            {"Blueprint": "/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponMetalHatchet.PrimalItem_WeaponMetalHatchet", "Amount": 1},
        ],
    }
    meta = enrich_kit("starter", entry)
    assert meta["item_count"] == 2
    assert len(meta["kit_contents"]) == 2
    assert meta["thumbnail_url"].endswith(".svg")
    assert meta["tier"] == "B"
    assert "kit iniciante" in meta["search_text"]
