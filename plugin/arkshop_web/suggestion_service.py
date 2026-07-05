"""Sugestões da comunidade — dinos, recursos e itens para avaliação admin."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

SUGGESTION_CATEGORIES = frozenset({"dino", "recurso", "item", "outro"})
SUGGESTION_CATEGORY_LABELS: dict[str, str] = {
    "dino": "Dino",
    "recurso": "Recurso",
    "item": "Item",
    "outro": "Outro",
}

SUGGESTION_STATUSES = frozenset({
    "pending", "em_analise", "aprovada", "recusada", "implementada",
})
SUGGESTION_STATUS_LABELS: dict[str, str] = {
    "pending": "Pendente",
    "em_analise": "Em análise",
    "aprovada": "Aprovada",
    "recusada": "Recusada",
    "implementada": "Implementada",
}

_MAX_TITLE = 200
_MAX_DESCRIPTION = 4000
_MAX_ADMIN_NOTE = 2000
_MAX_DETAIL_FIELD = 128
_MAX_REASON = 1000
_DAILY_LIMIT = 3


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | str | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        s = dt.strip()
        if not s:
            return None
        try:
            if "T" in s:
                parsed = datetime.fromisoformat(s.replace("Z", "+00:00"))
            else:
                parsed = datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            return s
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def suggestion_meta() -> dict[str, Any]:
    return {
        "categories": [
            {"id": k, "label": SUGGESTION_CATEGORY_LABELS[k]}
            for k in ("dino", "recurso", "item", "outro")
        ],
        "statuses": [
            {"id": k, "label": SUGGESTION_STATUS_LABELS[k]}
            for k in (
                "pending", "em_analise", "aprovada", "recusada", "implementada",
            )
        ],
        "daily_limit": _DAILY_LIMIT,
    }


def ensure_suggestion_schema(engine: Engine) -> None:
    """Cria tabela community_suggestions (idempotente — MySQL e SQLite)."""
    is_sqlite = "sqlite" in str(engine.url).lower()
    if is_sqlite:
        stmts = [
            """
            CREATE TABLE IF NOT EXISTS community_suggestions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              steam_id VARCHAR(32) NOT NULL,
              category VARCHAR(16) NOT NULL DEFAULT 'outro',
              title VARCHAR(200) NOT NULL,
              description TEXT NOT NULL,
              details_json TEXT NULL,
              status VARCHAR(16) NOT NULL DEFAULT 'pending',
              admin_note TEXT NULL,
              admin_steam_id VARCHAR(32) NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_sugg_steam ON community_suggestions (steam_id)",
            "CREATE INDEX IF NOT EXISTS idx_sugg_status ON community_suggestions (status)",
            "CREATE INDEX IF NOT EXISTS idx_sugg_created ON community_suggestions (created_at)",
        ]
    else:
        stmts = [
            """
            CREATE TABLE IF NOT EXISTS community_suggestions (
              id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
              steam_id VARCHAR(32) NOT NULL,
              category VARCHAR(16) NOT NULL DEFAULT 'outro',
              title VARCHAR(200) NOT NULL,
              description TEXT NOT NULL,
              details_json TEXT NULL,
              status VARCHAR(16) NOT NULL DEFAULT 'pending',
              admin_note TEXT NULL,
              admin_steam_id VARCHAR(32) NULL,
              created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
              updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                ON UPDATE CURRENT_TIMESTAMP(3),
              KEY idx_sugg_steam (steam_id),
              KEY idx_sugg_status (status),
              KEY idx_sugg_created (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        ]
    with engine.connect() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))
        conn.commit()


def _normalize_category(raw: str | None) -> str:
    cat = (raw or "outro").strip().lower()[:16] or "outro"
    return cat if cat in SUGGESTION_CATEGORIES else "outro"


def _normalize_status(raw: str | None) -> str | None:
    if not raw:
        return None
    s = str(raw).strip().lower()[:16]
    return s if s in SUGGESTION_STATUSES else None


def _parse_details(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}
    else:
        return {}

    out: dict[str, Any] = {}
    for key in ("species_name", "item_name", "reason"):
        val = data.get(key)
        if val is None:
            continue
        s = str(val).strip()
        if not s:
            continue
        limit = _MAX_REASON if key == "reason" else _MAX_DETAIL_FIELD
        out[key] = s[:limit]
    return out


def _details_to_json(details: dict[str, Any]) -> str | None:
    if not details:
        return None
    return json.dumps(details, ensure_ascii=False)


def _row_to_dict(row: Any) -> dict[str, Any]:
    category = row.category or "outro"
    status = row.status or "pending"
    details = _parse_details(row.details_json)
    return {
        "id": int(row.id),
        "steam_id": row.steam_id,
        "category": category,
        "category_label": SUGGESTION_CATEGORY_LABELS.get(category, category),
        "title": row.title or "",
        "description": row.description or "",
        "details": details,
        "status": status,
        "status_label": SUGGESTION_STATUS_LABELS.get(status, status),
        "admin_note": row.admin_note,
        "admin_steam_id": row.admin_steam_id,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _count_recent_for_player(db: Session, steam_id: str) -> int:
    since = (_utcnow() - timedelta(days=1)).replace(tzinfo=None)
    row = db.execute(
        text(
            "SELECT COUNT(*) AS c FROM community_suggestions "
            "WHERE steam_id = :sid AND created_at >= :since"
        ),
        {"sid": steam_id, "since": since},
    ).fetchone()
    return int(row.c if row else 0)


def create_suggestion(
    db: Session,
    *,
    steam_id: str,
    category: str,
    title: str,
    description: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    title_s = (title or "").strip()[:_MAX_TITLE]
    desc_s = (description or "").strip()[:_MAX_DESCRIPTION]
    if not title_s:
        return {"ok": False, "error": "Título obrigatório"}
    if not desc_s:
        return {"ok": False, "error": "Descrição obrigatória"}

    recent = _count_recent_for_player(db, steam_id)
    if recent >= _DAILY_LIMIT:
        return {
            "ok": False,
            "error": f"Limite de {_DAILY_LIMIT} sugestões por dia atingido. Tente amanhã.",
        }

    cat = _normalize_category(category)
    det = _parse_details(details or {})
    now = _utcnow().replace(tzinfo=None)
    url = str(getattr(db, "bind", None).url if getattr(db, "bind", None) else "").lower()

    params = {
        "sid": steam_id,
        "cat": cat,
        "title": title_s,
        "desc": desc_s,
        "details": _details_to_json(det),
        "now": now,
    }

    if "sqlite" in url:
        cur = db.execute(
            text(
                "INSERT INTO community_suggestions "
                "(steam_id, category, title, description, details_json, status, created_at, updated_at) "
                "VALUES (:sid, :cat, :title, :desc, :details, 'pending', :now, :now)"
            ),
            params,
        )
        sugg_id = int(cur.lastrowid)
    else:
        cur = db.execute(
            text(
                "INSERT INTO community_suggestions "
                "(steam_id, category, title, description, details_json, status, created_at, updated_at) "
                "VALUES (:sid, :cat, :title, :desc, :details, 'pending', :now, :now)"
            ),
            params,
        )
        sugg_id = int(cur.lastrowid)

    db.commit()
    row = db.execute(
        text("SELECT * FROM community_suggestions WHERE id = :id"),
        {"id": sugg_id},
    ).fetchone()
    return {"ok": True, "suggestion": _row_to_dict(row)}


def list_suggestions_for_player(
    db: Session,
    steam_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    total_row = db.execute(
        text("SELECT COUNT(*) AS c FROM community_suggestions WHERE steam_id = :sid"),
        {"sid": steam_id},
    ).fetchone()
    total = int(total_row.c if total_row else 0)
    rows = db.execute(
        text(
            "SELECT * FROM community_suggestions WHERE steam_id = :sid "
            "ORDER BY created_at DESC LIMIT :lim OFFSET :off"
        ),
        {"sid": steam_id, "lim": min(100, max(1, limit)), "off": max(0, offset)},
    ).fetchall()
    return [_row_to_dict(r) for r in rows], total


def list_suggestions_admin(
    db: Session,
    *,
    status: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    clauses = ["1=1"]
    params: dict[str, Any] = {
        "lim": min(100, max(1, limit)),
        "off": max(0, offset),
    }
    norm_status = _normalize_status(status)
    if norm_status:
        clauses.append("status = :status")
        params["status"] = norm_status
    search = (q or "").strip()
    if search:
        clauses.append(
            "(title LIKE :q OR description LIKE :q OR steam_id LIKE :q "
            "OR details_json LIKE :q)"
        )
        params["q"] = f"%{search}%"

    where = " AND ".join(clauses)
    total_row = db.execute(
        text(f"SELECT COUNT(*) AS c FROM community_suggestions WHERE {where}"),
        params,
    ).fetchone()
    total = int(total_row.c if total_row else 0)
    rows = db.execute(
        text(
            f"SELECT * FROM community_suggestions WHERE {where} "
            "ORDER BY created_at DESC LIMIT :lim OFFSET :off"
        ),
        params,
    ).fetchall()
    return [_row_to_dict(r) for r in rows], total


def update_suggestion_admin(
    db: Session,
    suggestion_id: int,
    *,
    status: str | None = None,
    admin_note: str | None = None,
    admin_steam_id: str | None = None,
) -> dict[str, Any]:
    row = db.execute(
        text("SELECT * FROM community_suggestions WHERE id = :id"),
        {"id": suggestion_id},
    ).fetchone()
    if not row:
        return {"ok": False, "error": "Sugestão não encontrada"}

    sets: list[str] = []
    params: dict[str, Any] = {"id": suggestion_id, "now": _utcnow().replace(tzinfo=None)}

    if status is not None:
        norm = _normalize_status(status)
        if not norm:
            return {"ok": False, "error": "Status inválido"}
        sets.append("status = :status")
        params["status"] = norm

    if admin_note is not None:
        note = str(admin_note).strip()[:_MAX_ADMIN_NOTE] or None
        sets.append("admin_note = :note")
        params["note"] = note

    if admin_steam_id:
        sets.append("admin_steam_id = :admin_sid")
        params["admin_sid"] = admin_steam_id

    if not sets:
        return {"ok": True, "suggestion": _row_to_dict(row)}

    sets.append("updated_at = :now")
    db.execute(
        text(f"UPDATE community_suggestions SET {', '.join(sets)} WHERE id = :id"),
        params,
    )
    db.commit()
    updated = db.execute(
        text("SELECT * FROM community_suggestions WHERE id = :id"),
        {"id": suggestion_id},
    ).fetchone()
    return {"ok": True, "suggestion": _row_to_dict(updated)}


def public_suggestion_stats(db: Session) -> dict[str, Any]:
    rows = db.execute(
        text(
            "SELECT status, COUNT(*) AS c FROM community_suggestions GROUP BY status"
        ),
    ).fetchall()
    by_status = {str(r.status): int(r.c) for r in rows}
    cat_rows = db.execute(
        text(
            "SELECT category, COUNT(*) AS c FROM community_suggestions GROUP BY category"
        ),
    ).fetchall()
    by_category = {str(r.category): int(r.c) for r in cat_rows}
    total = sum(by_status.values())
    implemented = by_status.get("implementada", 0)
    approved = by_status.get("aprovada", 0)
    return {
        "total": total,
        "by_status": by_status,
        "by_category": by_category,
        "implemented": implemented,
        "approved": approved,
    }
