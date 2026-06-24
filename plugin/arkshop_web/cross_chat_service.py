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


def list_messages(
    db: Any,
    *,
    limit: int = 50,
    offset: int = 0,
    steam_id: str = "",
    source_server: str = "",
    q: str = "",
) -> tuple[list[dict[str, Any]], int]:
    """Lista mensagens do chat cluster para painel admin."""
    limit = max(1, min(200, int(limit)))
    offset = max(0, int(offset))
    steam_id = re.sub(r"\D", "", steam_id or "")[:20]
    source_server = _sanitize_ascii(source_server, max_len=_MAX_SERVER)
    q = _sanitize_ascii(q, max_len=120)

    where: list[str] = []
    params: dict[str, Any] = {"lim": limit, "off": offset}
    if steam_id:
        where.append("steam_id = :steam_id")
        params["steam_id"] = steam_id
    if source_server:
        where.append("source_server = :source_server")
        params["source_server"] = source_server
    if q:
        where.append(
            "(player_name LIKE :q OR message LIKE :q OR steam_id LIKE :q "
            "OR source_server LIKE :q)"
        )
        params["q"] = f"%{q}%"

    clause = (" WHERE " + " AND ".join(where)) if where else ""
    count_row = db.execute(
        text(f"SELECT COUNT(*) FROM cross_server_chat{clause}"),
        {k: v for k, v in params.items() if k not in ("lim", "off")},
    ).fetchone()
    total = int(count_row[0]) if count_row and count_row[0] is not None else 0

    rows = db.execute(
        text(
            f"SELECT id, channel, source_server, steam_id, player_name, message, created_at "
            f"FROM cross_server_chat{clause} "
            f"ORDER BY id DESC LIMIT :lim OFFSET :off"
        ),
        params,
    ).fetchall()

    items = [
        {
            "id": int(r[0]),
            "channel": str(r[1]),
            "source_server": str(r[2]),
            "steam_id": str(r[3]),
            "player_name": str(r[4]),
            "message": str(r[5]),
            "created_at": str(r[6]) if r[6] is not None else "",
        }
        for r in rows
    ]
    return items, total


def chat_stats(db: Any) -> dict[str, Any]:
    """Contadores rápidos para o painel admin."""
    cutoff = _utcnow() - timedelta(hours=24)
    row = db.execute(
        text(
            "SELECT "
            "COUNT(*), "
            "COUNT(DISTINCT steam_id), "
            "COUNT(DISTINCT source_server) "
            "FROM cross_server_chat "
            "WHERE created_at >= :cutoff"
        ),
        {"cutoff": cutoff},
    ).fetchone()
    total_24h = int(row[0]) if row and row[0] is not None else 0
    players_24h = int(row[1]) if row and row[1] is not None else 0
    servers_24h = int(row[2]) if row and row[2] is not None else 0

    mute_row = db.execute(
        text(
            "SELECT COUNT(*) FROM cross_server_chat_mutes "
            "WHERE muted_until IS NULL OR muted_until > :now"
        ),
        {"now": _utcnow()},
    ).fetchone()
    mutes = int(mute_row[0]) if mute_row and mute_row[0] is not None else 0

    servers = db.execute(
        text(
            "SELECT DISTINCT source_server FROM cross_server_chat "
            "ORDER BY source_server ASC LIMIT 64"
        )
    ).fetchall()

    return {
        "messages_24h": total_24h,
        "players_24h": players_24h,
        "servers_24h": servers_24h,
        "active_mutes": mutes,
        "servers": [str(r[0]) for r in servers if r[0]],
    }


def list_mutes(db: Any) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            "SELECT steam_id, muted_until, reason "
            "FROM cross_server_chat_mutes "
            "WHERE muted_until IS NULL OR muted_until > :now "
            "ORDER BY steam_id ASC"
        ),
        {"now": _utcnow()},
    ).fetchall()
    return [
        {
            "steam_id": str(r[0]),
            "muted_until": str(r[1]) if r[1] is not None else None,
            "reason": str(r[2] or ""),
        }
        for r in rows
    ]


def mute_player(
    db: Any,
    *,
    steam_id: str,
    hours: int | None = None,
    reason: str = "",
) -> dict[str, Any]:
    steam_id = re.sub(r"\D", "", steam_id or "")[:20]
    if len(steam_id) < 15:
        return {"ok": False, "error": "steam_id invalido"}
    reason = _sanitize_ascii(reason, max_len=255)
    muted_until = None
    if hours is not None and int(hours) > 0:
        muted_until = _utcnow() + timedelta(hours=int(hours))
    bind = db.get_bind()
    is_sqlite = bind is not None and "sqlite" in str(bind.url).lower()
    if is_sqlite:
        db.execute(
            text("DELETE FROM cross_server_chat_mutes WHERE steam_id = :sid"),
            {"sid": steam_id},
        )
        db.execute(
            text(
                "INSERT INTO cross_server_chat_mutes (steam_id, muted_until, reason) "
                "VALUES (:sid, :until, :reason)"
            ),
            {"sid": steam_id, "until": muted_until, "reason": reason or None},
        )
    else:
        db.execute(
            text(
                "INSERT INTO cross_server_chat_mutes (steam_id, muted_until, reason) "
                "VALUES (:sid, :until, :reason) "
                "ON DUPLICATE KEY UPDATE muted_until = VALUES(muted_until), "
                "reason = VALUES(reason)"
            ),
            {"sid": steam_id, "until": muted_until, "reason": reason or None},
        )
    db.commit()
    return {"ok": True, "steam_id": steam_id, "muted_until": str(muted_until) if muted_until else None}


def unmute_player(db: Any, *, steam_id: str) -> dict[str, Any]:
    steam_id = re.sub(r"\D", "", steam_id or "")[:20]
    if len(steam_id) < 15:
        return {"ok": False, "error": "steam_id invalido"}
    result = db.execute(
        text("DELETE FROM cross_server_chat_mutes WHERE steam_id = :sid"),
        {"sid": steam_id},
    )
    db.commit()
    return {"ok": True, "deleted": int(result.rowcount or 0)}
