"""Resolução de thumbnails de recursos via resource_icons_manifest.json."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from resource_icon_gen import extract_blueprint_token

WEB = Path(__file__).resolve().parent
MANIFEST_PATH = WEB / "data" / "resource_icons_manifest.json"
OUTPUT_DIR = WEB / "static" / "catalog" / "resources"


@lru_cache(maxsize=1)
def load_resource_icons_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        return {"icons": {}}
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"icons": {}}


@lru_cache(maxsize=1)
def _resource_icon_by_key() -> dict[str, str]:
    urls: dict[str, str] = {}
    for key, meta in (load_resource_icons_manifest().get("icons") or {}).items():
        if not key:
            continue
        path = str((meta or {}).get("path") or "").strip()
        if path:
            urls[str(key).lower()] = path
    if OUTPUT_DIR.is_dir():
        for icon_file in OUTPUT_DIR.glob("*.webp"):
            urls.setdefault(icon_file.stem.lower(), f"/catalog/resources/{icon_file.name}")
    return urls


@lru_cache(maxsize=1)
def _resource_icon_by_blueprint() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for key, meta in (load_resource_icons_manifest().get("icons") or {}).items():
        path = str((meta or {}).get("path") or "").strip()
        if not path:
            continue
        tokens = (meta or {}).get("blueprint_tokens") or []
        if isinstance(tokens, str):
            tokens = [tokens]
        for token in tokens:
            tok = str(token or "").strip()
            if tok:
                mapping[tok.lower()] = path
        bp = str((meta or {}).get("blueprint") or "").strip()
        tok = extract_blueprint_token(bp)
        if tok:
            mapping[tok.lower()] = path
    return mapping


def resolve_resource_icon(
    catalog_key: str | None = None,
    *,
    blueprint: str | None = None,
) -> str | None:
    """URL servível para thumbnail de recurso, ou None se não houver ícone gerado."""
    by_key = _resource_icon_by_key()
    sk = (catalog_key or "").strip().lower()
    if sk and sk in by_key:
        return by_key[sk]

    by_bp = _resource_icon_by_blueprint()
    token = extract_blueprint_token(blueprint or "")
    if token and token.lower() in by_bp:
        return by_bp[token.lower()]
    return None
