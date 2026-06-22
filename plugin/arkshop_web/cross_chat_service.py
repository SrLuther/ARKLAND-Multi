"""Chat cluster entre mapas ARK — persistência MySQL."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

_ASCII_RE = re.compile(r"[\x20-\x7e]+")
_MAX_MESSAGE = 500
_MAX_NAME = 64
_MAX_SERVER = 64


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _sanitize_ascii(value: str, *, max_len: int) -> str:
    parts = _ASCII_RE.findall(value or "")
    out = " ".join("".join(parts).split())
    return out[:max_len]


def ensure_cross_chat_schema(engine: Engine) -> None:
    """Cria tabelas do chat cluster (idempotente)."""
    stmts = [
        """
        CREATE TABLE IF NOT EXISTS cross_server_chat (
          id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          channel       VARCHAR(16)  NOT NULL DEFAULT 'cluster',
          source_server VARCHAR(64)  NOT NULL,
          steam_id      VARCHAR(20)  NOT NULL,
          player_name   VARCHAR(64)  NOT NULL,
          message       VARCHAR(500) NOT NULL,
          created_at    DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
          KEY idx_poll (id),
          KEY idx_created (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS cross_server_chat_cursor (
          server_id  VARCHAR(64) PRIMARY KEY NOT NULL,
          last_id    BIGINT UNSIGNED NOT NULL DEFAULT 0,
          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS cross_server_chat_mutes (
          steam_id    VARCHAR(20) PRIMARY KEY NOT NULL,
          muted_until DATETIME DEFAULT NULL,
          reason      VARCHAR(255) DEFAULT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
    ]
    with engine.connect() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))
        conn.commit()


def is_muted(db: Any, steam_id: str) -> bool:
    row = db.execute(
        text(
            "SELECT 1 FROM cross_server_chat_mutes "
            "WHERE steam_id = :sid "
            "AND (muted_until IS NULL OR muted_until > :now) "
            "LIMIT 1"
        ),
        {"sid": steam_id, "now": _utcnow()},
    ).fetchone()
    return row is not None


def publish_message(
    db: Any,
    *,
    source_server: str,
    steam_id: str,
    player_name: str,
    message: str,
    channel: str = "cluster",
) -> dict[str, Any]:
    source_server = _sanitize_ascii(source_server, max_len=_MAX_SERVER)
    steam_id = re.sub(r"\D", "", steam_id or "")[:20]
    player_name = _sanitize_ascii(player_name, max_len=_MAX_NAME)
    message = _sanitize_ascii(message, max_len=_MAX_MESSAGE)
    channel = _sanitize_ascii(channel, max_len=16) or "cluster"

    if not source_server:
        return {"ok": False, "error": "source_server obrigatorio"}
    if len(steam_id) < 15:
        return {"ok": False, "error": "steam_id invalido"}
    if not message:
        return {"ok": False, "error": "mensagem vazia"}
    if is_muted(db, steam_id):
        return {"ok": False, "error": "jogador silenciado"}

    db.execute(
        text(
            "INSERT INTO cross_server_chat "
            "(channel, source_server, steam_id, player_name, message) "
            "VALUES (:channel, :source_server, :steam_id, :player_name, :message)"
        ),
        {
            "channel": channel,
            "source_server": source_server,
            "steam_id": steam_id,
            "player_name": player_name or steam_id,
            "message": message,
        },
    )
    db.commit()
    bind = db.get_bind()
    if bind is not None and "sqlite" in str(bind.url).lower():
        row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
    else:
        row = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()
    msg_id = int(row[0]) if row and row[0] else 0
    return {"ok": True, "id": msg_id}


def poll_messages(
    db: Any,
    *,
    server_id: str,
    since_id: int = 0,
    limit: int = 50,
) -> list[dict[str, Any]]:
    server_id = _sanitize_ascii(server_id, max_len=_MAX_SERVER)
    since_id = max(0, int(since_id))
    limit = max(1, min(100, int(limit)))

    rows = db.execute(
        text(
            "SELECT id, source_server, player_name, message "
            "FROM cross_server_chat "
            "WHERE id > :since "
            "ORDER BY id ASC "
            "LIMIT :lim"
        ),
        {"since": since_id, "lim": limit},
    ).fetchall()

    return [
        {
            "id": int(r[0]),
            "source_server": str(r[1]),
            "player_name": str(r[2]),
            "message": str(r[3]),
        }
        for r in rows
        if str(r[1]) != server_id
    ]


def purge_old_messages(db: Any, *, days: int = 7) -> int:
    days = max(1, int(days))
    cutoff = _utcnow() - timedelta(days=days)
    result = db.execute(
        text("DELETE FROM cross_server_chat WHERE created_at < :cutoff"),
        {"cutoff": cutoff},
    )
    db.commit()
    return int(result.rowcount or 0)
