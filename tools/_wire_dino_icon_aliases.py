#!/usr/bin/env python3
"""Wire catalog species_key aliases to existing generated/*.webp and re-sync AI manifest."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugin" / "arkshop_web"
sys.path.insert(0, str(ROOT / "tools"))

from generate_ai_species_icons import (  # noqa: E402
    AI_MANIFEST_PATH,
    CANONICAL_ICON_ALIASES,
    GENERATED_DIR,
    MANIFEST_PATH,
    load_manifest,
    save_manifest,
    sync_ai_manifest,
)

# Extra catalog synonyms → existing generated webp stems (beyond CANONICAL_ICON_ALIASES)
EXTRA_ALIASES: dict[str, str] = {
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
    "carcha": "carcha_femea",
    "lionfish": "lionfishlion",
    "parasaur": "para",
    "tusoteuthis": "tuso",
    "xenomorphgen2": "reaper",
    "snow_owl": "owl",
    "megalosaurus_aberrant": "megalosaurus",
    "gigant": "giga",
    "giganotosaurus": "giga",
    "beaver": "castoroides",
    "doed": "doedicurus",
}


def main() -> None:
    webp = {
        p.stem.lower()
        for p in GENERATED_DIR.glob("*.webp")
        if not p.stem.endswith("_framed_proof")
    }
    manifest = load_manifest()
    icons = manifest.setdefault("icons", {})
    wired = []
    skipped = []

    all_aliases = {**CANONICAL_ICON_ALIASES, **EXTRA_ALIASES}
    for alias, canon in sorted(all_aliases.items()):
        if canon not in webp:
            skipped.append((alias, canon, "canon missing webp"))
            continue
        canon_meta = icons.get(canon) or {
            "species_key": canon,
            "path": f"/species/icons/generated/{canon}.webp",
            "status": "compressed",
        }
        icons[alias] = {
            **{k: v for k, v in canon_meta.items() if k != "raw_path"},
            "species_key": alias,
            "path": f"/species/icons/generated/{canon}.webp",
            "canonical_species_key": canon,
            "status": "aliased",
            "display_name": icons.get(alias, {}).get("display_name") or alias,
        }
        wired.append(alias)

    save_manifest(manifest)
    sync_ai_manifest(manifest)

    # Also ensure EXTRA aliases land in AI manifest even if sync only uses CANONICAL
    ai = json.loads(AI_MANIFEST_PATH.read_text(encoding="utf-8"))
    ai_icons = ai.setdefault("icons", {})
    for alias, canon in EXTRA_ALIASES.items():
        if canon not in webp:
            continue
        src = ai_icons.get(canon) or {
            "path": f"/species/icons/generated/{canon}.webp",
            "display_name": canon,
        }
        ai_icons[alias] = {
            "path": src["path"],
            "display_name": src.get("display_name") or alias,
            "tier": src.get("tier"),
            "webp_kb": src.get("webp_kb"),
            "canonical_species_key": canon,
        }
    ai["count"] = len(ai_icons)
    AI_MANIFEST_PATH.write_text(json.dumps(ai, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"wired {len(wired)} aliases")
    print(f"skipped {len(skipped)}: {skipped}")
    print(f"AI manifest count={ai['count']}")


if __name__ == "__main__":
    main()
