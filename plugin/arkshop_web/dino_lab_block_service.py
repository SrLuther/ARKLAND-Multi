"""Bloqueio de venda no mercado — criaturas e linhagem do Dino Lab."""
from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

log = logging.getLogger("arkshop_web.dino_lab_block")

DINO_LAB_BLOCK_MESSAGE = (
    "este dino ou sua linhagem pertence ao Dino Lab e nao pode ser vendido."
)

PLAYER_CHECK_DISCLAIMER = (
    "Verificacao apenas do ID informado. Nao inclui ancestralidade."
)

PLAYER_CHECK_BLOCKED_MESSAGE = (
    "Este ID pertence ao Dino Lab e nao pode ser encomendado."
)

PLAYER_CHECK_ALLOWED_MESSAGE = (
    "Este ID nao consta na lista de bloqueio do Dino Lab."
)

AuditFn = Callable[..., None] | None


def canonical_id(dino_id1: int, dino_id2: int) -> str:
    return f"{int(dino_id1) & 0xFFFFFFFF:08X}-{int(dino_id2) & 0xFFFFFFFF:08X}"


def is_dino_lab_block_debug(settings: dict[str, Any] | None = None) -> bool:
    if not settings:
        return False
    return bool(settings.get("dino_lab_block_debug"))


def new_trace_id(prefix: str = "dlb") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def audit_dino_lab_block_event(
    audit_fn: AuditFn,
    event_type: str,
    *,
    severity: str = "info",
    source: str = "dino_lab_block",
    **kwargs: Any,
) -> None:
    """Registra evento estruturado via audit_event do app (se disponível)."""
    if not audit_fn:
        return
    payload = {k: v for k, v in kwargs.items() if v is not None}
    audit_fn(event_type, severity=severity, source=source, **payload)


def append_debug_fields(
    result: dict[str, Any],
    *,
    debug: bool,
    trace_id: str | None = None,
    match: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not debug:
        return result
    if trace_id:
        result["trace_id"] = trace_id
    if match:
        if match.get("canonical_id"):
            result["canonical_id"] = match["canonical_id"]
        mp = match.get("matched_pair")
        if mp:
            result["matched_pair"] = mp
    return result


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _table_exists(conn: Any, table: str) -> bool:
    row = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
        {"t": table},
    ).fetchone()
    return row is not None


def _repair_dino_ids_from_canonical(conn: Any) -> int:
    """Repara dino_id1/2 a partir do canonical_id (corrige overflow INT signed)."""
    rows = conn.execute(
        text("SELECT id, canonical_id, dino_id1, dino_id2 FROM dino_lab_blocked_ids")
    ).fetchall()
    fixed = 0
    for row in rows:
        try:
            mapping = row._mapping
            row_id = int(mapping["id"])
            canon = str(mapping.get("canonical_id") or "").strip().upper()
            cur1 = int(mapping.get("dino_id1", 0)) & 0xFFFFFFFF
            cur2 = int(mapping.get("dino_id2", 0)) & 0xFFFFFFFF
        except Exception:
            row_id = int(row[0])
            canon = str(row[1] or "").strip().upper()
            cur1 = int(row[2] or 0) & 0xFFFFFFFF
            cur2 = int(row[3] or 0) & 0xFFFFFFFF
        if "-" not in canon:
            continue
        left, right = canon.split("-", 1)
        try:
            want1 = int(left, 16) & 0xFFFFFFFF
            want2 = int(right, 16) & 0xFFFFFFFF
        except ValueError:
            continue
        if want1 == cur1 and want2 == cur2:
            continue
        conn.execute(
            text(
                "UPDATE dino_lab_blocked_ids "
                "SET dino_id1 = :id1, dino_id2 = :id2 WHERE id = :rid"
            ),
            {"id1": want1, "id2": want2, "rid": row_id},
        )
        fixed += 1
    return fixed


def ensure_dino_lab_block_schema(engine: Engine) -> None:
    """Cria tabela dino_lab_blocked_ids e repara IDs (idempotente)."""
    is_sqlite = "sqlite" in str(engine.url).lower()
    with engine.connect() as conn:
        if is_sqlite:
            if not _table_exists(conn, "dino_lab_blocked_ids"):
                conn.execute(
                    text(
                        "CREATE TABLE dino_lab_blocked_ids ("
                        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                        "dino_id1 INTEGER NOT NULL,"
                        "dino_id2 INTEGER NOT NULL,"
                        "canonical_id VARCHAR(24) NOT NULL,"
                        "order_id VARCHAR(64) NOT NULL,"
                        "steam_id VARCHAR(32) NOT NULL,"
                        "source VARCHAR(32) NOT NULL DEFAULT 'dino_lab',"
                        "role VARCHAR(16) NOT NULL DEFAULT 'self',"
                        "generation SMALLINT NULL,"
                        "delivered_at DATETIME NOT NULL,"
                        "created_at DATETIME NOT NULL,"
                        "UNIQUE (dino_id1, dino_id2)"
                        ")"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_dlb_canonical "
                        "ON dino_lab_blocked_ids (canonical_id)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_dlb_order "
                        "ON dino_lab_blocked_ids (order_id)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_dlb_steam "
                        "ON dino_lab_blocked_ids (steam_id)"
                    )
                )
                log.info("dino_lab_blocked_ids criada (sqlite)")
            fixed = _repair_dino_ids_from_canonical(conn)
            if fixed:
                log.info("dino_lab_blocked_ids: reparados %s id(s) via canonical", fixed)
            conn.commit()
            return

        row = conn.execute(text("SHOW TABLES LIKE 'dino_lab_blocked_ids'")).fetchone()
        if row is None:
            conn.execute(
                text(
                    "CREATE TABLE dino_lab_blocked_ids ("
                    "id INT AUTO_INCREMENT PRIMARY KEY,"
                    "dino_id1 INT UNSIGNED NOT NULL,"
                    "dino_id2 INT UNSIGNED NOT NULL,"
                    "canonical_id VARCHAR(24) NOT NULL,"
                    "order_id VARCHAR(64) NOT NULL,"
                    "steam_id VARCHAR(32) NOT NULL,"
                    "source VARCHAR(32) NOT NULL DEFAULT 'dino_lab',"
                    "role VARCHAR(16) NOT NULL DEFAULT 'self',"
                    "generation SMALLINT NULL,"
                    "delivered_at DATETIME NOT NULL,"
                    "created_at DATETIME NOT NULL,"
                    "UNIQUE KEY uq_dino_pair (dino_id1, dino_id2),"
                    "INDEX idx_canonical (canonical_id),"
                    "INDEX idx_order (order_id),"
                    "INDEX idx_steam (steam_id)"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                )
            )
            log.info("dino_lab_blocked_ids criada (mysql)")
        else:
            # Garante UNSIGNED — IDs ARK passam de 2^31-1 (ex.: 89271B4F).
            try:
                conn.execute(
                    text(
                        "ALTER TABLE dino_lab_blocked_ids "
                        "MODIFY dino_id1 INT UNSIGNED NOT NULL, "
                        "MODIFY dino_id2 INT UNSIGNED NOT NULL"
                    )
                )
            except Exception as exc:
                log.warning("dino_lab_blocked_ids ALTER UNSIGNED falhou: %s", exc)
        fixed = _repair_dino_ids_from_canonical(conn)
        if fixed:
            log.info("dino_lab_blocked_ids: reparados %s id(s) via canonical", fixed)
        conn.commit()


def parse_dino_id_input(body: dict[str, Any] | None) -> tuple[int, int] | None:
    """Interpreta ID de criatura a partir de JSON flexível (par, canonical ou string colada)."""
    if not isinstance(body, dict):
        return None

    if body.get("dino_id1") is not None and body.get("dino_id2") is not None:
        return _normalize_pair(body.get("dino_id1"), body.get("dino_id2"))

    raw_canon = str(body.get("canonical_id") or body.get("dino_id") or body.get("id") or "").strip()
    if not raw_canon:
        for key in ("input", "value", "query"):
            alt = str(body.get(key) or "").strip()
            if alt:
                raw_canon = alt
                break
    if not raw_canon:
        return None

    compact = re.sub(r"\s+", "", raw_canon).upper()
    if "-" in compact:
        left, right = compact.split("-", 1)
        for parser in (lambda s: int(s, 16), int):
            try:
                return _normalize_pair(parser(left), parser(right))
            except (TypeError, ValueError):
                continue
        return None

    if compact.isdigit():
        # Único decimal ambíguo — exige par explícito.
        return None

    if re.fullmatch(r"[0-9A-F]{16}", compact):
        try:
            id1 = int(compact[:8], 16)
            id2 = int(compact[8:], 16)
            return _normalize_pair(id1, id2)
        except ValueError:
            return None

    return None


def check_dino_id_from_body(db: Session, body: dict[str, Any] | None) -> dict[str, Any]:
    """Verificação jogador: parse flexível + match exato (sem ancestrais)."""
    pair = parse_dino_id_input(body if isinstance(body, dict) else {})
    if not pair:
        return {
            "ok": False,
            "error": "invalid_id",
            "message": "Informe o par de IDs (dino_id1 e dino_id2) ou o ID canonico (ex.: AABBCCDD-11223344).",
            "disclaimer": PLAYER_CHECK_DISCLAIMER,
        }
    return check_single_id_blocked(db, pair[0], pair[1])


def check_single_id_blocked(db: Session, dino_id1: int, dino_id2: int) -> dict[str, Any]:
    """Verifica bloqueio por match exato do par — sem ancestralidade."""
    pair = _normalize_pair(dino_id1, dino_id2)
    if not pair:
        return {
            "ok": False,
            "error": "invalid_id",
            "message": "ID de criatura invalido.",
            "disclaimer": PLAYER_CHECK_DISCLAIMER,
        }

    match = lookup_blocked_match(db, [pair])
    if match:
        return {
            "ok": True,
            "blocked": True,
            "order_id": match.get("order_id", ""),
            "canonical_id": match.get("canonical_id") or canonical_id(pair[0], pair[1]),
            "matched_pair": match.get("matched_pair") or [pair[0], pair[1]],
            "message": PLAYER_CHECK_BLOCKED_MESSAGE,
            "disclaimer": PLAYER_CHECK_DISCLAIMER,
        }

    return {
        "ok": True,
        "blocked": False,
        "canonical_id": canonical_id(pair[0], pair[1]),
        "matched_pair": [pair[0], pair[1]],
        "message": PLAYER_CHECK_ALLOWED_MESSAGE,
        "disclaimer": PLAYER_CHECK_DISCLAIMER,
    }


def _normalize_pair(dino_id1: Any, dino_id2: Any) -> tuple[int, int] | None:
    try:
        id1 = int(dino_id1) & 0xFFFFFFFF
        id2 = int(dino_id2) & 0xFFFFFFFF
    except (TypeError, ValueError):
        return None
    if id1 == 0 and id2 == 0:
        return None
    return id1, id2


def _as_signed_i32(value: int) -> int:
    """Equivente int32 assinado (MySQL INT legacy / overflow)."""
    u = int(value) & 0xFFFFFFFF
    return u if u < 0x80000000 else u - 0x100000000


def _normalize_id_pairs(id_pairs: list[tuple[int, int]] | list[Any]) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for raw in id_pairs or []:
        if not isinstance(raw, (list, tuple)) or len(raw) < 2:
            continue
        pair = _normalize_pair(raw[0], raw[1])
        if pair and pair not in seen:
            seen.add(pair)
            pairs.append(pair)
    return pairs


def _build_blocked_lookup_sql(
    pairs: list[tuple[int, int]],
) -> tuple[str, dict[str, Any]]:
    """Match por par unsigned, par signed (legacy) e canonical_id VARCHAR."""
    clauses: list[str] = []
    params: dict[str, Any] = {}
    for i, (id1, id2) in enumerate(pairs):
        clauses.append(f"(dino_id1 = :id1_{i} AND dino_id2 = :id2_{i})")
        params[f"id1_{i}"] = id1
        params[f"id2_{i}"] = id2
        s1 = _as_signed_i32(id1)
        s2 = _as_signed_i32(id2)
        if s1 != id1 or s2 != id2:
            clauses.append(f"(dino_id1 = :s1_{i} AND dino_id2 = :s2_{i})")
            params[f"s1_{i}"] = s1
            params[f"s2_{i}"] = s2
        clauses.append(f"canonical_id = :canon_{i}")
        params[f"canon_{i}"] = canonical_id(id1, id2)
    return " OR ".join(clauses), params


def _insert_blocked_row(
    db: Session,
    *,
    dino_id1: int,
    dino_id2: int,
    order_id: str,
    steam_id: str,
    role: str,
    generation: int | None,
    source: str,
    delivered_at: datetime,
    created_at: datetime,
) -> bool:
    canon = canonical_id(dino_id1, dino_id2)
    result = db.execute(
        text(
            "INSERT OR IGNORE INTO dino_lab_blocked_ids "
            "(dino_id1, dino_id2, canonical_id, order_id, steam_id, source, role, "
            "generation, delivered_at, created_at) "
            "VALUES (:id1, :id2, :canon, :oid, :sid, :src, :role, :gen, :del_at, :crt_at)"
            if "sqlite" in str(db.bind.url).lower()
            else "INSERT IGNORE INTO dino_lab_blocked_ids "
            "(dino_id1, dino_id2, canonical_id, order_id, steam_id, source, role, "
            "generation, delivered_at, created_at) "
            "VALUES (:id1, :id2, :canon, :oid, :sid, :src, :role, :gen, :del_at, :crt_at)"
        ),
        {
            "id1": dino_id1,
            "id2": dino_id2,
            "canon": canon,
            "oid": order_id,
            "sid": steam_id,
            "src": source,
            "role": role,
            "gen": generation,
            "del_at": delivered_at.replace(tzinfo=None),
            "crt_at": created_at.replace(tzinfo=None),
        },
    )
    return int(getattr(result, "rowcount", 0) or 0) > 0


def register_blocked_dino_ids(
    db: Session,
    order_id: str,
    steam_id: str,
    identities: dict[str, Any],
    *,
    source: str = "dino_lab",
) -> int:
    """Registra ID da criatura entregue e ancestrais presentes."""
    order_id = str(order_id or "").strip()
    steam_id = str(steam_id or "").strip()
    if not order_id or not steam_id:
        return 0

    now = _utcnow()
    inserted = 0
    self_pair = _normalize_pair(identities.get("dino_id1"), identities.get("dino_id2"))
    if self_pair:
        if _insert_blocked_row(
            db,
            dino_id1=self_pair[0],
            dino_id2=self_pair[1],
            order_id=order_id,
            steam_id=steam_id,
            role="self",
            generation=0,
            source=source,
            delivered_at=now,
            created_at=now,
        ):
            inserted += 1

    ancestors = identities.get("ancestors") or []
    if isinstance(ancestors, list):
        for anc in ancestors:
            if not isinstance(anc, dict):
                continue
            pair = _normalize_pair(anc.get("dino_id1"), anc.get("dino_id2"))
            if not pair:
                continue
            gen_raw = anc.get("generation")
            try:
                generation = int(gen_raw) if gen_raw is not None else None
            except (TypeError, ValueError):
                generation = None
            if _insert_blocked_row(
                db,
                dino_id1=pair[0],
                dino_id2=pair[1],
                order_id=order_id,
                steam_id=steam_id,
                role="ancestor",
                generation=generation,
                source=source,
                delivered_at=now,
                created_at=now,
            ):
                inserted += 1

    if inserted:
        log.info(
            "dino_lab_block: registered %s id(s) for order %s steam %s",
            inserted,
            order_id,
            steam_id,
        )
    return inserted


def lookup_blocked_from_metadata(
    db: Session,
    metadata: dict[str, Any],
) -> dict[str, Any] | None:
    return lookup_blocked_match(db, extract_id_pairs_from_metadata(metadata))


def is_any_id_blocked(db: Session, id_pairs: list[tuple[int, int]]) -> bool:
    return check_blocked_reason(db, id_pairs) is not None


def check_blocked_reason(db: Session, id_pairs: list[tuple[int, int]]) -> str | None:
    """Retorna mensagem de bloqueio ou None se permitido."""
    match = lookup_blocked_match(db, id_pairs)
    return match.get("message") if match else None


def extract_id_pairs_from_metadata(metadata: dict[str, Any]) -> list[tuple[int, int]]:
    """Extrai pares de ID do metadata de cryo (dino_identity + campos soltos)."""
    if not isinstance(metadata, dict):
        return []
    pairs: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()

    def _add(pair: tuple[int, int] | None) -> None:
        if pair and pair not in seen:
            seen.add(pair)
            pairs.append(pair)

    di = metadata.get("dino_identity")
    if isinstance(di, dict):
        _add(_normalize_pair(di.get("dino_id1"), di.get("dino_id2")))
        for anc in di.get("ancestors") or []:
            if isinstance(anc, dict):
                _add(_normalize_pair(anc.get("dino_id1"), anc.get("dino_id2")))
        raw_canon = str(di.get("canonical_id") or "").strip()
        if raw_canon:
            parsed = parse_dino_id_input({"canonical_id": raw_canon})
            _add(parsed)

    _add(_normalize_pair(metadata.get("dino_id1"), metadata.get("dino_id2")))
    raw_top = str(metadata.get("canonical_id") or "").strip()
    if raw_top:
        _add(parse_dino_id_input({"canonical_id": raw_top}))

    raw_pairs = metadata.get("dino_id_pairs")
    if isinstance(raw_pairs, list):
        for item in raw_pairs:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                _add(_normalize_pair(item[0], item[1]))

    return pairs


def enforce_market_dino_identity(metadata: dict[str, Any]) -> list[tuple[int, int]]:
    """Fail-closed: anúncio de cryo exige pelo menos um par de IDs legível."""
    pairs = extract_id_pairs_from_metadata(metadata if isinstance(metadata, dict) else {})
    if not pairs:
        raise ValueError(
            "Nao foi possivel validar a identidade do dino para o Comercio. "
            "Tente /enviar novamente."
        )
    return pairs


def check_blocked_from_metadata(db: Session, metadata: dict[str, Any]) -> str | None:
    return check_blocked_reason(db, extract_id_pairs_from_metadata(metadata))


def lookup_blocked_match(
    db: Session,
    id_pairs: list[tuple[int, int]],
) -> dict[str, Any] | None:
    pairs = _normalize_id_pairs(id_pairs)
    if not pairs:
        return None

    where_sql, params = _build_blocked_lookup_sql(pairs)
    row = db.execute(
        text(
            "SELECT order_id, source, canonical_id, dino_id1, dino_id2 "
            "FROM dino_lab_blocked_ids "
            f"WHERE {where_sql} LIMIT 1"
        ),
        params,
    ).fetchone()
    if not row:
        return None
    try:
        mapping = row._mapping
        order_id = str(mapping.get("order_id", ""))
        source = str(mapping.get("source", "dino_lab"))
        canon = str(mapping.get("canonical_id", ""))
        id1 = int(mapping.get("dino_id1", 0)) & 0xFFFFFFFF
        id2 = int(mapping.get("dino_id2", 0)) & 0xFFFFFFFF
    except Exception:
        order_id = str(row[0])
        source = str(row[1]) if len(row) > 1 else "dino_lab"
        canon = str(row[2]) if len(row) > 2 else canonical_id(
            int(row[3]) if len(row) > 3 else 0,
            int(row[4]) if len(row) > 4 else 0,
        )
        id1 = int(row[3]) & 0xFFFFFFFF if len(row) > 3 else 0
        id2 = int(row[4]) & 0xFFFFFFFF if len(row) > 4 else 0
    return {
        "blocked": True,
        "reason": "dino_lab_blocked",
        "source": source,
        "order_id": order_id,
        "canonical_id": canon or canonical_id(id1, id2),
        "matched_pair": [id1, id2],
        "message": DINO_LAB_BLOCK_MESSAGE,
    }


def get_dino_lab_block_stats(db: Session) -> dict[str, Any]:
    total = db.execute(text("SELECT COUNT(*) FROM dino_lab_blocked_ids")).scalar() or 0
    self_count = db.execute(
        text("SELECT COUNT(*) FROM dino_lab_blocked_ids WHERE role = 'self'")
    ).scalar() or 0
    ancestor_count = db.execute(
        text("SELECT COUNT(*) FROM dino_lab_blocked_ids WHERE role = 'ancestor'")
    ).scalar() or 0
    orders = db.execute(
        text("SELECT COUNT(DISTINCT order_id) FROM dino_lab_blocked_ids")
    ).scalar() or 0
    return {
        "total_rows": int(total),
        "self_ids": int(self_count),
        "ancestor_ids": int(ancestor_count),
        "distinct_orders": int(orders),
    }


def list_recent_blocked_ids(db: Session, *, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 200))
    rows = db.execute(
        text(
            "SELECT dino_id1, dino_id2, canonical_id, order_id, steam_id, source, "
            "role, generation, delivered_at "
            "FROM dino_lab_blocked_ids "
            "ORDER BY id DESC LIMIT :lim"
        ),
        {"lim": limit},
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(_row_to_blocked_dict(row))
    return out


def get_dino_lab_block_debug_snapshot(db: Session, *, limit: int = 50) -> dict[str, Any]:
    return {
        "stats": get_dino_lab_block_stats(db),
        "recent": list_recent_blocked_ids(db, limit=limit),
    }


def _row_to_blocked_dict(row: Any) -> dict[str, Any]:
    try:
        mapping = row._mapping
        return {
            "canonical_id": str(mapping.get("canonical_id", "")),
            "order_id": str(mapping.get("order_id", "")),
            "steam_id": str(mapping.get("steam_id", "")),
            "source": str(mapping.get("source", "dino_lab")),
            "role": str(mapping.get("role", "self")),
            "generation": mapping.get("generation"),
            "delivered_at": str(mapping.get("delivered_at", "")),
            "matched_pair": [
                int(mapping.get("dino_id1", 0)) & 0xFFFFFFFF,
                int(mapping.get("dino_id2", 0)) & 0xFFFFFFFF,
            ],
        }
    except Exception:
        return {
            "canonical_id": str(row[2]) if len(row) > 2 else "",
            "order_id": str(row[3]) if len(row) > 3 else "",
            "steam_id": str(row[4]) if len(row) > 4 else "",
            "source": str(row[5]) if len(row) > 5 else "dino_lab",
            "role": str(row[6]) if len(row) > 6 else "self",
            "generation": row[7] if len(row) > 7 else None,
            "delivered_at": str(row[8]) if len(row) > 8 else "",
            "matched_pair": [
                int(row[0]) & 0xFFFFFFFF,
                int(row[1]) & 0xFFFFFFFF,
            ],
        }


def _parse_date_filter(value: str | None, *, end_of_day: bool = False) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if len(raw) >= 10:
        try:
            dt = datetime.strptime(raw[:10], "%Y-%m-%d")
            if end_of_day:
                dt = dt.replace(hour=23, minute=59, second=59)
            return dt
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _build_search_q_clause(q: str) -> tuple[str, dict[str, Any]]:
    """Monta cláusula SQL para busca livre (hex parcial, par id1-id2 ou id decimal)."""
    raw = str(q or "").strip()
    if not raw:
        return "", {}

    if "-" in raw:
        left, right = raw.split("-", 1)
        left = left.strip()
        right = right.strip()
        for parser in (lambda s: int(s, 16), int):
            try:
                id1 = parser(left) & 0xFFFFFFFF
                id2 = parser(right) & 0xFFFFFFFF
                return (
                    "(dino_id1 = :q_id1 AND dino_id2 = :q_id2)",
                    {"q_id1": id1, "q_id2": id2},
                )
            except (TypeError, ValueError):
                continue
        canon = re.sub(r"\s+", "", raw).upper()
        return "canonical_id LIKE :q_canon", {"q_canon": f"%{canon}%"}

    if raw.isdigit():
        dec = int(raw) & 0xFFFFFFFF
        return "(dino_id1 = :q_dec OR dino_id2 = :q_dec)", {"q_dec": dec}

    compact = re.sub(r"\s+", "", raw).upper()
    if re.fullmatch(r"[0-9A-F]+", compact):
        return "canonical_id LIKE :q_canon", {"q_canon": f"%{compact}%"}

    return "canonical_id LIKE :q_canon", {"q_canon": f"%{compact}%"}


def search_blocked_ids(
    db: Session,
    *,
    q: str | None = None,
    steam_id: str | None = None,
    order_id: str | None = None,
    source: str | None = None,
    role: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    per_page: int = 10,
) -> dict[str, Any]:
    """Lista IDs bloqueados com filtros e paginação."""
    page = max(1, int(page or 1))
    per_page = max(1, min(int(per_page or 10), 200))
    offset = (page - 1) * per_page

    clauses: list[str] = []
    params: dict[str, Any] = {}

    q_clause, q_params = _build_search_q_clause(str(q or "").strip())
    if q_clause:
        clauses.append(q_clause)
        params.update(q_params)

    steam = str(steam_id or "").strip()
    if steam:
        clauses.append("steam_id = :steam_id")
        params["steam_id"] = steam

    oid = str(order_id or "").strip()
    if oid:
        clauses.append("order_id = :order_id")
        params["order_id"] = oid

    src = str(source or "").strip()
    if src:
        clauses.append("source = :source")
        params["source"] = src

    rl = str(role or "").strip()
    if rl:
        clauses.append("role = :role")
        params["role"] = rl

    dt_from = _parse_date_filter(date_from)
    if dt_from:
        clauses.append("delivered_at >= :date_from")
        params["date_from"] = dt_from

    dt_to = _parse_date_filter(date_to, end_of_day=True)
    if dt_to:
        clauses.append("delivered_at <= :date_to")
        params["date_to"] = dt_to

    where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""

    total = int(
        db.execute(text(f"SELECT COUNT(*) FROM dino_lab_blocked_ids{where_sql}"), params).scalar()
        or 0
    )

    list_params = {**params, "lim": per_page, "off": offset}
    rows = db.execute(
        text(
            "SELECT dino_id1, dino_id2, canonical_id, order_id, steam_id, source, "
            "role, generation, delivered_at "
            f"FROM dino_lab_blocked_ids{where_sql} "
            "ORDER BY id DESC LIMIT :lim OFFSET :off"
        ),
        list_params,
    ).fetchall()

    items = [_row_to_blocked_dict(row) for row in rows]
    pages = max(1, (total + per_page - 1) // per_page) if total else 1

    return {
        "total": total,
        "count": len(items),
        "page": page,
        "per_page": per_page,
        "pages": pages,
        "rows": items,
    }


def get_dino_lab_block_stats_api(db: Session) -> dict[str, Any]:
    """Estatísticas para painel admin (total, por source, últimas 24h)."""
    base = get_dino_lab_block_stats(db)
    by_source_rows = db.execute(
        text("SELECT source, COUNT(*) AS cnt FROM dino_lab_blocked_ids GROUP BY source")
    ).fetchall()
    by_source: dict[str, int] = {}
    for row in by_source_rows:
        try:
            by_source[str(row._mapping["source"])] = int(row._mapping["cnt"])
        except Exception:
            by_source[str(row[0])] = int(row[1])

    cutoff = (_utcnow() - timedelta(hours=24)).replace(tzinfo=None)
    last_24h = int(
        db.execute(
            text(
                "SELECT COUNT(*) FROM dino_lab_blocked_ids WHERE delivered_at >= :cutoff"
            ),
            {"cutoff": cutoff},
        ).scalar()
        or 0
    )

    return {
        **base,
        "by_source": by_source,
        "last_24h": last_24h,
    }
