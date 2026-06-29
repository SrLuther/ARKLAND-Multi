"""Cria kits licença Gamma/Beta/Alfa em docs/config.json."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

CONFIG = Path("docs/config.json")

BP_ELEMENT = "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Element.PrimalItemResource_Element"
BP_MUTAGEL = "/Game/Genesis2/CoreBlueprints/Environment/Mutagen/PrimalItemConsumable_Mutagel.PrimalItemConsumable_Mutagel"
BP_MUTAGEN = "/Game/Genesis2/CoreBlueprints/Environment/Mutagen/PrimalItemConsumable_Mutagen.PrimalItemConsumable_Mutagen"
BP_ELEMENT_SHARD = "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_ElementShard.PrimalItemResource_ElementShard"
BP_PROPAGATOR = "/Game/Mods/StructuresPlusMod/Misc/Propagator/PrimalItemStructure_Propagator.PrimalItemStructure_Propagator"
BP_REPLICATOR = "/Game/Mods/StructuresPlusMod/Crafting/replicator/PrimalItemStructure_Replicatorplus.PrimalItemStructure_replicatorplus"
BP_DEDICATED = "/Game/Mods/StructuresPlusMod/Misc/DedicatedStorage/PrimalItemStructure_DedicatedStorageSP.PrimalItemStructure_DedicatedStorageSP"
BP_TP_REMOTE = "/Game/Mods/AwesomeTeleporters/Blueprints/Remote/PrimalItem_AwesomeTeleporters_Remote.PrimalItem_AwesomeTeleporters_Remote"
BP_TP_PAD = "/Game/Mods/AwesomeTeleporters/Blueprints/Teleporter/PrimalItem_AwesomeTeleporters_Teleporter.PrimalItem_AwesomeTeleporters_Teleporter"
BP_STRYDER_RIG = "/Game/Mods/StryderRigChanger/PrimalItemConsumable_RigChanger_Base.PrimalItemConsumable_RigChanger_Base"
BP_HOVER_SKIFF = "/Game/Mods/ImprovedSkiff/Skiff/PrimalItem_Spawner_ImprovedHoverSkiff.PrimalItem_Spawner_ImprovedHoverSkiff"

VISOUS_KEYS_BY_TIER = {
    "gamma": [
        "arco_tek_gamma",
        "escopeta_gamma",
        "foice_gamma",
        "machado_gamma",
        "motosserra_gamma",
        "picareta_gamma",
        "visous_blindado_gamma",
        "visous_tek_padrao_gamma",
        "visous_tek_gen2_gamma",
    ],
    "beta": [
        "arco_tek_beta",
        "escopeta_beta",
        "foice_beta",
        "machado_beta",
        "motosserra_beta",
        "picareta_beta",
        "visous_blindado_beta",
        "visous_tek_padrao_beta",
        "visous_tek_gen2_beta",
    ],
    "alfa": [
        "arco_tek_alfa",
        "escopeta_alfa",
        "foice_alfa",
        "machado_alfa",
        "motosserra_alfa",
        "picareta_alfa",
        "visous_blindado_alfa",
        "visous_tek_padrao_alfa",
        "visous_tek_gen2_alfa",
    ],
}

DINO_BPS = {
    "rex_tek": "/Game/PrimalEarth/Dinos/Rex/BionicRex_Character_BP.BionicRex_Character_BP",
    "desmodus": "/Game/Fjordur/Dinos/Desmodus/Desmodus_Character_BP.Desmodus_Character_BP",
    "shadowmane": "/Game/Genesis2/Dinos/LionfishLion/LionfishLion_Character_BP.LionfishLion_Character_BP",
    "giga_tek": "/Game/PrimalEarth/Dinos/Giganotosaurus/BionicGigant_Character_BP.BionicGigant_Character_BP",
    "carcha": "/Game/PrimalEarth/Dinos/Carcharodontosaurus/Carcha_Character_BP.Carcha_Character_BP",
    "yutyrannus": "/Game/PrimalEarth/Dinos/Yutyrannus/Yutyrannus_Character_BP.Yutyrannus_Character_BP",
    "armaedron": "/Game/Mods/GrandHunt/Monsters/Armaedron/Armaedron_Character_BP.Armaedron_Character_BP",
    "therizino": "/Game/PrimalEarth/Dinos/Therizinosaurus/Therizinosaurus_Character_BP.Therizinosaurus_Character_BP",
    "megatherium": "/Game/PrimalEarth/Dinos/Megatherium/Megatherium_Character_BP.Megatherium_Character_BP",
}

GAMMA_DINOS = ["rex_tek", "desmodus", "shadowmane", "giga_tek"]
BETA_EXTRA = ["carcha", "yutyrannus", "armaedron"]
ALFA_EXTRA = ["therizino", "megatherium"]

DINO_LEVEL = 200

LICENSE_PRICES = {
    "gamma": 50_000,
    "beta": 75_000,
    "alfa": 100_000,
}

TIER_META = {
    "gamma": {
        "kit_id": "kit_gamma",
        "label": "Gamma",
        "perm": "Admins,Gamma",
        "license_price": LICENSE_PRICES["gamma"],
        "storage": 10,
        "dinos": GAMMA_DINOS,
    },
    "beta": {
        "kit_id": "kit_beta",
        "label": "Beta",
        "perm": "Admins,Beta",
        "license_price": LICENSE_PRICES["beta"],
        "storage": 20,
        "dinos": GAMMA_DINOS + BETA_EXTRA,
    },
    "alfa": {
        "kit_id": "kit_alfa",
        "label": "Alfa",
        "perm": "Admins,Alfa",
        "license_price": LICENSE_PRICES["alfa"],
        "storage": 30,
        "dinos": GAMMA_DINOS + BETA_EXTRA + ALFA_EXTRA,
    },
}


def item_entry(blueprint: str, qty: int = 1, quality: int = 0, force_bp: bool = False) -> dict:
    return {
        "Blueprint": blueprint,
        "Quantity": qty,
        "Quality": quality,
        "ForceBlueprint": force_bp,
    }


def dino_entry(blueprint: str, level: int = DINO_LEVEL) -> dict:
    return {
        "Blueprint": blueprint,
        "ForceTame": True,
        "Level": level,
        "Neutered": False,
    }


def visous_items_from_catalog(items: dict, tier: str) -> list[dict]:
    out: list[dict] = []
    for key in VISOUS_KEYS_BY_TIER[tier]:
        entry = items[key]
        subs = entry.get("Items") or []
        if subs:
            for sub in subs:
                out.append(
                    item_entry(
                        sub["Blueprint"],
                        sub.get("Quantity", 1),
                        sub.get("Quality", 0),
                        sub.get("ForceBlueprint", False),
                    )
                )
        elif entry.get("Blueprint"):
            out.append(
                item_entry(
                    entry["Blueprint"],
                    entry.get("Quantity", 1),
                    entry.get("Quality", 0),
                    entry.get("ForceBlueprint", False),
                )
            )
    return out


def common_items(meta: dict) -> list[dict]:
    qty_10k = 10000
    items = [
        item_entry(BP_ELEMENT, qty_10k),
        item_entry(BP_MUTAGEL, qty_10k),
        item_entry(BP_MUTAGEN, qty_10k),
        item_entry(BP_ELEMENT_SHARD, qty_10k),
        item_entry(BP_PROPAGATOR, 1),
        item_entry(BP_REPLICATOR, 1),
        item_entry(BP_DEDICATED, meta["storage"]),
        item_entry(BP_TP_REMOTE, 2),
        item_entry(BP_TP_PAD, 2),
        item_entry(BP_STRYDER_RIG, 1),
    ]
    return items


def _fmt_amber(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def build_kit(tier: str, items_catalog: dict) -> dict:
    meta = TIER_META[tier]
    kit_price = meta["license_price"] // 2
    kit_items = visous_items_from_catalog(items_catalog, tier)
    kit_items.extend(common_items(meta))

    if tier == "alfa":
        kit_items.append(item_entry(BP_HOVER_SKIFF, 1))

    dinos: list[dict] = []
    for dino_key in meta["dinos"]:
        dinos.append(dino_entry(DINO_BPS[dino_key], level=DINO_LEVEL))

    label = meta["label"]
    return {
        "DefaultAmount": 1,
        "Description": f"KIT {label.upper()}",
        "Dinos": dinos,
        "Items": kit_items,
        "Permissions": meta["perm"],
        "Price": kit_price,
    }


def main() -> None:
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    items = data.get("Items", {})
    kits = data.setdefault("Kits", {})

    for tier in ("gamma", "beta", "alfa"):
        meta = TIER_META[tier]
        kits[meta["kit_id"]] = build_kit(tier, items)

    CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for tier in ("gamma", "beta", "alfa"):
        k = kits[TIER_META[tier]["kit_id"]]
        print(
            f"{TIER_META[tier]['kit_id']}: "
            f"{len(k['Items'])} itens, {len(k['Dinos'])} dinos, price={k['Price']}"
        )


if __name__ == "__main__":
    main()
