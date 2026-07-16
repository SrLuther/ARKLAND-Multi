#!/usr/bin/env python3
"""Compose + compress a creature bust PNG into generated/{key}.webp and update manifests."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugin" / "arkshop_web"
sys.path.insert(0, str(WEB))
sys.path.insert(0, str(ROOT / "tools"))

from ark_species_registry import get_registry_entry  # noqa: E402
from generate_ai_species_icons import (  # noqa: E402
    GENERATED_DIR,
    RAW_DIR,
    compress_image,
    composite_species_icon,
    load_manifest,
    save_manifest,
    sync_ai_manifest,
)
from market_economy import load_default_species_map  # noqa: E402


def _display_and_tier(sk: str, display_name: str | None, tier: str | None) -> tuple[str, str]:
    defaults = load_default_species_map()
    entry = get_registry_entry(sk) or {}
    defn = defaults.get(sk) or {}
    dn = display_name or defn.get("display_name") or entry.get("display_name") or sk
    t = tier or defn.get("tier") or entry.get("tier") or "B"
    # Clean "Fêmea Nível 1" etc from catalog names
    for junk in (" Fêmea Nível 1", " Nível 1", " Nível 200", " Femea Nivel 1"):
        if dn.endswith(junk):
            dn = dn[: -len(junk)]
    return str(dn), str(t)


def process(species_key: str, bust_path: Path, *, display_name: str | None = None, tier: str | None = None) -> dict:
    sk = species_key.lower().strip()
    dn, t = _display_and_tier(sk, display_name, tier)
    if not bust_path.is_file():
        raise FileNotFoundError(bust_path)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    # Keep a copy of the bust
    bust_dest = RAW_DIR / f"{sk}_bust.png"
    if bust_path.resolve() != bust_dest.resolve():
        bust_dest.write_bytes(bust_path.read_bytes())

    framed = RAW_DIR / f"{sk}.png"
    composite_species_icon(sk, bust_dest, output_path=framed, display_name=dn, tier=t)
    webp = GENERATED_DIR / f"{sk}.webp"
    meta = compress_image(framed, webp)

    manifest = load_manifest()
    manifest.setdefault("icons", {})[sk] = {
        "species_key": sk,
        "display_name": dn,
        "tier": t,
        "path": f"/species/icons/generated/{sk}.webp",
        "raw_path": f"raw/{framed.name}",
        "bust_path": f"raw/{bust_dest.name}",
        **meta,
        "status": "compressed",
    }
    save_manifest(manifest)
    sync_ai_manifest(manifest)

    # Ensure AI manifest has this key (sync may skip non-official)
    ai_path = WEB / "data" / "species_ai_icons_manifest.json"
    ai = json.loads(ai_path.read_text(encoding="utf-8"))
    ai.setdefault("icons", {})[sk] = {
        "path": f"/species/icons/generated/{sk}.webp",
        "display_name": dn,
        "tier": t,
        "webp_kb": meta["webp_kb"],
    }
    ai["count"] = len(ai["icons"])
    ai_path.write_text(json.dumps(ai, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {"species_key": sk, "display_name": dn, "tier": t, "webp": str(webp), **meta}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--species", required=True)
    p.add_argument("--bust", required=True, type=Path)
    p.add_argument("--name")
    p.add_argument("--tier")
    args = p.parse_args()
    info = process(args.species, args.bust, display_name=args.name, tier=args.tier)
    print(json.dumps(info, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
