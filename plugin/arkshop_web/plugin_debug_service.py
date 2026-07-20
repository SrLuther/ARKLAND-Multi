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


def ensure_plugin_debug_schema(engine) -> None:
    if engine is None:
        return
    try:
        with engine.begin() as conn:
            conn.execute(text(ENSURE_DDL))
    except Exception as exc:
        log.warning("ensure_plugin_debug_schema failed: %s", exc)


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
    fields_json = None
    if fields is not None:
        try:
            fields_json = json.dumps(fields, ensure_ascii=False)
        except Exception:
            fields_json = None

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
            "server_id": (str(payload["server_id"])[:64] if payload.get("server_id") else None),
            "steam_id": (str(payload["steam_id"])[:32] if payload.get("steam_id") else None),
            "order_id": (str(payload["order_id"])[:64] if payload.get("order_id") else None),
            "corr": (
                str(payload["correlation_id"])[:64]
                if payload.get("correlation_id")
                else None
            ),
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
    steam_id: str | None = None,
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
    if level:
        clauses.append("level = :level")
        params["level"] = level[:8]
    if steam_id:
        clauses.append("steam_id = :steam_id")
        params["steam_id"] = steam_id[:32]
    if since_id is not None:
        clauses.append("id > :since_id")
        params["since_id"] = int(since_id)

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
        fj = item.get("fields_json")
        if isinstance(fj, str):
            try:
                item["fields_json"] = json.loads(fj)
            except Exception:
                pass
        out.append(item)
    return out
