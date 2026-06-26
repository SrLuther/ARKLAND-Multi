#!/usr/bin/env python3
"""Apply VIP/license/kit pricing strategy to CustomShop config.json."""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATHS = [
    ROOT / "plugin" / "CustomShop" / "configs" / "config.json",
    ROOT / "plugin" / "CustomShop" / "bin" / "config.json",
]

# License Âmbar (150 Âmbar/R$ reference from tier face values)
VIP_LICENSES = {
    "licenca_vip_bronze": {
        "group": "VIPBronze",
        "name": "Licença VIP Bronze",
        "price": 3000,
        "brl": 20,
        "description": "Licença VIP Bronze (30 dias) — necessária para resgatar o Kit VIP Bronze",
    },
    "licenca_vip_prata": {
        "group": "VIPPrata",
        "name": "Licença VIP Prata",
        "price": 4500,
        "brl": 30,
        "description": "Licença VIP Prata (30 dias) — necessária para resgatar o Kit VIP Prata",
    },
    "licenca_vip_ouro": {
        "group": "VIPOuro",
        "name": "Licença VIP Ouro",
        "price": 7500,
        "brl": 50,
        "description": "Licença VIP Ouro (30 dias) — necessária para resgatar o Kit VIP Ouro (kit alfa)",
    },
    "licenca_vip_diamante": {
        "group": "VIPDiamante",
        "name": "Licença VIP Diamante",
        "price": 11250,
        "brl": 75,
        "description": "Licença VIP Diamante (30 dias) — somente Âmbar; não disponível em doações PIX",
    },
}

VIP_KITS = {
    "vip_bronze": {"license_key": "licenca_vip_bronze", "perm": "VIPBronze", "label": "Bronze"},
    "prata": {"license_key": "licenca_vip_prata", "perm": "VIPPrata", "label": "Prata"},
    "ouro": {"license_key": "licenca_vip_ouro", "perm": "VIPOuro", "label": "Ouro"},
    "diamante": {"license_key": "licenca_vip_diamante", "perm": "Admins", "label": "Diamante"},
}

MARKUP = 1.5
MAJOR_STRUCT_COUNT = 5  # transmitter, soultraps, rig, generator, replicator

POINT_PACKAGES = [
    {"id": "p500", "label": "500 Âmbares", "points": 500, "price_brl": 5.0},
    {"id": "p1200", "label": "1.200 Âmbares", "points": 1200, "price_brl": 10.0},
    {"id": "p3000", "label": "3.000 Âmbares", "points": 3000, "price_brl": 20.0},
    {"id": "p8000", "label": "8.000 Âmbares", "points": 8000, "price_brl": 45.0},
    {
        "id": "p8250",
        "label": "8.250 Âmbares — Kit VIP Ouro",
        "points": 8250,
        "price_brl": 75.0,
        "note": "Suficiente para Licença VIP Ouro (7.500) + Kit Ouro/alfa (750). Apenas Âmbar — VIP Diamante não incluído.",
    },
]


def bundle_item_price(kit_price: int) -> int:
    return max(1, math.ceil(kit_price / MAJOR_STRUCT_COUNT * MARKUP))


def license_entry(spec: dict) -> dict:
    return {
        "Type": "license",
        "Category": "Licenças VIP",
        "Name": spec["name"],
        "Price": spec["price"],
        "Description": spec["description"],
        "LicenseGrant": {
            "Group": spec["group"],
            "Days": 30,
            "Redeemable": True,
        },
    }


def apply(config_path: Path) -> None:
    data = json.loads(config_path.read_text(encoding="utf-8"))
    items = data.setdefault("Items", {})
    kits = data.setdefault("Kits", {})

    for key, spec in VIP_LICENSES.items():
        items[key] = license_entry(spec)

    # Kit prices = 10% license
    for kit_id, meta in VIP_KITS.items():
        if kit_id not in kits:
            continue
        lic_price = VIP_LICENSES[meta["license_key"]]["price"]
        kit_price = lic_price // 10
        kits[kit_id]["Price"] = kit_price
        kits[kit_id]["Permissions"] = f"Admins,{meta['perm']}" if meta["perm"] != "Admins" else "Admins"
        label = meta["label"]
        kits[kit_id]["Description"] = (
            f"Kit VIP {label} — {kit_price:,} Âmbar (10% da licença). "
            f"Requer Licença VIP {label}."
        ).replace(",", ".")

    # Standalone premium structures
    if "struct_tekforge" in items:
        items["struct_tekforge"]["Price"] = 50000
        items["struct_tekforge"]["Category"] = items["struct_tekforge"].get("Category") or "Ferramentas"
    if "struct_tekreplicator" in items:
        items["struct_tekreplicator"]["Price"] = 52500
        items["struct_tekreplicator"]["Category"] = items["struct_tekreplicator"].get("Category") or "Ferramentas"

    bronze_kit = VIP_LICENSES["licenca_vip_bronze"]["price"] // 10
    indiv_price = bundle_item_price(bronze_kit)

    vip_individuals = {
        "struct_transmitter": {
            "Type": "item",
            "Category": "Ferramentas",
            "Price": indiv_price,
            "Permissions": "Admins,VIPBronze",
            "Description": f"Transmissor S+ (1x) — {indiv_price:,} Âmbar; kit VIP Bronze é melhor custo-benefício".replace(",", "."),
            "Items": [
                {
                    "Blueprint": "/Game/Mods/StructuresPlusMod/Misc/Transmitter/PrimalItemStructure_TransmitterPlus.PrimalItemStructure_TransmitterPlus",
                    "Quantity": 1,
                    "Quality": 0,
                    "ForceBlueprint": False,
                }
            ],
        },
        "struct_generatortek": {
            "Type": "item",
            "Category": "Ferramentas",
            "Price": indiv_price,
            "Permissions": "Admins,VIPBronze",
            "Description": f"Gerador Tek S+ (1x) — {indiv_price:,} Âmbar; kit VIP Bronze é melhor custo-benefício".replace(",", "."),
            "Items": [
                {
                    "Blueprint": "/Game/Mods/StructuresPlusMod/Misc/GeneratorTek/PrimalItemStructure_GeneratorTek.PrimalItemStructure_GeneratorTek",
                    "Quantity": 1,
                    "Quality": 0,
                    "ForceBlueprint": False,
                }
            ],
        },
        "item_soultraps_20": {
            "Type": "item",
            "Category": "Ferramentas",
            "Price": indiv_price,
            "Permissions": "Admins,VIPBronze",
            "Description": f"Soul Traps DinoStorage (20x) — {indiv_price:,} Âmbar; kit VIP Bronze é melhor custo-benefício".replace(",", "."),
            "Items": [
                {
                    "Blueprint": "/Game/Mods/DinoStorage2/SoulTraps_DS.SoulTraps_DS",
                    "Quantity": 20,
                    "Quality": 0,
                    "ForceBlueprint": False,
                }
            ],
        },
        "struct_tekreplicator_vip": {
            "Type": "item",
            "Category": "Ferramentas",
            "Price": indiv_price,
            "Permissions": "Admins,VIPBronze",
            "Description": f"Replicador S+ VIP (1x) — {indiv_price:,} Âmbar; kit VIP Bronze é melhor custo-benefício. Avulso premium: struct_tekreplicator (52.500).".replace(",", "."),
            "Items": [
                {
                    "Blueprint": "/Game/Mods/StructuresPlusMod/Crafting/replicator/PrimalItemStructure_Replicatorplus.PrimalItemStructure_replicatorplus",
                    "Quantity": 1,
                    "Quality": 0,
                    "ForceBlueprint": False,
                }
            ],
        },
    }
    for key, entry in vip_individuals.items():
        items[key] = entry

    if "stryder_rig" in items:
        items["stryder_rig"]["Price"] = indiv_price
        items["stryder_rig"]["Permissions"] = "Admins,VIPBronze"
        items["stryder_rig"]["Category"] = items["stryder_rig"].get("Category") or "Ferramentas"
        items["stryder_rig"]["Description"] = (
            f"Swappable Stryder Rig (1x) — {indiv_price:,} Âmbar; kit VIP Bronze é melhor custo-benefício"
        ).replace(",", ".")

    data["PointPackages"] = POINT_PACKAGES

    config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {config_path}")


def main() -> None:
    source = CONFIG_PATHS[0]
    apply(source)
    for dest in CONFIG_PATHS[1:]:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        print(f"Synced {dest}")


if __name__ == "__main__":
    main()
