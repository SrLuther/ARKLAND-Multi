#!/usr/bin/env python3
"""Unique catalog dinos missing dedicated generated/*.webp portraits."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugin" / "arkshop_web"
sys.path.insert(0, str(WEB))

from ark_species_registry import lookup_species  # noqa: E402
from catalog_enrich import enrich_catalog_payload  # noqa: E402
from market_economy import _species_key_from_catalog_item_id  # noqa: E402

# Synonyms that should share an existing generated icon (canonical keys in generated/)
ALIAS_TO_EXISTING_WEBP = {
    "ankylosaurus": "ankylo",
    "argentavis": "argent",
    "brontosaurus": "bronto",
    "carnotaurus": "carno",
    "dunkleosteus": "dunkle",
    "quetzal": "quetz",
    "therizinosaur": "theriz",
    "thylacoleo": "thyla",
    "spinosaur": "spino",
    "stegosaurus": "stego",
    "triceratops": "trike",
    "pteranodon": "ptera",
    "allosaurus": "allo",
    "dimorphodon": "dimorph",
    "beelzebufo": "toad",
    "carcha": "carcha_femea",
    "lionfish": "lionfishlion",
    "snow_owl": "snowowl",
    "gigant": "giga",
    "giganotosaurus": "giga",
    "woolly_rhino": "rhino",
    "tusoteuthis": "tuso",
    "ichthyosaurus": "icthy",
    "megaloceros": "stag",
    "mesopithecus": "monkey",
    "oviraptor": "ovi",
    "parasaur": "para",
    "terror_bird": "terror",
    "dilophosaur": "dilo",
    "electrophorus": "eel",
    "liopleurodon": "lio",
    "karkinos": "crab",
    "rock_elemental": "golem",
    "roll_rat": "rollrat",
    "pachyrhinosaurus": "pachyrhino",
    "acrocanto": "acro",
    "xenomorphgen2": "reaper",
    "beaver": "castoroides",
    "doed": "doedicurus",
}


def main() -> None:
    gen = WEB / "static" / "species" / "icons" / "generated"
    webp = {p.stem.lower() for p in gen.glob("*.webp") if not p.stem.endswith("_framed_proof")}

    with (ROOT / "plugin" / "CustomShop" / "configs" / "config.json").open(encoding="utf-8") as f:
        catalog = json.load(f)
    items = {
        k: v
        for k, v in (catalog.get("Items") or {}).items()
        if str(v.get("Type") or "").lower() == "dino"
    }
    enriched, _ = enrich_catalog_payload(items, {})

    has_gen = 0
    by_need: dict[str, list] = defaultdict(list)
    for iid, e in enriched.items():
        url = e.get("thumbnail_url") or ""
        if "/generated/" in url:
            has_gen += 1
            continue
        sk = e.get("species_key")
        if not sk:
            if "/icons/" in url and url.endswith(".svg") and "tier-" not in url:
                sk = Path(url).stem
            else:
                dinos = e.get("Dinos") or []
                bp = ""
                if dinos and isinstance(dinos[0], dict):
                    bp = str(dinos[0].get("Blueprint") or "")
                hit = lookup_species(blueprint=bp) if bp else None
                sk = (hit or {}).get("species_key") or _species_key_from_catalog_item_id(iid)
        sk = str(sk).lower()
        by_need[sk].append(
            {
                "item_id": iid,
                "name": e.get("Name") or e.get("Description"),
                "url": url,
            }
        )

    aliasable = []
    need_create = []
    for sk, rows in sorted(by_need.items()):
        target = ALIAS_TO_EXISTING_WEBP.get(sk)
        if target and target in webp:
            aliasable.append({"species_key": sk, "alias_of": target, "items": len(rows)})
        elif sk in webp:
            aliasable.append({"species_key": sk, "alias_of": sk, "items": len(rows), "note": "webp exists but not resolved"})
        else:
            need_create.append(
                {
                    "species_key": sk,
                    "display_name": rows[0]["name"],
                    "current_url": rows[0]["url"],
                    "item_count": len(rows),
                    "item_ids": [r["item_id"] for r in rows[:6]],
                }
            )

    payload = {
        "sessionId": "24417c",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "catalog_dino_items": len(items),
        "with_generated_image": has_gen,
        "without_generated_image_items": len(items) - has_gen,
        "unique_species_without_generated": len(by_need),
        "aliasable_to_existing_webp": len(aliasable),
        "need_new_image": len(need_create),
        "aliasable": aliasable,
        "missing": need_create,
    }
    out = ROOT / "_inventory_need_create.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # NDJSON debug log
    log = ROOT / "debug-24417c.log"
    lines = [
        {
            "sessionId": "24417c",
            "hypothesisId": "H1",
            "location": "tools/_inventory_need_create.py",
            "message": "dino image inventory",
            "data": {
                "total_dino_items": len(items),
                "with_image": has_gen,
                "without_image": len(items) - has_gen,
                "unique_missing_species": len(by_need),
                "aliasable": len(aliasable),
                "need_create": len(need_create),
                "missing_ids": [m["species_key"] for m in need_create],
                "missing_names": [m["display_name"] for m in need_create],
            },
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
        }
    ]
    with log.open("a", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")

    print("catalog dino items:", len(items))
    print("with generated:", has_gen)
    print("without generated (items):", len(items) - has_gen)
    print("unique species without generated resolve:", len(by_need))
    print("aliasable to existing webp:", len(aliasable))
    print("need NEW image:", len(need_create))
    print("wrote", out)
    print("appended", log)
    for m in need_create:
        print(f"  CREATE {m['species_key']:40} items={m['item_count']} {m['current_url']}")


if __name__ == "__main__":
    main()
