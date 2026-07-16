#!/usr/bin/env python3
"""Apply alias webp copies + register in generated/manifest.json."""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "plugin" / "arkshop_web"))

spec = importlib.util.spec_from_file_location("gen", ROOT / "tools" / "generate_ai_species_icons.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

PLAN = ROOT / "tools" / "_watchdog_plan.json"
GAPS = ROOT / "tools" / "_watchdog_gaps.json"
GEN = ROOT / "plugin" / "arkshop_web" / "static" / "species" / "icons" / "generated"

# Extra safe copies discovered after plan
EXTRA_COPY = {
    "parasaur": "para",
    "thylacoleo": "thyla",
}


def main() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    gaps = json.loads(GAPS.read_text(encoding="utf-8"))
    copies = dict(plan.get("copy_from") or {})
    copies.update(EXTRA_COPY)

    manifest = gen.load_manifest()
    icons = manifest.setdefault("icons", {})
    done = []
    skipped = []

    for dest_sk, src_sk in sorted(copies.items()):
        src = GEN / f"{src_sk}.webp"
        dest = GEN / f"{dest_sk}.webp"
        if not src.is_file():
            skipped.append((dest_sk, f"missing_src:{src_sk}"))
            continue
        if dest.is_file():
            skipped.append((dest_sk, "already_exists"))
            continue
        shutil.copy2(src, dest)
        src_meta = icons.get(src_sk) or {}
        gap = (gaps.get("truly_missing") or {}).get(dest_sk) or {}
        icons[dest_sk] = {
            "species_key": dest_sk,
            "path": f"/species/icons/generated/{dest_sk}.webp",
            "display_name": gap.get("display") or dest_sk,
            "tier": gap.get("tier") or src_meta.get("tier") or "B",
            "status": "compressed",
            "canonical_species_key": src_sk,
            "copied_from": src_sk,
        }
        done.append(dest_sk)
        print(f"COPIED {dest_sk} <- {src_sk}")

    gen.save_manifest(manifest)
    gen.sync_ai_manifest(manifest)
    print(f"DONE {len(done)} SKIPPED {len(skipped)}")


if __name__ == "__main__":
    main()
