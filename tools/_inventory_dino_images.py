#!/usr/bin/env python3
"""Inventory catalog dinos vs dedicated AI species images."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugin" / "arkshop_web"
sys.path.insert(0, str(WEB))
sys.path.insert(0, str(ROOT / "tools"))

from ark_species_registry import (  # noqa: E402
    get_registry_entry,
    load_registry,
    lookup_species,
    resolve_species_image,
)
from market_economy import (  # noqa: E402
    build_catalog_economy_map,
    iter_catalog_dinos,
    load_default_species_map,
)
from market_economy import _species_key_from_catalog_item_id  # noqa: E402
from generate_ai_species_icons import (  # noqa: E402
    CANONICAL_ICON_ALIASES,
    GENERATED_DIR,
    build_official_species_list,
)


def main() -> None:
    gen_dir = GENERATED_DIR
    webp = {
        p.stem.lower()
        for p in gen_dir.glob("*.webp")
        if not p.stem.endswith("_framed_proof")
    }
    svg = {
        p.stem.lower()
        for p in (WEB / "static" / "species" / "icons").glob("*.svg")
    }

    with (ROOT / "plugin" / "CustomShop" / "configs" / "config.json").open(
        encoding="utf-8"
    ) as f:
        catalog = json.load(f)

    catalog_map = build_catalog_economy_map()
    defaults_map = load_default_species_map()
    dinos = iter_catalog_dinos(catalog)

    species_from_catalog: dict[str, dict] = {}

    def resolve_sk(item_id: str, entry: dict) -> str:
        defn = catalog_map.get(item_id)
        if defn and defn.get("species_key"):
            return str(defn["species_key"]).lower()
        sk = _species_key_from_catalog_item_id(item_id)
        if sk:
            return str(sk).lower()
        opts = entry.get("Options") or entry.get("DinoOptions") or {}
        bp = ""
        if isinstance(opts, dict):
            bp = str(opts.get("Blueprint") or opts.get("BlueprintPath") or "")
        hit = None
        if bp:
            hit = lookup_species(blueprint=bp)
        if not hit:
            name = str(entry.get("Description") or entry.get("Name") or "")
            if name:
                hit = lookup_species(name_hint=name)
        if hit and hit.get("species_key"):
            return str(hit["species_key"]).lower()
        return item_id.lower()

    for item_id, entry in dinos:
        sk = resolve_sk(item_id, entry)
        canon = CANONICAL_ICON_ALIASES.get(sk, sk)
        info = species_from_catalog.setdefault(
            sk,
            {
                "species_key": sk,
                "canonical_icon": canon,
                "item_ids": [],
                "display_name": str(entry.get("Description") or entry.get("Name") or sk),
                "price_max": 0,
            },
        )
        info["item_ids"].append(item_id)
        info["price_max"] = max(info["price_max"], int(entry.get("Price") or 0))
        dn = defaults_map.get(sk) or defaults_map.get(canon)
        if dn and dn.get("display_name"):
            info["display_name"] = dn["display_name"]

    reg = load_registry()
    reg_keys = [
        str(e.get("species_key") or "").lower()
        for e in (reg.get("species") or [])
        if e.get("species_key")
    ]

    has_dedicated = []
    has_svg_only = []
    has_tier_only = []
    missing_webp = []

    for sk, info in sorted(species_from_catalog.items()):
        canon = info["canonical_icon"]
        has_w = sk in webp or canon in webp
        has_s = sk in svg or canon in svg
        entry = get_registry_entry(sk) or get_registry_entry(canon) or {
            "species_key": sk,
            "tier": "B",
        }
        url = resolve_species_image(entry)
        info["resolved_url"] = url
        info["has_webp"] = has_w
        info["has_svg"] = has_s
        if has_w or ("/generated/" in url and url.endswith((".webp", ".png"))):
            info["has_webp"] = True
            has_dedicated.append(info)
        elif has_s or (
            "/icons/" in url and url.endswith(".svg") and "tier-" not in url
        ):
            has_svg_only.append(info)
            missing_webp.append(info)
        else:
            has_tier_only.append(info)
            missing_webp.append(info)

    official = build_official_species_list()
    off_missing = [
        s
        for s in official
        if s["species_key"] not in webp
        and CANONICAL_ICON_ALIASES.get(s["species_key"], s["species_key"]) not in webp
    ]

    # Registry commerce dinos missing webp (mods/abyss included if in catalog)
    print("=== COUNTS ===")
    print("catalog Type=dino items:", len(dinos))
    print("unique species_keys from catalog:", len(species_from_catalog))
    print("registry species:", len(reg_keys))
    print("generated webp:", len(webp))
    print("svg icons:", len(svg))
    print("with dedicated webp:", len(has_dedicated))
    print("svg only (need AI image):", len(has_svg_only))
    print("tier fallback only:", len(has_tier_only))
    print("total missing dedicated image:", len(missing_webp))
    print("official vanilla:", len(official), "missing webp:", len(off_missing))

    print("\n--- Missing catalog species ---")
    for info in missing_webp:
        print(
            f"  {info['species_key']:40} canon={info['canonical_icon']:30} "
            f"svg={info['has_svg']} url={info['resolved_url']}"
        )

    out = {
        "catalog_dino_items": len(dinos),
        "unique_species": len(species_from_catalog),
        "with_webp": len(has_dedicated),
        "svg_only": len(has_svg_only),
        "tier_only": len(has_tier_only),
        "missing_count": len(missing_webp),
        "missing": [
            {
                "species_key": i["species_key"],
                "canonical_icon": i["canonical_icon"],
                "display_name": i["display_name"],
                "has_svg": i["has_svg"],
                "resolved_url": i["resolved_url"],
                "item_ids": i["item_ids"][:8],
            }
            for i in missing_webp
        ],
        "official_missing": [
            {
                "species_key": s["species_key"],
                "display_name": s["display_name"],
                "tier": s["tier"],
            }
            for s in off_missing
        ],
        "with_webp_keys": sorted(i["species_key"] for i in has_dedicated),
    }
    dest = ROOT / "_inventory_tmp.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {dest}")


if __name__ == "__main__":
    main()
