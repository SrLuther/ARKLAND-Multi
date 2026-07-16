#!/usr/bin/env python3
"""Watchdog inventory: catalog dinos missing generated/*.webp icons."""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "plugin" / "arkshop_web"))

spec = importlib.util.spec_from_file_location("gen", ROOT / "tools" / "generate_ai_species_icons.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

ALIASES = gen.CANONICAL_ICON_ALIASES
GEN = ROOT / "plugin" / "arkshop_web" / "static" / "species" / "icons" / "generated"
ICONS = ROOT / "plugin" / "arkshop_web" / "static" / "species" / "icons"
RAW = GEN / "raw"
REFS = ROOT / "refs" / "species_icons"
CONFIG = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"
DEFAULTS = ROOT / "plugin" / "arkshop_web" / "data" / "market_species_defaults.json"
SUFFIX_RE = re.compile(r"(_200|_femea|_pack\d+)$")


def catalog_species_key(item_id: str, defn: dict | None = None) -> str:
    if defn and defn.get("species_key"):
        return str(defn["species_key"])
    return SUFFIX_RE.sub("", item_id)


def canonical(sk: str) -> str:
    return ALIASES.get(sk.lower(), sk.lower())


def has_webp(sk: str) -> str | None:
    c = canonical(sk)
    for key in (c, sk.lower()):
        if (GEN / f"{key}.webp").is_file():
            return key
    return None


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    items = cfg.get("Items") or {}
    defaults: dict[str, dict] = {}
    if DEFAULTS.is_file():
        for s in json.loads(DEFAULTS.read_text(encoding="utf-8")).get("species", []):
            sk = s.get("species_key")
            if sk:
                defaults[str(sk)] = s

    dino_items: list[tuple[str, dict]] = []
    for item_id, entry in items.items():
        if not isinstance(entry, dict):
            continue
        t = str(entry.get("Type") or entry.get("type") or "").lower()
        has_dinos = bool(entry.get("Dinos"))
        if t != "dino" and not has_dinos:
            continue
        lid = item_id.lower()
        if "criofreezer" in lid or lid.startswith("cryofreezer"):
            continue
        dino_items.append((item_id, entry))

    species: dict[str, dict] = {}
    for item_id, entry in dino_items:
        base = catalog_species_key(item_id)
        defn = defaults.get(base) or defaults.get(canonical(base))
        sk = catalog_species_key(item_id, defn).lower()
        dn = (defn or {}).get("display_name") or entry.get("Description") or entry.get("Name") or item_id
        if sk not in species:
            species[sk] = {
                "species_key": sk,
                "canonical": canonical(sk),
                "display_name": dn,
                "items": [],
                "webp": has_webp(sk),
                "tier": (defn or {}).get("tier") or "B",
            }
        species[sk]["items"].append(item_id)

    missing = sorted([s for s in species.values() if not s["webp"]], key=lambda x: x["species_key"])
    present = sorted([s for s in species.values() if s["webp"]], key=lambda x: x["species_key"])

    print(f"DINO_ITEMS {len(dino_items)}")
    print(f"UNIQUE_SPECIES {len(species)}")
    print(f"WITH_WEBP {len(present)}")
    print(f"MISSING {len(missing)}")
    print("---MISSING---")
    for m in missing:
        c = m["canonical"]
        ref = (REFS / f"{c}.png").is_file() or (REFS / f"{m['species_key']}.png").is_file()
        raw = (RAW / f"{c}.png").is_file() or (RAW / f"{m['species_key']}.png").is_file()
        svg = (ICONS / f"{c}.svg").is_file() or (ICONS / f"{m['species_key']}.svg").is_file()
        print(
            f"{m['species_key']}|{c}|{str(m['display_name'])[:50]}|tier={m['tier']}|"
            f"ref={ref}|raw={raw}|svg={svg}|items={','.join(m['items'][:4])}"
        )

    webps = sorted(p.stem for p in GEN.glob("*.webp") if not p.stem.endswith("_framed_proof"))
    print(f"DISK_WEBP {len(webps)}")

    out = ROOT / "tools" / "_watchdog_missing.json"
    out.write_text(json.dumps(missing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE {out}")


if __name__ == "__main__":
    main()
