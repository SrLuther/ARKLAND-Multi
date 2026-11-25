"""Armazenamento persistente e validação de imagens da Comunicação Lumo."""
from __future__ import annotations

import io
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_FORMATS = {"PNG": ("image/png", ".png"), "JPEG": ("image/jpeg", ".jpg"), "GIF": ("image/gif", ".gif"), "WEBP": ("image/webp", ".webp")}


def validate_and_store(directory: Path, stream: Any, original_name: str, actor: str) -> dict[str, Any]:
    raw = stream.read(MAX_IMAGE_BYTES + 1)
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("A imagem deve ter entre 1 byte e 8 MB.")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            fmt = str(image.format or "").upper()
            width, height = image.size
            if fmt not in ALLOWED_FORMATS:
                raise ValueError("Formato não permitido. Use PNG, JPEG, GIF ou WebP.")
            if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS or max(width, height) > 8192:
                raise ValueError("Dimensões da imagem excedem o limite seguro.")
            # Força decodificação completa para rejeitar arquivos malformados.
            image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("O arquivo não é uma imagem válida ou está malformado.") from exc
    mime, suffix = ALLOWED_FORMATS[fmt]
    asset_id = uuid.uuid4().hex
    safe_name = f"{asset_id}{suffix}"
    directory.mkdir(parents=True, exist_ok=True)
    target = (directory / safe_name).resolve()
    if target.parent != directory.resolve():
        raise ValueError("Destino de armazenamento inválido.")
    # Criação exclusiva: nunca sobrescreve arquivo existente.
    with target.open("xb") as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())
    now = datetime.now(UTC).isoformat(timespec="seconds")
    return {"id": asset_id, "original_name": Path(str(original_name or "imagem")).name[:180],
            "filename": safe_name, "mime_type": mime, "size": len(raw), "width": width,
            "height": height, "uploaded_at": now, "last_used_at": "", "uploaded_by": str(actor or "")[:64],
            "references": [], "status": "active"}


def resolve_asset(directory: Path, record: dict[str, Any]) -> Path:
    name = str(record.get("filename") or "")
    if not name or Path(name).name != name:
        raise ValueError("Arquivo de imagem inválido.")
    root = directory.resolve()
    path = (root / name).resolve()
    if path.parent != root or not path.is_file():
        raise ValueError("Arquivo de imagem não encontrado.")
    return path


def cleanup_assets(directory: Path, records: list[dict[str, Any]], *, retention_days: int, now: datetime | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    cutoff = (now or datetime.now(UTC)) - timedelta(days=max(1, min(3650, int(retention_days))))
    kept: list[dict[str, Any]] = []
    removed: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        stamp = record.get("last_used_at") or record.get("uploaded_at") or ""
        try:
            used = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
            used = used.replace(tzinfo=UTC) if used.tzinfo is None else used.astimezone(UTC)
        except (ValueError, TypeError):
            kept.append(record)
            continue
        if used >= cutoff or record.get("references"):
            kept.append(record)
            continue
        try:
            path = resolve_asset(directory, record)
            path.unlink()
            removed.append(str(record.get("id") or ""))
        except (OSError, ValueError):
            # Falha/arquivo fora da raiz não remove o registro e não interrompe o Lumo.
            kept.append(record)
    return kept, removed
