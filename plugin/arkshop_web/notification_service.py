"""Notificações in-app para jogadores (tickets, pedidos, etc.)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

_MAX_TITLE = 200
_MAX_BODY = 2000
_MAX_TYPE = 64
_MAX_LINK_TYPE = 32
_MAX_LINK_ID = 64
_NOTIFICATION_TYPES = frozenset({
    "ticket_reply",
    "ticket_status",
    "ticket_attended",
    "ticket_closed",
    "ticket_priority",
    "ticket_created",
    "order_update",
    "poll_reward",
    "market_sale",
    "market_buyer_claimed",
    "market_admin_flag",
    "market_admin_remove",
    "market_staff_alert",
    "market_staff_critical",
    "general",
})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_notification_schema(engine: Engine) -> None:
    """Cria tabela user_notifications (idempotente — MySQL e SQLite)."""
    is_sqlite = "sqlite" in str(engine.url).lower()
    if is_sqlite:
        ddl = """
        CREATE TABLE IF NOT EXISTS user_notifications (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          steam_id VARCHAR(32) NOT NULL,
          type VARCHAR(64) NOT NULL DEFAULT 'general',
          title VARCHAR(200) NOT NULL,
          body TEXT NOT NULL DEFAULT '',
          is_read INTEGER NOT NULL DEFAULT 0,
          link_type VARCHAR(32) NULL,
          link_id VARCHAR(64) NULL,
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
        idx = [
            "CREATE INDEX IF NOT EXISTS idx_notif_steam ON user_notifications (steam_id)",
            "CREATE INDEX IF NOT EXISTS idx_notif_read ON user_notifications (steam_id, is_read)",
            "CREATE INDEX IF NOT EXISTS idx_notif_created ON user_notifications (created_at)",
        ]
    else:
        ddl = """
        CREATE TABLE IF NOT EXISTS user_notifications (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          steam_id VARCHAR(32) NOT NULL,
          type VARCHAR(64) NOT NULL DEFAULT 'general',
          title VARCHAR(200) NOT NULL,
          body TEXT NOT NULL,
          is_read TINYINT(1) NOT NULL DEFAULT 0,
          link_type VARCHAR(32) NULL,
          link_id VARCHAR(64) NULL,
          created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
          KEY idx_notif_steam (steam_id),
          KEY idx_notif_read (steam_id, is_read),
          KEY idx_notif_created (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        idx = []
    with engine.connect() as conn:
        conn.execute(text(ddl))
        for stmt in idx:
            conn.execute(text(stmt))
        conn.commit()


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": int(row.id),
        "steam_id": row.steam_id,
        "type": row.type,
        "title": row.title,
        "body": row.body or "",
        "read": bool(row.is_read),
        "link_type": row.link_type,
        "link_id": row.link_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def create_notification(
    db: Any,
    *,
    steam_id: str,
    type: str = "general",
    title: str,
    body: str = "",
    link_type: str | None = None,
    link_id: str | None = None,
) -> dict[str, Any]:
    from app import UserNotification

    ntype = (type or "general").strip()[:_MAX_TYPE]
    if ntype not in _NOTIFICATION_TYPES:
        ntype = "general"
    row = UserNotification(
        steam_id=steam_id,
        type=ntype,
        title=(title or "")[:_MAX_TITLE],
        body=(body or "")[:_MAX_BODY],
        is_read=False,
        link_type=(link_type[:_MAX_LINK_TYPE] if link_type else None),
        link_id=(str(link_id)[:_MAX_LINK_ID] if link_id else None),
        created_at=_utcnow(),
    )
    db.add(row)
    db.flush()
    return _row_to_dict(row)


def list_notifications(
    db: Any,
    steam_id: str,
    *,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    from app import UserNotification

    q = db.query(UserNotification).filter(UserNotification.steam_id == steam_id)
    if unread_only:
        q = q.filter(UserNotification.is_read.is_(False))
    total = q.count()
    rows = (
        q.order_by(UserNotification.created_at.desc())
        .offset(max(0, offset))
        .limit(min(100, max(1, limit)))
        .all()
    )
    return [_row_to_dict(r) for r in rows], total


def unread_count(db: Any, steam_id: str) -> int:
    from app import UserNotification

    return (
        db.query(UserNotification)
        .filter(
            UserNotification.steam_id == steam_id,
            UserNotification.is_read.is_(False),
        )
        .count()
    )


def mark_read(db: Any, notification_id: int, *, steam_id: str) -> dict[str, Any]:
    from app import UserNotification

    row = db.get(UserNotification, notification_id)
    if not row or row.steam_id != steam_id:
        return {"ok": False, "error": "Notificação não encontrada"}
    row.is_read = True
    db.commit()
    return {"ok": True, "notification": _row_to_dict(row)}


def mark_all_read(db: Any, *, steam_id: str) -> dict[str, Any]:
    from app import UserNotification

    updated = (
        db.query(UserNotification)
        .filter(
            UserNotification.steam_id == steam_id,
            UserNotification.is_read.is_(False),
        )
        .update({UserNotification.is_read: True}, synchronize_session=False)
    )
    db.commit()
    return {"ok": True, "updated": int(updated or 0)}
