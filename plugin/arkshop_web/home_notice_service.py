"""Mural de avisos da home — cards do carrossel (com migração do aviso único legado)."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

_MAX_TITLE = 120
_MAX_BODY = 4000
_MAX_IMAGE_URL = 512
_MAX_LINK_URL = 512
_SINGLETON_ID = 1
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_ALLOWED_IMAGE_MIME = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})
_SAFE_FILENAME = re.compile(r"^[a-zA-Z0-9._-]+$")
_RECOMMENDED_WIDTH = 1200
_RECOMMENDED_HEIGHT = 675

_uploads_dir: Path | None = None
_image_url_prefix: str = "/api/public/home-card-images"


def configure_home_cards(
    *,
    uploads_dir: Path,
    image_url_prefix: str = "/api/public/home-card-images",
) -> None:
    global _uploads_dir, _image_url_prefix
    _uploads_dir = uploads_dir
    _image_url_prefix = image_url_prefix.rstrip("/")
    uploads_dir.mkdir(parents=True, exist_ok=True)


def home_cards_meta() -> dict[str, Any]:
    return {
        "recommended_width": _RECOMMENDED_WIDTH,
        "recommended_height": _RECOMMENDED_HEIGHT,
        "recommended_aspect": "16:9",
        "recommended_label": f"{_RECOMMENDED_WIDTH} × {_RECOMMENDED_HEIGHT} px (16:9)",
        "max_image_bytes": _MAX_IMAGE_BYTES,
        "allowed_mime": sorted(_ALLOWED_IMAGE_MIME),
    }


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


def _uploads_path() -> Path:
    if _uploads_dir is None:
        raise ValueError("home_cards_uploads_not_configured")
    return _uploads_dir


def _guess_ext(mime: str, filename: str) -> str:
    low = (filename or "").lower()
    if low.endswith(".png"):
        return ".png"
    if low.endswith(".webp"):
        return ".webp"
    if low.endswith(".gif"):
        return ".gif"
    if low.endswith(".jpg") or low.endswith(".jpeg"):
        return ".jpg"
    if mime == "image/png":
        return ".png"
    if mime == "image/webp":
        return ".webp"
    if mime == "image/gif":
        return ".gif"
    return ".jpg"


def save_home_card_image(file_storage: Any, *, mime_type: str | None = None) -> dict[str, Any]:
    if file_storage is None:
        raise ValueError("file_required")
    mime = (mime_type or getattr(file_storage, "mimetype", None) or "").split(";")[0].strip().lower()
    if mime not in _ALLOWED_IMAGE_MIME:
        raise ValueError("invalid_image_type")
    raw = file_storage.read()
    if not raw:
        raise ValueError("empty_file")
    if len(raw) > _MAX_IMAGE_BYTES:
        raise ValueError("file_too_large")
    original = str(getattr(file_storage, "filename", None) or "image.jpg")
    ext = _guess_ext(mime, original)
    name = f"{uuid.uuid4().hex}{ext}"
    dest = _uploads_path() / name
    dest.write_bytes(raw)
    url = f"{_image_url_prefix}/{name}"
    return {"filename": name, "image_url": url, "size": len(raw), "mime_type": mime}


def resolve_home_card_image_path(filename: str) -> Path | None:
    safe = Path(filename).name
    if not safe or not _SAFE_FILENAME.match(safe):
        return None
    if _uploads_dir is None:
        return None
    full = _uploads_dir / safe
    if not full.is_file():
        return None
    return full


def ensure_home_notice_schema(engine: Engine) -> None:
    """Cria tabelas do mural (idempotente — MySQL e SQLite) e migra aviso legado."""
    is_sqlite = "sqlite" in str(engine.url).lower()
    if is_sqlite:
        notice_stmt = """
            CREATE TABLE IF NOT EXISTS home_notice (
              id INTEGER PRIMARY KEY NOT NULL,
              title VARCHAR(120) NOT NULL DEFAULT '',
              body TEXT NOT NULL DEFAULT '',
              updated_by_steam_id VARCHAR(32) NULL,
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        cards_stmt = """
            CREATE TABLE IF NOT EXISTS home_cards (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title VARCHAR(120) NOT NULL DEFAULT '',
              body TEXT NOT NULL DEFAULT '',
              image_url VARCHAR(512) NOT NULL DEFAULT '',
              link_url VARCHAR(512) NOT NULL DEFAULT '',
              active INTEGER NOT NULL DEFAULT 1,
              sort_order INTEGER NOT NULL DEFAULT 0,
              updated_by_steam_id VARCHAR(32) NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
    else:
        notice_stmt = """
            CREATE TABLE IF NOT EXISTS home_notice (
              id TINYINT UNSIGNED NOT NULL PRIMARY KEY,
              title VARCHAR(120) NOT NULL DEFAULT '',
              body TEXT NOT NULL,
              updated_by_steam_id VARCHAR(32) NULL,
              updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                ON UPDATE CURRENT_TIMESTAMP(3)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        cards_stmt = """
            CREATE TABLE IF NOT EXISTS home_cards (
              id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
              title VARCHAR(120) NOT NULL DEFAULT '',
              body TEXT NOT NULL,
              image_url VARCHAR(512) NOT NULL DEFAULT '',
              link_url VARCHAR(512) NOT NULL DEFAULT '',
              active TINYINT(1) NOT NULL DEFAULT 1,
              sort_order INT NOT NULL DEFAULT 0,
              updated_by_steam_id VARCHAR(32) NULL,
              created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
              updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                ON UPDATE CURRENT_TIMESTAMP(3),
              KEY ix_home_cards_active_order (active, sort_order, id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
    with engine.begin() as conn:
        conn.execute(text(notice_stmt))
        conn.execute(text(cards_stmt))
        _migrate_legacy_notice_to_cards(conn)


def _migrate_legacy_notice_to_cards(conn: Any) -> None:
    cards_count = conn.execute(text("SELECT COUNT(*) FROM home_cards")).scalar() or 0
    if int(cards_count) > 0:
        return
    row = conn.execute(
        text(
            "SELECT title, body, updated_by_steam_id, updated_at "
            "FROM home_notice WHERE id = :id"
        ),
        {"id": _SINGLETON_ID},
    ).fetchone()
    if row is None:
        return
    mapping = row._mapping if hasattr(row, "_mapping") else None
    if mapping is not None:
        title = str(mapping.get("title") or "").strip()
        body = str(mapping.get("body") or "").strip()
        sid = mapping.get("updated_by_steam_id")
        updated_at = mapping.get("updated_at") or _utcnow()
    else:
        title = str(row[0] or "").strip()
        body = str(row[1] or "").strip()
        sid = row[2] if len(row) > 2 else None
        updated_at = row[3] if len(row) > 3 else _utcnow()
    if not title and not body:
        return
    conn.execute(
        text(
            "INSERT INTO home_cards "
            "(title, body, image_url, link_url, active, sort_order, "
            " updated_by_steam_id, created_at, updated_at) "
            "VALUES (:title, :body, '', '', 1, 0, :sid, :created_at, :updated_at)"
        ),
        {
            "title": title[:_MAX_TITLE],
            "body": body[:_MAX_BODY],
            "sid": str(sid).strip() if sid else None,
            "created_at": updated_at,
            "updated_at": updated_at,
        },
    )


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


def _as_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(int(value))
    s = str(value).strip().lower()
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off"):
        return False
    return default


def _clean_url(value: Any, *, max_len: int) -> str:
    s = str(value or "").strip()[:max_len]
    if not s:
        return ""
    low = s.lower()
    if low.startswith(("http://", "https://", "/")):
        return s
    raise ValueError("invalid_url")


def _row_to_card(row: Any) -> dict[str, Any]:
    mapping = row._mapping if hasattr(row, "_mapping") else None
    if mapping is None:
        raise ValueError("invalid_card_row")
    title = str(mapping.get("title") or "").strip()
    body = str(mapping.get("body") or "").strip()
    image_url = str(mapping.get("image_url") or "").strip()
    link_url = str(mapping.get("link_url") or "").strip()
    return {
        "id": int(mapping["id"]),
        "title": title,
        "body": body,
        "text": body,
        "image_url": image_url or None,
        "link_url": link_url or None,
        "active": _as_bool(mapping.get("active"), True),
        "order": int(mapping.get("sort_order") or 0),
        "sort_order": int(mapping.get("sort_order") or 0),
        "updated_by_steam_id": (
            str(mapping.get("updated_by_steam_id")).strip()
            if mapping.get("updated_by_steam_id")
            else None
        ),
        "created_at": _iso(mapping.get("created_at")),
        "updated_at": _iso(mapping.get("updated_at")),
        "has_content": bool(title or body or image_url),
        "has_image": bool(image_url),
    }


def get_home_notice(db: Session) -> dict[str, Any]:
    """Legado: sintetiza o aviso a partir do primeiro card ativo (ou singleton)."""
    cards = list_home_cards(db, active_only=True)
    if cards:
        first = cards[0]
        return {
            "title": first.get("title") or "",
            "body": first.get("body") or "",
            "updated_at": first.get("updated_at"),
            "updated_by_steam_id": first.get("updated_by_steam_id"),
            "has_content": bool(first.get("has_content")),
        }
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
    """Legado: atualiza o singleton e sincroniza/cria o primeiro card."""
    clean_title = str(title or "").strip()[:_MAX_TITLE]
    clean_body = str(body or "").strip()[:_MAX_BODY]
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

    cards = list_home_cards(db, active_only=False)
    if not clean_title and not clean_body:
        for card in cards:
            if not card.get("image_url") and not card.get("link_url"):
                delete_home_card(db, int(card["id"]), commit=False)
        db.commit()
        return get_home_notice(db)

    if cards:
        update_home_card(
            db,
            int(cards[0]["id"]),
            title=clean_title,
            body=clean_body,
            updated_by_steam_id=sid,
            commit=False,
        )
    else:
        create_home_card(
            db,
            title=clean_title,
            body=clean_body,
            active=True,
            sort_order=0,
            updated_by_steam_id=sid,
            commit=False,
        )
    db.commit()
    return get_home_notice(db)


def list_home_cards(db: Session, *, active_only: bool = False) -> list[dict[str, Any]]:
    where = "WHERE active = 1" if active_only else ""
    rows = db.execute(
        text(
            f"SELECT id, title, body, image_url, link_url, active, sort_order, "
            f"updated_by_steam_id, created_at, updated_at "
            f"FROM home_cards {where} "
            f"ORDER BY sort_order ASC, id ASC"
        )
    ).fetchall()
    return [_row_to_card(r) for r in rows]


def get_home_card(db: Session, card_id: int) -> dict[str, Any] | None:
    row = db.execute(
        text(
            "SELECT id, title, body, image_url, link_url, active, sort_order, "
            "updated_by_steam_id, created_at, updated_at "
            "FROM home_cards WHERE id = :id"
        ),
        {"id": int(card_id)},
    ).fetchone()
    if row is None:
        return None
    return _row_to_card(row)


def create_home_card(
    db: Session,
    *,
    title: str | None = None,
    body: str | None = None,
    image_url: str | None = None,
    link_url: str | None = None,
    active: bool = True,
    sort_order: int | None = None,
    updated_by_steam_id: str | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    clean_title = str(title or "").strip()[:_MAX_TITLE]
    clean_body = str(body or "").strip()[:_MAX_BODY]
    clean_image = _clean_url(image_url, max_len=_MAX_IMAGE_URL) if image_url else ""
    clean_link = _clean_url(link_url, max_len=_MAX_LINK_URL) if link_url else ""
    if not clean_title and not clean_body and not clean_image:
        raise ValueError("card_empty")
    if sort_order is None:
        max_order = db.execute(text("SELECT COALESCE(MAX(sort_order), -1) FROM home_cards")).scalar()
        order_val = int(max_order or -1) + 1
    else:
        order_val = int(sort_order)
    now = _utcnow()
    sid = (str(updated_by_steam_id or "").strip() or None)
    result = db.execute(
        text(
            "INSERT INTO home_cards "
            "(title, body, image_url, link_url, active, sort_order, "
            " updated_by_steam_id, created_at, updated_at) "
            "VALUES (:title, :body, :image_url, :link_url, :active, :sort_order, "
            " :sid, :created_at, :updated_at)"
        ),
        {
            "title": clean_title,
            "body": clean_body,
            "image_url": clean_image,
            "link_url": clean_link,
            "active": 1 if active else 0,
            "sort_order": order_val,
            "sid": sid,
            "created_at": now,
            "updated_at": now,
        },
    )
    card_id = int(result.lastrowid)
    if commit:
        db.commit()
    card = get_home_card(db, card_id)
    if card is None:
        raise RuntimeError("card_create_failed")
    return card


def update_home_card(
    db: Session,
    card_id: int,
    *,
    title: Any = ...,
    body: Any = ...,
    image_url: Any = ...,
    link_url: Any = ...,
    active: Any = ...,
    sort_order: Any = ...,
    updated_by_steam_id: str | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    current = get_home_card(db, card_id)
    if current is None:
        raise ValueError("card_not_found")

    new_title = current["title"] if title is ... else str(title or "").strip()[:_MAX_TITLE]
    new_body = current["body"] if body is ... else str(body or "").strip()[:_MAX_BODY]
    if image_url is ...:
        new_image = current.get("image_url") or ""
    else:
        new_image = _clean_url(image_url, max_len=_MAX_IMAGE_URL) if image_url else ""
    if link_url is ...:
        new_link = current.get("link_url") or ""
    else:
        new_link = _clean_url(link_url, max_len=_MAX_LINK_URL) if link_url else ""
    new_active = current["active"] if active is ... else _as_bool(active, True)
    new_order = current["sort_order"] if sort_order is ... else int(sort_order)
    if not new_title and not new_body and not new_image:
        raise ValueError("card_empty")

    now = _utcnow()
    sid = (str(updated_by_steam_id or "").strip() or None)
    db.execute(
        text(
            "UPDATE home_cards SET title = :title, body = :body, image_url = :image_url, "
            "link_url = :link_url, active = :active, sort_order = :sort_order, "
            "updated_by_steam_id = :sid, updated_at = :updated_at WHERE id = :id"
        ),
        {
            "id": int(card_id),
            "title": new_title,
            "body": new_body,
            "image_url": new_image,
            "link_url": new_link,
            "active": 1 if new_active else 0,
            "sort_order": new_order,
            "sid": sid,
            "updated_at": now,
        },
    )
    if commit:
        db.commit()
    card = get_home_card(db, card_id)
    if card is None:
        raise RuntimeError("card_update_failed")
    return card


def delete_home_card(db: Session, card_id: int, *, commit: bool = True) -> dict[str, Any]:
    current = get_home_card(db, card_id)
    if current is None:
        raise ValueError("card_not_found")
    db.execute(text("DELETE FROM home_cards WHERE id = :id"), {"id": int(card_id)})
    if commit:
        db.commit()
    return current


def reorder_home_cards(
    db: Session,
    ordered_ids: list[int],
    *,
    updated_by_steam_id: str | None = None,
) -> list[dict[str, Any]]:
    sid = (str(updated_by_steam_id or "").strip() or None)
    now = _utcnow()
    for idx, card_id in enumerate(ordered_ids):
        db.execute(
            text(
                "UPDATE home_cards SET sort_order = :ord, updated_by_steam_id = :sid, "
                "updated_at = :updated_at WHERE id = :id"
            ),
            {"ord": idx, "sid": sid, "updated_at": now, "id": int(card_id)},
        )
    db.commit()
    return list_home_cards(db, active_only=False)
