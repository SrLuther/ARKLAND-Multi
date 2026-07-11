"""
Apply full vanilla/DLC tameable dino inventory to CustomShop configs.
Level 1 only, female gender, prices from tier/role ladder.
"""
import json
import shutil
import re
from datetime import datetime

# ── Price ladder ─────────────────────────────────────────────────────────────
PRICE_MAP = {
    ("A", "ataque"):     9500,
    ("A", "utilitario"): 7000,
    ("A", "locomocao"):  7000,
    ("B", "ataque"):     3500,
    ("B", "utilitario"): 2500,
    ("B", "locomocao"):  3500,
    ("C", "ataque"):     1500,
    ("C", "utilitario"):  800,
    ("C", "locomocao"):  1000,
    ("S", "utilitario"): 9500,  # Titanosaur — S tier but no-cryo practical limitation
}

# premium_budget per (tier, role): market_254 - root_value
BUDGET_MAP = {
    ("A", "ataque"):     65500,   # market_254 = 75000
    ("A", "utilitario"): 35000,   # market_254 = 42000
    ("A", "locomocao"):  35000,   # market_254 = 42000
    ("B", "ataque"):     31500,   # market_254 = 35000
    ("B", "utilitario"): 12500,   # market_254 = 15000
    ("B", "locomocao"):  31500,   # market_254 = 35000
    ("C", "ataque"):     13500,   # market_254 = 15000
    ("C", "utilitario"):  7200,   # market_254 = 8000
    ("C", "locomocao"):   7000,   # market_254 = 8000
    ("S", "utilitario"): 65500,   # market_254 = 75000
}

PRESTIGE_MAP = {
    ("A", "ataque"):     62,
    ("A", "utilitario"): 60,
    ("A", "locomocao"):  62,
    ("B", "ataque"):     46,
    ("B", "utilitario"): 42,
    ("B", "locomocao"):  46,
    ("C", "ataque"):     28,
    ("C", "utilitario"): 20,
    ("C", "locomocao"):  24,
    ("S", "utilitario"): 78,
}

BREEDING_DIFF = {
    "A": "alto",
    "B": "moderado",
    "C": "basico",
    "S": "extremo",
}

# ── Load sources ──────────────────────────────────────────────────────────────
BASE = r"c:\Users\Ciano\Documents\arkland-multi"

with open(f"{BASE}/tools/arkids_bp_fill.json", encoding="utf-8") as f:
    arkids = json.load(f)

with open(f"{BASE}/tools/gap_report_vanilla_tameables.json", encoding="utf-8") as f:
    gap = json.load(f)

with open(f"{BASE}/plugin/CustomShop/configs/config.json", encoding="utf-8") as f:
    config = json.load(f)

with open(f"{BASE}/plugin/arkshop_web/data/market_species_defaults.json", encoding="utf-8") as f:
    msd = json.load(f)

# ── Build indices ─────────────────────────────────────────────────────────────
gap_index = {s["species_key"]: s for s in gap["absent_species"]}

existing_bps = set()
for k, v in config.get("Items", {}).items():
    if v.get("Type") == "dino":
        for d in v.get("Dinos", []):
            existing_bps.add(d.get("Blueprint", "").lower())

existing_msd_keys = {s["species_key"] for s in msd.get("species", [])}

print(f"Existing dino entries: {sum(1 for v in config['Items'].values() if v.get('Type')=='dino')}")
print(f"Existing unique BPs in catalog: {len(existing_bps)}")
print(f"Existing market_species_defaults entries: {len(existing_msd_keys)}")
print()

# ── Process each species ──────────────────────────────────────────────────────
added = []
skipped = []

for entry in arkids["filled"]:
    sk = entry["species_key"]
    bp = entry["blueprint_path"]

    if bp.lower() in existing_bps:
        skipped.append((sk, "already_in_catalog"))
        continue

    gap_info = gap_index.get(sk, {})
    tier = gap_info.get("estimated_tier", "C")
    role = gap_info.get("estimated_role", "utilitario")
    display_name = entry.get("display_name_pt", sk)
    cryopodable = gap_info.get("cryopodable", True)
    origin = entry.get("origin", "Vanilla")

    price = PRICE_MAP.get((tier, role), 800)
    budget = BUDGET_MAP.get((tier, role), 7200)
    prestige = PRESTIGE_MAP.get((tier, role), 20)
    breed_diff = BREEDING_DIFF.get(tier, "basico")

    item_key = sk
    item_name = f"{display_name} Femea Nivel 1"

    # Determine mod_source
    if "Scorched Earth" in origin:
        mod_src = "dlc_scorched_earth"
    elif "Aberration" in origin:
        mod_src = "dlc_aberration"
    elif "Extinction" in origin:
        mod_src = "dlc_extinction"
    elif "Genesis 1" in origin:
        mod_src = "dlc_genesis1"
    elif "Genesis 2" in origin:
        mod_src = "dlc_genesis2"
    elif "Lost Island" in origin:
        mod_src = "dlc_lost_island"
    elif "Fjordur" in origin:
        mod_src = "dlc_fjordur"
    else:
        mod_src = "vanilla"

    # Add to config Items
    config["Items"][item_key] = {
        "Description": item_name,
        "Dinos": [{
            "Blueprint": bp,
            "ForceTame": True,
            "Gender": "female",
            "Level": 1,
            "Neutered": False
        }],
        "ForceBlueprint": False,
        "MarketInclude": True,
        "Name": item_name,
        "Price": price,
        "Quality": 0,
        "Type": "dino"
    }
    existing_bps.add(bp.lower())

    # Add to market_species_defaults
    if sk not in existing_msd_keys:
        msd_entry = {
            "species_key": sk,
            "display_name": display_name,
            "blueprint_path": bp,
            "catalog_item_id": sk,
            "reference_catalog_item_id": sk,
            "catalog_item_ids": [sk],
            "root_value": price,
            "premium_budget": budget,
            "tier": tier,
            "dino_role": role,
            "prestige_rank": prestige,
            "commerce_channel": "market_p2p",
            "pricing_mode": "floor_quality",
            "diet_class": "unknown",
            "size_class": "medium",
            "breeding_difficulty": breed_diff,
            "breeding_notes": f"{origin} — vanilla/DLC; adicionado em Jul/2026",
            "mod_source": mod_src,
            "economy_stats": {
                "health": {"enabled": True},
                "melee": {"enabled": True},
                "weight": {"enabled": True},
                "stamina": {"enabled": True},
                "speed": {"enabled": True}
            },
            "blueprint_aliases": []
        }
        msd["species"].append(msd_entry)
        existing_msd_keys.add(sk)

    added.append({
        "key": item_key,
        "display_name": display_name,
        "bp": bp,
        "price": price,
        "tier": tier,
        "role": role,
        "cryopodable": cryopodable,
        "origin": origin
    })

print(f"Added: {len(added)}")
print(f"Skipped (already in catalog): {len(skipped)}")
for s, reason in skipped:
    print(f"  SKIP [{reason}]: {s}")

print()
for a in added:
    cryo_tag = "" if a["cryopodable"] else " [NO-CRYO]"
    print(f"  [{a['tier']}/{a['role']}] {a['key']}: {a['display_name']} | Price={a['price']}{cryo_tag}")

total_dino_after = sum(1 for v in config["Items"].values() if v.get("Type") == "dino")
print(f"\nTotal dino entries after: {total_dino_after}")
print(f"Total market_species_defaults after: {len(msd['species'])}")

# ── Save files ────────────────────────────────────────────────────────────────
with open(f"{BASE}/plugin/CustomShop/configs/config.json", "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

shutil.copy(
    f"{BASE}/plugin/CustomShop/configs/config.json",
    f"{BASE}/plugin/CustomShop/bin/config.json"
)

with open(f"{BASE}/plugin/arkshop_web/data/market_species_defaults.json", "w", encoding="utf-8") as f:
    json.dump(msd, f, indent=2, ensure_ascii=False)

print("\nSaved: configs/config.json, bin/config.json, market_species_defaults.json")

# Store added list for use by CHANGELOG/tabela scripts
with open(f"{BASE}/tools/_apply_result.json", "w", encoding="utf-8") as f:
    json.dump({"added": added, "skipped": [{"key": s, "reason": r} for s, r in skipped]}, f, indent=2, ensure_ascii=False)
