#!/usr/bin/env python3
"""Gera ícones WebP ARKLAND para recursos do catálogo a partir de refs/resource_icons/.

Uso:
  python tools/generate_resource_icons.py
  python tools/generate_resource_icons.py --dry-run
  python tools/generate_resource_icons.py --keys rec_wood abyss_barnacle
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugin" / "arkshop_web"
sys.path.insert(0, str(WEB))

from resource_icon_gen import (  # noqa: E402
    CONFIG_PATH,
    MANIFEST_PATH,
    OUTPUT_DIR,
    catalog_entry_blueprint,
    catalog_entry_display_name,
    collect_catalog_resource_keys,
    composite_resource_icon,
    compress_to_webp,
    expected_ref_path,
    extract_blueprint_token,
)


def _load_catalog() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("Items") or {}


def generate_one(key: str, *, dry_run: bool = False, force: bool = False) -> dict | None:
    items = _load_catalog()
    entry = items.get(key)
    if not isinstance(entry, dict):
        print(f"  skip {key}: not in catalog")
        return None

    ref_path = expected_ref_path(key)
    if not ref_path.is_file():
        print(f"  skip {key}: missing ref {ref_path.name}")
        return None

    display_name = catalog_entry_display_name(key, entry)
    blueprint = catalog_entry_blueprint(entry)
    dest = OUTPUT_DIR / f"{key}.webp"
    if dest.is_file() and not force and not dry_run:
        meta = compress_to_webp(dest, dest)  # no-op read for size
        return {
            "catalog_key": key,
            "path": f"/catalog/resources/{key}.webp",
            "display_name": display_name,
            "blueprint": blueprint,
            "blueprint_tokens": [extract_blueprint_token(blueprint)] if blueprint else [],
            "reference_path": str(ref_path.relative_to(ROOT)).replace("\\", "/"),
            "status": "existing",
            **meta,
        }

    if dry_run:
        print(f"  [dry-run] {key} <- {ref_path.name} -> {dest.name}")
        return {
            "catalog_key": key,
            "path": f"/catalog/resources/{key}.webp",
            "display_name": display_name,
            "blueprint": blueprint,
            "blueprint_tokens": [extract_blueprint_token(blueprint)] if blueprint else [],
            "reference_path": str(ref_path.relative_to(ROOT)).replace("\\", "/"),
            "status": "dry_run",
        }

    from PIL import Image

    with Image.open(ref_path) as im:
        composed = composite_resource_icon(im, display_name=display_name)
    raw_path = OUTPUT_DIR / f"_{key}_raw.png"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    composed.save(raw_path, format="PNG")
    meta = compress_to_webp(raw_path, dest)
    raw_path.unlink(missing_ok=True)
    print(f"  generated {key}.webp ({meta['webp_kb']} KB)")
    return {
        "catalog_key": key,
        "path": f"/catalog/resources/{key}.webp",
        "display_name": display_name,
        "blueprint": blueprint,
        "blueprint_tokens": [extract_blueprint_token(blueprint)] if blueprint else [],
        "reference_path": str(ref_path.relative_to(ROOT)).replace("\\", "/"),
        "status": "generated",
        **meta,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera ícones WebP de recursos ARKLAND.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Regenera mesmo se .webp existir.")
    parser.add_argument("--keys", nargs="*", help="Subset de chaves do catálogo.")
    args = parser.parse_args()

    keys = args.keys or collect_catalog_resource_keys()
    manifest: dict = {
        "_comment": "Ícones WebP ARKLAND para recursos — gerados por tools/generate_resource_icons.py",
        "_license": "© ARKLAND — composição original; refs internas apenas para anatomia visual.",
        "_frame_style": "dark_metallic_rounded + ARK logo + REC badge + item name",
        "_output_dir": "static/catalog/resources/",
        "generated_at": None,
        "icons": {},
    }

    written = 0
    skipped = 0
    for key in keys:
        result = generate_one(key, dry_run=args.dry_run, force=args.force)
        if result:
            manifest["icons"][key] = result
            if result.get("status") in ("generated", "existing", "dry_run"):
                written += 1
        else:
            skipped += 1

    manifest["count"] = len(manifest["icons"])
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    if not args.dry_run:
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\n{'[dry-run] ' if args.dry_run else ''}Icons: {written} written, {skipped} skipped -> {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
