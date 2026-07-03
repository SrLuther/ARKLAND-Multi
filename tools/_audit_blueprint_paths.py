#!/usr/bin/env python3
"""Auditoria temporária de blueprint paths no catálogo."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"

# Estruturas tek: alguns assets usam pasta lowercase "tek", outros "Tek"
_STRUCT_TEK_LOWERCASE_ASSETS = frozenset({
    "PrimalItemStructure_TekRoof",
    "PrimalItemStructure_TekWall_Sloped_Left",
    "PrimalItemStructure_TekWall_Sloped_Right",
    "PrimalItemStructure_Tekfencefoundation",
    "PrimalItemStructure_TekStairs",
})

# Mapa confirmado wrong -> right (além dos já em shop_catalog_import)
_CONFIRMED_FIXES: dict[str, str] = {
    # Armor Tek casing
    "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Tek/PrimalItemArmor_TekGloves.PrimalItemArmor_TekGloves": (
        "/Game/PrimalEarth/CoreBlueprints/Items/Armor/TEK/PrimalItemArmor_TekGloves.PrimalItemArmor_TekGloves"
    ),
    "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Tek/PrimalItemArmor_TekBoots.PrimalItemArmor_TekBoots": (
        "/Game/PrimalEarth/CoreBlueprints/Items/Armor/TEK/PrimalItemArmor_TekBoots.PrimalItemArmor_TekBoots"
    ),
    "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Tek/PrimalItemArmor_TekShirt.PrimalItemArmor_TekShirt": (
        "/Game/PrimalEarth/CoreBlueprints/Items/Armor/TEK/PrimalItemArmor_TekShirt.PrimalItemArmor_TekShirt"
    ),
    "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Tek/PrimalItemArmor_TekPants.PrimalItemArmor_TekPants": (
        "/Game/PrimalEarth/CoreBlueprints/Items/Armor/TEK/PrimalItemArmor_TekPants.PrimalItemArmor_TekPants"
    ),
    # Consumable em Resources
    "/Game/Aberration/CoreBlueprints/Resources/PrimalItemConsumable_NamelessVenom.PrimalItemConsumable_NamelessVenom": (
        "/Game/Aberration/CoreBlueprints/Items/Consumables/"
        "PrimalItemConsumable_NamelessVenom.PrimalItemConsumable_NamelessVenom"
    ),
}

# Structures Tek -> tek (lowercase folder) for specific assets
for asset in _STRUCT_TEK_LOWERCASE_ASSETS:
    wrong = f"/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/{asset}.{asset}"
    right = f"/Game/PrimalEarth/CoreBlueprints/Items/Structures/tek/{asset}.{asset}"
    _CONFIRMED_FIXES[wrong] = right

_BP_IN_TEXT = re.compile(r"(/Game/[^\s\"']+)")


def iter_blueprints(data: dict) -> list[tuple[str, str, str]]:
    """(section.key, field_path, blueprint_or_command_text)"""
    out: list[tuple[str, str, str]] = []

    def walk(obj, label: str, path: str) -> None:
        if isinstance(obj, dict):
            if "Blueprint" in obj and isinstance(obj["Blueprint"], str):
                out.append((label, path + ".Blueprint", obj["Blueprint"]))
            if "Command" in obj and isinstance(obj["Command"], str) and "/Game/" in obj["Command"]:
                out.append((label, path + ".Command", obj["Command"]))
            for k, v in obj.items():
                walk(v, label, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, label, f"{path}[{i}]")

    for section in ("Items", "Kits"):
        for key, val in (data.get(section) or {}).items():
            walk(val, f"{section}.{key}", section)

    return out


def extract_game_paths(text: str) -> list[str]:
    if text.startswith("/Game/"):
        return [text]
    return [m.group(1) for m in _BP_IN_TEXT.finditer(text)]


def suggest_fix(bp: str) -> str | None:
    if bp in _CONFIRMED_FIXES:
        return _CONFIRMED_FIXES[bp]
    # Generic: Resources/PrimalItemConsumable -> Items/Consumables
    if "/Resources/PrimalItemConsumable" in bp:
        return bp.replace("/Resources/", "/Items/Consumables/", 1)
    # Generic: Armor/Tek/ -> Armor/TEK/
    if "/Armor/Tek/" in bp:
        return bp.replace("/Armor/Tek/", "/Armor/TEK/")
    # Structures/Tek/ -> tek/ for known assets
    m = re.search(r"/Structures/Tek/(PrimalItemStructure_Tek\w+)\.", bp)
    if m and m.group(1) in _STRUCT_TEK_LOWERCASE_ASSETS:
        return bp.replace("/Structures/Tek/", "/Structures/tek/")
    return None


def main() -> None:
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    entries = iter_blueprints(data)

    issues: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    for label, field, text in entries:
        for bp in extract_game_paths(text):
            fix = suggest_fix(bp)
            if fix and fix != bp:
                key = (bp, fix)
                if key not in seen:
                    seen.add(key)
                    issues.append((label, field, bp, fix))

    print(f"Total blueprint refs scanned: {len(entries)}")
    print(f"Confirmed issues: {len(issues)}\n")
    for label, field, wrong, right in issues:
        print(f"{label} ({field})")
        print(f"  WRONG: {wrong}")
        print(f"  RIGHT: {right}")
        print()


if __name__ == "__main__":
    main()
