"""Galeria visual de cores — Encomenda de Dino (admin + jogador)."""
from __future__ import annotations

import json
import logging
import re
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("arkshop_web.dino_order_showcase")

_DATA_VERSION = 1
MAX_SHOWCASES_PER_SPECIES = 10
_MAX_DESCRIPTION = 4000
_MAX_LABEL = 200
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_ALLOWED_IMAGE_MIME = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})
_SAFE_FILENAME = re.compile(r"^[a-zA-Z0-9._-]+$")

_showcases_file: Path | None = None
_uploads_dir: Path | None = None
_image_url_prefix: str = "/api/dino-order/showcase-images"


def configure_dino_order_showcase(
    *,
    showcases_file: Path,
    uploads_dir: Path,
    image_url_prefix: str = "/api/dino-order/showcase-images",
) -> None:
    global _showcases_file, _uploads_dir, _image_url_prefix
    _showcases_file = showcases_file
    _uploads_dir = uploads_dir
    _image_url_prefix = image_url_prefix.rstrip("/")
    uploads_dir.mkdir(parents=True, exist_ok=True)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _default_store() -> dict[str, Any]:
    return {"version": _DATA_VERSION, "entries": []}


def _store_path() -> Path:
    if _showcases_file is None:
        raise ValueError("showcase_not_configured")
    return _showcases_file


def _uploads_path() -> Path:
    if _uploads_dir is None:
        raise ValueError("showcase_not_configured")
    return _uploads_dir


def load_store() -> dict[str, Any]:
    path = _store_path()
    if not path.is_file():
        return _default_store()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("showcase load failed: %s", exc)
        return _default_store()
    if not isinstance(data, dict):
        return _default_store()
    entries = data.get("entries")
    if not isinstance(entries, list):
        data["entries"] = []
    data["version"] = _DATA_VERSION
    return data


def save_store(data: dict[str, Any]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": _DATA_VERSION,
        "entries": list(data.get("entries") or []),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _new_id() -> str:
    return f"sc_{secrets.token_hex(8)}"


def _normalize_colors(raw: Any) -> list[int]:
    if not isinstance(raw, list) or len(raw) != 6:
        raise ValueError("colors_must_be_six_ints")
    out: list[int] = []
    for item in raw:
        try:
            val = int(item)
        except (TypeError, ValueError):
            raise ValueError("colors_must_be_six_ints") from None
        if val < 0 or val > 255:
            raise ValueError("color_index_out_of_range")
        out.append(val)
    return out


def _entry_to_public(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entry.get("id"),
        "species_key": entry.get("species_key"),
        "color_name": entry.get("color_name"),
        "colors": entry.get("colors"),
        "regions_label": entry.get("regions_label") or "",
        "description": entry.get("description") or "",
        "image_url": entry.get("image_url") or "",
        "sort_order": int(entry.get("sort_order") or 0),
    }


def _sort_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        entries,
        key=lambda e: (int(e.get("sort_order") or 0), str(e.get("color_name") or "").lower()),
    )


def list_showcases(
    *,
    species_key: str | None = None,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    entries = load_store().get("entries") or []
    out: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if active_only and not entry.get("active", True):
            continue
        sk = str(entry.get("species_key") or "").strip()
        if species_key and sk != species_key.strip():
            continue
        if not sk:
            continue
        out.append(_entry_to_public(entry))
    return _sort_entries(out)[:MAX_SHOWCASES_PER_SPECIES]


def list_showcases_admin(*, species_key: str | None = None) -> list[dict[str, Any]]:
    entries = load_store().get("entries") or []
    out: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        sk = str(entry.get("species_key") or "").strip()
        if species_key and sk != species_key.strip():
            continue
        if not sk:
            continue
        item = dict(entry)
        item.setdefault("active", True)
        item.setdefault("sort_order", 0)
        out.append(item)
    return _sort_entries(out)


def get_showcase(entry_id: str) -> dict[str, Any] | None:
    for entry in load_store().get("entries") or []:
        if isinstance(entry, dict) and str(entry.get("id")) == entry_id:
            return dict(entry)
    return None


def count_showcases_for_species(species_key: str, *, exclude_id: str | None = None) -> int:
    sk = str(species_key or "").strip()
    if not sk:
        return 0
    count = 0
    for entry in load_store().get("entries") or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("species_key") or "").strip() != sk:
            continue
        if exclude_id and str(entry.get("id")) == exclude_id:
            continue
        count += 1
    return count


def showcase_counts_by_species(*, active_only: bool = True) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in load_store().get("entries") or []:
        if not isinstance(entry, dict):
            continue
        if active_only and not entry.get("active", True):
            continue
        sk = str(entry.get("species_key") or "").strip()
        if not sk:
            continue
        counts[sk] = counts.get(sk, 0) + 1
    return counts


def primary_showcase_by_species(*, active_only: bool = True) -> dict[str, dict[str, Any]]:
    """Primeira vitrine ativa por espécie (thumb do card)."""
    result: dict[str, dict[str, Any]] = {}
    entries = load_store().get("entries") or []
    for entry in _sort_entries([e for e in entries if isinstance(e, dict)]):
        if active_only and not entry.get("active", True):
            continue
        sk = str(entry.get("species_key") or "").strip()
        if not sk or sk in result:
            continue
        result[sk] = _entry_to_public(entry)
    return result


def is_species_orderable(species_key: str) -> bool:
    return int(showcase_counts_by_species(active_only=True).get(str(species_key or "").strip()) or 0) > 0


def _validate_body(body: dict[str, Any], *, require_species: bool = True) -> dict[str, Any]:
    species_key = str(body.get("species_key") or "").strip()
    if require_species and not species_key:
        raise ValueError("species_key_required")
    color_name = str(body.get("color_name") or "").strip()
    if not color_name:
        raise ValueError("color_name_required")
    if len(color_name) > _MAX_LABEL:
        raise ValueError("color_name_too_long")
    regions_label = str(body.get("regions_label") or "").strip()[:_MAX_LABEL]
    description = str(body.get("description") or "").strip()[:_MAX_DESCRIPTION]
    colors = _normalize_colors(body.get("colors"))
    image_url = str(body.get("image_url") or "").strip()
    if image_url and len(image_url) > 500:
        raise ValueError("image_url_too_long")
    sort_order = int(body.get("sort_order") or 0)
    active = bool(body.get("active", True))
    return {
        "species_key": species_key,
        "color_name": color_name,
        "regions_label": regions_label,
        "description": description,
        "colors": colors,
        "image_url": image_url,
        "sort_order": sort_order,
        "active": active,
    }


def create_showcase(body: dict[str, Any]) -> dict[str, Any]:
    fields = _validate_body(body)
    if count_showcases_for_species(fields["species_key"]) >= MAX_SHOWCASES_PER_SPECIES:
        raise ValueError("showcase_limit_reached")
    now = _utcnow().isoformat()
    entry = {
        "id": _new_id(),
        **fields,
        "created_at": now,
        "updated_at": now,
    }
    data = load_store()
    entries = list(data.get("entries") or [])
    entries.append(entry)
    data["entries"] = entries
    save_store(data)
    return dict(entry)


def update_showcase(entry_id: str, body: dict[str, Any]) -> dict[str, Any]:
    data = load_store()
    entries = list(data.get("entries") or [])
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict) or str(entry.get("id")) != entry_id:
            continue
        merged = dict(entry)
        fields = _validate_body({**entry, **body})
        new_sk = fields["species_key"]
        if count_showcases_for_species(new_sk, exclude_id=entry_id) >= MAX_SHOWCASES_PER_SPECIES:
            raise ValueError("showcase_limit_reached")
        merged.update(fields)
        merged["updated_at"] = _utcnow().isoformat()
        entries[idx] = merged
        data["entries"] = entries
        save_store(data)
        return dict(merged)
    raise ValueError("showcase_not_found")


def delete_showcase(entry_id: str) -> dict[str, Any]:
    data = load_store()
    entries = list(data.get("entries") or [])
    removed: dict[str, Any] | None = None
    kept: list[dict[str, Any]] = []
    for entry in entries:
        if isinstance(entry, dict) and str(entry.get("id")) == entry_id:
            removed = dict(entry)
            continue
        kept.append(entry)
    if removed is None:
        raise ValueError("showcase_not_found")
    data["entries"] = kept
    save_store(data)
    return removed


def _guess_ext(mime: str, filename: str) -> str:
    low = (filename or "").lower()
    if low.endswith(".png"):
        return ".png"
    if low.endswith(".webp"):
        return ".webp"
    if low.endswith(".gif"):
        return ".gif"
    if low.endswith(".jpg") or low.endswith(".jpeg"):
        return ".jpg"
    if mime == "image/png":
        return ".png"
    if mime == "image/webp":
        return ".webp"
    if mime == "image/gif":
        return ".gif"
    return ".jpg"


def save_showcase_image(
    file_storage: Any,
    *,
    mime_type: str | None = None,
) -> dict[str, Any]:
    if file_storage is None:
        raise ValueError("file_required")
    mime = (mime_type or getattr(file_storage, "mimetype", None) or "").split(";")[0].strip().lower()
    if mime not in _ALLOWED_IMAGE_MIME:
        raise ValueError("invalid_image_type")
    raw = file_storage.read()
    if not raw:
        raise ValueError("empty_file")
    if len(raw) > _MAX_IMAGE_BYTES:
        raise ValueError("file_too_large")
    original = str(getattr(file_storage, "filename", None) or "image.jpg")
    ext = _guess_ext(mime, original)
    name = f"{uuid.uuid4().hex}{ext}"
    dest = _uploads_path() / name
    dest.write_bytes(raw)
    url = f"{_image_url_prefix}/{name}"
    return {"filename": name, "image_url": url, "size": len(raw), "mime_type": mime}


def resolve_showcase_image_path(filename: str) -> Path | None:
    safe = Path(filename).name
    if not safe or not _SAFE_FILENAME.match(safe):
        return None
    full = _uploads_path() / safe
    if not full.is_file():
        return None
    return full
