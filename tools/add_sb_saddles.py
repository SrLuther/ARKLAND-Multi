"""Adiciona selas SmallBosses (pronta 30% / BP 75% do dino)."""
from __future__ import annotations

import json
from pathlib import Path

CONFIG = Path("docs/config.json")

SADDLES = [
    (
        "sb_small_dragon",
        "sela_sb_dragon",
        "Sela Small Dragon",
        "/Game/Mods/SmallBosses/SmallDragon/PrimalItemArmor_DragonArmor.PrimalItemArmor_DragonArmor",
    ),
    (
        "sb_dodowyvern",
        "sela_sb_wyvern_tek",
        "Sela Tek Wyvern (SmallBosses)",
        "/Game/Mods/SmallBosses/TekSaddleWyvern/Items/PrimalItemArmor_WyvernTekSaddle.PrimalItemArmor_WyvernTekSaddle",
    ),
    (
        "sb_cyclops",
        "sela_sb_cyclops",
        "Armadura Small Cyclops",
        "/Game/Mods/SmallBosses/SmallCyclops/PrimalItemArmor_CyclopsArmor.PrimalItemArmor_CyclopsArmor",
    ),
    (
        "sb_hippocampus",
        "sela_sb_hippocampus",
        "Sela Small Hippocampus",
        "/Game/Mods/SmallBosses/SmallHippocampus/PrimalItemArmor_HippocampusSaddle.PrimalItemArmor_HippocampusSaddle",
    ),
    (
        "sb_hydra",
        "sela_sb_hydra",
        "Armadura Small Hydra",
        "/Game/Mods/SmallBosses/SmallHydra/PrimalItemArmor_HydraArmor.PrimalItemArmor_HydraArmor",
    ),
    (
        "sb_dodorex",
        "sela_sb_dodorex",
        "Armadura Small DodoRex",
        "/Game/Mods/SmallBosses/SmallDodoRex/PrimalItemArmor_DodoRexArmor.PrimalItemArmor_DodoRexArmor",
    ),
    (
        "sb_manticore",
        "sela_sb_manticore",
        "Armadura Small Manticore",
        "/Game/Mods/SmallBosses/SmallManticore/PrimalItemArmor_ManticoreArmor.PrimalItemArmor_ManticoreArmor",
    ),
    (
        "sb_broodmother",
        "sela_sb_broodmother",
        "Armadura Small Broodmother",
        "/Game/Mods/SmallBosses/SmallBroodmother/PrimalItemArmor_BroodmotherArmor.PrimalItemArmor_BroodmotherArmor",
    ),
    (
        "sb_megapithecus",
        "sela_sb_megapithecus",
        "Armadura Small Megapithecus",
        "/Game/Mods/SmallBosses/SmallMegapithecus/PrimalItemArmor_MegapithecusArmor.PrimalItemArmor_MegapithecusArmor",
    ),
    (
        "sb_moeder",
        "sela_sb_moeder",
        "Armadura Small Moeder",
        "/Game/Mods/SmallBosses/SmallMoeder/PrimalItemArmor_MoederArmor.PrimalItemArmor_MoederArmor",
    ),
    (
        "sb_dodoreaper",
        "sela_sb_dodoreaper",
        "Armadura Small Dodoreaper",
        "/Game/Mods/SmallBosses/SmallDodoreaper/PrimalItemArmor_DodoreaperArmor.PrimalItemArmor_DodoreaperArmor",
    ),
    (
        "sb_drake_fire",
        "sela_sb_drake",
        "Armadura Small Drake",
        "/Game/Mods/SmallBosses/SmallDrake/PrimalItemArmor_DrakeArmor.PrimalItemArmor_DrakeArmor",
    ),
    (
        "sb_desert_titan",
        "sela_sb_desert_titan",
        "Plataforma Small Desert Titan",
        "/Game/Mods/SmallBosses/SmallDesertTitan/PrimalItemArmor_Saddle_DesertTitan_Platform.PrimalItemArmor_Saddle_DesertTitan_Platform",
    ),
]


def make_saddle(name: str, blueprint: str, price: int, *, bp: bool) -> dict:
    label = f"{name} BP (1x)" if bp else f"{name} (1x)"
    return {
        "Description": label,
        "Items": [
            {
                "Blueprint": blueprint,
                "Quantity": 1,
                "Quality": 100,
                "ForceBlueprint": bp,
            }
        ],
        "Price": price,
        "Type": "item",
    }


def main() -> None:
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    items = data.setdefault("Items", {})

    added = []
    for dino_key, item_key, name, blueprint in SADDLES:
        dino_price = items[dino_key]["Price"]
        ready_price = int(dino_price * 0.30)
        bp_price = int(dino_price * 0.75)
        items[item_key] = make_saddle(name, blueprint, ready_price, bp=False)
        items[f"{item_key}_bp"] = make_saddle(name, blueprint, bp_price, bp=True)
        added.append((item_key, dino_price, ready_price, bp_price))

    data["Items"] = dict(sorted(items.items()))
    CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for key, dp, rp, bpp in added:
        print(f"{key}: dino={dp} pronta={rp} bp={bpp}")


if __name__ == "__main__":
    main()
