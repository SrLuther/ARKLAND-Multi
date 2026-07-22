"""Vídeos YouTube — tutoriais e conteúdo informativo do servidor."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

MEDIA_CATEGORIES = frozenset({"tutorial", "informativo", "geral"})
MEDIA_CATEGORY_LABELS: dict[str, str] = {
    "tutorial": "Tutorial",
    "informativo": "Informativo",
    "geral": "Geral",
}

_MAX_TITLE = 200
_MAX_DESCRIPTION = 4000
_MAX_URL = 512
_YT_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
_YT_URL_PATTERNS = (
    re.compile(
        r"(?:youtube\.com/watch\?(?:[^&]*&)*v=|youtu\.be/|youtube\.com/embed/"
        r"|youtube\.com/v/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})"
    ),
    re.compile(r"^([a-zA-Z0-9_-]{11})$"),
)


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


def parse_youtube_id(raw: str | None) -> str | None:
    """Extrai ID de 11 caracteres de URL ou ID YouTube."""
    s = (raw or "").strip()
    if not s:
        return None
    for pat in _YT_URL_PATTERNS:
        m = pat.search(s)
        if m:
            vid = m.group(1)
            if _YT_ID_RE.match(vid):
                return vid
    return None


def youtube_embed_url(video_id: str) -> str:
    return f"https://www.youtube.com/embed/{video_id}"


def youtube_watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def media_meta() -> dict[str, Any]:
    return {
        "categories": [
            {"id": k, "label": MEDIA_CATEGORY_LABELS[k]}
            for k in ("tutorial", "informativo", "geral")
        ],
    }


def ensure_media_schema(engine: Engine) -> None:
    """Cria tabela media_videos (idempotente — MySQL e SQLite)."""
    is_sqlite = "sqlite" in str(engine.url).lower()
    if is_sqlite:
        stmts = [
            """
            CREATE TABLE IF NOT EXISTS media_videos (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              video_id VARCHAR(16) NOT NULL,
              youtube_url VARCHAR(512) NULL,
              title VARCHAR(200) NOT NULL,
              description TEXT NULL,
              category VARCHAR(16) NOT NULL DEFAULT 'geral',
              sort_order INTEGER NOT NULL DEFAULT 0,
              published INTEGER NOT NULL DEFAULT 0,
              created_by_steam_id VARCHAR(32) NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_media_pub ON media_videos (published, sort_order)",
            "CREATE INDEX IF NOT EXISTS idx_media_cat ON media_videos (category)",
        ]
    else:
        stmts = [
            """
            CREATE TABLE IF NOT EXISTS media_videos (
              id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
              video_id VARCHAR(16) NOT NULL,
              youtube_url VARCHAR(512) NULL,
              title VARCHAR(200) NOT NULL,
              description TEXT NULL,
              category VARCHAR(16) NOT NULL DEFAULT 'geral',
              sort_order INT NOT NULL DEFAULT 0,
              published TINYINT(1) NOT NULL DEFAULT 0,
              created_by_steam_id VARCHAR(32) NULL,
              created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
              updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                ON UPDATE CURRENT_TIMESTAMP(3),
              KEY idx_media_pub (published, sort_order),
              KEY idx_media_cat (category)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        ]
    with engine.connect() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))
        conn.commit()


def _normalize_category(raw: str | None) -> str:
    cat = (raw or "geral").strip().lower()[:16] or "geral"
    return cat if cat in MEDIA_CATEGORIES else "geral"


def _row_to_dict(row: Any) -> dict[str, Any]:
    category = row.category or "geral"
    video_id = str(row.video_id or "")
    return {
        "id": int(row.id),
        "video_id": video_id,
        "youtube_url": row.youtube_url or youtube_watch_url(video_id),
        "embed_url": youtube_embed_url(video_id),
        "title": row.title or "",
        "description": row.description or "",
        "category": category,
        "category_label": MEDIA_CATEGORY_LABELS.get(category, category),
        "sort_order": int(row.sort_order or 0),
        "published": bool(int(row.published or 0)),
        "created_by_steam_id": row.created_by_steam_id,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


_MEDIA_LIST_COLS = (
    "id, video_id, youtube_url, title, description, category, sort_order, "
    "published, created_by_steam_id, created_at, updated_at"
)


def _fetch_row(db: Session, video_pk: int) -> Any | None:
    return db.execute(
        text(f"SELECT {_MEDIA_LIST_COLS} FROM media_videos WHERE id = :id"),
        {"id": video_pk},
    ).fetchone()


def list_media_public(
    db: Session,
    *,
    category: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses = ["published = 1"]
    params: dict[str, Any] = {"lim": min(100, max(1, limit))}
    norm_cat = _normalize_category(category) if category else None
    if category and norm_cat:
        clauses.append("category = :cat")
        params["cat"] = norm_cat
    where = " AND ".join(clauses)
    rows = db.execute(
        text(
            f"SELECT {_MEDIA_LIST_COLS} FROM media_videos WHERE {where} "
            "ORDER BY sort_order ASC, id DESC LIMIT :lim"
        ),
        params,
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def list_media_admin(db: Session, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            f"SELECT {_MEDIA_LIST_COLS} FROM media_videos "
            "ORDER BY sort_order ASC, id DESC LIMIT :lim"
        ),
        {"lim": min(100, max(1, limit))},
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def create_media_video(
    db: Session,
    *,
    youtube_url: str | None = None,
    video_id: str | None = None,
    title: str,
    description: str | None = None,
    category: str = "geral",
    sort_order: int = 0,
    published: bool = False,
    created_by_steam_id: str | None = None,
) -> dict[str, Any]:
    vid = parse_youtube_id(video_id) or parse_youtube_id(youtube_url)
    if not vid:
        raise ValueError("URL ou ID do YouTube inválido")

    title_s = (title or "").strip()[:_MAX_TITLE]
    if not title_s:
        raise ValueError("Título obrigatório")

    desc_s = (description or "").strip()[:_MAX_DESCRIPTION] or None
    cat = _normalize_category(category)
    order = int(sort_order or 0)
    url_stored = (youtube_url or "").strip()[:_MAX_URL] or youtube_watch_url(vid)
    now = _utcnow().replace(tzinfo=None)
    url = str(getattr(db, "bind", None).url if getattr(db, "bind", None) else "").lower()

    params = {
        "vid": vid,
        "url": url_stored,
        "title": title_s,
        "desc": desc_s,
        "cat": cat,
        "ord": order,
        "pub": 1 if published else 0,
        "by": created_by_steam_id,
        "now": now,
    }

    if "sqlite" in url:
        cur = db.execute(
            text(
                "INSERT INTO media_videos "
                "(video_id, youtube_url, title, description, category, sort_order, "
                "published, created_by_steam_id, created_at, updated_at) "
                "VALUES (:vid, :url, :title, :desc, :cat, :ord, :pub, :by, :now, :now)"
            ),
            params,
        )
        pk = int(cur.lastrowid)
    else:
        cur = db.execute(
            text(
                "INSERT INTO media_videos "
                "(video_id, youtube_url, title, description, category, sort_order, "
                "published, created_by_steam_id, created_at, updated_at) "
                "VALUES (:vid, :url, :title, :desc, :cat, :ord, :pub, :by, :now, :now)"
            ),
            params,
        )
        pk = int(cur.lastrowid)

    db.commit()
    row = _fetch_row(db, pk)
    if not row:
        raise ValueError("Falha ao criar vídeo")
    return _row_to_dict(row)


def update_media_video(
    db: Session,
    video_pk: int,
    *,
    youtube_url: str | None = None,
    video_id: str | None = None,
    title: str | None = None,
    description: str | None = None,
    category: str | None = None,
    sort_order: int | None = None,
    published: bool | None = None,
) -> dict[str, Any]:
    row = _fetch_row(db, video_pk)
    if not row:
        raise ValueError("Vídeo não encontrado")

    sets: list[str] = []
    params: dict[str, Any] = {"id": video_pk, "now": _utcnow().replace(tzinfo=None)}

    if video_id is not None or youtube_url is not None:
        vid = parse_youtube_id(video_id) or parse_youtube_id(youtube_url)
        if not vid:
            raise ValueError("URL ou ID do YouTube inválido")
        sets.append("video_id = :vid")
        params["vid"] = vid
        if youtube_url is not None:
            sets.append("youtube_url = :url")
            params["url"] = (youtube_url or "").strip()[:_MAX_URL] or youtube_watch_url(vid)
        elif video_id is not None:
            sets.append("youtube_url = :url")
            params["url"] = youtube_watch_url(vid)

    if title is not None:
        t = str(title).strip()[:_MAX_TITLE]
        if not t:
            raise ValueError("Título inválido")
        sets.append("title = :title")
        params["title"] = t

    if description is not None:
        sets.append("description = :desc")
        params["desc"] = str(description).strip()[:_MAX_DESCRIPTION] or None

    if category is not None:
        sets.append("category = :cat")
        params["cat"] = _normalize_category(category)

    if sort_order is not None:
        sets.append("sort_order = :ord")
        params["ord"] = int(sort_order)

    if published is not None:
        sets.append("published = :pub")
        params["pub"] = 1 if published else 0

    if not sets:
        return _row_to_dict(row)

    sets.append("updated_at = :now")
    db.execute(
        text(f"UPDATE media_videos SET {', '.join(sets)} WHERE id = :id"),
        params,
    )
    db.commit()
    updated = _fetch_row(db, video_pk)
    if not updated:
        raise ValueError("Vídeo não encontrado")
    return _row_to_dict(updated)


def delete_media_video(db: Session, video_pk: int) -> None:
    row = _fetch_row(db, video_pk)
    if not row:
        raise ValueError("Vídeo não encontrado")
    db.execute(text("DELETE FROM media_videos WHERE id = :id"), {"id": video_pk})
    db.commit()
