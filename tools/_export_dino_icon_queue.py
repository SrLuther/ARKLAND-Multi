#!/usr/bin/env python3
"""Export creature-bust prompts for catalog dinos missing generated/*.webp."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugin" / "arkshop_web"
sys.path.insert(0, str(WEB))
sys.path.insert(0, str(ROOT / "tools"))

from generate_ai_species_icons import creature_bust_prompt, resolve_tier  # noqa: E402
from market_economy import load_default_species_map  # noqa: E402


def main() -> None:
    inv = json.loads((ROOT / "_inventory_final.json").read_text(encoding="utf-8"))
    defaults = load_default_species_map()
    queue = []
    for row in inv["missing"]:
        sk = row["species_key"]
        defn = defaults.get(sk) or {}
        dn = defn.get("display_name") or row["display_name"]
        for junk in (" Fêmea Nível 1", " Nível 1", " Nível 200"):
            if str(dn).endswith(junk):
                dn = str(dn)[: -len(junk)]
        tier = defn.get("tier") or resolve_tier(sk)
        prompt = creature_bust_prompt(dn, species_key=sk, role=str(defn.get("role") or ""))
        queue.append(
            {
                "species_key": sk,
                "display_name": dn,
                "tier": tier,
                "prompt": prompt,
                "item_count": row["item_count"],
                "current_url": row["current_url"],
            }
        )
    out = ROOT / "_dino_icon_queue.json"
    out.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"queued {len(queue)} species -> {out}")


if __name__ == "__main__":
    main()
