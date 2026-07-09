#!/usr/bin/env python3
"""Auditoria completa: catálogo × refs/resource_icons × wiki Aquatica."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"
REFS_DIR = ROOT / "refs" / "resource_icons"
DODO_PATH = ROOT / "plugin" / "arkshop_web" / "data" / "dododex_resource_slugs.json"
WIKI_PATH = ROOT / "plugin" / "arkshop_web" / "data" / "wiki_resource_refs.json"

# Wiki Aquatica — página inteira (Items), extraído 2026-07-09
WIKI_AQUATICA_ITEMS: dict[str, list[str]] = {
    "Resources": [
        "Aqualyrium", "Barnacle", "Crystallized Wood", "Fish Scale",
        "Hardened Steel Ingot", "Manganese", "Seaweed",
    ],
    "Seeds": [
        "Cucumis Seed", "Oryraise Seed", "Plant Species W Seed",
    ],
    "Consumables": [
        "Air Bladder", "Air Jar", "Broth of Atlan", "Cooked Supreme Fish Meat",
        "Cucumis", "Daco Sushi", "Dried Seaweed", "Earthworms", "Filled Dipping Net",
        "Fish Jerky", "Gilly Feast", "Homarus Egg", "Infected Barnacle",
        "Infected Blubber", "Infected Fin", "Infected Liver", "Infected Meat",
        "Infected Scale", "Infected Stomach", "Infected Tooth", "Kathreptis Egg",
        "Kibble Mash", "Mantis Shrimp Egg", "Mudpuppy Egg", "Ocepechelon Egg",
        "Oceans Bounty", "Oryraise", "Oryraise Ball", "Plant Species W Fruit",
        "Prime Fish Jerky", "Raw Supreme Fish Meat", "Sea Dragon Soup",
        "Takifugu Egg", "Tiktaalik Egg", "Vulcanite Egg", "Water Wyvern Egg",
        "Worm Gum",
    ],
    "Trophies and Tributes": [
        "Alpha Water Talon", "Cymathoa Flag", "Cymathoa Trophy", "Fractalis Flag",
        "Fractalis Trophy", "Monodon Horn", "Onchopristis Blade", "Pygocentrus Flag",
        "Pygocentrus Trophy", "Vulcanithys Flag", "Vulcanithys Trophy", "Water Talon",
    ],
    "Weapons, Armor, and Tools": [
        "Carving Knife", "Boot Weights", "Dipping Net (Ammo)", "Dipping Net (Weapon)",
        "Pearl Boots", "Pearl Chestpiece", "Pearl Gauntlets", "Pearl Helmet",
        "Pearl Leggings", "Seafin Glider Suit", "Tek Trident", "Thalassian Ammo",
        "Thalassian Pistol", "Thalassian Rifle", "Thalassian Rocket Launcher",
        "Thalassian Propelled Rocket", "Tranq Thalassian Ammo",
    ],
    "Structures": [
        "Behemoth Pearl Dinosaur Gate", "Behemoth Pearl Dinosaur Gateway",
        "Giant Pearl Hatchframe", "Giant Pearl Trapdoor", "Hydrosphere", "Infectarium",
        "Large Pearl Wall", "Pearl Catwalk", "Pearl Ceiling", "Pearl Dinosaur Gate",
        "Pearl Dinosaur Gateway", "Pearl Door", "Pearl Doorframe", "Pearl Double Door",
        "Pearl Double Doorframe", "Pearl Fence Foundation", "Pearl Fence Support",
        "Pearl Fireplace", "Pearl Floating Foundation", "Pearl Foundation",
        "Pearl Hatchframe", "Pearl Ladder", "Pearl Pillar", "Pearl Railing",
        "Pearl Ramp", "Pearl Staircase", "Pearl Stairs", "Pearl Trapdoor",
        "Pearl Triangle Ceiling", "Pearl Triangle Floating Foundation",
        "Pearl Triangle Foundation", "Pearl Triangle Roof", "Pearl Vacuum Compartment",
        "Pearl Vacuum Compartment Moonpool", "Pearl Wall", "Pearl Window",
        "Pearl Windowframe", "Rift Generator", "Sloped Pearl Roof",
        "Sloped Pearl Wall Left", "Sloped Pearl Wall Right", "Stinger Ship",
        "Tek Floating Foundation", "Tek Ocean Platform", "Tek Thalassian Hoversail",
        "Tek Triangle Floating Foundation", "Unassembled TEK Thalassian Hover Skiff",
        "Underwater Crop Plot",
    ],
    "Saddles": [
        "Dakosaurus Saddle", "Dakosaurus Platform Saddle", "Homarus Saddle",
        "Malleocephalus Saddle", "Monodon Saddle", "Ocepechelon Saddle",
        "Onchopristis Saddle", "Seahorse Saddle",
    ],
    "Cosmetics": [
        "Tribal Canoe Costume", "Tribal Raft Costume",
    ],
    "Other": [
        "Anniversary Firework Blue", "Anniversary Firework Green",
        "Anniversary Firework Red",
    ],
    "Artifacts": [
        "Artifact of the Fallen", "Artifact of the Mighty", "Artifact of the Seeking",
    ],
    "Pearls": [
        "Blue Abyssal Pearl", "Green Abyssal Pearl", "Red Abyssal Pearl",
    ],
}

# abyss_* → ref filename (quando não é rec_{key}.png)
ABYSS_REF_MAP: dict[str, str] = {
    "abyss_aqualyrium": "rec_aqualyrium.png",
    "abyss_barnacle": "rec_barnacle.png",
    "abyss_crystallized_wood": "rec_crystallizedWood.png",
    "abyss_fish_scale": "rec_fishScale.png",
    "abyss_hardened_steel": "rec_HardenedSteelIngot.png",
    "abyss_manganese": "rec_manganese.png",
    "abyss_seaweed": "rec_seaweed.png",
    "abyss_seed_cucumis": "abyss_seed_cucumis.png",
    "abyss_seed_rice": "abyss_seed_rice.png",
    "abyss_seed_plantspeciesw": "abyss_seed_plantspeciesw.png",
    "abyss_hover_sail": "abyss_hover_sail.png",
    "abyss_hover_skiff": "abyss_hover_skiff.png",
    "daco_sushi": "daco_sushi.png",
}

# wiki name → catalog key (quando existe)
WIKI_TO_CATALOG: dict[str, str] = {
    "Aqualyrium": "abyss_aqualyrium",
    "Barnacle": "abyss_barnacle",
    "Crystallized Wood": "abyss_crystallized_wood",
    "Fish Scale": "abyss_fish_scale",
    "Hardened Steel Ingot": "abyss_hardened_steel",
    "Manganese": "abyss_manganese",
    "Seaweed": "abyss_seaweed",
    "Cucumis Seed": "abyss_seed_cucumis",
    "Oryraise Seed": "abyss_seed_rice",
    "Plant Species W Seed": "abyss_seed_plantspeciesw",
    "Daco Sushi": "daco_sushi",
    "Unassembled TEK Thalassian Hover Skiff": "abyss_hover_skiff",
    "Tek Thalassian Hoversail": "abyss_hover_sail",
}


def expected_ref(catalog_key: str) -> str:
    if catalog_key in ABYSS_REF_MAP:
        return ABYSS_REF_MAP[catalog_key]
    if catalog_key.startswith("rec_"):
        return f"{catalog_key}.png"
    return f"{catalog_key}.png"


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    items = config.get("Items") or {}
    kits = config.get("Kits") or {}
    refs_on_disk = {p.name for p in REFS_DIR.glob("*.png")}

    rec_keys = sorted(k for k in items if k.startswith("rec_"))
    abyss_recursos = sorted(
        k for k, v in items.items()
        if k.startswith("abyss_") and v.get("Category") == "Recursos"
    )
    abyss_items = sorted(
        k for k, v in items.items()
        if k.startswith("abyss_") and v.get("Type") == "item"
    )
    other_recursos = sorted(
        k for k, v in items.items()
        if v.get("Category") == "Recursos" and not k.startswith(("rec_", "abyss_"))
    )

    abyss_type_item = sorted(
        k for k, v in items.items()
        if k.startswith("abyss_") and v.get("Type") == "item"
    )
    catalog_resource_keys = sorted(
        set(rec_keys) | set(abyss_recursos) | set(other_recursos) | set(abyss_type_item)
    )

    print("=== CATÁLOGO ===")
    print(f"rec_*: {len(rec_keys)}")
    print(f"abyss_* Category=Recursos: {len(abyss_recursos)}")
    print(f"outros Category=Recursos: {len(other_recursos)}")
    print(f"abyss_* Type=item: {len(abyss_items)}")
    print(f"TOTAL resource-like no catálogo: {len(catalog_resource_keys)}")

    missing_refs: list[tuple[str, str]] = []
    have_refs: list[tuple[str, str]] = []
    for key in catalog_resource_keys:
        ref = expected_ref(key)
        if ref in refs_on_disk:
            have_refs.append((key, ref))
        else:
            missing_refs.append((key, ref))

    print(f"\n=== REFS (refs/resource_icons/) ===")
    print(f"PNGs no disco: {len(refs_on_disk)}")
    print(f"Catálogo COM ref: {len(have_refs)}")
    print(f"Catálogo SEM ref: {len(missing_refs)}")
    for k, r in missing_refs:
        print(f"  MISSING {k} -> {r}")

    # Orphan refs (no catalog key)
    catalog_refs = {expected_ref(k) for k in catalog_resource_keys}
    orphans = sorted(refs_on_disk - catalog_refs)
    print(f"\nRefs órfãos (sem chave catálogo direta): {len(orphans)}")
    for o in orphans:
        print(f"  {o}")

    # Wiki vs catalog
    all_wiki = []
    for section, names in WIKI_AQUATICA_ITEMS.items():
        for n in names:
            all_wiki.append((section, n))

    wiki_in_catalog = []
    wiki_not_catalog = []
    for section, name in all_wiki:
        key = WIKI_TO_CATALOG.get(name)
        if key and key in items:
            wiki_in_catalog.append((section, name, key))
        else:
            wiki_not_catalog.append((section, name))

    catalog_abyss_wiki_names = set(WIKI_TO_CATALOG.values()) & set(items.keys())
    catalog_not_wiki = [
        k for k in catalog_resource_keys
        if k not in catalog_abyss_wiki_names and not k.startswith("rec_")
    ]

    print(f"\n=== WIKI AQUATICA (página inteira) ===")
    print(f"Total itens listados: {len(all_wiki)}")
    print(f"No catálogo (mapeados): {len(wiki_in_catalog)}")
    print(f"Na wiki, NÃO no catálogo: {len(wiki_not_catalog)}")
    print(f"No catálogo, NÃO na wiki Aquatica: {len([k for k in rec_keys])} rec_* + {len(catalog_not_wiki)} outros")

    # Kit recursos (em Kits.recursos, não Items)
    kit = kits.get("recursos") or {}
    kit_bps = [row.get("Blueprint", "") for row in (kit.get("Items") or [])]
    kit_rec_keys = sorted(rec_keys)  # kit só usa rec_*
    print(f"\n=== KIT RECURSOS ===")
    print(f"Itens no kit (Kits.recursos): {len(kit_bps)}")
    print(f"rec_* no catálogo (cobertura kit): {len(rec_keys)}")

    # dododex gaps
    if DODO_PATH.exists():
        dodo = json.loads(DODO_PATH.read_text(encoding="utf-8"))
        mapping = dodo.get("mapping") or {}
        no_image = [k for k in rec_keys if k in mapping and not mapping[k].get("image_url")]
        print(f"\n=== DODODEX ===")
        print(f"rec_* sem image_url: {len(no_image)}")
        for k in no_image:
            print(f"  {k}: {mapping[k].get('image_source', '?')}")


if __name__ == "__main__":
    main()
