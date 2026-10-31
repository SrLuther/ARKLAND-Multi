"""Staff — membros conhecidos por mapa (tribe_members / tribe_presences)."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger("arkshop_web.map_members")


def _as_int(value: Any) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        n = int(value)
        return n if n != 0 else None
    except (TypeError, ValueError):
        return None


def _label_for(server_id: str, labels: dict[str, str] | None) -> str:
    sid = str(server_id or "").strip()
    if not sid:
        return "?"
    if labels:
        lab = (labels.get(sid) or "").strip()
        if lab:
            return lab
    return sid


def list_members_for_server(
    db: Session,
    *,
    server_id: str,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    """Lista jogadores com filiação conhecida num mapa."""
    sid = str(server_id or "").strip()
    limit = max(1, min(int(limit or 200), 500))
    offset = max(0, int(offset or 0))
    if not sid:
        return {"server_id": "", "total": 0, "items": []}

    # Uma linha por steam_id (última vista) neste server_id.
    rows = db.execute(
        text("""
            SELECT steam_id, character_name, tribe_id, tribe_name,
                   player_data_id, last_seen_at
            FROM tribe_members
            WHERE server_id = :svid
            ORDER BY
              CASE WHEN last_seen_at IS NULL THEN 1 ELSE 0 END,
              last_seen_at DESC,
              character_name ASC
            LIMIT :lim OFFSET :off
        """),
        {"svid": sid, "lim": limit, "off": offset},
    ).fetchall()

    total_row = db.execute(
        text("""
            SELECT COUNT(DISTINCT steam_id) FROM tribe_members
            WHERE server_id = :svid
        """),
        {"svid": sid},
    ).fetchone()
    total = int(total_row[0] or 0) if total_row else 0

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in rows:
        steam = str(r[0] or "").strip()
        if not steam or steam in seen:
            continue
        seen.add(steam)
        items.append({
            "steam_id": steam,
            "character_name": (r[1] or "").strip() or steam,
            "tribe_id": _as_int(r[2]),
            "tribe_name": (r[3] or "").strip() or None,
            "player_data_id": _as_int(r[4]),
            "last_seen_at": str(r[5]) if r[5] else None,
            "source": "members",
            "is_offline_identity": steam.startswith("pdid:"),
        })
        if len(items) >= limit:
            break

    # Fallback: presenças com tribo quando ainda não há members neste mapa.
    if total == 0:
        pres = db.execute(
            text("""
                SELECT steam_id, tribe_id, tribe_name, captured_at
                FROM tribe_presences
                WHERE server_id = :svid
                  AND tribe_id IS NOT NULL
                ORDER BY captured_at DESC
                LIMIT :lim OFFSET :off
            """),
            {"svid": sid, "lim": limit, "off": offset},
        ).fetchall()
        for r in pres:
            steam = str(r[0] or "").strip()
            if not steam or steam in seen:
                continue
            seen.add(steam)
            items.append({
                "steam_id": steam,
                "character_name": steam,
                "tribe_id": _as_int(r[1]),
                "tribe_name": (r[2] or "").strip() or None,
                "player_data_id": None,
                "last_seen_at": str(r[3]) if r[3] else None,
                "source": "presence",
                "is_offline_identity": steam.startswith("pdid:"),
            })
        total_p = db.execute(
            text("""
                SELECT COUNT(DISTINCT steam_id) FROM tribe_presences
                WHERE server_id = :svid
                  AND tribe_id IS NOT NULL
            """),
            {"svid": sid},
        ).fetchone()
        total = int(total_p[0] or 0) if total_p else len(items)

    return {
        "server_id": sid,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


def get_member_detail(
    db: Session,
    *,
    server_id: str,
    steam_id: str,
    map_labels: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Detalhe DADOS para um jogador num mapa + mapas associados."""
    svid = str(server_id or "").strip()
    sid = str(steam_id or "").strip()
    if not svid or not sid:
        return None

    row = db.execute(
        text("""
            SELECT steam_id, character_name, tribe_id, tribe_name,
                   player_data_id, last_seen_at
            FROM tribe_members
            WHERE server_id = :svid AND steam_id = :sid
            ORDER BY last_seen_at DESC
            LIMIT 1
        """),
        {"svid": svid, "sid": sid},
    ).fetchone()

    source = "members"
    if not row:
        row = db.execute(
            text("""
                SELECT steam_id, NULL, tribe_id, tribe_name, NULL, captured_at
                FROM tribe_presences
                WHERE server_id = :svid AND steam_id = :sid AND tribe_id IS NOT NULL
                ORDER BY captured_at DESC
                LIMIT 1
            """),
            {"svid": svid, "sid": sid},
        ).fetchone()
        source = "presence"
        if not row:
            return None

    associated: list[dict[str, Any]] = []
    other_rows = db.execute(
        text("""
            SELECT server_id, tribe_id, tribe_name, character_name, last_seen_at
            FROM tribe_members
            WHERE steam_id = :sid AND server_id != :svid
            ORDER BY last_seen_at DESC
        """),
        {"sid": sid, "svid": svid},
    ).fetchall()
    seen_maps: set[str] = set()
    for r in other_rows:
        other_sid = str(r[0] or "").strip()
        if not other_sid or other_sid in seen_maps:
            continue
        seen_maps.add(other_sid)
        associated.append({
            "server_id": other_sid,
            "label": _label_for(other_sid, map_labels),
            "tribe_id": _as_int(r[1]),
            "tribe_name": (r[2] or "").strip() or None,
            "character_name": (r[3] or "").strip() or None,
            "last_seen_at": str(r[4]) if r[4] else None,
            "source": "members",
        })

    # Presenças noutros mapas sem linha em tribe_members.
    pres_rows = db.execute(
        text("""
            SELECT server_id, tribe_id, tribe_name, captured_at
            FROM tribe_presences
            WHERE steam_id = :sid AND server_id != :svid AND tribe_id IS NOT NULL
            ORDER BY captured_at DESC
        """),
        {"sid": sid, "svid": svid},
    ).fetchall()
    for r in pres_rows:
        other_sid = str(r[0] or "").strip()
        if not other_sid or other_sid in seen_maps:
            continue
        seen_maps.add(other_sid)
        associated.append({
            "server_id": other_sid,
            "label": _label_for(other_sid, map_labels),
            "tribe_id": _as_int(r[1]),
            "tribe_name": (r[2] or "").strip() or None,
            "character_name": None,
            "last_seen_at": str(r[3]) if r[3] else None,
            "source": "presence",
        })

    return {
        "server_id": svid,
        "map_label": _label_for(svid, map_labels),
        "steam_id": sid,
        "character_name": (row[1] or "").strip() or sid,
        "player_data_id": _as_int(row[4]),
        "tribe_id": _as_int(row[2]),
        "tribe_name": (row[3] or "").strip() or None,
        "last_seen_at": str(row[5]) if row[5] else None,
        "source": source,
        "associated_maps": associated,
    }


def build_map_members_payload(
    db: Session,
    *,
    servers: list[dict[str, Any]],
    server_id: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    """Monta resposta de listagem (um mapa ou todos os cadastrados)."""
    labels = {
        str(s.get("server_id") or "").strip(): str(s.get("label") or s.get("server_id") or "").strip()
        for s in servers
        if str(s.get("server_id") or "").strip()
    }
    latest_map_names: dict[str, str] = {}
    for row in db.execute(text("""
        SELECT server_id, map_name FROM tribe_presences
        WHERE COALESCE(server_id, '') != ''
        ORDER BY captured_at DESC
    """)).fetchall():
        discovered_id = str(row[0] or "").strip()
        map_name = str(row[1] or "").strip()
        if discovered_id and map_name and discovered_id not in latest_map_names:
            latest_map_names[discovered_id] = map_name
    target_ids: list[str]
    if server_id:
        target_ids = [str(server_id).strip()]
    else:
        target_ids = [
            str(s.get("server_id") or "").strip()
            for s in servers
            if str(s.get("server_id") or "").strip()
        ]

        # TribeSync grava usando Settings.ServerId/CrossChat.ServerId do plugin.
        # Se esse valor divergir do cadastro da Web Store, os registros não podem
        # desaparecer silenciosamente: inclui os IDs realmente encontrados.
        discovered = db.execute(text("""
            SELECT server_id FROM tribe_members WHERE COALESCE(server_id, '') != ''
            UNION
            SELECT server_id FROM tribe_presences WHERE COALESCE(server_id, '') != ''
        """)).fetchall()
        for row in discovered:
            discovered_id = str(row[0] or "").strip()
            if discovered_id and discovered_id not in target_ids:
                target_ids.append(discovered_id)

    maps_out: list[dict[str, Any]] = []
    for sid in target_ids:
        block = list_members_for_server(db, server_id=sid, limit=limit, offset=offset)
        maps_out.append({
            "server_id": sid,
            "label": labels.get(sid) or latest_map_names.get(sid) or sid,
            "registered": sid in labels,
            "total": block["total"],
            "limit": block["limit"],
            "offset": block["offset"],
            "items": block["items"],
        })
    return {"ok": True, "maps": maps_out}
