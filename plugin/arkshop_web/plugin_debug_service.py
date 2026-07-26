"""Serviço MySQL para eventos de debug dos plugins ARKLAND.

Tabela: arkland_plugin_debug (criada também pelo CustomShop::ShopPoints::Open).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

log = logging.getLogger("arkshop_web.plugin_debug")

ENSURE_DDL = """
CREATE TABLE IF NOT EXISTS arkland_plugin_debug (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  plugin VARCHAR(32) NOT NULL,
  plugin_version VARCHAR(16) NOT NULL DEFAULT '',
  level VARCHAR(8) NOT NULL,
  category VARCHAR(32) NOT NULL,
  server_id VARCHAR(64) DEFAULT NULL,
  steam_id VARCHAR(32) DEFAULT NULL,
  order_id VARCHAR(64) DEFAULT NULL,
  correlation_id VARCHAR(64) DEFAULT NULL,
  message TEXT NOT NULL,
  fields_json JSON NULL,
  KEY idx_apd_created (created_at),
  KEY idx_apd_plugin_cat (plugin, category),
  KEY idx_apd_steam (steam_id),
  KEY idx_apd_corr (correlation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# Severidade: número menor = mais grave (ERROR < WARN < INFO …).
_LEVEL_RANK: dict[str, int] = {
    "ERROR": 1,
    "ERR": 1,
    "WARN": 2,
    "WARNING": 2,
    "INFO": 3,
    "DEBUG": 4,
    "DBG": 4,
    "TRACE": 5,
}

_LEVELS_BY_RANK: list[tuple[str, int]] = [
    ("ERROR", 1),
    ("WARN", 2),
    ("INFO", 3),
    ("DEBUG", 4),
    ("TRACE", 5),
]

_STEAM_KEYS = ("steam_id", "steamid", "SteamId", "steamId")
_ORDER_KEYS = ("order_id", "orderId", "OrderId")
_SERVER_KEYS = ("server_id", "serverId", "ServerId")
_CORR_KEYS = ("correlation_id", "correlationId", "request_id", "requestId")


def ensure_plugin_debug_schema(engine) -> None:
    if engine is None:
        return
    try:
        with engine.begin() as conn:
            conn.execute(text(ENSURE_DDL))
    except Exception as exc:
        log.warning("ensure_plugin_debug_schema failed: %s", exc)


def _as_fields_dict(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            parsed = json.loads(s)
        except Exception:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _pick_str(*candidates: Any, max_len: int = 64) -> str | None:
    for c in candidates:
        if c is None:
            continue
        s = str(c).strip()
        if s:
            return s[:max_len]
    return None


def _pick_from_mapping(mapping: dict[str, Any] | None, keys: tuple[str, ...], max_len: int) -> str | None:
    if not mapping:
        return None
    for k in keys:
        if k in mapping and mapping[k] is not None:
            s = str(mapping[k]).strip()
            if s:
                return s[:max_len]
    return None


def _levels_at_or_above(min_level: str) -> list[str]:
    key = (min_level or "").strip().upper()
    if key.endswith("+"):
        key = key[:-1]
    rank = _LEVEL_RANK.get(key)
    if rank is None:
        return [key] if key else []
    return [name for name, r in _LEVELS_BY_RANK if r <= rank]


def _sanitize_like_term(term: str) -> str:
    """Remove metacaracteres LIKE para pesquisa portátil (MySQL + SQLite)."""
    return "".join(ch for ch in term if ch not in "%_\\")


def enrich_event_row(item: dict[str, Any]) -> dict[str, Any]:
    """Normaliza fields_json e preenche steam/order/server/corr a partir do payload."""
    fj = _as_fields_dict(item.get("fields_json"))
    if fj is not None:
        item["fields_json"] = fj
    else:
        # Manter string ilegível como veio (UI mostra raw no detalhe se preciso).
        pass

    if not item.get("steam_id"):
        picked = _pick_from_mapping(fj, _STEAM_KEYS, 32)
        if picked:
            item["steam_id"] = picked
    if not item.get("order_id"):
        picked = _pick_from_mapping(fj, _ORDER_KEYS, 64)
        if picked:
            item["order_id"] = picked
    if not item.get("server_id"):
        picked = _pick_from_mapping(fj, _SERVER_KEYS, 64)
        if picked:
            item["server_id"] = picked
    if not item.get("correlation_id"):
        picked = _pick_from_mapping(fj, _CORR_KEYS, 64)
        if picked:
            item["correlation_id"] = picked
    return item


def ingest_event(session, payload: dict[str, Any]) -> int | None:
    """Insere um evento (plugin API key). Devolve id ou None."""
    plugin = str(payload.get("plugin") or "unknown")[:32]
    version = str(payload.get("version") or payload.get("plugin_version") or "")[:16]
    level = str(payload.get("level") or "INFO")[:8]
    category = str(payload.get("category") or "General")[:32]
    message = str(payload.get("message") or "")[:4000]
    if not message:
        return None

    fields = payload.get("fields")
    if fields is None and isinstance(payload.get("extra"), dict):
        fields = payload["extra"]
    if fields is None and isinstance(payload.get("details"), dict):
        fields = payload["details"]
    if fields is None and isinstance(payload.get("payload"), dict):
        fields = payload["payload"]
    fields_dict = _as_fields_dict(fields)
    fields_json = None
    if fields_dict is not None:
        try:
            fields_json = json.dumps(fields_dict, ensure_ascii=False)
        except Exception:
            fields_json = None
    elif fields is not None:
        try:
            fields_json = json.dumps(fields, ensure_ascii=False)
        except Exception:
            fields_json = None

    steam_id = _pick_str(
        payload.get("steam_id"),
        _pick_from_mapping(fields_dict, _STEAM_KEYS, 32),
        max_len=32,
    )
    order_id = _pick_str(
        payload.get("order_id"),
        _pick_from_mapping(fields_dict, _ORDER_KEYS, 64),
        max_len=64,
    )
    server_id = _pick_str(
        payload.get("server_id"),
        _pick_from_mapping(fields_dict, _SERVER_KEYS, 64),
        max_len=64,
    )
    corr = _pick_str(
        payload.get("correlation_id"),
        payload.get("request_id"),
        _pick_from_mapping(fields_dict, _CORR_KEYS, 64),
        max_len=64,
    )

    row = session.execute(
        text(
            "INSERT INTO arkland_plugin_debug "
            "(plugin, plugin_version, level, category, server_id, steam_id, "
            "order_id, correlation_id, message, fields_json) "
            "VALUES (:plugin, :ver, :level, :cat, :server_id, :steam_id, "
            ":order_id, :corr, :message, :fields_json)"
        ),
        {
            "plugin": plugin,
            "ver": version,
            "level": level,
            "cat": category,
            "server_id": server_id,
            "steam_id": steam_id,
            "order_id": order_id,
            "corr": corr,
            "message": message,
            "fields_json": fields_json,
        },
    )
    return int(row.lastrowid) if row.lastrowid else None


def list_events(
    session,
    *,
    plugin: str | None = None,
    category: str | None = None,
    level: str | None = None,
    min_level: str | None = None,
    steam_id: str | None = None,
    q: str | None = None,
    limit: int = 10,
    offset: int = 0,
    since_id: int | None = None,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 10), 500))
    offset = max(0, int(offset or 0))
    clauses = ["1=1"]
    params: dict[str, Any] = {"lim": limit, "off": offset}
    if plugin:
        clauses.append("plugin = :plugin")
        params["plugin"] = plugin[:32]
    if category:
        clauses.append("category = :category")
        params["category"] = category[:32]

    level_exact = (level or "").strip()
    if level_exact.endswith("+") and not min_level:
        min_level = level_exact
        level_exact = ""
    if level_exact:
        clauses.append("level = :level")
        params["level"] = level_exact[:8]
    elif min_level:
        levels = _levels_at_or_above(min_level)
        if levels:
            placeholders = []
            for i, lv in enumerate(levels):
                key = f"lvl{i}"
                placeholders.append(f":{key}")
                params[key] = lv
            clauses.append(f"level IN ({', '.join(placeholders)})")

    if steam_id:
        clauses.append("steam_id = :steam_id")
        params["steam_id"] = steam_id[:32]
    if since_id is not None:
        clauses.append("id > :since_id")
        params["since_id"] = int(since_id)

    q_term = _sanitize_like_term((q or "").strip())[:120]
    if q_term:
        like = f"%{q_term}%"
        params["q"] = like
        clauses.append(
            "("
            "message LIKE :q OR "
            "IFNULL(steam_id,'') LIKE :q OR "
            "IFNULL(order_id,'') LIKE :q OR "
            "IFNULL(correlation_id,'') LIKE :q OR "
            "IFNULL(server_id,'') LIKE :q OR "
            "CAST(fields_json AS CHAR) LIKE :q"
            ")"
        )

    sql = (
        "SELECT id, created_at, plugin, plugin_version, level, category, "
        "server_id, steam_id, order_id, correlation_id, message, fields_json "
        f"FROM arkland_plugin_debug WHERE {' AND '.join(clauses)} "
        "ORDER BY id DESC LIMIT :lim OFFSET :off"
    )
    rows = session.execute(text(sql), params).mappings().all()
    out: list[dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        ca = item.get("created_at")
        if isinstance(ca, datetime):
            if ca.tzinfo is None:
                ca = ca.replace(tzinfo=timezone.utc)
            item["created_at"] = ca.isoformat()
        out.append(enrich_event_row(item))
    return out
