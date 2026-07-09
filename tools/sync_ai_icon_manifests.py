#!/usr/bin/env python3
"""Rebuild generated/manifest.json and update species_icons_manifest.json for AI icons."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugin" / "arkshop_web"
sys.path.insert(0, str(ROOT / "tools"))

import importlib.util

spec = importlib.util.spec_from_file_location("gen", ROOT / "tools" / "generate_ai_species_icons.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

species = gen.build_official_species_list()
gen_dir = WEB / "static" / "species" / "icons" / "generated"
raw_dir = gen_dir / "raw"

manifest = gen.load_manifest()
manifest["icons"] = {}
manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
manifest["batch_complete"] = True
manifest["official_total"] = len(species)

for s in species:
    sk = s["species_key"]
    webp = gen_dir / f"{sk}.webp"
    raw = raw_dir / f"{sk}.png"
    if not webp.is_file():
        continue
    meta = {
        "species_key": sk,
        "display_name": s["display_name"],
        "tier": s["tier"],
        "path": f"/species/icons/generated/{sk}.webp",
        "status": "compressed",
        "size": "256x256",
        "webp_kb": round(webp.stat().st_size / 1024, 1),
    }
    if raw.is_file():
        meta["raw_path"] = f"raw/{sk}.png"
        meta["raw_kb"] = round(raw.stat().st_size / 1024, 1)
    manifest["icons"][sk] = meta

manifest["count"] = len(manifest["icons"])
gen.save_manifest(manifest)
gen.sync_ai_manifest(manifest)

icons_manifest_path = WEB / "data" / "species_icons_manifest.json"
icons_data = json.loads(icons_manifest_path.read_text(encoding="utf-8"))
ai_count = 0
for sk, meta in manifest["icons"].items():
    entry = icons_data["icons"].get(sk, {})
    entry.update({
        "path": meta["path"],
        "tier": meta.get("tier", entry.get("tier")),
        "display_name": meta.get("display_name", entry.get("display_name")),
        "archetype_source": "ai_raster",
        "webp_kb": meta.get("webp_kb"),
    })
    icons_data["icons"][sk] = entry
    ai_count += 1

by_key = {s["species_key"]: s for s in species}
for alias, canon in gen.CANONICAL_ICON_ALIASES.items():
    canon_meta = manifest["icons"].get(canon)
    if not canon_meta or not canon_meta.get("path"):
        continue
    alias_species = by_key.get(alias, {})
    entry = icons_data["icons"].get(alias, {})
    entry.update({
        "path": canon_meta["path"],
        "tier": alias_species.get("tier", entry.get("tier")),
        "display_name": alias_species.get("display_name", entry.get("display_name")),
        "archetype_source": "ai_raster_alias",
        "canonical_species_key": canon,
        "webp_kb": canon_meta.get("webp_kb"),
    })
    icons_data["icons"][alias] = entry

icons_data["_ai_icons"] = f"{ai_count} vanilla species use AI raster icons in icons/generated/"
icons_data["_ai_manifest"] = "static/species/icons/generated/manifest.json"
icons_manifest_path.write_text(json.dumps(icons_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(f"Manifest: {manifest['count']}/{len(species)}")
print(f"species_icons_manifest updated: {ai_count} AI entries")
