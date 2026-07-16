#!/usr/bin/env python3
"""Watchdog: list unique species keys needing generated/*.webp (via enrich_shop_item)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin" / "arkshop_web"))
sys.path.insert(0, str(ROOT / "tools"))

from catalog_enrich import enrich_shop_item  # noqa: E402
from market_economy import canonicalize_species_key  # noqa: E402

spec = importlib.util.spec_from_file_location("gen", ROOT / "tools" / "generate_ai_species_icons.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

ALIASES = gen.CANONICAL_ICON_ALIASES
GEN = ROOT / "plugin" / "arkshop_web" / "static" / "species" / "icons" / "generated"
CONFIG = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"
OUT = ROOT / "tools" / "_watchdog_gaps.json"


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    webps = {p.stem for p in GEN.glob("*.webp")}
    need: dict[str, dict] = {}

    for kid, entry in (cfg.get("Items") or {}).items():
        if not isinstance(entry, dict):
            continue
        t = str(entry.get("Type") or "").lower()
        if t != "dino" and not entry.get("Dinos"):
            continue
        if "criofreezer" in kid.lower():
            continue
        meta = enrich_shop_item(kid, entry)
        thumb = meta.get("thumbnail_url") or ""
        if "/generated/" in thumb and str(thumb).endswith(".webp"):
            continue
        sk = str(meta.get("species_key") or kid)
        canon = canonicalize_species_key(sk)
        has = None
        for cand in (
            sk,
            canon,
            ALIASES.get(sk, sk),
            ALIASES.get(canon, canon),
            sk.replace("_l200", "").replace("_femea", ""),
            canon.replace("_l200", "").replace("_femea", ""),
        ):
            c = ALIASES.get(cand, cand)
            if c in webps:
                has = c
                break
            if cand in webps:
                has = cand
                break
        if sk not in need:
            need[sk] = {
                "items": [],
                "thumb": thumb,
                "existing_alias_webp": has,
                "display": entry.get("Description") or entry.get("Name") or sk,
                "tier": meta.get("tier") or "B",
                "canonical": canon,
            }
        need[sk]["items"].append(kid)

    alias_ok = {k: v for k, v in need.items() if v["existing_alias_webp"]}
    truly_missing = {k: v for k, v in need.items() if not v["existing_alias_webp"]}

    print(f"NEED_KEYS {len(need)}")
    print(f"ALIAS_TO_EXISTING {len(alias_ok)}")
    print(f"TRULY_MISSING {len(truly_missing)}")
    print("---TRULY_MISSING---")
    for k in sorted(truly_missing):
        v = truly_missing[k]
        print(f"{k}|{v['display']}|tier={v['tier']}|n={len(v['items'])}")

    OUT.write_text(
        json.dumps(
            {
                "need_keys": len(need),
                "alias_ok": alias_ok,
                "truly_missing": truly_missing,
                "disk_webp": len(webps),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"WROTE {OUT}")


if __name__ == "__main__":
    main()
