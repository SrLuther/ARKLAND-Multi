"""Mural de avisos da home — mensagem única editável pelo admin."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

_MAX_TITLE = 120
_MAX_BODY = 4000
_SINGLETON_ID = 1


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


def ensure_home_notice_schema(engine: Engine) -> None:
    """Cria tabela do mural (idempotente — MySQL e SQLite)."""
    is_sqlite = "sqlite" in str(engine.url).lower()
    if is_sqlite:
        stmts = [
            """
            CREATE TABLE IF NOT EXISTS home_notice (
              id INTEGER PRIMARY KEY NOT NULL,
              title VARCHAR(120) NOT NULL DEFAULT '',
              body TEXT NOT NULL DEFAULT '',
              updated_by_steam_id VARCHAR(32) NULL,
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
        ]
    else:
        stmts = [
            """
            CREATE TABLE IF NOT EXISTS home_notice (
              id TINYINT UNSIGNED NOT NULL PRIMARY KEY,
              title VARCHAR(120) NOT NULL DEFAULT '',
              body TEXT NOT NULL,
              updated_by_steam_id VARCHAR(32) NULL,
              updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                ON UPDATE CURRENT_TIMESTAMP(3)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        ]
    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))


def _empty_notice() -> dict[str, Any]:
    return {
        "title": "",
        "body": "",
        "updated_at": None,
        "updated_by_steam_id": None,
        "has_content": False,
    }


def _row_to_notice(row: Any) -> dict[str, Any]:
    if row is None:
        return _empty_notice()
    mapping = row._mapping if hasattr(row, "_mapping") else None
    if mapping is not None:
        title = str(mapping.get("title") or "").strip()
        body = str(mapping.get("body") or "").strip()
        updated_at = mapping.get("updated_at")
        updated_by = mapping.get("updated_by_steam_id")
    else:
        title = str(row[1] if len(row) > 1 else "").strip()
        body = str(row[2] if len(row) > 2 else "").strip()
        updated_by = row[3] if len(row) > 3 else None
        updated_at = row[4] if len(row) > 4 else None
    return {
        "title": title,
        "body": body,
        "updated_at": _iso(updated_at),
        "updated_by_steam_id": str(updated_by).strip() if updated_by else None,
        "has_content": bool(title or body),
    }


def get_home_notice(db: Session) -> dict[str, Any]:
    row = db.execute(
        text(
            "SELECT id, title, body, updated_by_steam_id, updated_at "
            "FROM home_notice WHERE id = :id"
        ),
        {"id": _SINGLETON_ID},
    ).fetchone()
    return _row_to_notice(row)


def set_home_notice(
    db: Session,
    *,
    title: str | None,
    body: str | None,
    updated_by_steam_id: str | None = None,
) -> dict[str, Any]:
    clean_title = str(title or "").strip()[:_MAX_TITLE]
    clean_body = str(body or "").strip()[:_MAX_BODY]
    if not clean_title and not clean_body:
        # Permitir limpar o mural
        pass
    now = _utcnow()
    sid = (str(updated_by_steam_id or "").strip() or None)
    existing = db.execute(
        text("SELECT id FROM home_notice WHERE id = :id"),
        {"id": _SINGLETON_ID},
    ).fetchone()
    if existing is None:
        db.execute(
            text(
                "INSERT INTO home_notice (id, title, body, updated_by_steam_id, updated_at) "
                "VALUES (:id, :title, :body, :sid, :updated_at)"
            ),
            {
                "id": _SINGLETON_ID,
                "title": clean_title,
                "body": clean_body,
                "sid": sid,
                "updated_at": now,
            },
        )
    else:
        db.execute(
            text(
                "UPDATE home_notice SET title = :title, body = :body, "
                "updated_by_steam_id = :sid, updated_at = :updated_at WHERE id = :id"
            ),
            {
                "id": _SINGLETON_ID,
                "title": clean_title,
                "body": clean_body,
                "sid": sid,
                "updated_at": now,
            },
        )
    db.commit()
    return get_home_notice(db)
