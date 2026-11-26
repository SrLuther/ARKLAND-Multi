"""Consulta administrativa de identidades por mapa; não modifica registros."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache
import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, inspect, text
from sqlalchemy.orm import Session

log = logging.getLogger("arkshop_web.map_members")


def _as_int(value: Any) -> int | None:
    try:
        result = int(value)
        return result if result > 0 else None
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=128)
def _plugin_identity(path: str, mtime_ns: int, size: int) -> str:
    config = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        return ""
    # Mesma precedência do plugin, sem inferir identidade pelo nome ou UUID.
    for section in ("Settings", "CrossChat"):
        section_config = config.get(section) or {}
        if not isinstance(section_config, dict):
            continue
        value = str(section_config.get("ServerId") or "").strip()
        if value and value.lower() not in {"unknown", "server", "master"}:
            return value
    return ""


def server_identity_catalog(servers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    catalog = []
    owners: dict[str, set[str]] = defaultdict(set)
    for server in servers:
        sid = str(server.get("server_id") or "").strip()
        if not sid:
            continue
        aliases = {sid}
        path = str(server.get("plugin_config_path") or "").strip()
        if path:
            try:
                stat = Path(path).stat()
                plugin_id = _plugin_identity(path, stat.st_mtime_ns, stat.st_size)
                if plugin_id:
                    aliases.add(plugin_id)
            except (OSError, ValueError, TypeError):
                log.debug("Configuração local indisponível para o mapa %s", sid)
        for alias in aliases:
            owners[alias].add(sid)
        catalog.append({**server, "server_id": sid, "identity_server_ids": sorted(aliases)})
    for server in catalog:
        sid = server["server_id"]
        ambiguous = [alias for alias in server["identity_server_ids"] if len(owners[alias]) > 1]
        server["identity_server_ids"] = [alias for alias in server["identity_server_ids"] if alias == sid or len(owners[alias]) == 1]
        server["identity_warning"] = (
            "ID de plugin compartilhado por mais de um cadastro: associação automática suspensa."
            if ambiguous else ""
        )
    return catalog


def _timestamp(value: Any) -> datetime:
    if value:
        try:
            result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)
        except (TypeError, ValueError):
            pass
    return datetime.min.replace(tzinfo=timezone.utc)


def _identity_rows(db: Session, server_ids: list[str] | None = None, steam_id: str | None = None) -> list[dict[str, Any]]:
    clauses, params = [], {}
    if server_ids is not None:
        if not server_ids:
            return []
        clauses.append("server_id IN :server_ids")
        params["server_ids"] = server_ids
    if steam_id:
        clauses.append("steam_id = :steam_id")
        params["steam_id"] = steam_id
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    queries = [
        ("members", "SELECT steam_id, character_name, player_data_id, tribe_id, tribe_name, server_id, last_seen_at, '' AS map_name, 0 AS observation_id FROM tribe_members" + where),
        ("presence", "SELECT p.steam_id, '' AS character_name, NULL AS player_data_id, p.tribe_id, p.tribe_name, p.server_id, p.captured_at AS last_seen_at, p.map_name, p.id AS observation_id "
         "FROM tribe_presences p JOIN (SELECT steam_id, server_id, MAX(captured_at) AS latest FROM tribe_presences" + where +
         " GROUP BY steam_id, server_id) latest ON p.steam_id=latest.steam_id AND p.server_id=latest.server_id AND p.captured_at=latest.latest"),
    ]
    if inspect(db.get_bind()).has_table("game_players"):
        queries.append(("monitor", "SELECT steam_id, player_name AS character_name, character_id AS player_data_id, tribe_id, tribe_name, server_id, last_seen_at, '' AS map_name, 0 AS observation_id FROM game_players" + where))
    result = []
    for source, sql in queries:
        query = text(sql)
        if server_ids is not None:
            query = query.bindparams(bindparam("server_ids", expanding=True))
        for raw in db.execute(query, params).mappings():
            row = dict(raw)
            row["source"] = source
            row["server_id"] = str(row["server_id"] or "").strip()
            row["steam_id"] = str(row["steam_id"] or "").strip()
            if row["server_id"] and row["steam_id"]:
                result.append(row)
    return result


def _members(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {"members": 0, "monitor": 1, "presence": 2}
    ordered = sorted(rows, key=lambda row: (priority[row["source"]], row["steam_id"], row["server_id"], -int(row["observation_id"])))
    ordered.sort(key=lambda row: _timestamp(row["last_seen_at"]), reverse=True)
    # Presenças não têm nome nem PlayerDataID. São fallback por jogador, sem
    # substituir um snapshot completo por uma linha parcial mais recente.
    ordered.sort(key=lambda row: row["source"] == "presence")
    known_ids: dict[int, set[str]] = defaultdict(set)
    for row in ordered:
        pdid = _as_int(row["player_data_id"])
        if pdid and not row["steam_id"].startswith("pdid:"):
            known_ids[pdid].add(row["steam_id"])
    found: dict[str, dict[str, Any]] = {}
    for row in ordered:
        steam = row["steam_id"]
        pdid = _as_int(row["player_data_id"])
        if steam.startswith("pdid:") and len(known_ids.get(pdid, ())) == 1:
            continue
        if steam in found:
            continue
        found[steam] = {
            "steam_id": steam,
            "character_name": str(row["character_name"] or "").strip() or steam,
            "player_data_id": pdid,
            "tribe_id": _as_int(row["tribe_id"]),
            "tribe_name": str(row["tribe_name"] or "").strip() or None,
            "last_seen_at": str(row["last_seen_at"]) if row["last_seen_at"] else None,
            "source": row["source"],
            "source_server_id": row["server_id"],
            "is_offline_identity": steam.startswith("pdid:"),
        }
    return list(found.values())


def list_members_for_server(db: Session, *, server_id: str, limit: int = 200, offset: int = 0, server_ids: list[str] | None = None) -> dict[str, Any]:
    sid = str(server_id or "").strip()
    limit, offset = max(1, min(int(limit or 200), 500)), max(0, int(offset or 0))
    members = _members(_identity_rows(db, server_ids or [sid])) if sid else []
    return {"server_id": sid, "total": len(members), "limit": limit, "offset": offset, "items": members[offset:offset + limit]}


def get_member_detail(db: Session, *, server_id: str, steam_id: str, map_labels: dict[str, str] | None = None, servers: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    server_id, steam_id = str(server_id or "").strip(), str(steam_id or "").strip()
    if not server_id or not steam_id:
        return None
    catalog = server_identity_catalog(servers or [])
    labels = dict(map_labels or {})
    canonical = {}
    for server in catalog:
        sid = server["server_id"]
        labels[sid] = str(server.get("label") or sid)
        for alias in server["identity_server_ids"]:
            canonical[alias] = sid
    sid = canonical.get(server_id, server_id)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _identity_rows(db, steam_id=steam_id):
        grouped[canonical.get(row["server_id"], row["server_id"])].append(row)
    members = _members(grouped.get(sid, []))
    if not members:
        return None
    associated = []
    for other, rows in grouped.items():
        if other == sid:
            continue
        player = _members(rows)[0]
        associated.append({**player, "server_id": other, "label": labels.get(other) or other})
    return {**members[0], "server_id": sid, "map_label": labels.get(sid) or sid, "associated_maps": associated}


def build_map_members_payload(db: Session, *, servers: list[dict[str, Any]], server_id: str | None = None, limit: int = 200, offset: int = 0) -> dict[str, Any]:
    catalog = server_identity_catalog(servers)
    by_id = {server["server_id"]: server for server in catalog}
    canonical = {alias: sid for sid, server in by_id.items() for alias in server["identity_server_ids"]}
    target = canonical.get(server_id, server_id) if server_id else None
    ids = by_id[target]["identity_server_ids"] if target in by_id else [target] if target else None
    rows = _identity_rows(db, ids)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    historical_labels = {}
    for row in rows:
        key = canonical.get(row["server_id"], row["server_id"])
        grouped[key].append(row)
        if row.get("map_name"):
            historical_labels[key] = row["map_name"]
    limit, offset = max(1, min(int(limit or 200), 500)), max(0, int(offset or 0))

    def block(sid: str) -> dict[str, Any]:
        server = by_id.get(sid, {})
        members = _members(grouped.get(sid, []))
        return {"server_id": sid, "label": server.get("label") or historical_labels.get(sid) or sid,
                "registered": sid in by_id, "identity_server_ids": server.get("identity_server_ids", [sid]),
                "identity_warning": server.get("identity_warning", ""), "total": len(members),
                "limit": limit, "offset": offset, "items": members[offset:offset + limit]}

    targets = [target] if target else list(by_id)
    return {"ok": True, "maps": [block(sid) for sid in targets],
            "unregistered": [block(sid) for sid in sorted(grouped) if sid not in by_id] if not target else []}
