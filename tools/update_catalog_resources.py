"""Atualiza docs/config.json: recursos, kit recursos, starter, VIP, mindwipe."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

CONFIG = Path("docs/config.json")
DISCOUNT = 0.75  # kit paga 25% do valor avulso (75% de desconto)

# (id, blueprint, descricao, stack, preco total do stack)
NEW_REC_ITEMS: list[tuple[str, str, str, int, int]] = [
    ("rec_stone", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Stone.PrimalItemResource_Stone", "Pedra (1000x)", 1000, 100),
    ("rec_wood", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Wood.PrimalItemResource_Wood", "Madeira (1000x)", 1000, 100),
    ("rec_thatch", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Thatch.PrimalItemResource_Thatch", "Sapinho (1000x)", 1000, 100),
    ("rec_flint", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Flint.PrimalItemResource_Flint", "Sílex (1000x)", 1000, 100),
    ("rec_fiber", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Fibers.PrimalItemResource_Fibers", "Fibra (1000x)", 1000, 100),
    ("rec_hide", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Hide.PrimalItemResource_Hide", "Couro (1000x)", 1000, 100),
    ("rec_cookedmeat", "/Game/PrimalEarth/CoreBlueprints/Items/Consumables/PrimalItemConsumable_CookedMeat.PrimalItemConsumable_CookedMeat", "Carne Cozida (1000x)", 1000, 100),
    ("rec_metal", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Metal.PrimalItemResource_Metal", "Metal (1000x)", 1000, 200),
    ("rec_metalingot", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_MetalIngot.PrimalItemResource_MetalIngot", "Lingote de Metal (1000x)", 1000, 200),
    ("rec_obsidian", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Obsidian.PrimalItemResource_Obsidian", "Obsidiana (1000x)", 1000, 200),
    ("rec_silicon", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Silicon.PrimalItemResource_Silicon", "Pó de Cimento (1000x)", 1000, 375),
    ("rec_cement", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_ChitinPaste.PrimalItemResource_ChitinPaste", "Pasta de Cimento (1000x)", 1000, 375),
    ("rec_electronics", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Electronics.PrimalItemResource_Electronics", "Eletrônicos (1000x)", 1000, 375),
    ("rec_oil", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Oil.PrimalItemResource_Oil", "Óleo (1000x)", 1000, 375),
    ("rec_element", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Element.PrimalItemResource_Element", "Elemento (1000x)", 1000, 900),
    ("rec_mutagel", "/Game/Genesis2/CoreBlueprints/Environment/Mutagen/PrimalItemConsumable_Mutagel.PrimalItemConsumable_Mutagel", "Mutagel (1000x)", 1000, 600),
    ("rec_sparkpowder", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Sparkpowder.PrimalItemResource_Sparkpowder", "Pó de Ignição (1000x)", 1000, 250),
    ("rec_gunpowder", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Gunpowder.PrimalItemResource_Gunpowder", "Pólvora (1000x)", 1000, 300),
    ("rec_charcoal", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Charcoal.PrimalItemResource_Charcoal", "Carvão (1000x)", 1000, 150),
    ("rec_narcotic", "/Game/PrimalEarth/CoreBlueprints/Items/Consumables/PrimalItemConsumable_Narcotic.PrimalItemConsumable_Narcotic", "Narcótico (1000x)", 1000, 275),
    ("rec_medicalbrew", "/Game/PrimalEarth/CoreBlueprints/Items/Consumables/PrimalItemConsumable_HealSoup.PrimalItemConsumable_HealSoup", "Poção Médica (1000x)", 1000, 325),
    ("rec_stimulant", "/Game/PrimalEarth/CoreBlueprints/Items/Consumables/PrimalItemConsumable_Stimulant.PrimalItemConsumable_Stimulant", "Estimulante (1000x)", 1000, 275),
    ("rec_gasoline", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Gasoline.PrimalItemResource_Gasoline", "Gasolina (1000x)", 1000, 400),
    ("rec_propellant", "/Game/ScorchedEarth/WeaponFlamethrower/PrimalItemResource_Propellant.PrimalItemResource_Propellant", "Propelente (1000x)", 1000, 350),
]

# rec_key -> quantidade no kit emergencial
KIT_RECURSOS_CONTENTS: list[tuple[str, int]] = [
    ("rec_stone", 5000),
    ("rec_wood", 5000),
    ("rec_thatch", 5000),
    ("rec_flint", 5000),
    ("rec_fiber", 5000),
    ("rec_hide", 5000),
    ("rec_cookedmeat", 5000),
    ("rec_charcoal", 3000),
    ("rec_metal", 3000),
    ("rec_metalingot", 3000),
    ("rec_obsidian", 2000),
    ("rec_crystal", 2000),
    ("rec_chitin", 2000),
    ("rec_keratin", 2000),
    ("rec_silicon", 2000),
    ("rec_cement", 2000),
    ("rec_polymer", 2000),
    ("rec_electronics", 1500),
    ("rec_oil", 1500),
    ("rec_sparkpowder", 2000),
    ("rec_gunpowder", 1500),
    ("rec_narcotic", 1000),
    ("rec_medicalbrew", 500),
    ("rec_stimulant", 500),
    ("rec_pnegra", 1000),
    ("rec_gasoline", 1000),
    ("rec_element", 500),
    ("rec_mutagel", 500),
    ("rec_elementore", 1000),
]

VIP_KIT_PREFIXES = (
    "kit_blindado_",
    "kit_tek_gen2_",
    "kit_tek_padrao_",
)

VIP_ITEM_KEYS = {
    "blindado_gamma_pacote",
    "tek_gamma_pacote",
    "tek_gen2_gamma_pacote",
}


def make_rec_item(blueprint: str, desc: str, stack: int, price: int) -> dict:
    return {
        "Description": desc,
        "Items": [
            {
                "Blueprint": blueprint,
                "Quantity": stack,
                "Quality": 0,
                "ForceBlueprint": False,
            }
        ],
        "Price": price,
        "Type": "item",
    }


def make_kit_item(blueprint: str, qty: int, quality: int = 0) -> dict:
    return {
        "Blueprint": blueprint,
        "Quantity": qty,
        "Quality": quality,
        "ForceBlueprint": False,
    }


def stack_size(item: dict) -> int:
    desc = item.get("Description", "")
    m = re.search(r"\((\d+)x\)", desc)
    if m:
        return int(m.group(1))
    items = item.get("Items") or []
    if items:
        return items[0].get("Quantity", 1000)
    return item.get("Quantity", 1000)


def unit_price(items: dict, key: str) -> float:
    item = items[key]
    return item["Price"] / stack_size(item)


def blueprint_for_rec(items: dict, key: str) -> str:
    sub = items[key]["Items"][0]
    return sub["Blueprint"]


def build_starter() -> dict:
    return {
        "DefaultAmount": 1,
        "Description": "Kit Inicial — ferramentas, breeding S+, dinos e selas",
        "Dinos": [
            {
                "Blueprint": "/Game/PrimalEarth/Dinos/Argentavis/Argent_Character_BP.Argent_Character_BP",
                "ForceTame": True,
                "Gender": "female",
                "Level": 350,
                "Neutered": False,
            },
            {
                "Blueprint": "/Game/PrimalEarth/Dinos/Trike/Trike_Character_BP_Aberrant.Trike_Character_BP_Aberrant",
                "ForceTame": True,
                "Gender": "female",
                "Level": 350,
                "Neutered": False,
            },
        ],
        "Items": [
            make_kit_item("/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponMetalPick.PrimalItem_WeaponMetalPick", 1, 100),
            make_kit_item("/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponMetalHatchet.PrimalItem_WeaponMetalHatchet", 1, 100),
            make_kit_item("/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponPike.PrimalItem_WeaponPike", 1, 100),
            make_kit_item("/Game/Mods/1404697612/PrimalItem_AwesomeSpyGlass.PrimalItem_AwesomeSpyGlass", 1),
            make_kit_item("/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponCrossbow.PrimalItem_WeaponCrossbow", 1, 100),
            make_kit_item("/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItemAmmo_ArrowTranq.PrimalItemAmmo_ArrowTranq", 50),
            make_kit_item("/Game/PrimalEarth/CoreBlueprints/Items/Consumables/PrimalItemConsumable_Kibble_Base_Special.PrimalItemConsumable_Kibble_Base_Special", 30),
            make_kit_item("/Game/Mods/DinoStorage2/SoulTraps_DS.SoulTraps_DS", 5),
            make_kit_item("/Game/PrimalEarth/CoreBlueprints/Items/Armor/Hide/PrimalItemArmor_HideHelmet.PrimalItemArmor_HideHelmet", 1),
            make_kit_item("/Game/PrimalEarth/CoreBlueprints/Items/Armor/Hide/PrimalItemArmor_HideShirt.PrimalItemArmor_HideShirt", 1),
            make_kit_item("/Game/PrimalEarth/CoreBlueprints/Items/Armor/Hide/PrimalItemArmor_HidePants.PrimalItemArmor_HidePants", 1),
            make_kit_item("/Game/PrimalEarth/CoreBlueprints/Items/Armor/Hide/PrimalItemArmor_HideGloves.PrimalItemArmor_HideGloves", 1),
            make_kit_item("/Game/PrimalEarth/CoreBlueprints/Items/Armor/Hide/PrimalItemArmor_HideBoots.PrimalItemArmor_HideBoots", 1),
            make_kit_item("/Game/Mods/AwesomeTeleporters/Blueprints/Remote/PrimalItem_AwesomeTeleporters_Remote.PrimalItem_AwesomeTeleporters_Remote", 1),
            make_kit_item("/Game/Mods/AwesomeTeleporters/Blueprints/Teleporter/PrimalItem_AwesomeTeleporters_Teleporter.PrimalItem_AwesomeTeleporters_Teleporter", 1),
            make_kit_item("/Game/Mods/DinoStorage2/SoulGun_DS.SoulGun_DS", 1),
            make_kit_item("/Game/Mods/StructuresPlusMod/Misc/Hatchery/PrimalItemStructure_Hatchery.PrimalItemStructure_Hatchery", 1),
            make_kit_item("/Game/Mods/StructuresPlusMod/Misc/Nanny/PrimalItemStructure_Nanny.PrimalItemStructure_Nanny", 1),
            make_kit_item("/Game/PrimalEarth/CoreBlueprints/Items/Consumables/BaseBPs/PrimalItemConsumableMiracleGro.PrimalItemConsumableMiracleGro", 1000),
            make_kit_item("/Game/PrimalEarth/CoreBlueprints/Items/Armor/Saddles/PrimalItemArmor_ArgentavisSaddle.PrimalItemArmor_ArgentavisSaddle", 1),
            make_kit_item("/Game/PrimalEarth/CoreBlueprints/Items/Armor/Saddles/PrimalItemArmor_TrikeSaddle.PrimalItemArmor_TrikeSaddle", 1),
        ],
        "Price": 0,
    }


def main() -> None:
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    items: dict = data.setdefault("Items", {})
    kits: dict = data.setdefault("Kits", {})

    # --- novos recursos avulsos ---
    for key, bp, desc, stack, price in NEW_REC_ITEMS:
        items[key] = make_rec_item(bp, desc, stack, price)

    items["rec_pnegra"]["Price"] = 450

    # --- remover VIP kits ---
    for key in list(kits.keys()):
        if any(key.startswith(p) for p in VIP_KIT_PREFIXES):
            del kits[key]

    # --- remover itens VIP / pacotes licenciados ---
    for key in VIP_ITEM_KEYS:
        items.pop(key, None)

    # --- limpar Permissions em Items ---
    for key, item in list(items.items()):
        if "Permissions" in item:
            del item["Permissions"]
        desc = item.get("Description", "")
        if "VIP" in desc or "vip" in desc.lower():
            item["Description"] = re.sub(r"\s*[—–-]\s*\d+\s*Âmbar.*VIP.*", "", desc).strip()
            item["Description"] = re.sub(r"\s*;\s*kit VIP.*", "", item["Description"], flags=re.I).strip()

    # --- preços públicos para ex-VIP ---
    if "struct_generatortek" in items:
        items["struct_generatortek"]["Price"] = 18000
        items["struct_generatortek"]["Description"] = "Gerador Tek S+ (1x)"
    if "struct_transmitter" in items:
        items["struct_transmitter"]["Price"] = 22000
        items["struct_transmitter"]["Description"] = "Transmissor S+ (1x)"
    if "stryder_rig" in items:
        items["stryder_rig"]["Price"] = 3500
        items["stryder_rig"]["Description"] = "Swappable Stryder Rig (1x)"
    if "item_soultraps_20" in items:
        items["item_soultraps_20"]["Price"] = 750
        items["item_soultraps_20"]["Description"] = "Soul Traps DinoStorage (20x)"

    # --- mindwipe ---
    items["res_mindwipe"]["Price"] = 100

    # --- kit recursos ---
    kit_items = []
    total_retail = 0.0
    for rec_key, qty in KIT_RECURSOS_CONTENTS:
        if rec_key not in items:
            raise KeyError(f"Recurso ausente no catálogo: {rec_key}")
        bp = blueprint_for_rec(items, rec_key)
        kit_items.append(make_kit_item(bp, qty))
        total_retail += unit_price(items, rec_key) * qty

    kit_price = max(1, int(total_retail * (1 - DISCOUNT)))
    kits["recursos"] = {
        "DefaultAmount": 1,
        "Description": "Kit Recursos Emergencial (75% off vs compra avulsa)",
        "Items": kit_items,
        "Price": kit_price,
    }

    # --- starter unificado ---
    kits["starter"] = build_starter()
    kits.pop("starter2", None)

    CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Recursos avulsos novos: {len(NEW_REC_ITEMS)}")
    print(f"Kit recursos: {len(kit_items)} linhas, retail={int(total_retail)}, price={kit_price}")
    print(f"Kits VIP removidos; starter2 removido; mindwipe=100")


if __name__ == "__main__":
    main()
