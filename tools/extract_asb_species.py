#!/usr/bin/env python3
"""Extrai subset de espécies do values.json do ASB para o catálogo Arkland."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"
OUT = ROOT / "plugin" / "arkshop_web" / "data" / "asb_species_subset.json"
DEFAULT_ASB = Path(r"C:\Users\Ciano\Documents\ARKStatsExtractor-dev\ARKBreedingStats\json\values\values.json")


def norm_bp(bp: str) -> str:
    bp = (bp or "").strip()
    if bp.startswith("Blueprint'") and bp.endswith("'"):
        bp = bp[10:-1]
    if not bp.startswith("/"):
        bp = "/Game/" + bp.lstrip("/")
    return bp.lower()


def main() -> int:
    asb_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ASB
    if not asb_path.is_file():
        print(f"ASB values.json não encontrado: {asb_path}", file=sys.stderr)
        return 1
    if not CONFIG.is_file():
        print(f"config.json não encontrado: {CONFIG}", file=sys.stderr)
        return 1

    catalog = json.loads(CONFIG.read_text(encoding="utf-8"))
    items = catalog.get("Items") or {}
    wanted: dict[str, str] = {}
    for item_id, entry in items.items():
        if str(entry.get("Type") or "").lower() != "dino":
            continue
        dino = (entry.get("Dinos") or [{}])[0]
        bp = norm_bp(str(dino.get("Blueprint") or ""))
        if bp:
            wanted[item_id] = bp

    asb_data = json.loads(asb_path.read_text(encoding="utf-8"))
    by_bp: dict[str, dict] = {}
    for sp in asb_data.get("species") or []:
        bp = norm_bp(str(sp.get("blueprintPath") or ""))
        if bp and bp not in by_bp:
            by_bp[bp] = sp

    subset: dict[str, dict] = {}
    missing: list[str] = []
    for item_id, bp in wanted.items():
        sp = by_bp.get(bp)
        if not sp:
            missing.append(f"{item_id} ({bp})")
            continue
        subset[item_id] = {
            "species_key": item_id,
            "name": sp.get("name"),
            "blueprintPath": sp.get("blueprintPath"),
            "fullStatsRaw": sp.get("fullStatsRaw"),
            "TamedBaseHealthMultiplier": sp.get("TamedBaseHealthMultiplier", 1),
            "noGender": sp.get("noGender", False),
        }

    out = {
        "asb_version": asb_data.get("version"),
        "format": asb_data.get("format"),
        "species": subset,
        "missing": missing,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Escrito {OUT} — {len(subset)} espécies, {len(missing)} ausentes")
    if missing:
        for m in missing:
            print(f"  MISSING: {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
