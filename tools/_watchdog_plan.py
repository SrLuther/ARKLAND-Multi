#!/usr/bin/env python3
"""Classify missing icons: copy-from-existing vs need GenerateImage."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAPS = ROOT / "tools" / "_watchdog_gaps.json"
GEN = ROOT / "plugin" / "arkshop_web" / "static" / "species" / "icons" / "generated"
OUT = ROOT / "tools" / "_watchdog_plan.json"

# Manual catalog_id / species_key → existing generated webp stem
KNOWN_MAP: dict[str, str] = {
    "allosaurus": "allo",
    "ankylosaurus": "ankylo",
    "argentavis": "argent",
    "brontosaurus": "bronto",
    "carnotaurus": "carno",
    "dilophosaur": "dilo",
    "dimorphodon": "dimorph",
    "direbear": "direbear",  # may exist
    "dunkleosteus": "dunkle",
    "ichthyosaurus": "ichthy",
    "pteranodon": "ptera",
    "quetzal": "quetz",
    "spinosaur": "spino",
    "stegosaurus": "stego",
    "therizinosaur": "theriz",
    "triceratops": "trike",
    "tusoteuthis": "tuso",
    "woolly_rhino": "rhino",
    "snow_owl": "owl",
    "lionfish": "lionfishlion",
    "carcha": "carcha_femea",
    "wyvern_fire": "wyvern",
    "wyvern_lightning": "wyvern",
    "wyvern_poison": "wyvern",
    "xenomorphgen2": "reaper",
    "megalosaurus_aberrant": "megalosaurus",
    "moschops": "abyss_moschops_abyssal",  # no — need own; leave unmapped
}


def fuzzy_candidates(sk: str, webps: set[str]) -> list[str]:
    sk = sk.lower()
    hits = []
    # strip common prefixes/suffixes
    base = re.sub(r"^(abyss_|sb_|brighamia_)", "", sk)
    base = re.sub(r"(_abyssal|_l200|_femea|_200)$", "", base)
    for w in sorted(webps):
        if w == sk or w == base:
            hits.append(w)
        elif base.startswith(w) or w.startswith(base):
            if abs(len(w) - len(base)) <= 4:
                hits.append(w)
        elif base in w or w in base:
            if min(len(w), len(base)) >= 4:
                hits.append(w)
    return hits


def main() -> None:
    gaps = json.loads(GAPS.read_text(encoding="utf-8"))
    missing = gaps["truly_missing"]
    webps = {p.stem for p in GEN.glob("*.webp")}
    # drop direbear mapping if missing
    if "direbear" not in webps:
        KNOWN_MAP.pop("direbear", None)
    if "moschops" in KNOWN_MAP:
        KNOWN_MAP.pop("moschops", None)

    copy_from: dict[str, str] = {}
    generate: list[str] = []
    for sk in sorted(missing):
        if sk in KNOWN_MAP and KNOWN_MAP[sk] in webps:
            copy_from[sk] = KNOWN_MAP[sk]
            continue
        fuzzy = fuzzy_candidates(sk, webps)
        # only auto-accept exact/near for vanilla renames already in KNOWN or single clear hit
        if len(fuzzy) == 1 and fuzzy[0] != sk and sk in KNOWN_MAP:
            copy_from[sk] = fuzzy[0]
        else:
            generate.append(sk)

    # re-check: for generate list, apply KNOWN again after fuzzy
    still = []
    for sk in generate:
        if sk in copy_from:
            continue
        still.append(sk)

    plan = {
        "copy_from": copy_from,
        "generate": still,
        "generate_count": len(still),
        "copy_count": len(copy_from),
        "fuzzy_notes": {sk: fuzzy_candidates(sk, webps)[:5] for sk in still[:40]},
    }
    OUT.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"COPY {len(copy_from)}")
    for k, v in sorted(copy_from.items()):
        print(f"  {k} <- {v}")
    print(f"GENERATE {len(still)}")
    for sk in still:
        print(f"  {sk}")


if __name__ == "__main__":
    main()
