"""Sistema de tickets — persistência e regras de negócio (MVP 1.9.149)."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine

_TICKET_STATUSES = frozenset({"OPEN", "IN_PROGRESS", "CLOSED"})
_AUTHOR_TYPES = frozenset({"player", "admin", "system"})
_MAX_SUBJECT = 200
_MAX_BODY = 8000
_MAX_LINKS = 10
_MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
_ALLOWED_MIME_PREFIXES = ("image/",)
_ALLOWED_MIME_EXACT = frozenset({"application/pdf"})
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_ticket_schema(engine: Engine) -> None:
    """Cria tabelas de tickets (idempotente — MySQL e SQLite)."""
    is_sqlite = "sqlite" in str(engine.url).lower()
    if is_sqlite:
        stmts = [
            """
            CREATE TABLE IF NOT EXISTS support_tickets (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              steam_id VARCHAR(32) NOT NULL,
              player_name VARCHAR(128) NOT NULL DEFAULT '',
              discord_user_id VARCHAR(32) NULL,
              discord_username VARCHAR(128) NULL,
              subject VARCHAR(200) NOT NULL,
              category VARCHAR(64) NOT NULL DEFAULT 'geral',
              status VARCHAR(32) NOT NULL DEFAULT 'OPEN',
              assigned_admin_steam_id VARCHAR(32) NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              closed_at DATETIME NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS support_ticket_messages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ticket_id INTEGER NOT NULL,
              author_type VARCHAR(16) NOT NULL DEFAULT 'player',
              author_steam_id VARCHAR(32) NULL,
              author_name VARCHAR(128) NOT NULL DEFAULT '',
              body TEXT NOT NULL,
              links_json TEXT NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS support_ticket_attachments (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ticket_id INTEGER NOT NULL,
              message_id INTEGER NULL,
              filename VARCHAR(255) NOT NULL,
              original_filename VARCHAR(255) NOT NULL,
              mime_type VARCHAR(128) NOT NULL DEFAULT 'application/octet-stream',
              size_bytes INTEGER NOT NULL DEFAULT 0,
              storage_path VARCHAR(512) NOT NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS support_ticket_discord_links (
              steam_id VARCHAR(32) PRIMARY KEY NOT NULL,
              discord_user_id VARCHAR(32) NULL,
              discord_username VARCHAR(128) NULL,
              link_method VARCHAR(16) NOT NULL DEFAULT 'manual',
              linked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
        ]
    else:
        stmts = [
            """
            CREATE TABLE IF NOT EXISTS support_tickets (
              id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
              steam_id VARCHAR(32) NOT NULL,
              player_name VARCHAR(128) NOT NULL DEFAULT '',
              discord_user_id VARCHAR(32) NULL,
              discord_username VARCHAR(128) NULL,
              subject VARCHAR(200) NOT NULL,
              category VARCHAR(64) NOT NULL DEFAULT 'geral',
              status VARCHAR(32) NOT NULL DEFAULT 'OPEN',
              assigned_admin_steam_id VARCHAR(32) NULL,
              created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
              updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                ON UPDATE CURRENT_TIMESTAMP(3),
              closed_at DATETIME(3) NULL,
              KEY idx_ticket_steam (steam_id),
              KEY idx_ticket_status (status),
              KEY idx_ticket_updated (updated_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS support_ticket_messages (
              id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
              ticket_id BIGINT UNSIGNED NOT NULL,
              author_type VARCHAR(16) NOT NULL DEFAULT 'player',
              author_steam_id VARCHAR(32) NULL,
              author_name VARCHAR(128) NOT NULL DEFAULT '',
              body TEXT NOT NULL,
              links_json TEXT NULL,
              created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
              KEY idx_msg_ticket (ticket_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS support_ticket_attachments (
              id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
              ticket_id BIGINT UNSIGNED NOT NULL,
              message_id BIGINT UNSIGNED NULL,
              filename VARCHAR(255) NOT NULL,
              original_filename VARCHAR(255) NOT NULL,
              mime_type VARCHAR(128) NOT NULL DEFAULT 'application/octet-stream',
              size_bytes INT UNSIGNED NOT NULL DEFAULT 0,
              storage_path VARCHAR(512) NOT NULL,
              created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
              KEY idx_att_ticket (ticket_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS support_ticket_discord_links (
              steam_id VARCHAR(32) PRIMARY KEY NOT NULL,
              discord_user_id VARCHAR(32) NULL,
              discord_username VARCHAR(128) NULL,
              link_method VARCHAR(16) NOT NULL DEFAULT 'manual',
              linked_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
              updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                ON UPDATE CURRENT_TIMESTAMP(3)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        ]
    with engine.connect() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))
        conn.commit()


def _parse_links(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, str):
        items = _URL_RE.findall(raw)
    else:
        return []
    out: list[str] = []
    for item in items:
        url = str(item).strip()
        if url and url not in out:
            out.append(url[:512])
        if len(out) >= _MAX_LINKS:
            break
    return out


def _ticket_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": int(row.id),
        "steam_id": row.steam_id,
        "player_name": row.player_name or "",
        "discord_user_id": row.discord_user_id,
        "discord_username": row.discord_username,
        "subject": row.subject,
        "category": row.category or "geral",
        "status": row.status,
        "assigned_admin_steam_id": row.assigned_admin_steam_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
    }


def _message_row_to_dict(row: Any, attachments: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    links: list[str] = []
    if row.links_json:
        try:
            parsed = json.loads(row.links_json)
            if isinstance(parsed, list):
                links = [str(x) for x in parsed]
        except (TypeError, json.JSONDecodeError):
            links = []
    return {
        "id": int(row.id),
        "ticket_id": int(row.ticket_id),
        "author_type": row.author_type,
        "author_steam_id": row.author_steam_id,
        "author_name": row.author_name or "",
        "body": row.body or "",
        "links": links,
        "attachments": attachments or [],
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _attachment_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": int(row.id),
        "ticket_id": int(row.ticket_id),
        "message_id": int(row.message_id) if row.message_id else None,
        "filename": row.filename,
        "original_filename": row.original_filename,
        "mime_type": row.mime_type,
        "size_bytes": int(row.size_bytes or 0),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def get_discord_link(db: Any, steam_id: str) -> dict[str, Any] | None:
    from app import SupportTicketDiscordLink

    row = db.get(SupportTicketDiscordLink, steam_id)
    if not row:
        return None
    return {
        "steam_id": row.steam_id,
        "discord_user_id": row.discord_user_id,
        "discord_username": row.discord_username,
        "link_method": row.link_method,
        "linked_at": row.linked_at.isoformat() if row.linked_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def save_discord_link(
    db: Any,
    *,
    steam_id: str,
    discord_user_id: str | None = None,
    discord_username: str | None = None,
    link_method: str = "manual",
) -> dict[str, Any]:
    from app import SupportTicketDiscordLink

    now = _utcnow()
    row = db.get(SupportTicketDiscordLink, steam_id)
    if row is None:
        row = SupportTicketDiscordLink(
            steam_id=steam_id,
            discord_user_id=(discord_user_id or None),
            discord_username=(discord_username or None),
            link_method=link_method or "manual",
            linked_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        if discord_user_id is not None:
            row.discord_user_id = discord_user_id or None
        if discord_username is not None:
            row.discord_username = discord_username or None
        row.link_method = link_method or row.link_method or "manual"
        row.updated_at = now
    db.commit()
    db.refresh(row)
    return get_discord_link(db, steam_id) or {}


def create_ticket(
    db: Any,
    *,
    steam_id: str,
    player_name: str,
    subject: str,
    body: str,
    category: str = "geral",
    links: list[str] | None = None,
    discord_user_id: str | None = None,
    discord_username: str | None = None,
) -> dict[str, Any]:
    from app import SupportTicket, SupportTicketMessage

    subj = (subject or "").strip()[:_MAX_SUBJECT]
    text_body = (body or "").strip()
    if not subj:
        return {"ok": False, "error": "Assunto obrigatório"}
    if not text_body:
        return {"ok": False, "error": "Mensagem obrigatória"}

    link_list = _parse_links(links or [])
    now = _utcnow()
    ticket = SupportTicket(
        steam_id=steam_id,
        player_name=(player_name or steam_id)[:128],
        discord_user_id=discord_user_id,
        discord_username=discord_username,
        subject=subj,
        category=(category or "geral").strip()[:64] or "geral",
        status="OPEN",
        created_at=now,
        updated_at=now,
    )
    db.add(ticket)
    db.flush()

    msg = SupportTicketMessage(
        ticket_id=ticket.id,
        author_type="player",
        author_steam_id=steam_id,
        author_name=(player_name or steam_id)[:128],
        body=text_body[:_MAX_BODY],
        links_json=json.dumps(link_list) if link_list else None,
        created_at=now,
    )
    db.add(msg)
    db.commit()
    db.refresh(ticket)
    return {
        "ok": True,
        "ticket": _ticket_row_to_dict(ticket),
        "message_id": int(msg.id),
    }


def list_tickets_for_player(
    db: Any,
    steam_id: str,
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    from app import SupportTicket

    q = db.query(SupportTicket).filter(SupportTicket.steam_id == steam_id)
    if status == "open":
        q = q.filter(SupportTicket.status.in_(("OPEN", "IN_PROGRESS")))
    elif status == "closed":
        q = q.filter(SupportTicket.status == "CLOSED")
    total = q.count()
    rows = (
        q.order_by(SupportTicket.updated_at.desc())
        .offset(max(0, offset))
        .limit(min(100, max(1, limit)))
        .all()
    )
    return [_ticket_row_to_dict(r) for r in rows], total


def list_tickets_admin(
    db: Any,
    *,
    status: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    from app import SupportTicket
    from sqlalchemy import or_

    query = db.query(SupportTicket)
    if status and status in _TICKET_STATUSES:
        query = query.filter(SupportTicket.status == status)
    elif status == "open":
        query = query.filter(SupportTicket.status.in_(("OPEN", "IN_PROGRESS")))
    search = (q or "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                SupportTicket.subject.like(like),
                SupportTicket.player_name.like(like),
                SupportTicket.steam_id.like(like),
                SupportTicket.discord_username.like(like),
            )
        )
    total = query.count()
    rows = (
        query.order_by(SupportTicket.updated_at.desc())
        .offset(max(0, offset))
        .limit(min(100, max(1, limit)))
        .all()
    )
    return [_ticket_row_to_dict(r) for r in rows], total


def _load_attachments_for_messages(db: Any, message_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    from app import SupportTicketAttachment

    if not message_ids:
        return {}
    rows = (
        db.query(SupportTicketAttachment)
        .filter(SupportTicketAttachment.message_id.in_(message_ids))
        .all()
    )
    out: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        mid = int(row.message_id) if row.message_id else 0
        out.setdefault(mid, []).append(_attachment_row_to_dict(row))
    return out


def get_ticket_detail(
    db: Any,
    ticket_id: int,
    *,
    viewer_steam_id: str | None = None,
    is_admin: bool = False,
) -> dict[str, Any] | None:
    from app import SupportTicket, SupportTicketAttachment, SupportTicketMessage

    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        return None
    if not is_admin and viewer_steam_id and ticket.steam_id != viewer_steam_id:
        return None

    messages = (
        db.query(SupportTicketMessage)
        .filter(SupportTicketMessage.ticket_id == ticket_id)
        .order_by(SupportTicketMessage.created_at.asc())
        .all()
    )
    msg_ids = [int(m.id) for m in messages]
    att_by_msg = _load_attachments_for_messages(db, msg_ids)
    orphan_atts = (
        db.query(SupportTicketAttachment)
        .filter(
            SupportTicketAttachment.ticket_id == ticket_id,
            SupportTicketAttachment.message_id.is_(None),
        )
        .all()
    )
    ticket_atts = [_attachment_row_to_dict(a) for a in orphan_atts]

    return {
        "ticket": _ticket_row_to_dict(ticket),
        "messages": [
            _message_row_to_dict(m, att_by_msg.get(int(m.id), []))
            for m in messages
        ],
        "orphan_attachments": ticket_atts,
    }


def add_ticket_reply(
    db: Any,
    ticket_id: int,
    *,
    author_type: str,
    author_steam_id: str | None,
    author_name: str,
    body: str,
    links: list[str] | None = None,
    viewer_steam_id: str | None = None,
    is_admin: bool = False,
) -> dict[str, Any]:
    from app import SupportTicket, SupportTicketMessage

    if author_type not in _AUTHOR_TYPES:
        return {"ok": False, "error": "Tipo de autor inválido"}
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        return {"ok": False, "error": "Ticket não encontrado"}
    if ticket.status == "CLOSED":
        return {"ok": False, "error": "Ticket encerrado"}
    if not is_admin and ticket.steam_id != viewer_steam_id:
        return {"ok": False, "error": "Acesso negado"}

    text_body = (body or "").strip()
    if not text_body:
        return {"ok": False, "error": "Mensagem vazia"}

    now = _utcnow()
    link_list = _parse_links(links or [])
    msg = SupportTicketMessage(
        ticket_id=ticket_id,
        author_type=author_type,
        author_steam_id=author_steam_id,
        author_name=(author_name or "")[:128],
        body=text_body[:_MAX_BODY],
        links_json=json.dumps(link_list) if link_list else None,
        created_at=now,
    )
    db.add(msg)
    ticket.updated_at = now
    if is_admin and author_type == "admin":
        if ticket.status == "OPEN":
            ticket.status = "IN_PROGRESS"
        if author_steam_id and not ticket.assigned_admin_steam_id:
            ticket.assigned_admin_steam_id = author_steam_id
    db.commit()
    db.refresh(msg)
    return {"ok": True, "message": _message_row_to_dict(msg)}


def update_ticket_status(
    db: Any,
    ticket_id: int,
    *,
    status: str,
    admin_steam_id: str | None = None,
) -> dict[str, Any]:
    from app import SupportTicket

    if status not in _TICKET_STATUSES:
        return {"ok": False, "error": "Status inválido"}
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        return {"ok": False, "error": "Ticket não encontrado"}

    now = _utcnow()
    ticket.status = status
    ticket.updated_at = now
    if status == "CLOSED":
        ticket.closed_at = now
    else:
        ticket.closed_at = None
    if admin_steam_id and status in ("IN_PROGRESS", "OPEN"):
        ticket.assigned_admin_steam_id = admin_steam_id
    db.commit()
    db.refresh(ticket)
    return {"ok": True, "ticket": _ticket_row_to_dict(ticket)}


def _mime_allowed(mime: str) -> bool:
    m = (mime or "").strip().lower()
    if m in _ALLOWED_MIME_EXACT:
        return True
    return any(m.startswith(p) for p in _ALLOWED_MIME_PREFIXES)


def save_ticket_attachment(
    db: Any,
    *,
    ticket_id: int,
    message_id: int | None,
    file_storage: Any,
    uploads_dir: Path,
    viewer_steam_id: str,
    is_admin: bool = False,
) -> dict[str, Any]:
    from app import SupportTicket, SupportTicketAttachment

    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        return {"ok": False, "error": "Ticket não encontrado"}
    if not is_admin and ticket.steam_id != viewer_steam_id:
        return {"ok": False, "error": "Acesso negado"}
    if ticket.status == "CLOSED":
        return {"ok": False, "error": "Ticket encerrado"}

    if not file_storage or not getattr(file_storage, "filename", None):
        return {"ok": False, "error": "Arquivo ausente"}

    mime = (getattr(file_storage, "mimetype", None) or "application/octet-stream").strip()
    if not _mime_allowed(mime):
        return {"ok": False, "error": "Tipo de arquivo não permitido (imagens ou PDF)"}

    data = file_storage.read()
    size = len(data)
    if size <= 0:
        return {"ok": False, "error": "Arquivo vazio"}
    if size > _MAX_ATTACHMENT_BYTES:
        return {"ok": False, "error": "Arquivo excede 5 MB"}

    original = Path(file_storage.filename).name[:255]
    ext = Path(original).suffix.lower()[:16]
    stored_name = f"{uuid.uuid4().hex}{ext}"
    dest_dir = uploads_dir / str(ticket_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / stored_name
    dest_path.write_bytes(data)
    rel_path = f"{ticket_id}/{stored_name}"

    now = _utcnow()
    row = SupportTicketAttachment(
        ticket_id=ticket_id,
        message_id=message_id,
        filename=stored_name,
        original_filename=original,
        mime_type=mime[:128],
        size_bytes=size,
        storage_path=rel_path,
        created_at=now,
    )
    db.add(row)
    ticket.updated_at = now
    db.commit()
    db.refresh(row)
    return {"ok": True, "attachment": _attachment_row_to_dict(row)}


def get_attachment_for_download(
    db: Any,
    attachment_id: int,
    *,
    viewer_steam_id: str | None,
    is_admin: bool,
    uploads_dir: Path,
) -> dict[str, Any] | None:
    from app import SupportTicket, SupportTicketAttachment

    row = db.get(SupportTicketAttachment, attachment_id)
    if not row:
        return None
    ticket = db.get(SupportTicket, row.ticket_id)
    if not ticket:
        return None
    if not is_admin and ticket.steam_id != viewer_steam_id:
        return None
    full = uploads_dir / row.storage_path
    if not full.is_file():
        return None
    return {
        "path": full,
        "mime_type": row.mime_type,
        "original_filename": row.original_filename,
    }


def resolve_player_name(
    db: Any,
    steam_id: str,
    *,
    resolve_display_name: Callable[[str], str] | None = None,
) -> str:
    if resolve_display_name:
        return resolve_display_name(steam_id)
    from app import StoreUser

    row = db.get(StoreUser, steam_id)
    if row and (row.display_name or "").strip():
        return str(row.display_name).strip()[:128]
    return steam_id
