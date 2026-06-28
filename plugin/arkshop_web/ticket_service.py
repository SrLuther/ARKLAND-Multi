"""Sistema de tickets — persistência e regras de negócio (1.9.153)."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine

# Status internos (persistidos no banco)
TICKET_STATUSES = frozenset({"ABERTO", "EM_ANALISE", "AGUARDANDO_JOGADOR", "ENCERRADO"})
TICKET_STATUS_LABELS: dict[str, str] = {
    "ABERTO": "Aberto",
    "EM_ANALISE": "Em análise",
    "AGUARDANDO_JOGADOR": "Aguardando jogador",
    "ENCERRADO": "Encerrado",
}
# Legado (aceito em filtros / migração)
_LEGACY_STATUS_MAP = {
    "OPEN": "ABERTO",
    "IN_PROGRESS": "EM_ANALISE",
    "CLOSED": "ENCERRADO",
}
_OPEN_STATUSES = frozenset({"ABERTO", "EM_ANALISE", "AGUARDANDO_JOGADOR", "OPEN", "IN_PROGRESS"})
_CLOSED_STATUSES = frozenset({"ENCERRADO", "CLOSED"})
_PLAYER_REPLY_STATUSES = frozenset({"ABERTO", "EM_ANALISE", "AGUARDANDO_JOGADOR"})
_TAB_OPEN_ALIASES = frozenset({"open", "abertos", "aberto", "ativos", "active"})
_TAB_CLOSED_ALIASES = frozenset({"closed", "encerrados", "encerrado", "fechados"})

TICKET_CATEGORIES = frozenset({
    "suporte", "bug", "doacao", "recurso_ban", "resgate", "pagamento", "mercado", "conta", "geral", "outro",
})
TICKET_CATEGORY_LABELS: dict[str, str] = {
    "suporte": "Suporte",
    "bug": "Bug / erro",
    "doacao": "Doação",
    "recurso_ban": "Recurso de banimento",
    "resgate": "Resgate / entrega",
    "pagamento": "Pagamento / doação",
    "mercado": "Mercado de dinos",
    "conta": "Conta / acesso",
    "geral": "Geral",
    "outro": "Outro",
}

TICKET_PRIORITIES = frozenset({"baixa", "normal", "urgente"})
TICKET_PRIORITY_LABELS: dict[str, str] = {
    "baixa": "Baixa",
    "normal": "Normal",
    "urgente": "Urgente",
}

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


def ticket_meta() -> dict[str, Any]:
    """Metadados para UI (categorias, prioridades, status)."""
    return {
        "categories": [
            {"id": k, "label": TICKET_CATEGORY_LABELS[k]}
            for k in sorted(TICKET_CATEGORIES, key=lambda x: TICKET_CATEGORY_LABELS.get(x, x))
        ],
        "priorities": [
            {"id": k, "label": TICKET_PRIORITY_LABELS[k]} for k in ("baixa", "normal", "urgente")
        ],
        "statuses": [
            {"id": k, "label": TICKET_STATUS_LABELS[k]} for k in (
                "ABERTO", "EM_ANALISE", "AGUARDANDO_JOGADOR", "ENCERRADO"
            )
        ],
    }


def _normalize_status(raw: str | None) -> str | None:
    if not raw:
        return None
    s = str(raw).strip().upper()
    if s in _LEGACY_STATUS_MAP:
        return _LEGACY_STATUS_MAP[s]
    return s if s in TICKET_STATUSES else None


def _is_closed_status(status: str | None) -> bool:
    norm = _normalize_status(status)
    return norm == "ENCERRADO" if norm else (status or "") in _CLOSED_STATUSES


def _can_player_reply(status: str | None) -> bool:
    norm = _normalize_status(status) or (status or "")
    return norm in _PLAYER_REPLY_STATUSES


def ticket_permissions(status: str | None, *, is_admin: bool = False) -> dict[str, bool]:
    """Flags de permissão para UI (jogador e admin)."""
    closed = _is_closed_status(status)
    norm = _normalize_status(status) or (status or "ABERTO")
    return {
        "can_player_reply": not closed and norm in _PLAYER_REPLY_STATUSES,
        "can_admin_reply": not closed,
        "can_player_request_close": not closed and norm in _PLAYER_REPLY_STATUSES,
        "can_admin_close": not closed,
        "can_admin_attend": not closed and norm == "ABERTO",
        "is_closed": closed,
    }


def _resolve_list_status_filter(status: str | None) -> str | None:
    """Normaliza filtros de listagem (abas abertos/encerrados e códigos legados)."""
    if not status:
        return None
    raw = str(status).strip()
    if not raw:
        return None
    low = raw.lower()
    if low in _TAB_OPEN_ALIASES:
        return "__open__"
    if low in _TAB_CLOSED_ALIASES:
        return "__closed__"
    norm = _normalize_status(raw)
    if norm:
        return norm
    if low == "open":
        return "__open__"
    if low == "closed":
        return "__closed__"
    return None


def _column_exists(conn: Any, table: str, column: str, *, is_sqlite: bool) -> bool:
    if is_sqlite:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return any(str(r[1]) == column for r in rows)
    row = conn.execute(
        text(f"SHOW COLUMNS FROM `{table}` LIKE :col"),
        {"col": column},
    ).fetchone()
    return row is not None


def _migrate_ticket_columns(conn: Any, *, is_sqlite: bool) -> None:
    """Adiciona colunas novas e migra status legados."""
    alters: list[str] = []
    if not _column_exists(conn, "support_tickets", "priority", is_sqlite=is_sqlite):
        if is_sqlite:
            alters.append(
                "ALTER TABLE support_tickets ADD COLUMN priority VARCHAR(16) NOT NULL DEFAULT 'normal'"
            )
        else:
            alters.append(
                "ALTER TABLE support_tickets ADD COLUMN priority VARCHAR(16) NOT NULL DEFAULT 'normal'"
            )
    if not _column_exists(conn, "support_tickets", "order_id", is_sqlite=is_sqlite):
        alters.append(
            "ALTER TABLE support_tickets ADD COLUMN order_id VARCHAR(64) NULL"
        )
    for stmt in alters:
        conn.execute(text(stmt))

    for old, new in _LEGACY_STATUS_MAP.items():
        conn.execute(
            text("UPDATE support_tickets SET status = :new WHERE status = :old"),
            {"old": old, "new": new},
        )


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
              priority VARCHAR(16) NOT NULL DEFAULT 'normal',
              status VARCHAR(32) NOT NULL DEFAULT 'ABERTO',
              order_id VARCHAR(64) NULL,
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
            """
            CREATE TABLE IF NOT EXISTS support_ticket_history (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ticket_id INTEGER NOT NULL,
              event_type VARCHAR(32) NOT NULL,
              actor_steam_id VARCHAR(32) NULL,
              actor_name VARCHAR(128) NOT NULL DEFAULT '',
              field_name VARCHAR(32) NULL,
              old_value VARCHAR(256) NULL,
              new_value VARCHAR(256) NULL,
              note TEXT NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
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
              priority VARCHAR(16) NOT NULL DEFAULT 'normal',
              status VARCHAR(32) NOT NULL DEFAULT 'ABERTO',
              order_id VARCHAR(64) NULL,
              assigned_admin_steam_id VARCHAR(32) NULL,
              created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
              updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                ON UPDATE CURRENT_TIMESTAMP(3),
              closed_at DATETIME(3) NULL,
              KEY idx_ticket_steam (steam_id),
              KEY idx_ticket_status (status),
              KEY idx_ticket_priority (priority),
              KEY idx_ticket_category (category),
              KEY idx_ticket_order (order_id),
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
            """
            CREATE TABLE IF NOT EXISTS support_ticket_history (
              id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
              ticket_id BIGINT UNSIGNED NOT NULL,
              event_type VARCHAR(32) NOT NULL,
              actor_steam_id VARCHAR(32) NULL,
              actor_name VARCHAR(128) NOT NULL DEFAULT '',
              field_name VARCHAR(32) NULL,
              old_value VARCHAR(256) NULL,
              new_value VARCHAR(256) NULL,
              note TEXT NULL,
              created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
              KEY idx_hist_ticket (ticket_id),
              KEY idx_hist_created (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        ]
    with engine.connect() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))
        _migrate_ticket_columns(conn, is_sqlite=is_sqlite)
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


def _normalize_category(raw: str | None) -> str:
    cat = (raw or "geral").strip().lower()[:64] or "geral"
    return cat if cat in TICKET_CATEGORIES else "geral"


def _normalize_priority(raw: str | None) -> str:
    pri = (raw or "normal").strip().lower()[:16] or "normal"
    return pri if pri in TICKET_PRIORITIES else "normal"


def _status_label(code: str | None) -> str:
    if not code:
        return ""
    norm = _normalize_status(code) or code
    return TICKET_STATUS_LABELS.get(norm, code)


def _ticket_row_to_dict(row: Any) -> dict[str, Any]:
    status = _normalize_status(row.status) or row.status or "ABERTO"
    category = row.category or "geral"
    priority = row.priority or "normal"
    return {
        "id": int(row.id),
        "steam_id": row.steam_id,
        "player_name": row.player_name or "",
        "discord_user_id": row.discord_user_id,
        "discord_username": row.discord_username,
        "subject": row.subject,
        "category": category,
        "category_label": TICKET_CATEGORY_LABELS.get(category, category),
        "priority": priority,
        "priority_label": TICKET_PRIORITY_LABELS.get(priority, priority),
        "status": status,
        "status_label": _status_label(status),
        "order_id": getattr(row, "order_id", None),
        "assigned_admin_steam_id": row.assigned_admin_steam_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
    }


def _history_row_to_dict(row: Any) -> dict[str, Any]:
    field = row.field_name
    old_v = row.old_value
    new_v = row.new_value
    return {
        "id": int(row.id),
        "ticket_id": int(row.ticket_id),
        "event_type": row.event_type,
        "actor_steam_id": row.actor_steam_id,
        "actor_name": row.actor_name or "",
        "field_name": field,
        "old_value": old_v,
        "new_value": new_v,
        "old_label": _history_value_label(field, old_v),
        "new_label": _history_value_label(field, new_v),
        "note": row.note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _history_value_label(field: str | None, value: str | None) -> str | None:
    if value is None:
        return None
    if field == "status":
        return _status_label(value)
    if field == "priority":
        return TICKET_PRIORITY_LABELS.get(value, value)
    if field == "category":
        return TICKET_CATEGORY_LABELS.get(value, value)
    return value


def _append_history(
    db: Any,
    *,
    ticket_id: int,
    event_type: str,
    actor_steam_id: str | None = None,
    actor_name: str = "",
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    note: str | None = None,
    created_at: datetime | None = None,
) -> None:
    from app import SupportTicketHistory

    db.add(
        SupportTicketHistory(
            ticket_id=ticket_id,
            event_type=event_type,
            actor_steam_id=actor_steam_id,
            actor_name=(actor_name or "")[:128],
            field_name=field_name,
            old_value=(old_value[:256] if old_value else None),
            new_value=(new_value[:256] if new_value else None),
            note=note,
            created_at=created_at or _utcnow(),
        )
    )


def _load_ticket_history(db: Any, ticket_id: int) -> list[dict[str, Any]]:
    from app import SupportTicketHistory

    rows = (
        db.query(SupportTicketHistory)
        .filter(SupportTicketHistory.ticket_id == ticket_id)
        .order_by(SupportTicketHistory.created_at.asc())
        .all()
    )
    return [_history_row_to_dict(r) for r in rows]


def get_order_summary_for_ticket(db: Any, order_id: str | None, *, steam_id: str | None = None) -> dict[str, Any] | None:
    """Resumo de pedido vinculado ao ticket (admin / validação)."""
    if not order_id:
        return None
    from app import Dispute, Order

    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        return None
    if steam_id and order.steam_id != steam_id:
        return None
    disputes: list[Any] = []
    try:
        disputes = db.query(Dispute).filter(Dispute.order_id == order_id).all()
    except Exception:
        disputes = []
    return {
        "order_id": order.order_id,
        "steam_id": order.steam_id,
        "server_id": order.server_id,
        "item_type": order.item_type,
        "item_id": order.item_id,
        "amount": order.amount,
        "points_spent": int(order.points_spent or 0),
        "status": order.status,
        "contested": bool(order.contested),
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "disputes": [
            {
                "id": d.id,
                "status": d.status,
                "reason": (d.reason or "")[:200],
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in disputes
        ],
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
    priority: str = "normal",
    order_id: str | None = None,
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

    cat = _normalize_category(category)
    pri = _normalize_priority(priority)
    oid = (order_id or "").strip() or None
    if oid:
        summary = get_order_summary_for_ticket(db, oid, steam_id=steam_id)
        if not summary:
            return {"ok": False, "error": "Pedido não encontrado ou não pertence à sua conta"}

    link_list = _parse_links(links or [])
    now = _utcnow()
    ticket = SupportTicket(
        steam_id=steam_id,
        player_name=(player_name or steam_id)[:128],
        discord_user_id=discord_user_id,
        discord_username=discord_username,
        subject=subj,
        category=cat,
        priority=pri,
        status="ABERTO",
        order_id=oid,
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

    _append_history(
        db,
        ticket_id=int(ticket.id),
        event_type="created",
        actor_steam_id=steam_id,
        actor_name=(player_name or steam_id)[:128],
        note=f"Categoria: {TICKET_CATEGORY_LABELS.get(cat, cat)} · Prioridade: {TICKET_PRIORITY_LABELS.get(pri, pri)}",
        created_at=now,
    )
    if oid:
        _append_history(
            db,
            ticket_id=int(ticket.id),
            event_type="order_linked",
            actor_steam_id=steam_id,
            actor_name=(player_name or steam_id)[:128],
            field_name="order_id",
            new_value=oid,
            created_at=now,
        )

    db.commit()
    db.refresh(ticket)
    return {
        "ok": True,
        "ticket": _ticket_row_to_dict(ticket),
        "message_id": int(msg.id),
    }


def _apply_status_filter(query: Any, status: str | None) -> Any:
    from app import SupportTicket

    resolved = _resolve_list_status_filter(status)
    if not resolved:
        return query
    if resolved == "__open__":
        return query.filter(SupportTicket.status.in_(tuple(_OPEN_STATUSES)))
    if resolved == "__closed__":
        return query.filter(SupportTicket.status.in_(tuple(_CLOSED_STATUSES)))
    return query.filter(SupportTicket.status == resolved)


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
    q = _apply_status_filter(q, status)
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
    category: str | None = None,
    priority: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    from app import SupportTicket
    from sqlalchemy import or_

    query = db.query(SupportTicket)
    query = _apply_status_filter(query, status)
    cat = (category or "").strip().lower()
    if cat and cat in TICKET_CATEGORIES:
        query = query.filter(SupportTicket.category == cat)
    pri = (priority or "").strip().lower()
    if pri and pri in TICKET_PRIORITIES:
        query = query.filter(SupportTicket.priority == pri)
    search = (q or "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                SupportTicket.subject.like(like),
                SupportTicket.player_name.like(like),
                SupportTicket.steam_id.like(like),
                SupportTicket.discord_username.like(like),
                SupportTicket.order_id.like(like),
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
    include_order: bool = False,
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
    history = _load_ticket_history(db, ticket_id)

    result: dict[str, Any] = {
        "ticket": _ticket_row_to_dict(ticket),
        "messages": [
            _message_row_to_dict(m, att_by_msg.get(int(m.id), []))
            for m in messages
        ],
        "orphan_attachments": ticket_atts,
        "history": history,
        "permissions": ticket_permissions(ticket.status, is_admin=is_admin),
    }
    if include_order or ticket.order_id:
        oid = ticket.order_id
        result["order"] = get_order_summary_for_ticket(
            db, oid, steam_id=None if is_admin else viewer_steam_id
        )
    return result


def get_ticket_history(
    db: Any,
    ticket_id: int,
    *,
    viewer_steam_id: str | None = None,
    is_admin: bool = False,
) -> dict[str, Any] | None:
    from app import SupportTicket

    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        return None
    if not is_admin and viewer_steam_id and ticket.steam_id != viewer_steam_id:
        return None
    return {"ticket_id": ticket_id, "history": _load_ticket_history(db, ticket_id)}


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
    if _is_closed_status(ticket.status):
        return {"ok": False, "error": "Ticket encerrado"}
    if not is_admin and ticket.steam_id != viewer_steam_id:
        return {"ok": False, "error": "Acesso negado"}
    if not is_admin and author_type == "player" and not _can_player_reply(ticket.status):
        return {"ok": False, "error": "Não é possível responder neste status"}

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
    old_status = _normalize_status(ticket.status) or ticket.status or "ABERTO"
    if is_admin and author_type == "admin":
        if old_status == "ABERTO":
            ticket.status = "EM_ANALISE"
            _append_history(
                db,
                ticket_id=ticket_id,
                event_type="status_changed",
                actor_steam_id=author_steam_id,
                actor_name=(author_name or "")[:128],
                field_name="status",
                old_value=old_status,
                new_value="EM_ANALISE",
                created_at=now,
            )
        if author_steam_id and not ticket.assigned_admin_steam_id:
            ticket.assigned_admin_steam_id = author_steam_id
    elif author_type == "player" and old_status == "AGUARDANDO_JOGADOR":
        ticket.status = "EM_ANALISE"
        _append_history(
            db,
            ticket_id=ticket_id,
            event_type="status_changed",
            actor_steam_id=author_steam_id,
            actor_name=(author_name or "")[:128],
            field_name="status",
            old_value=old_status,
            new_value="EM_ANALISE",
            note="Jogador respondeu",
            created_at=now,
        )
    _append_history(
        db,
        ticket_id=ticket_id,
        event_type="reply_admin" if author_type == "admin" else "reply_player",
        actor_steam_id=author_steam_id,
        actor_name=(author_name or "")[:128],
        note=text_body[:200],
        created_at=now,
    )
    db.commit()
    db.refresh(msg)
    return {"ok": True, "message": _message_row_to_dict(msg)}


def update_ticket_status(
    db: Any,
    ticket_id: int,
    *,
    status: str,
    admin_steam_id: str | None = None,
    admin_name: str = "",
) -> dict[str, Any]:
    from app import SupportTicket

    new_status = _normalize_status(status)
    if not new_status:
        return {"ok": False, "error": "Status inválido"}
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        return {"ok": False, "error": "Ticket não encontrado"}

    old_status = _normalize_status(ticket.status) or ticket.status or "ABERTO"
    now = _utcnow()
    ticket.status = new_status
    ticket.updated_at = now
    if new_status == "ENCERRADO":
        ticket.closed_at = now
    else:
        ticket.closed_at = None
    if admin_steam_id and new_status in ("EM_ANALISE", "ABERTO", "AGUARDANDO_JOGADOR"):
        ticket.assigned_admin_steam_id = admin_steam_id
    if old_status != new_status:
        _append_history(
            db,
            ticket_id=ticket_id,
            event_type="status_changed",
            actor_steam_id=admin_steam_id,
            actor_name=(admin_name or "Admin")[:128],
            field_name="status",
            old_value=old_status,
            new_value=new_status,
            created_at=now,
        )
        if new_status == "ENCERRADO":
            _append_history(
                db,
                ticket_id=ticket_id,
                event_type="closed",
                actor_steam_id=admin_steam_id,
                actor_name=(admin_name or "Admin")[:128],
                created_at=now,
            )
    db.commit()
    db.refresh(ticket)
    return {"ok": True, "ticket": _ticket_row_to_dict(ticket)}


def attend_ticket(
    db: Any,
    ticket_id: int,
    *,
    admin_steam_id: str | None = None,
    admin_name: str = "",
) -> dict[str, Any]:
    """Admin assume ticket — status EM_ANALISE sem remover da lista do jogador."""
    from app import SupportTicket

    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        return {"ok": False, "error": "Ticket não encontrado"}
    if _is_closed_status(ticket.status):
        return {"ok": False, "error": "Ticket já encerrado"}

    old_status = _normalize_status(ticket.status) or ticket.status or "ABERTO"
    now = _utcnow()
    ticket.status = "EM_ANALISE"
    ticket.updated_at = now
    if admin_steam_id:
        ticket.assigned_admin_steam_id = admin_steam_id
    if old_status != "EM_ANALISE":
        _append_history(
            db,
            ticket_id=ticket_id,
            event_type="status_changed",
            actor_steam_id=admin_steam_id,
            actor_name=(admin_name or "Admin")[:128],
            field_name="status",
            old_value=old_status,
            new_value="EM_ANALISE",
            note="Ticket em atendimento",
            created_at=now,
        )
    _append_history(
        db,
        ticket_id=ticket_id,
        event_type="attended",
        actor_steam_id=admin_steam_id,
        actor_name=(admin_name or "Admin")[:128],
        created_at=now,
    )
    _notify_ticket_event(ticket_id, "attended", actor_name=admin_name)
    db.commit()
    db.refresh(ticket)
    return {"ok": True, "ticket": _ticket_row_to_dict(ticket)}


def close_ticket(
    db: Any,
    ticket_id: int,
    *,
    admin_steam_id: str | None = None,
    admin_name: str = "",
    note: str | None = None,
) -> dict[str, Any]:
    """Encerra ticket (admin)."""
    from app import SupportTicket

    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        return {"ok": False, "error": "Ticket não encontrado"}
    if _is_closed_status(ticket.status):
        return {"ok": False, "error": "Ticket já encerrado"}

    old_status = _normalize_status(ticket.status) or ticket.status or "ABERTO"
    now = _utcnow()
    ticket.status = "ENCERRADO"
    ticket.updated_at = now
    ticket.closed_at = now
    if admin_steam_id:
        ticket.assigned_admin_steam_id = admin_steam_id
    _append_history(
        db,
        ticket_id=ticket_id,
        event_type="status_changed",
        actor_steam_id=admin_steam_id,
        actor_name=(admin_name or "Admin")[:128],
        field_name="status",
        old_value=old_status,
        new_value="ENCERRADO",
        created_at=now,
    )
    _append_history(
        db,
        ticket_id=ticket_id,
        event_type="closed",
        actor_steam_id=admin_steam_id,
        actor_name=(admin_name or "Admin")[:128],
        note=(note[:500] if note else None),
        created_at=now,
    )
    _notify_ticket_event(ticket_id, "closed", actor_name=admin_name)
    db.commit()
    db.refresh(ticket)
    return {"ok": True, "ticket": _ticket_row_to_dict(ticket)}


def request_player_close(
    db: Any,
    ticket_id: int,
    *,
    steam_id: str,
    player_name: str = "",
    note: str | None = None,
) -> dict[str, Any]:
    """Jogador solicita encerramento — não fecha automaticamente."""
    from app import SupportTicket

    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        return {"ok": False, "error": "Ticket não encontrado"}
    if ticket.steam_id != steam_id:
        return {"ok": False, "error": "Acesso negado"}
    if _is_closed_status(ticket.status):
        return {"ok": False, "error": "Ticket já encerrado"}
    if not _can_player_reply(ticket.status):
        return {"ok": False, "error": "Não é possível solicitar encerramento neste status"}

    now = _utcnow()
    msg_note = (note or "Jogador considera o problema resolvido e solicita encerramento.").strip()
    _append_history(
        db,
        ticket_id=ticket_id,
        event_type="close_requested",
        actor_steam_id=steam_id,
        actor_name=(player_name or steam_id)[:128],
        note=msg_note[:500],
        created_at=now,
    )
    old_status = _normalize_status(ticket.status) or ticket.status or "ABERTO"
    if old_status in ("ABERTO", "EM_ANALISE"):
        ticket.status = "AGUARDANDO_JOGADOR"
        ticket.updated_at = now
        _append_history(
            db,
            ticket_id=ticket_id,
            event_type="status_changed",
            actor_steam_id=steam_id,
            actor_name=(player_name or steam_id)[:128],
            field_name="status",
            old_value=old_status,
            new_value="AGUARDANDO_JOGADOR",
            note="Aguardando confirmação do suporte",
            created_at=now,
        )
    else:
        ticket.updated_at = now
    _notify_ticket_event(ticket_id, "close_requested", actor_name=player_name)
    db.commit()
    db.refresh(ticket)
    return {"ok": True, "ticket": _ticket_row_to_dict(ticket)}


def _notify_ticket_event(ticket_id: int, event: str, *, actor_name: str = "") -> None:
    """Stub para notificações futuras (Discord, e-mail, in-game)."""
    _ = (ticket_id, event, actor_name)


def update_ticket_priority(
    db: Any,
    ticket_id: int,
    *,
    priority: str,
    admin_steam_id: str | None = None,
    admin_name: str = "",
) -> dict[str, Any]:
    from app import SupportTicket

    new_pri = _normalize_priority(priority)
    if new_pri not in TICKET_PRIORITIES:
        return {"ok": False, "error": "Prioridade inválida"}
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        return {"ok": False, "error": "Ticket não encontrado"}

    old_pri = ticket.priority or "normal"
    if old_pri == new_pri:
        return {"ok": True, "ticket": _ticket_row_to_dict(ticket)}

    now = _utcnow()
    ticket.priority = new_pri
    ticket.updated_at = now
    _append_history(
        db,
        ticket_id=ticket_id,
        event_type="priority_changed",
        actor_steam_id=admin_steam_id,
        actor_name=(admin_name or "Admin")[:128],
        field_name="priority",
        old_value=old_pri,
        new_value=new_pri,
        created_at=now,
    )
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
    actor_name: str = "",
) -> dict[str, Any]:
    from app import SupportTicket, SupportTicketAttachment

    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        return {"ok": False, "error": "Ticket não encontrado"}
    if not is_admin and ticket.steam_id != viewer_steam_id:
        return {"ok": False, "error": "Acesso negado"}
    if _is_closed_status(ticket.status):
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
    _append_history(
        db,
        ticket_id=ticket_id,
        event_type="attachment_added",
        actor_steam_id=viewer_steam_id,
        actor_name=(actor_name or viewer_steam_id)[:128],
        note=original[:200],
        created_at=now,
    )
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
