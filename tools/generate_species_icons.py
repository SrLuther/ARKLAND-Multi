#!/usr/bin/env python3
"""Gera ícones SVG originais ARKLAND para todas as espécies do registro.

Uso:
  python tools/generate_species_icons.py
  python tools/generate_species_icons.py --dry-run
  python tools/generate_species_icons.py --species rex giga
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugin" / "arkshop_web"
sys.path.insert(0, str(WEB))

from species_icon_gen import collect_registry_species, render_species_icon_svg  # noqa: E402

ICONS_DIR = WEB / "static" / "species" / "icons"
MANIFEST_PATH = WEB / "data" / "species_icons_manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera ícones SVG por espécie (arte original ARKLAND).")
    parser.add_argument("--dry-run", action="store_true", help="Só conta espécies, não grava arquivos.")
    parser.add_argument("--species", nargs="*", help="Subset de species_key (default: todas).")
    args = parser.parse_args()

    species_list = collect_registry_species()
    wanted = {s.lower() for s in args.species} if args.species else None

    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {
        "_comment": "Ícones SVG originais ARKLAND — gerados por tools/generate_species_icons.py",
        "_license": "© ARKLAND — silhuetas procedurais; não são assets do jogo nem de wikis terceiras.",
        "icons": {},
    }

    written = 0
    for entry in species_list:
        sk = str(entry.get("species_key") or "").strip()
        if not sk or (wanted and sk.lower() not in wanted):
            continue
        if str(entry.get("role") or "").lower() == "resource" and not sk.startswith("abyss_"):
            continue
        svg = render_species_icon_svg(
            species_key=sk,
            display_name=str(entry.get("display_name") or sk),
            tier=str(entry.get("tier") or "B"),
            role=str(entry.get("role") or ""),
        )
        rel = f"icons/{sk}.svg"
        if not args.dry_run:
            (ICONS_DIR / f"{sk}.svg").write_text(svg, encoding="utf-8")
        manifest["icons"][sk] = {
            "path": f"/species/{rel}",
            "tier": entry.get("tier"),
            "display_name": entry.get("display_name"),
            "archetype_source": "procedural",
        }
        written += 1

    manifest["count"] = written
    if not args.dry_run:
        MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{'[dry-run] ' if args.dry_run else ''}Icons: {written} -> {ICONS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
