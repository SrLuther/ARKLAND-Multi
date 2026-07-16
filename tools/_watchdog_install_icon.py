#!/usr/bin/env python3
"""Install a generated bust/framed PNG into the species icon pipeline."""
from __future__ import annotations

import argparse
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

GAPS = ROOT / "tools" / "_watchdog_gaps.json"
RAW = gen.RAW_DIR
GEN = gen.GENERATED_DIR


def install(species_key: str, source: Path, *, framed: bool = False, display_name: str | None = None, tier: str | None = None) -> Path:
    sk = species_key.lower().strip()
    gaps = json.loads(GAPS.read_text(encoding="utf-8")) if GAPS.is_file() else {}
    meta = (gaps.get("truly_missing") or {}).get(sk) or {}
    dn = display_name or meta.get("display") or sk
    # strip level noise from display for nameplate
    for junk in (" Fêmea Nível 1", " Femea Nivel 1", " Nível 1", " Nivel 1", " (SmallBosses)", " (Brighamia Creatures)", " (BigAL's Collection)"):
        if junk in str(dn):
            dn = str(dn).split(junk)[0]
    t = tier or meta.get("tier") or "B"

    RAW.mkdir(parents=True, exist_ok=True)
    GEN.mkdir(parents=True, exist_ok=True)

    bust_or_frame = RAW / f"{sk}_bust.png"
    shutil.copy2(source, bust_or_frame)

    if framed:
        framed_raw = RAW / f"{sk}.png"
        shutil.copy2(source, framed_raw)
    else:
        framed_raw = gen.composite_species_icon(sk, bust_or_frame, display_name=dn, tier=t)

    dest = GEN / f"{sk}.webp"
    stats = gen.compress_image(framed_raw, dest)
    manifest = gen.load_manifest()
    entry = manifest.setdefault("icons", {}).get(sk, {})
    entry.update(
        {
            "species_key": sk,
            "path": f"/species/icons/generated/{sk}.webp",
            "raw_path": f"raw/{framed_raw.name}",
            "display_name": dn,
            "tier": t,
            "status": "compressed",
            **stats,
        }
    )
    manifest["icons"][sk] = entry
    gen.save_manifest(manifest)
    gen.sync_ai_manifest(manifest)
    print(f"INSTALLED {dest} ({stats.get('webp_kb')} KB) tier={t} name={dn}")
    return dest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", required=True)
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--framed", action="store_true", help="Source already includes frame")
    ap.add_argument("--display-name")
    ap.add_argument("--tier")
    args = ap.parse_args()
    if not args.source.is_file():
        raise SystemExit(f"missing source: {args.source}")
    install(args.species, args.source, framed=args.framed, display_name=args.display_name, tier=args.tier)


if __name__ == "__main__":
    main()
