#!/usr/bin/env python3
"""Sincroniza entradas Abyss de ark_species_registry.json → CustomShop config.json (Items)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "plugin/arkshop_web/data/ark_species_registry.json"
CONFIGS = [
    ROOT / "plugin/CustomShop/configs/config.json",
    ROOT / "plugin/CustomShop/bin/config.json",
]


def is_dino(bp: str) -> bool:
    return "/Dinos/" in bp or "_Character_BP" in bp


def build_items(registry: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for sp in registry.get("species", []):
        key = str(sp["species_key"])
        name = str(sp["display_name"])
        price = int(sp.get("root_value", 0))
        bp = str(sp["blueprint_paths"][0])
        role = str(sp.get("role", "utility"))
        if is_dino(bp):
            out[key] = {
                "Type": "dino",
                "Price": price,
                "Category": "Abyss",
                "Name": name,
                "Description": f"{name} Nível 1 (mod Abyss)",
                "Dinos": [
                    {
                        "Blueprint": bp,
                        "Level": 1,
                        "ForceTame": True,
                        "Neutered": False,
                    }
                ],
            }
        else:
            qty = 10 if role in ("resource", "farm") and "Seed" not in bp else 1
            out[key] = {
                "Type": "item",
                "Price": price,
                "Category": "Abyss",
                "Name": name,
                "Description": f"{name} (mod Abyss)",
                "Blueprint": bp,
                "Quantity": qty,
            }
    return out


def main() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    new_items = build_items(registry)
    for cfg in CONFIGS:
        text = cfg.read_text(encoding="utf-8-sig")
        data = json.loads(re.sub(r"//[^\n]*", "", text))
        items = data.setdefault("Items", {})
        added = 0
        for key, entry in new_items.items():
            if key not in items:
                items[key] = entry
                added += 1
        cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{cfg.relative_to(ROOT)}: +{added} itens Abyss (total Items={len(items)})")


if __name__ == "__main__":
    main()
