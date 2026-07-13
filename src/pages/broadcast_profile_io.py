"""Exportação e importação da biblioteca global de broadcasts TEK."""
from __future__ import annotations

import json
import platform
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

FORMAT_ID = "arkland-broadcast-library"
FORMAT_VERSION = 1
_MAX_MSG_LEN = 900


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_entry(raw: dict[str, Any]) -> dict[str, Any]:
    """Valida e normaliza um item da biblioteca."""
    label = str(raw.get("label", "")).strip()
    message = str(raw.get("message", "")).strip()
    if not label or not message:
        raise ValueError("Cada mensagem precisa de rótulo e texto.")
    entry_id = str(raw.get("id") or uuid.uuid4())
    now = _now_iso()
    entry: dict[str, Any] = {
        "id": entry_id,
        "label": label[:120],
        "message": message[:_MAX_MSG_LEN],
        "created_at": str(raw.get("created_at") or now),
        "updated_at": str(raw.get("updated_at") or now),
    }
    # Metadados opcionais (ex.: pacote Regulamento)
    source = str(raw.get("source") or "").strip()
    if source:
        entry["source"] = source[:64]
    category = str(raw.get("category") or "").strip()
    if category:
        entry["category"] = category[:64]
    section = str(raw.get("section") or "").strip()
    if section:
        entry["section"] = section[:32]
    return entry


def get_library(app: "ARKServerManagerApp") -> list[dict[str, Any]]:
    lib = app.config_manager.config.broadcast_library
    if not isinstance(lib, list):
        return []
    return list(lib)


def set_library(app: "ARKServerManagerApp", entries: list[dict[str, Any]]) -> None:
    app.config_manager.config.broadcast_library = entries
    app.config_manager.save()


def build_export_document(app: "ARKServerManagerApp") -> dict[str, Any]:
    from ..config_manager import BroadcastTekConfig
    from .broadcast_tek_settings import get_settings

    messages = [normalize_entry(e) for e in get_library(app)]
    settings = get_settings(app)
    settings_payload = {
        "interval_minutes": settings.interval_minutes,
        "random_order": settings.random_order,
        "target_server_ids": list(settings.target_server_ids),
        "enabled_message_ids": list(settings.enabled_message_ids),
    }
    return {
        "format": FORMAT_ID,
        "version": FORMAT_VERSION,
        "exported_at": _now_iso(),
        "source_host": platform.node(),
        "messages": messages,
        "settings": settings_payload,
        "notes": (
            "Importe este arquivo em outro PC com ARKLAND TEK. "
            "Use mesclar para atualizar por ID ou substituir para trocar a biblioteca inteira."
        ),
    }


def export_broadcast_library(app: "ARKServerManagerApp", path: str) -> None:
    doc = build_export_document(app)
    Path(path).write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_import_document(raw: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Arquivo inválido: esperado objeto JSON.")

    if data.get("format") == FORMAT_ID:
        messages_raw = data.get("messages") or []
        meta = {k: v for k, v in data.items() if k != "messages"}
    elif isinstance(data.get("messages"), list):
        messages_raw = data["messages"]
        meta = {}
    else:
        raise ValueError("Arquivo não reconhecido como biblioteca de broadcasts ARKLAND.")

    if not isinstance(messages_raw, list):
        raise ValueError("Campo 'messages' inválido.")

    messages = [normalize_entry(m) for m in messages_raw if isinstance(m, dict)]
    return messages, meta


def merge_library(
    current: list[dict[str, Any]],
    imported: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Mescla por id — atualiza existentes, adiciona novos."""
    by_id = {str(e.get("id")): deepcopy(e) for e in current if isinstance(e, dict) and e.get("id")}
    for item in imported:
        entry = normalize_entry(item)
        existing = by_id.get(entry["id"])
        if existing:
            entry["created_at"] = existing.get("created_at", entry["created_at"])
        entry["updated_at"] = _now_iso()
        by_id[entry["id"]] = entry
    return list(by_id.values())


def import_broadcast_library_from_file(
    app: "ARKServerManagerApp",
    path: str,
    *,
    replace: bool = False,
) -> tuple[int, int, dict[str, Any]]:
    """Importa biblioteca. Retorna (adicionados, atualizados, meta)."""
    raw = Path(path).read_text(encoding="utf-8")
    imported, meta = parse_import_document(raw)

    if replace:
        set_library(app, imported)
        added, updated = len(imported), 0
    else:
        current = get_library(app)
        before_ids = {str(e.get("id")) for e in current if e.get("id")}
        merged = merge_library(current, imported)
        set_library(app, merged)
        after_ids = {str(e.get("id")) for e in merged}
        added = len(after_ids - before_ids)
        updated = sum(1 for e in imported if str(e.get("id")) in before_ids)

    _apply_imported_settings(app, meta.get("settings"))
    return added, updated, meta


def _apply_imported_settings(app: "ARKServerManagerApp", raw: Any) -> None:
    from ..config_manager import BroadcastTekConfig
    from .broadcast_tek_settings import get_settings, save_settings

    if not isinstance(raw, dict):
        return
    cur = get_settings(app)
    cur.interval_minutes = max(1, int(raw.get("interval_minutes", cur.interval_minutes)))
    cur.random_order = bool(raw.get("random_order", cur.random_order))
    if isinstance(raw.get("target_server_ids"), list):
        cur.target_server_ids = [str(x) for x in raw["target_server_ids"]]
    if isinstance(raw.get("enabled_message_ids"), list):
        cur.enabled_message_ids = [str(x) for x in raw["enabled_message_ids"]]
    save_settings(app, cur)
