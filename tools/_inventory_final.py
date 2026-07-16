#!/usr/bin/env python3
"""Final accurate inventory: catalog dinos without generated/*.webp thumbnail."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugin" / "arkshop_web"
sys.path.insert(0, str(WEB))

from catalog_enrich import enrich_catalog_payload  # noqa: E402


def main() -> None:
    with (ROOT / "plugin" / "CustomShop" / "configs" / "config.json").open(
        encoding="utf-8"
    ) as f:
        catalog = json.load(f)
    items = {
        k: v
        for k, v in (catalog.get("Items") or {}).items()
        if str(v.get("Type") or "").lower() == "dino"
    }
    enriched, _ = enrich_catalog_payload(items, {})

    by_sk: dict[str, list[str]] = defaultdict(list)
    has_gen = 0
    for iid, e in enriched.items():
        url = e.get("thumbnail_url") or ""
        if "/generated/" in url:
            has_gen += 1
            continue
        sk = str(e.get("species_key") or iid).lower()
        by_sk[sk].append(iid)

    missing = []
    for sk, ids in sorted(by_sk.items()):
        e = enriched[ids[0]]
        missing.append(
            {
                "species_key": sk,
                "display_name": e.get("Name") or e.get("Description"),
                "current_url": e.get("thumbnail_url"),
                "item_count": len(ids),
                "item_ids": ids[:8],
            }
        )

    payload = {
        "sessionId": "24417c",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "catalog_dino_items": len(enriched),
        "with_generated_image": has_gen,
        "without_generated_image_items": len(enriched) - has_gen,
        "unique_species_without_generated": len(by_sk),
        "missing": missing,
    }
    out = ROOT / "_inventory_final.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    log = ROOT / "debug-24417c.log"
    with log.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "sessionId": "24417c",
                    "hypothesisId": "H2",
                    "location": "tools/_inventory_final.py",
                    "message": "final dino image inventory via catalog_enrich",
                    "data": {
                        "total_dinos": len(enriched),
                        "with_image": has_gen,
                        "without_image": len(enriched) - has_gen,
                        "unique_missing_species": len(by_sk),
                        "missing_ids": [m["species_key"] for m in missing],
                        "missing_names": [m["display_name"] for m in missing],
                    },
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    print("catalog dino items:", len(enriched))
    print("with generated:", has_gen)
    print("without generated:", len(enriched) - has_gen)
    print("unique species needing image:", len(by_sk))
    print("wrote", out)
    for m in missing:
        print(f"  {m['species_key']:40} items={m['item_count']} {m['current_url']}")


if __name__ == "__main__":
    main()
