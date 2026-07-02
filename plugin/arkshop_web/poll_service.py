"""Votações da comunidade — enquetes com recompensa em Âmbares."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

POLL_STATUSES = frozenset({"DRAFT", "ACTIVE", "CLOSED", "CANCELLED"})
POLL_STATUS_LABELS = {
    "DRAFT": "Rascunho",
    "ACTIVE": "Em andamento",
    "CLOSED": "Encerrada",
    "CANCELLED": "Cancelada",
}

_MAX_TITLE = 200
_MAX_DESCRIPTION = 4000
_MAX_OPTION_LABEL = 200
_MAX_OPTIONS = 12
_MIN_OPTIONS = 2


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    s = str(raw).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def ensure_poll_schema(engine: Engine) -> None:
    """Cria tabelas de votações (idempotente — MySQL e SQLite)."""
    is_sqlite = "sqlite" in str(engine.url).lower()
    if is_sqlite:
        stmts = [
            """
            CREATE TABLE IF NOT EXISTS community_polls (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title VARCHAR(200) NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              reward_amber INTEGER NOT NULL DEFAULT 0,
              allow_multiple INTEGER NOT NULL DEFAULT 0,
              min_votes_valid INTEGER NULL,
              ends_at DATETIME NOT NULL,
              status VARCHAR(16) NOT NULL DEFAULT 'DRAFT',
              winner_option_id INTEGER NULL,
              result_valid INTEGER NULL,
              total_voters INTEGER NOT NULL DEFAULT 0,
              closed_at DATETIME NULL,
              created_by_steam_id VARCHAR(32) NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS community_poll_options (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              poll_id INTEGER NOT NULL,
              label VARCHAR(200) NOT NULL,
              sort_order INTEGER NOT NULL DEFAULT 0
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS community_poll_votes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              poll_id INTEGER NOT NULL,
              option_id INTEGER NOT NULL,
              steam_id VARCHAR(32) NOT NULL,
              reward_granted INTEGER NOT NULL DEFAULT 0,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(poll_id, steam_id, option_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_poll_status ON community_polls (status)",
            "CREATE INDEX IF NOT EXISTS idx_poll_ends ON community_polls (ends_at)",
            "CREATE INDEX IF NOT EXISTS idx_poll_opt_poll ON community_poll_options (poll_id)",
            "CREATE INDEX IF NOT EXISTS idx_poll_vote_poll ON community_poll_votes (poll_id)",
            "CREATE INDEX IF NOT EXISTS idx_poll_vote_steam ON community_poll_votes (poll_id, steam_id)",
        ]
    else:
        stmts = [
            """
            CREATE TABLE IF NOT EXISTS community_polls (
              id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
              title VARCHAR(200) NOT NULL,
              description TEXT NOT NULL,
              reward_amber INT NOT NULL DEFAULT 0,
              allow_multiple TINYINT(1) NOT NULL DEFAULT 0,
              min_votes_valid INT NULL,
              ends_at DATETIME(3) NOT NULL,
              status VARCHAR(16) NOT NULL DEFAULT 'DRAFT',
              winner_option_id BIGINT UNSIGNED NULL,
              result_valid TINYINT(1) NULL,
              total_voters INT NOT NULL DEFAULT 0,
              closed_at DATETIME(3) NULL,
              created_by_steam_id VARCHAR(32) NULL,
              created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
              updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
              KEY idx_poll_status (status),
              KEY idx_poll_ends (ends_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS community_poll_options (
              id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
              poll_id BIGINT UNSIGNED NOT NULL,
              label VARCHAR(200) NOT NULL,
              sort_order INT NOT NULL DEFAULT 0,
              KEY idx_poll_opt_poll (poll_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS community_poll_votes (
              id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
              poll_id BIGINT UNSIGNED NOT NULL,
              option_id BIGINT UNSIGNED NOT NULL,
              steam_id VARCHAR(32) NOT NULL,
              reward_granted TINYINT(1) NOT NULL DEFAULT 0,
              created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
              UNIQUE KEY uq_poll_steam_option (poll_id, steam_id, option_id),
              KEY idx_poll_vote_poll (poll_id),
              KEY idx_poll_vote_steam (poll_id, steam_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        ]
    with engine.connect() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))
        conn.commit()


def _credit_points(db: Session, steam_id: str, amount: int) -> int:
    if amount <= 0:
        return _player_points(db, steam_id)
    url = str(getattr(db, "bind", None).url if getattr(db, "bind", None) else "").lower()
    if "sqlite" in url:
        db.execute(
            text(
                "INSERT INTO players (steam_id, points) VALUES (:sid, :amt) "
                "ON CONFLICT(steam_id) DO UPDATE SET points = points + :amt"
            ),
            {"sid": steam_id, "amt": amount},
        )
    else:
        db.execute(
            text(
                "INSERT INTO players (steam_id, points) VALUES (:sid, :amt) "
                "ON DUPLICATE KEY UPDATE points = points + :amt"
            ),
            {"sid": steam_id, "amt": amount},
        )
    return _player_points(db, steam_id)


def _player_points(db: Session, steam_id: str) -> int:
    row = db.execute(
        text("SELECT points FROM players WHERE steam_id = :sid LIMIT 1"),
        {"sid": steam_id},
    ).fetchone()
    return int(row[0] if row else 0)


def _fetch_poll_row(db: Session, poll_id: int) -> Any | None:
    return db.execute(
        text("SELECT * FROM community_polls WHERE id = :id"),
        {"id": poll_id},
    ).fetchone()


def _fetch_options(db: Session, poll_id: int) -> list[Any]:
    return list(
        db.execute(
            text(
                "SELECT * FROM community_poll_options WHERE poll_id = :pid "
                "ORDER BY sort_order ASC, id ASC"
            ),
            {"pid": poll_id},
        ).fetchall()
    )


def _vote_counts(db: Session, poll_id: int) -> dict[int, int]:
    rows = db.execute(
        text(
            "SELECT option_id, COUNT(*) AS c FROM community_poll_votes "
            "WHERE poll_id = :pid GROUP BY option_id"
        ),
        {"pid": poll_id},
    ).fetchall()
    return {int(r.option_id): int(r.c) for r in rows}


def _total_voters(db: Session, poll_id: int) -> int:
    row = db.execute(
        text(
            "SELECT COUNT(DISTINCT steam_id) AS c FROM community_poll_votes WHERE poll_id = :pid"
        ),
        {"pid": poll_id},
    ).fetchone()
    return int(row.c if row else 0)


def _user_voted_option_ids(db: Session, poll_id: int, steam_id: str) -> list[int]:
    rows = db.execute(
        text(
            "SELECT option_id FROM community_poll_votes "
            "WHERE poll_id = :pid AND steam_id = :sid"
        ),
        {"pid": poll_id, "sid": steam_id},
    ).fetchall()
    return [int(r.option_id) for r in rows]


def _build_option_stats(
    options: list[Any],
    counts: dict[int, int],
    total_votes: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for opt in options:
        oid = int(opt.id)
        votes = counts.get(oid, 0)
        pct = round((votes / total_votes) * 100.0, 1) if total_votes > 0 else 0.0
        out.append({
            "id": oid,
            "label": str(opt.label),
            "sort_order": int(opt.sort_order or 0),
            "votes": votes,
            "percent": pct,
        })
    return out


def _poll_to_dict(
    row: Any,
    *,
    options_stats: list[dict[str, Any]] | None = None,
    viewer_steam_id: str | None = None,
    viewer_votes: list[int] | None = None,
) -> dict[str, Any]:
    now = _utcnow()
    ends = _parse_dt(row.ends_at)
    status = str(row.status or "DRAFT").upper()
    total_voters = int(row.total_voters or 0)
    total_option_votes = sum(o.get("votes", 0) for o in (options_stats or []))
    progress_pct = 0.0
    if ends and status == "ACTIVE":
        created = _parse_dt(row.created_at) or now
        span = (ends - created).total_seconds()
        elapsed = (now - created).total_seconds()
        if span > 0:
            progress_pct = round(min(100.0, max(0.0, (elapsed / span) * 100.0)), 1)

    d: dict[str, Any] = {
        "id": int(row.id),
        "title": str(row.title),
        "description": str(row.description or ""),
        "reward_amber": int(row.reward_amber or 0),
        "allow_multiple": bool(int(row.allow_multiple or 0)),
        "min_votes_valid": int(row.min_votes_valid) if row.min_votes_valid is not None else None,
        "ends_at": _iso(ends),
        "status": status,
        "status_label": POLL_STATUS_LABELS.get(status, status),
        "winner_option_id": int(row.winner_option_id) if row.winner_option_id else None,
        "result_valid": (
            None if row.result_valid is None else bool(int(row.result_valid))
        ),
        "total_voters": total_voters,
        "total_option_votes": total_option_votes,
        "time_progress_percent": progress_pct,
        "closed_at": _iso(_parse_dt(row.closed_at)),
        "created_at": _iso(_parse_dt(row.created_at)),
        "is_open": status == "ACTIVE" and ends is not None and now < ends,
        "has_ended": ends is not None and now >= ends,
    }
    if options_stats is not None:
        d["options"] = options_stats
    if viewer_steam_id:
        d["viewer_has_voted"] = bool(viewer_votes)
        d["viewer_option_ids"] = viewer_votes or []
    return d


def process_expired_polls(db: Session) -> int:
    """Encerra votações ACTIVE com prazo vencido e calcula resultado."""
    now = _utcnow()
    rows = db.execute(
        text(
            "SELECT id FROM community_polls "
            "WHERE status = 'ACTIVE' AND ends_at <= :now"
        ),
        {"now": now.replace(tzinfo=None)},
    ).fetchall()
    closed = 0
    for r in rows:
        close_poll(db, int(r.id), auto=True)
        closed += 1
    if closed:
        db.commit()
    return closed


def close_poll(db: Session, poll_id: int, *, auto: bool = False) -> dict[str, Any]:
    """Encerra votação, define vencedor e validade do resultado."""
    row = _fetch_poll_row(db, poll_id)
    if not row:
        raise ValueError("Votação não encontrada")
    status = str(row.status or "").upper()
    if status == "CLOSED":
        return get_poll_detail(db, poll_id)
    if status not in ("ACTIVE", "DRAFT"):
        raise ValueError("Só é possível encerrar votações ativas ou rascunhos publicados")

    options = _fetch_options(db, poll_id)
    counts = _vote_counts(db, poll_id)
    total_voters = _total_voters(db, poll_id)
    total_votes = sum(counts.values())

    min_valid = row.min_votes_valid
    result_valid = True
    if min_valid is not None and int(min_valid) > 0 and total_voters < int(min_valid):
        result_valid = False

    winner_id = None
    if result_valid and options and total_votes > 0:
        best = max(
            options,
            key=lambda o: (counts.get(int(o.id), 0), -int(o.sort_order or 0)),
        )
        if counts.get(int(best.id), 0) > 0:
            winner_id = int(best.id)

    now = _utcnow()
    db.execute(
        text(
            "UPDATE community_polls SET status = 'CLOSED', winner_option_id = :wid, "
            "result_valid = :rv, total_voters = :tv, closed_at = :now, updated_at = :now "
            "WHERE id = :id"
        ),
        {
            "id": poll_id,
            "wid": winner_id,
            "rv": 1 if result_valid else 0,
            "tv": total_voters,
            "now": now.replace(tzinfo=None),
        },
    )
    if not auto:
        db.commit()
    return get_poll_detail(db, poll_id)


def get_poll_detail(
    db: Session,
    poll_id: int,
    *,
    viewer_steam_id: str | None = None,
) -> dict[str, Any]:
    row = _fetch_poll_row(db, poll_id)
    if not row:
        raise ValueError("Votação não encontrada")
    options = _fetch_options(db, poll_id)
    counts = _vote_counts(db, poll_id)
    total_votes = sum(counts.values())
    stats = _build_option_stats(options, counts, total_votes)
    viewer_votes = (
        _user_voted_option_ids(db, poll_id, viewer_steam_id)
        if viewer_steam_id
        else None
    )
    return _poll_to_dict(
        row,
        options_stats=stats,
        viewer_steam_id=viewer_steam_id,
        viewer_votes=viewer_votes,
    )


def list_polls_public(
    db: Session,
    *,
    viewer_steam_id: str | None = None,
    include_closed: bool = True,
    limit: int = 50,
) -> list[dict[str, Any]]:
    process_expired_polls(db)
    statuses = ("ACTIVE",)
    if include_closed:
        statuses = ("ACTIVE", "CLOSED")
    placeholders = ", ".join(f":s{i}" for i in range(len(statuses)))
    params = {f"s{i}": s for i, s in enumerate(statuses)}
    params["lim"] = limit
    rows = db.execute(
        text(
            f"SELECT * FROM community_polls WHERE status IN ({placeholders}) "
            "ORDER BY CASE status WHEN 'ACTIVE' THEN 0 ELSE 1 END, ends_at DESC LIMIT :lim"
        ),
        params,
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        pid = int(row.id)
        options = _fetch_options(db, pid)
        counts = _vote_counts(db, pid)
        total_votes = sum(counts.values())
        stats = _build_option_stats(options, counts, total_votes)
        viewer_votes = (
            _user_voted_option_ids(db, pid, viewer_steam_id)
            if viewer_steam_id
            else None
        )
        out.append(
            _poll_to_dict(
                row,
                options_stats=stats,
                viewer_steam_id=viewer_steam_id,
                viewer_votes=viewer_votes,
            )
        )
    return out


def list_polls_admin(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    process_expired_polls(db)
    rows = db.execute(
        text(
            "SELECT * FROM community_polls ORDER BY id DESC LIMIT :lim"
        ),
        {"lim": limit},
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        pid = int(row.id)
        options = _fetch_options(db, pid)
        counts = _vote_counts(db, pid)
        total_votes = sum(counts.values())
        stats = _build_option_stats(options, counts, total_votes)
        out.append(_poll_to_dict(row, options_stats=stats))
    return out


def _validate_options(options: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    for i, opt in enumerate(options):
        label = str(opt.get("label") or "").strip()
        if not label:
            raise ValueError(f"Opção {i + 1}: texto vazio")
        if len(label) > _MAX_OPTION_LABEL:
            raise ValueError(f"Opção {i + 1}: texto muito longo")
        labels.append(label)
    if len(labels) < _MIN_OPTIONS:
        raise ValueError(f"Mínimo de {_MIN_OPTIONS} opções")
    if len(labels) > _MAX_OPTIONS:
        raise ValueError(f"Máximo de {_MAX_OPTIONS} opções")
    return labels


def create_poll(
    db: Session,
    *,
    title: str,
    description: str,
    options: list[dict[str, Any]],
    ends_at: Any,
    reward_amber: int = 0,
    allow_multiple: bool = False,
    min_votes_valid: int | None = None,
    publish: bool = True,
    created_by_steam_id: str | None = None,
) -> dict[str, Any]:
    title = str(title or "").strip()
    if not title or len(title) > _MAX_TITLE:
        raise ValueError("Título inválido")
    description = str(description or "").strip()[:_MAX_DESCRIPTION]
    ends = _parse_dt(ends_at)
    if not ends or ends <= _utcnow():
        raise ValueError("Data/hora final deve ser no futuro")
    labels = _validate_options(options)
    reward_amber = max(0, int(reward_amber or 0))
    if min_votes_valid is not None and int(min_votes_valid) < 0:
        raise ValueError("Votos mínimos inválidos")

    status = "ACTIVE" if publish else "DRAFT"
    now = _utcnow()
    url = str(getattr(db, "bind", None).url if getattr(db, "bind", None) else "").lower()
    if "sqlite" in url:
        cur = db.execute(
            text(
                "INSERT INTO community_polls "
                "(title, description, reward_amber, allow_multiple, min_votes_valid, "
                "ends_at, status, created_by_steam_id, created_at, updated_at) "
                "VALUES (:t, :d, :r, :am, :mv, :ends, :st, :by, :now, :now)"
            ),
            {
                "t": title,
                "d": description,
                "r": reward_amber,
                "am": 1 if allow_multiple else 0,
                "mv": min_votes_valid,
                "ends": ends.replace(tzinfo=None),
                "st": status,
                "by": created_by_steam_id,
                "now": now.replace(tzinfo=None),
            },
        )
        poll_id = int(cur.lastrowid)
    else:
        cur = db.execute(
            text(
                "INSERT INTO community_polls "
                "(title, description, reward_amber, allow_multiple, min_votes_valid, "
                "ends_at, status, created_by_steam_id) "
                "VALUES (:t, :d, :r, :am, :mv, :ends, :st, :by)"
            ),
            {
                "t": title,
                "d": description,
                "r": reward_amber,
                "am": 1 if allow_multiple else 0,
                "mv": min_votes_valid,
                "ends": ends.replace(tzinfo=None),
                "st": status,
                "by": created_by_steam_id,
            },
        )
        poll_id = int(cur.lastrowid)

    for i, label in enumerate(labels):
        db.execute(
            text(
                "INSERT INTO community_poll_options (poll_id, label, sort_order) "
                "VALUES (:pid, :lbl, :ord)"
            ),
            {"pid": poll_id, "lbl": label, "ord": i},
        )
    db.commit()
    return get_poll_detail(db, poll_id)


def update_poll(
    db: Session,
    poll_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    ends_at: Any = None,
    reward_amber: int | None = None,
    allow_multiple: bool | None = None,
    min_votes_valid: int | None = None,
    options: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    row = _fetch_poll_row(db, poll_id)
    if not row:
        raise ValueError("Votação não encontrada")
    status = str(row.status or "").upper()
    if status not in ("DRAFT", "ACTIVE"):
        raise ValueError("Só rascunhos ou votações ativas podem ser editadas")

    sets: list[str] = []
    params: dict[str, Any] = {"id": poll_id}
    if title is not None:
        t = str(title).strip()
        if not t:
            raise ValueError("Título inválido")
        sets.append("title = :title")
        params["title"] = t[:_MAX_TITLE]
    if description is not None:
        sets.append("description = :desc")
        params["desc"] = str(description).strip()[:_MAX_DESCRIPTION]
    if ends_at is not None:
        ends = _parse_dt(ends_at)
        if not ends:
            raise ValueError("Data final inválida")
        if status == "ACTIVE" and ends <= _utcnow():
            raise ValueError("Nova data final deve ser no futuro")
        sets.append("ends_at = :ends")
        params["ends"] = ends.replace(tzinfo=None)
    if reward_amber is not None:
        sets.append("reward_amber = :reward")
        params["reward"] = max(0, int(reward_amber))
    if allow_multiple is not None:
        sets.append("allow_multiple = :am")
        params["am"] = 1 if allow_multiple else 0
    if min_votes_valid is not None:
        mv = int(min_votes_valid) if min_votes_valid else None
        if mv is not None and mv < 0:
            raise ValueError("Votos mínimos inválidos")
        sets.append("min_votes_valid = :mv")
        params["mv"] = mv

    if sets:
        sets.append("updated_at = :now")
        params["now"] = _utcnow().replace(tzinfo=None)
        db.execute(
            text(f"UPDATE community_polls SET {', '.join(sets)} WHERE id = :id"),
            params,
        )

    if options is not None:
        if status != "DRAFT":
            raise ValueError("Opções só podem ser alteradas em rascunho")
        labels = _validate_options(options)
        db.execute(
            text("DELETE FROM community_poll_options WHERE poll_id = :pid"),
            {"pid": poll_id},
        )
        for i, label in enumerate(labels):
            db.execute(
                text(
                    "INSERT INTO community_poll_options (poll_id, label, sort_order) "
                    "VALUES (:pid, :lbl, :ord)"
                ),
                {"pid": poll_id, "lbl": label, "ord": i},
            )

    db.commit()
    return get_poll_detail(db, poll_id)


def publish_poll(db: Session, poll_id: int) -> dict[str, Any]:
    row = _fetch_poll_row(db, poll_id)
    if not row:
        raise ValueError("Votação não encontrada")
    if str(row.status).upper() != "DRAFT":
        raise ValueError("Só rascunhos podem ser publicados")
    ends = _parse_dt(row.ends_at)
    if not ends or ends <= _utcnow():
        raise ValueError("Defina uma data final futura antes de publicar")
    now = _utcnow()
    db.execute(
        text(
            "UPDATE community_polls SET status = 'ACTIVE', updated_at = :now WHERE id = :id"
        ),
        {"id": poll_id, "now": now.replace(tzinfo=None)},
    )
    db.commit()
    return get_poll_detail(db, poll_id)


def cancel_poll(db: Session, poll_id: int) -> dict[str, Any]:
    row = _fetch_poll_row(db, poll_id)
    if not row:
        raise ValueError("Votação não encontrada")
    if str(row.status).upper() == "CLOSED":
        raise ValueError("Votação já encerrada")
    now = _utcnow()
    db.execute(
        text(
            "UPDATE community_polls SET status = 'CANCELLED', updated_at = :now WHERE id = :id"
        ),
        {"id": poll_id, "now": now.replace(tzinfo=None)},
    )
    db.commit()
    return get_poll_detail(db, poll_id)


def cast_vote(
    db: Session,
    poll_id: int,
    steam_id: str,
    option_ids: list[int],
    *,
    notify_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    process_expired_polls(db)
    row = _fetch_poll_row(db, poll_id)
    if not row:
        raise ValueError("Votação não encontrada")
    status = str(row.status or "").upper()
    if status != "ACTIVE":
        raise ValueError("Esta votação não está aberta")
    ends = _parse_dt(row.ends_at)
    if ends and _utcnow() >= ends:
        close_poll(db, poll_id, auto=True)
        db.commit()
        raise ValueError("O prazo desta votação já encerrou")

    if not option_ids:
        raise ValueError("Selecione ao menos uma opção")

    allow_multiple = bool(int(row.allow_multiple or 0))
    unique_opts = list(dict.fromkeys(int(x) for x in option_ids))
    if not allow_multiple and len(unique_opts) != 1:
        raise ValueError("Esta votação permite apenas uma opção")

    valid_ids = {int(o.id) for o in _fetch_options(db, poll_id)}
    for oid in unique_opts:
        if oid not in valid_ids:
            raise ValueError("Opção inválida")

    existing = _user_voted_option_ids(db, poll_id, steam_id)
    if existing:
        raise ValueError("Você já votou nesta enquete")

    reward = int(row.reward_amber or 0)
    now = _utcnow()
    for oid in unique_opts:
        db.execute(
            text(
                "INSERT INTO community_poll_votes "
                "(poll_id, option_id, steam_id, reward_granted, created_at) "
                "VALUES (:pid, :oid, :sid, :rg, :now)"
            ),
            {
                "pid": poll_id,
                "oid": oid,
                "sid": steam_id,
                "rg": 1 if reward > 0 else 0,
                "now": now.replace(tzinfo=None),
            },
        )

    if reward > 0:
        _credit_points(db, steam_id, reward)

    total_voters = _total_voters(db, poll_id)
    db.execute(
        text("UPDATE community_polls SET total_voters = :tv, updated_at = :now WHERE id = :id"),
        {"id": poll_id, "tv": total_voters, "now": now.replace(tzinfo=None)},
    )
    db.commit()

    if notify_fn and reward > 0:
        try:
            notify_fn(
                db,
                steam_id=steam_id,
                type="poll_reward",
                title="Recompensa de votação",
                body=f"Você recebeu {reward} Âmbares por participar da enquete «{row.title}».",
                link_type="poll",
                link_id=str(poll_id),
            )
        except Exception:
            pass

    return get_poll_detail(db, poll_id, viewer_steam_id=steam_id)


def poll_meta() -> dict[str, Any]:
    return {
        "statuses": [{"id": k, "label": v} for k, v in POLL_STATUS_LABELS.items()],
        "min_options": _MIN_OPTIONS,
        "max_options": _MAX_OPTIONS,
    }
