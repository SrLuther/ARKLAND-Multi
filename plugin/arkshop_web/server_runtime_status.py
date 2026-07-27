"""Status runtime dos servidores (TEK → Web Store) para a home pública."""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_lock = threading.Lock()
_cache: dict[str, Any] = {"at": 0.0, "by_id": {}}
_CACHE_TTL_S = 2.0

VALID_STATUSES = frozenset({"PARADO", "INICIANDO", "ATUALIZANDO", "ONLINE"})


def _store_path() -> Path:
    try:
        from arkland_environment import webstore_data_dir

        return Path(webstore_data_dir()) / "server_runtime_status.json"
    except Exception:
        return Path("server_runtime_status.json")


def _read_disk() -> dict[str, dict[str, Any]]:
    path = _store_path()
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("server_runtime_status read: %s", exc)
        return {}
    if not isinstance(raw, dict):
        return {}
    items = raw.get("servers") if isinstance(raw.get("servers"), dict) else raw
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(items, dict):
        return out
    for sid, row in items.items():
        key = str(sid or "").strip()
        if not key or not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").strip().upper()
        if status not in VALID_STATUSES:
            continue
        out[key] = {
            "status": status,
            "display_name": str(row.get("display_name") or "").strip(),
            "updated_at": str(row.get("updated_at") or "").strip(),
            "updated_at_unix": float(row.get("updated_at_unix") or 0) or 0.0,
        }
    return out


def _write_disk(by_id: dict[str, dict[str, Any]]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at_unix": time.time(),
        "servers": by_id,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def get_all_statuses(*, max_age_s: float = 300.0) -> dict[str, dict[str, Any]]:
    """Retorna mapa server_id → status (descarta entradas muito antigas)."""
    now = time.time()
    with _lock:
        if now - float(_cache.get("at") or 0) < _CACHE_TTL_S and isinstance(
            _cache.get("by_id"), dict
        ):
            by_id = dict(_cache["by_id"])
        else:
            by_id = _read_disk()
            _cache["by_id"] = dict(by_id)
            _cache["at"] = now
    if max_age_s <= 0:
        return by_id
    fresh: dict[str, dict[str, Any]] = {}
    for sid, row in by_id.items():
        ts = float(row.get("updated_at_unix") or 0)
        if ts and (now - ts) > max_age_s:
            continue
        fresh[sid] = row
    return fresh


def upsert_statuses(items: list[dict[str, Any]]) -> int:
    """Mescla lista de status. Retorna quantos foram gravados."""
    now = time.time()
    with _lock:
        by_id = _read_disk()
        n = 0
        for raw in items:
            if not isinstance(raw, dict):
                continue
            sid = str(raw.get("server_id") or "").strip()
            status = str(raw.get("status") or "").strip().upper()
            if not sid or status not in VALID_STATUSES:
                continue
            by_id[sid] = {
                "status": status,
                "display_name": str(raw.get("display_name") or "").strip(),
                "updated_at": str(raw.get("updated_at") or "").strip(),
                "updated_at_unix": float(raw.get("updated_at_unix") or now) or now,
            }
            n += 1
        if n:
            _write_disk(by_id)
            _cache["by_id"] = dict(by_id)
            _cache["at"] = now
        return n


def status_for_server(server_id: str, *, max_age_s: float = 300.0) -> dict[str, Any] | None:
    sid = str(server_id or "").strip()
    if not sid:
        return None
    return get_all_statuses(max_age_s=max_age_s).get(sid)
