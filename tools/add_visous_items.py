"""Adiciona itens VISOUSMod faltantes em docs/config.json."""
from __future__ import annotations

import json
from pathlib import Path

CONFIG = Path("docs/config.json")

TIER_PRICES = {"alfa": 3500, "beta": 2000, "gama": 1200}
ARMOR_TIER_PRICES = {"alfa": 10000, "beta": 7500, "gama": 5000}

WEAPONS = [
    (
        "motosserra",
        "Motoserra",
        {
            "alfa": "/Game/Mods/VISOUSMod/Motoserra/Alfa/PrimalItem_Motosserra_Alfa.PrimalItem_Motosserra_Alfa",
            "beta": "/Game/Mods/VISOUSMod/Motoserra/Beta/PrimalItem_Motosserra_Beta.PrimalItem_Motosserra_Beta",
            "gama": "/Game/Mods/VISOUSMod/Motoserra/Gama/PrimalItem_Motosserra_Gama.PrimalItem_Motosserra_Gama",
        },
    ),
]

ARMOR_SETS = [
    (
        "visous_blindado",
        "Armadura Blindada VISOUS",
        {
            "alfa": "/Game/Mods/VISOUSMod/Blindado/Alfa/PrimalItemArmor_Metal{piece}_Alfa.PrimalItemArmor_Metal{piece}_Alfa",
            "beta": "/Game/Mods/VISOUSMod/Blindado/Beta/PrimalItemArmor_Metal{piece}_Beta.PrimalItemArmor_Metal{piece}_Beta",
            "gama": "/Game/Mods/VISOUSMod/Blindado/Gama/PrimalItemArmor_Metal{piece}_Gama.PrimalItemArmor_Metal{piece}_Gama",
        },
        ["Helmet", "Shirt", "Gloves", "Pants", "Boots"],
    ),
    (
        "visous_tek_padrao",
        "Armadura Tek VISOUS",
        {
            "alfa": "/Game/Mods/VISOUSMod/Roupa_Tek/Padrao/Alfa/PrimalItemArmor_Tek{piece}_Alfa.PrimalItemArmor_Tek{piece}_Alfa",
            "beta": "/Game/Mods/VISOUSMod/Roupa_Tek/Padrao/Beta/PrimalItemArmor_Tek{piece}_Beta.PrimalItemArmor_Tek{piece}_Beta",
            "gama": "/Game/Mods/VISOUSMod/Roupa_Tek/Padrao/Gama/PrimalItemArmor_Tek{piece}_Gama.PrimalItemArmor_Tek{piece}_Gama",
        },
        ["Helmet", "Shirt", "Gloves", "Pants", "Boots"],
    ),
    (
        "visous_tek_gen2",
        "Armadura Tek Gen2 VISOUS",
        {
            "alfa": "/Game/Mods/VISOUSMod/Roupa_Tek/Gen2/Alfa/PrimalItemArmor_Tek{piece}_Gen2_Alfa.PrimalItemArmor_Tek{piece}_Gen2_Alfa",
            "beta": "/Game/Mods/VISOUSMod/Roupa_Tek/Gen2/Beta/PrimalItemArmor_Tek{piece}_Gen2_Beta.PrimalItemArmor_Tek{piece}_Gen2_Beta",
            "gama": "/Game/Mods/VISOUSMod/Roupa_Tek/Gen2/Gama/PrimalItemArmor_Tek{piece}_Gen2_Gama.PrimalItemArmor_Tek{piece}_Gen2_Gama",
        },
        ["Helmet", "Shirt", "Gloves", "Pants", "Boots"],
    ),
]

EXISTING_WEAPONS = {
    "arco_tek_alfa",
    "arco_tek_beta",
    "arco_tek_gamma",
    "escopeta_alfa",
    "escopeta_beta",
    "escopeta_gamma",
    "foice_alfa",
    "foice_beta",
    "foice_gamma",
    "machado_alfa",
    "machado_beta",
    "machado_gamma",
    "picareta_alfa",
    "picareta_beta",
    "picareta_gamma",
}


def weapon_item(key: str, desc: str, blueprint: str, price: int) -> dict:
    return {
        "Description": desc,
        "Items": [{"Blueprint": blueprint, "Quantity": 1, "Quality": 0, "ForceBlueprint": False}],
        "Price": price,
        "Type": "item",
    }


def armor_item(desc: str, blueprints: list[str], price: int) -> dict:
    return {
        "Description": desc,
        "Items": [
            {"Blueprint": bp, "Quantity": 1, "Quality": 0, "ForceBlueprint": False}
            for bp in blueprints
        ],
        "Price": price,
        "Type": "item",
    }


def main() -> None:
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    items = data.setdefault("Items", {})
    added: list[str] = []
    skipped: list[str] = []

    for prefix, label, bps in WEAPONS:
        for tier, bp in bps.items():
            suffix = "gamma" if tier == "gama" else tier
            key = f"{prefix}_{suffix}"
            tier_label = {"alfa": "Alfa", "beta": "Beta", "gama": "Gamma"}[tier]
            if key in items:
                skipped.append(key)
                continue
            items[key] = weapon_item(key, f"{label} {tier_label} (1x)", bp, TIER_PRICES[tier])
            added.append(key)

    for prefix, label, tier_templates, pieces in ARMOR_SETS:
        for tier, template in tier_templates.items():
            suffix = "gamma" if tier == "gama" else tier
            key = f"{prefix}_{suffix}"
            if key in items:
                skipped.append(key)
                continue
            tier_label = {"alfa": "Alfa", "beta": "Beta", "gama": "Gamma"}[tier]
            bps = [template.format(piece=p) for p in pieces]
            items[key] = armor_item(
                f"{label} {tier_label} (5 peças)",
                bps,
                ARMOR_TIER_PRICES[tier],
            )
            added.append(key)

    data["Items"] = dict(sorted(items.items()))
    CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Ja existiam (armas): {len(EXISTING_WEAPONS)} tipos")
    print(f"Adicionados: {len(added)}")
    for k in added:
        print(f"  + {k}")
    if skipped:
        print(f"Pulados (ja no catalogo): {skipped}")


if __name__ == "__main__":
    main()
