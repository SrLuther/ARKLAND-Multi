#!/usr/bin/env python3
"""Baixa refs de artefatos do arkids.net e gera WebP ARKLAND via composite.

Uso:
  python tools/fetch_artifact_icons.py
  python tools/fetch_artifact_icons.py --skip-download
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugin" / "arkshop_web"
sys.path.insert(0, str(WEB))

from resource_icon_gen import (  # noqa: E402
    OUTPUT_DIR,
    REFS_DIR,
    catalog_entry_blueprint,
    catalog_entry_display_name,
    composite_resource_icon,
    compress_to_webp,
    extract_blueprint_token,
)

UA = {"User-Agent": "Mozilla/5.0 (compatible; ARKLAND-icon-pipeline/1.0)"}
BASE = "https://arkids.net/image/item/120"

# catalog_key -> arkids slug
ARTIFACT_SLUGS: dict[str, str] = {
    "artifact_brute": "artifact-of-the-brute",
    "artifact_chaos": "artifact-of-chaos",
    "artifact_clever": "artifact-of-the-clever",
    "artifact_crag": "artifact-of-the-crag",
    "artifact_cunning": "artifact-of-the-cunning",
    "artifact_depths": "artifact-of-the-depths",
    "artifact_destroyer": "artifact-of-the-destroyer",
    "artifact_devourer": "artifact-of-the-devourer",
    "artifact_gatekeeper": "artifact-of-the-gatekeeper",
    "artifact_growth": "artifact-of-growth",
    "artifact_hunter": "artifact-of-the-hunter",
    "artifact_immune": "artifact-of-the-immune",
    "artifact_lost": "artifact-of-the-lost",
    "artifact_massive": "artifact-of-the-massive",
    "artifact_pack": "artifact-of-the-pack",
    "artifact_shadows": "artifact-of-the-shadows",
    "artifact_skylord": "artifact-of-the-skylord",
    "artifact_stalker": "artifact-of-the-stalker",
    "artifact_strong": "artifact-of-the-strong",
    "artifact_void": "artifact-of-the-void",
}

CATALOG_CANDIDATES = (
    ROOT / "plugin" / "CustomShop" / "catalog.json",
    ROOT / "plugin" / "CustomShop" / "configs" / "config.json",
)
MANIFEST_PATH = WEB / "data" / "resource_icons_manifest.json"


def _load_items() -> dict:
    for path in CATALOG_CANDIDATES:
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("Items") or {}
        if "artifact_hunter" in items or any(k.startswith("artifact_") for k in items):
            return items
    return {}


def download_ref(slug: str, dest: Path) -> bool:
    url = f"{BASE}/{slug}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            dest.write_bytes(resp.read())
        print(f"  downloaded {dest.name} ({dest.stat().st_size} B)")
        return True
    except Exception as exc:
        print(f"  FAIL {slug}: {exc}")
        return False


def upsert_manifest(entries: list[dict]) -> None:
    if MANIFEST_PATH.is_file():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    else:
        manifest = {
            "_comment": "Ícones WebP ARKLAND — gerados pelo pipeline de recursos",
            "icons": {},
        }
    icons = manifest.setdefault("icons", {})
    for entry in entries:
        key = entry["catalog_key"]
        icons[key] = {k: v for k, v in entry.items() if k != "catalog_key"}
        icons[key]["catalog_key"] = key
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    from PIL import Image

    items = _load_items()
    written: list[dict] = []

    for key, slug in ARTIFACT_SLUGS.items():
        ref = REFS_DIR / f"{key}.png"
        if not args.skip_download:
            if not download_ref(slug, ref):
                continue
        if not ref.is_file():
            print(f"  skip {key}: missing ref")
            continue

        entry = items.get(key) if isinstance(items.get(key), dict) else {}
        display = catalog_entry_display_name(key, entry or {"Description": key.replace("_", " ")})
        # Nomes curtos para nameplate
        display = display.replace("Artifact of the ", "").replace("Artifact of ", "")
        display = display.replace("Artifact Of The ", "").replace("Artifact Of ", "")
        blueprint = catalog_entry_blueprint(entry) if entry else ""

        with Image.open(ref) as im:
            composed = composite_resource_icon(im, display_name=display)
        raw = OUTPUT_DIR / f"_{key}_raw.png"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        composed.save(raw, format="PNG")
        dest = OUTPUT_DIR / f"{key}.webp"
        meta = compress_to_webp(raw, dest)
        raw.unlink(missing_ok=True)
        print(f"  generated {dest.name} ({meta['webp_kb']} KB)")
        written.append(
            {
                "catalog_key": key,
                "path": f"/catalog/resources/{key}.webp",
                "display_name": display,
                "blueprint": blueprint,
                "blueprint_tokens": [extract_blueprint_token(blueprint)] if blueprint else [],
                "reference_path": f"refs/resource_icons/{key}.png",
                "status": "generated",
                **meta,
            }
        )

    if written:
        upsert_manifest(written)
        print(f"manifest updated: {len(written)} artifacts")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
