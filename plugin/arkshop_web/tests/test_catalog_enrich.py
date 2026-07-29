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


def test_enrich_rex_uses_generated_webp():
    entry = {
        "Type": "dino",
        "Price": 8000,
        "Description": "Rex Fêmea Nível 1",
        "Dinos": [{
            "Blueprint": "/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP",
            "Level": 1,
        }],
    }
    meta = enrich_shop_item("rex", entry)
    assert meta["thumbnail_url"].endswith("/species/icons/generated/rex.webp")
    assert meta["species_key"] == "rex"
    assert meta["tier"] == "A"


def test_enrich_bionicrex_uses_generated_webp():
    entry = {
        "Type": "dino",
        "Price": 9000,
        "Description": "Rex Bionic",
        "Dinos": [{
            "Blueprint": "/Game/PrimalEarth/Dinos/Rex/BionicRex_Character_BP.BionicRex_Character_BP",
            "Level": 1,
        }],
    }
    meta = enrich_shop_item("bionicrex", entry)
    assert meta["thumbnail_url"].endswith("/species/icons/generated/bionicrex.webp")
    assert meta["species_key"] == "bionicrex"


def test_enrich_rec_wood_uses_resource_webp():
    entry = {
        "Type": "item",
        "Description": "Madeira (1000x)",
        "Items": [{
            "Blueprint": "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Wood.PrimalItemResource_Wood",
            "Quantity": 1000,
        }],
        "Price": 100,
    }
    meta = enrich_shop_item("rec_wood", entry)
    assert meta["thumbnail_url"].endswith("/catalog/resources/rec_wood.webp")
    assert meta["display_category"] == "Recursos"
    assert "madeira" in meta["search_text"]


def test_enrich_daco_sushi_uses_resource_webp():
    entry = {
        "Type": "item",
        "Category": "Recursos",
        "Name": "Sushi Daco (1x)",
        "Items": [{
            "Blueprint": "/Game/Abyss/CoreBlueprints/Items/Consumables/PrimalItemConsumable_DacoSushi.PrimalItemConsumable_DacoSushi",
            "Quantity": 1,
        }],
        "Price": 15,
    }
    meta = enrich_shop_item("daco_sushi", entry)
    assert meta["thumbnail_url"].endswith("/catalog/resources/daco_sushi.webp")


def test_enrich_resource_fallback_consumable_without_manifest():
    entry = {
        "Type": "item",
        "Category": "Recursos",
        "Name": "Recurso Fantasma",
        "Price": 10,
    }
    meta = enrich_shop_item("recurso_fantasma_xyz", entry)
    assert meta["thumbnail_url"] == "/catalog/category-resources.webp"


def test_enrich_item_category_icon():
    entry = {
        "Type": "item",
        "Category": "Ferramentas",
        "Name": "Metal Pick",
        "Description": "Picareta de metal",
        "Price": 100,
    }
    meta = enrich_shop_item("pick", entry)
    assert meta["thumbnail_url"] == "/catalog/category-tools.webp"
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


def test_infer_category_saddle():
    entry = {
        "Type": "item",
        "Name": "Rex Saddle",
        "Description": "Sela para Rex",
        "Price": 500,
    }
    meta = enrich_shop_item("rex_saddle", entry)
    assert meta["display_category"] == "Selas"


def test_infer_category_blueprint():
    entry = {
        "Type": "blueprint",
        "Name": "Metal Pick BP",
        "Price": 200,
    }
    meta = enrich_shop_item("pick_bp", entry)
    assert meta["display_category"] == "Blueprints"


def test_infer_category_estrutura():
    entry = {
        "Type": "item",
        "Name": "Tek Replicator",
        "Description": "Estrutura de crafting",
        "Price": 10000,
    }
    meta = enrich_shop_item("tek_rep", entry)
    assert meta["display_category"] == "Estruturas"
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
    assert meta["thumbnail_url"] == "/catalog/category-kits.webp"
    assert meta["tier"] == "B"
    assert "kit iniciante" in meta["search_text"]
    # Estrutura pronta para kits sem metadados ItensAlfa
    assert meta["kit_description"] == ""
    assert "characteristics" in meta["kit_contents"][0]
    assert meta["kit_contents"][0]["characteristics"] == ""


def test_enrich_kit_itensalfa_from_sheet():
    entry = {
        "Description": "Kit ItensAlfa Delta",
        "KitDescription": "Pacote completo do tier Delta.",
        "Price": 9890,
        "Items": [{
            "Blueprint": "/Game/Mods/ItensAlfa/Armas/Delta/AlfaItemWeapon_TekRifle_D.AlfaItemWeapon_TekRifle_D",
            "Quantity": 1,
        }],
    }
    meta = enrich_kit("kit_itensalfa_delta", entry)
    assert meta["kit_description"] == "Pacote completo do tier Delta."
    assert len(meta["kit_contents"]) == 1
    c0 = meta["kit_contents"][0]
    assert c0["label"] == "Rifle TEK"
    assert c0["kind"] == "weapon"
    assert c0["tier"] == "Delta"
    assert "Dano" in (c0.get("characteristics") or "")
    assert "Polímero" in (c0.get("materials_text") or "")
    assert meta["kit_summary"]["counts"]["weapon"] == 1
    assert meta["kit_summary"]["highlights"]


def test_enrich_kit_itensalfa_with_saddle():
    entry = {
        "Name": "Kit ItensAlfa Delta",
        "Description": "legacy one-liner",
        "Price": 9890,
        "Items": [
            {
                "Blueprint": "/Game/Mods/ItensAlfa/Armadura/Delta/AlfaItemArmor_TekBoots_D.AlfaItemArmor_TekBoots_D",
                "Quantity": 1,
            },
            {
                "Blueprint": "/Game/Mods/ItensAlfa/Selas/Delta/AlfaItemSaddle_Megalodon_D.AlfaItemSaddle_Megalodon_D",
                "Quantity": 1,
            },
        ],
    }
    meta = enrich_kit("kit_itensalfa_delta", entry)
    assert meta["kit_summary"]["counts"]["armor"] == 1
    assert meta["kit_summary"]["counts"]["saddle"] == 1
    assert any("sela" in h.lower() for h in meta["kit_summary"]["highlights"])
    assert "Armadura da sela" in (meta["kit_contents"][1].get("characteristics") or meta["kit_contents"][1].get("stats", {}).get("label") or "")
    assert meta["kit_description"]  # auto a partir dos highlights


def test_enrich_kit_manual_characteristics_override():
    entry = {
        "Description": "Kit custom",
        "Price": 100,
        "Items": [{
            "Blueprint": "/Game/Foo/Bar.Bar",
            "Amount": 2,
            "Characteristics": "Item especial de evento",
        }],
    }
    meta = enrich_kit("kit_custom", entry)
    assert meta["kit_contents"][0]["characteristics"] == "Item especial de evento"
    assert meta["kit_contents"][0]["amount"] == 2
