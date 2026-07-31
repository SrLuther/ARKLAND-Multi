"""Auditoria pública de dinos gerados via catálogo (L1 / L200)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from catalog_dino_public_code import (
    build_public_code,
    code_prefix,
    lookup_catalog_entry,
    parse_species_key,
    resolve_gender_digit,
    seed_families_from_catalog,
)

log = logging.getLogger("arkshop_web.catalog_dino_audit")

_ALLOWED_LEVELS = frozenset({1, 200})
_STEAMID_RE = re.compile(r"^7656119\d{10}$")


def canonical_id(dino_id1: int, dino_id2: int) -> str:
    return f"{int(dino_id1) & 0xFFFFFFFF:08X}-{int(dino_id2) & 0xFFFFFFFF:08X}"


def species_key_from_item_id(item_id: str) -> str:
    s = str(item_id or "").strip()
    if s.endswith("_pack10"):
        s = s[: -len("_pack10")]
    if s.endswith("_l200"):
        s = s[: -len("_l200")]
    return s


def mask_display_name(name: str) -> str:
    """Mesmo padrão da loteria — evita PII completa na listagem pública."""
    src = (name or "Jogador").strip() or "Jogador"
    if _STEAMID_RE.match(src):
        return "Jogador"
    if len(src) <= 3:
        return "***"
    tail_n = 0 if len(src) <= 6 else min(3, max(1, len(src) - 6))
    return src[:3] + "***" + (src[-tail_n:] if tail_n else "")


def _table_exists(conn: Any, name: str) -> bool:
    row = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": name},
    ).fetchone()
    return row is not None


def _column_names(conn: Any, table: str, *, is_sqlite: bool) -> set[str]:
    if is_sqlite:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return {str(r[1]) for r in rows}
    rows = conn.execute(text(f"SHOW COLUMNS FROM {table}")).fetchall()
    return {str(r[0]) for r in rows}


def _ensure_column(
    conn: Any,
    *,
    is_sqlite: bool,
    table: str,
    column: str,
    ddl_sqlite: str,
    ddl_mysql: str,
) -> None:
    cols = _column_names(conn, table, is_sqlite=is_sqlite)
    if column in cols:
        return
    conn.execute(text(ddl_sqlite if is_sqlite else ddl_mysql))
    log.info("catalog_dino_generations: coluna %s adicionada", column)


def ensure_catalog_dino_generations_schema(engine: Engine) -> None:
    """Cria tabela catalog_dino_generations (idempotente) + colunas public_code/gender."""
    is_sqlite = "sqlite" in str(engine.url).lower()
    with engine.connect() as conn:
        if is_sqlite:
            if not _table_exists(conn, "catalog_dino_generations"):
                conn.execute(
                    text(
                        "CREATE TABLE catalog_dino_generations ("
                        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                        "dino_id1 INTEGER NOT NULL,"
                        "dino_id2 INTEGER NOT NULL,"
                        "canonical_id VARCHAR(24) NOT NULL,"
                        "public_code VARCHAR(16) NOT NULL DEFAULT '',"
                        "gender_digit SMALLINT NOT NULL DEFAULT 3,"
                        "order_id VARCHAR(64) NOT NULL,"
                        "steam_id VARCHAR(32) NOT NULL,"
                        "item_id VARCHAR(128) NOT NULL,"
                        "level SMALLINT NOT NULL,"
                        "species_key VARCHAR(128) NOT NULL DEFAULT '',"
                        "display_name VARCHAR(128) NULL,"
                        "delivered_at DATETIME NOT NULL,"
                        "created_at DATETIME NOT NULL,"
                        "UNIQUE (dino_id1, dino_id2)"
                        ")"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_cdg_canonical "
                        "ON catalog_dino_generations (canonical_id)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_cdg_public "
                        "ON catalog_dino_generations (public_code)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_cdg_order "
                        "ON catalog_dino_generations (order_id)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_cdg_level "
                        "ON catalog_dino_generations (level)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_cdg_species "
                        "ON catalog_dino_generations (species_key)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_cdg_delivered "
                        "ON catalog_dino_generations (delivered_at)"
                    )
                )
                log.info("catalog_dino_generations criada (sqlite)")
            else:
                _ensure_column(
                    conn,
                    is_sqlite=True,
                    table="catalog_dino_generations",
                    column="public_code",
                    ddl_sqlite=(
                        "ALTER TABLE catalog_dino_generations "
                        "ADD COLUMN public_code VARCHAR(16) NOT NULL DEFAULT ''"
                    ),
                    ddl_mysql="",
                )
                _ensure_column(
                    conn,
                    is_sqlite=True,
                    table="catalog_dino_generations",
                    column="gender_digit",
                    ddl_sqlite=(
                        "ALTER TABLE catalog_dino_generations "
                        "ADD COLUMN gender_digit SMALLINT NOT NULL DEFAULT 3"
                    ),
                    ddl_mysql="",
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_cdg_public "
                        "ON catalog_dino_generations (public_code)"
                    )
                )
            conn.commit()
            return

        row = conn.execute(text("SHOW TABLES LIKE 'catalog_dino_generations'")).fetchone()
        if row is None:
            conn.execute(
                text(
                    "CREATE TABLE catalog_dino_generations ("
                    "id INT AUTO_INCREMENT PRIMARY KEY,"
                    "dino_id1 INT UNSIGNED NOT NULL,"
                    "dino_id2 INT UNSIGNED NOT NULL,"
                    "canonical_id VARCHAR(24) NOT NULL,"
                    "public_code VARCHAR(16) NOT NULL DEFAULT '',"
                    "gender_digit SMALLINT NOT NULL DEFAULT 3,"
                    "order_id VARCHAR(64) NOT NULL,"
                    "steam_id VARCHAR(32) NOT NULL,"
                    "item_id VARCHAR(128) NOT NULL,"
                    "level SMALLINT NOT NULL,"
                    "species_key VARCHAR(128) NOT NULL DEFAULT '',"
                    "display_name VARCHAR(128) NULL,"
                    "delivered_at DATETIME NOT NULL,"
                    "created_at DATETIME NOT NULL,"
                    "UNIQUE KEY uq_cdg_dino_pair (dino_id1, dino_id2),"
                    "INDEX idx_cdg_canonical (canonical_id),"
                    "INDEX idx_cdg_public (public_code),"
                    "INDEX idx_cdg_order (order_id),"
                    "INDEX idx_cdg_level (level),"
                    "INDEX idx_cdg_species (species_key),"
                    "INDEX idx_cdg_delivered (delivered_at)"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                )
            )
            log.info("catalog_dino_generations criada (mysql)")
        else:
            _ensure_column(
                conn,
                is_sqlite=False,
                table="catalog_dino_generations",
                column="public_code",
                ddl_sqlite="",
                ddl_mysql=(
                    "ALTER TABLE catalog_dino_generations "
                    "ADD COLUMN public_code VARCHAR(16) NOT NULL DEFAULT ''"
                ),
            )
            _ensure_column(
                conn,
                is_sqlite=False,
                table="catalog_dino_generations",
                column="gender_digit",
                ddl_sqlite="",
                ddl_mysql=(
                    "ALTER TABLE catalog_dino_generations "
                    "ADD COLUMN gender_digit SMALLINT NOT NULL DEFAULT 3"
                ),
            )
        conn.commit()


def ensure_catalog_dino_code_reservations_schema(engine: Engine) -> None:
    """Reservas de public_code no claim (antes do spawn) — idempotente."""
    is_sqlite = "sqlite" in str(engine.url).lower()
    with engine.connect() as conn:
        if is_sqlite:
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS catalog_dino_code_reservations ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "public_code VARCHAR(16) NOT NULL UNIQUE,"
                    "order_id VARCHAR(64) NOT NULL,"
                    "slot_index INTEGER NOT NULL,"
                    "species_key VARCHAR(128) NOT NULL DEFAULT '',"
                    "gender_digit SMALLINT NOT NULL DEFAULT 3,"
                    "steam_id VARCHAR(32) NOT NULL DEFAULT '',"
                    "created_at DATETIME NOT NULL,"
                    "UNIQUE (order_id, slot_index)"
                    ")"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_cdcr_order "
                    "ON catalog_dino_code_reservations (order_id)"
                )
            )
            conn.commit()
            return
        row = conn.execute(
            text("SHOW TABLES LIKE 'catalog_dino_code_reservations'")
        ).fetchone()
        if row is None:
            conn.execute(
                text(
                    "CREATE TABLE catalog_dino_code_reservations ("
                    "id INT AUTO_INCREMENT PRIMARY KEY,"
                    "public_code VARCHAR(16) NOT NULL,"
                    "order_id VARCHAR(64) NOT NULL,"
                    "slot_index INT NOT NULL,"
                    "species_key VARCHAR(128) NOT NULL DEFAULT '',"
                    "gender_digit SMALLINT NOT NULL DEFAULT 3,"
                    "steam_id VARCHAR(32) NOT NULL DEFAULT '',"
                    "created_at DATETIME NOT NULL,"
                    "UNIQUE KEY uq_cdcr_code (public_code),"
                    "UNIQUE KEY uq_cdcr_order_slot (order_id, slot_index),"
                    "INDEX idx_cdcr_order (order_id)"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                )
            )
        conn.commit()


def _normalize_bp(raw: str) -> str:
    s = str(raw or "").strip().lower()
    if s.startswith("blueprint'"):
        s = s[len("blueprint'") :]
    if s.endswith("'"):
        s = s[:-1]
    return s.strip()


def _species_key_from_blueprint(catalog: dict[str, Any] | None, blueprint: str) -> str:
    want = _normalize_bp(blueprint)
    if not want or not isinstance(catalog, dict):
        return ""
    items = catalog.get("Items") or catalog.get("ShopItems") or {}
    if not isinstance(items, dict):
        return ""
    for kid, entry in items.items():
        if not isinstance(entry, dict):
            continue
        dinos = entry.get("Dinos")
        if not isinstance(dinos, list):
            continue
        for dino in dinos:
            if not isinstance(dino, dict):
                continue
            if _normalize_bp(str(dino.get("Blueprint") or "")) == want:
                return species_key_from_item_id(str(kid))
    return ""


def list_audit_spawn_slots(
    catalog: dict[str, Any] | None,
    *,
    item_type: str,
    item_id: str,
    amount: int = 1,
) -> list[dict[str, Any]]:
    """Slots L1/L200 que o plugin vai spawnar (para pré-alocar public_code)."""
    if not isinstance(catalog, dict):
        return []
    qty = max(1, int(amount or 1))
    itype = str(item_type or "shop").strip().lower()
    iid = str(item_id or "").strip()
    if not iid:
        return []
    dinos: list[Any] = []
    if itype == "kit":
        kits = catalog.get("Kits") or {}
        entry = kits.get(iid) if isinstance(kits, dict) else None
        if isinstance(entry, dict) and isinstance(entry.get("Dinos"), list):
            dinos = list(entry["Dinos"])
        qty = 1  # GiveKit não multiplica amount
    else:
        items = catalog.get("Items") or catalog.get("ShopItems") or {}
        entry = items.get(iid) if isinstance(items, dict) else None
        if isinstance(entry, dict) and isinstance(entry.get("Dinos"), list):
            dinos = list(entry["Dinos"])
    slots: list[dict[str, Any]] = []
    for _ in range(qty):
        for dino in dinos:
            if not isinstance(dino, dict):
                continue
            level = int(dino.get("Level") or 0)
            if level not in _ALLOWED_LEVELS:
                continue
            bp = str(dino.get("Blueprint") or "")
            species = _species_key_from_blueprint(catalog, bp) or species_key_from_item_id(iid)
            gender_digit = resolve_gender_digit(
                payload_gender=dino.get("Gender", dino.get("gender")),
                item_id=iid or species,
                catalog_entry=dino,
            )
            slots.append(
                {
                    "species_key": species,
                    "gender_digit": gender_digit,
                    "level": level,
                }
            )
    return slots


def _code_taken(db: Session, code: str) -> bool:
    exists = db.execute(
        text(
            "SELECT 1 FROM catalog_dino_generations "
            "WHERE public_code = :c LIMIT 1"
        ),
        {"c": code},
    ).fetchone()
    if exists:
        return True
    try:
        reserved = db.execute(
            text(
                "SELECT 1 FROM catalog_dino_code_reservations "
                "WHERE public_code = :c LIMIT 1"
            ),
            {"c": code},
        ).fetchone()
    except Exception:
        return False
    return reserved is not None


def _resolve_display_name(db: Session, steam_id: str) -> str | None:
    try:
        row = db.execute(
            text(
                "SELECT steam_persona, display_name "
                "FROM store_users WHERE steam_id = :sid LIMIT 1"
            ),
            {"sid": steam_id},
        ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    for col in (row[0], row[1]):
        val = str(col or "").strip()
        if val and not _STEAMID_RE.match(val):
            return val
    return None


def _as_u32(raw: Any) -> int:
    try:
        return int(raw) & 0xFFFFFFFF
    except (TypeError, ValueError):
        return 0


def _next_sequence_for_prefix(db: Session, prefix: str) -> int:
    """Próximo seq 1..n único dentro do prefixo tipo+variante+género."""
    # Códigos: prefix(3) + digits; extrai sufixo numérico dos existentes.
    codes: list[str] = []
    rows = db.execute(
        text(
            "SELECT public_code FROM catalog_dino_generations "
            "WHERE public_code LIKE :pat"
        ),
        {"pat": f"{prefix}%"},
    ).fetchall()
    codes.extend(str(row[0] or "") for row in rows)
    try:
        rows_r = db.execute(
            text(
                "SELECT public_code FROM catalog_dino_code_reservations "
                "WHERE public_code LIKE :pat"
            ),
            {"pat": f"{prefix}%"},
        ).fetchall()
        codes.extend(str(row[0] or "") for row in rows_r)
    except Exception:
        pass
    max_seq = 0
    plen = len(prefix)
    for code in codes:
        if not code.startswith(prefix):
            continue
        tail = code[plen:]
        if tail.isdigit():
            max_seq = max(max_seq, int(tail))
    return max_seq + 1


def _allocate_public_code(
    db: Session,
    *,
    species_key: str,
    gender_digit: int,
) -> str:
    family, variant = parse_species_key(species_key)
    prefix = code_prefix(family, variant, gender_digit)
    for _ in range(40):
        seq = _next_sequence_for_prefix(db, prefix)
        code = build_public_code(
            species_key=species_key,
            gender_digit=gender_digit,
            sequence=seq,
        )
        if not _code_taken(db, code):
            return code
    return build_public_code(
        species_key=species_key,
        gender_digit=gender_digit,
        sequence=int(datetime.now(timezone.utc).timestamp()) % 100000,
    )


def reserve_public_codes_for_order(
    db: Session,
    *,
    order_id: str,
    steam_id: str,
    item_type: str,
    item_id: str,
    amount: int = 1,
    catalog: dict[str, Any] | None = None,
) -> list[str]:
    """Pré-aloca public_codes no claim para o plugin nomear o dino no 1º spawn."""
    oid = str(order_id or "").strip()
    if not oid:
        return []
    if catalog:
        seed_families_from_catalog(catalog)
    # Já reservado (reclaim) — devolve na ordem dos slots.
    existing = db.execute(
        text(
            "SELECT public_code FROM catalog_dino_code_reservations "
            "WHERE order_id = :oid ORDER BY slot_index ASC"
        ),
        {"oid": oid},
    ).fetchall()
    if existing:
        return [str(r[0]) for r in existing if str(r[0] or "").strip()]

    slots = list_audit_spawn_slots(
        catalog,
        item_type=item_type,
        item_id=item_id,
        amount=amount,
    )
    if not slots:
        return []

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    is_sqlite = "sqlite" in str(db.get_bind().url).lower()
    insert_sql = (
        "INSERT OR IGNORE INTO catalog_dino_code_reservations "
        "(public_code, order_id, slot_index, species_key, gender_digit, steam_id, created_at) "
        "VALUES (:pc, :oid, :slot, :sk, :gd, :sid, :crt)"
        if is_sqlite
        else "INSERT IGNORE INTO catalog_dino_code_reservations "
        "(public_code, order_id, slot_index, species_key, gender_digit, steam_id, created_at) "
        "VALUES (:pc, :oid, :slot, :sk, :gd, :sid, :crt)"
    )
    codes: list[str] = []
    for idx, slot in enumerate(slots):
        species = str(slot.get("species_key") or item_id)
        gender_digit = int(slot.get("gender_digit") or 3)
        parse_species_key(species)
        code = _allocate_public_code(
            db, species_key=species, gender_digit=gender_digit
        )
        db.execute(
            text(insert_sql),
            {
                "pc": code,
                "oid": oid,
                "slot": idx,
                "sk": species,
                "gd": gender_digit,
                "sid": str(steam_id or ""),
                "crt": now,
            },
        )
        codes.append(code)
    return codes


def release_public_code_reservations(db: Session, order_ids: list[str]) -> int:
    ids = [str(x).strip() for x in (order_ids or []) if str(x).strip()]
    if not ids:
        return 0
    deleted = 0
    for oid in ids:
        result = db.execute(
            text(
                "DELETE FROM catalog_dino_code_reservations WHERE order_id = :oid"
            ),
            {"oid": oid},
        )
        try:
            deleted += int(result.rowcount or 0)
        except Exception:
            pass
    return deleted


def _consume_public_code_reservation(
    db: Session, *, public_code: str, order_id: str
) -> None:
    code = str(public_code or "").strip()
    oid = str(order_id or "").strip()
    if not code:
        return
    try:
        if oid:
            db.execute(
                text(
                    "DELETE FROM catalog_dino_code_reservations "
                    "WHERE public_code = :c AND order_id = :oid"
                ),
                {"c": code, "oid": oid},
            )
        else:
            db.execute(
                text(
                    "DELETE FROM catalog_dino_code_reservations "
                    "WHERE public_code = :c"
                ),
                {"c": code},
            )
    except Exception:
        pass


def _take_next_reservation_for_order(db: Session, *, order_id: str) -> str | None:
    oid = str(order_id or "").strip()
    if not oid:
        return None
    try:
        row = db.execute(
            text(
                "SELECT public_code FROM catalog_dino_code_reservations "
                "WHERE order_id = :oid ORDER BY slot_index ASC LIMIT 1"
            ),
            {"oid": oid},
        ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    code = str(row[0] or "").strip()
    if code:
        _consume_public_code_reservation(db, public_code=code, order_id=oid)
    return code or None


def register_catalog_dino_records(
    db: Session,
    *,
    steam_id: str,
    dino_records: list[Any],
    delivered_at: datetime | None = None,
    catalog: dict[str, Any] | None = None,
) -> int:
    """Persiste registros L1/L200 enviados pelo plugin após spawn com sucesso.

    Kits com N dinos → N linhas (mesmo order_id). Ignora níveis fora de {1, 200}.
    Gera ``public_code`` único (formato R21347) por registo.
    """
    if not isinstance(dino_records, list) or not dino_records:
        return 0
    if catalog:
        seed_families_from_catalog(catalog)
    now = delivered_at or datetime.now(timezone.utc)
    if now.tzinfo is not None:
        now_naive = now.replace(tzinfo=None)
    else:
        now_naive = now
    display = _resolve_display_name(db, steam_id)
    is_sqlite = "sqlite" in str(db.get_bind().url).lower()
    insert_sql = (
        "INSERT OR IGNORE INTO catalog_dino_generations "
        "(dino_id1, dino_id2, canonical_id, public_code, gender_digit, order_id, "
        "steam_id, item_id, level, species_key, display_name, delivered_at, created_at) "
        "VALUES (:id1, :id2, :canon, :pcode, :gd, :oid, :sid, :iid, :lvl, :sk, "
        ":dn, :del_at, :crt)"
        if is_sqlite
        else "INSERT IGNORE INTO catalog_dino_generations "
        "(dino_id1, dino_id2, canonical_id, public_code, gender_digit, order_id, "
        "steam_id, item_id, level, species_key, display_name, delivered_at, created_at) "
        "VALUES (:id1, :id2, :canon, :pcode, :gd, :oid, :sid, :iid, :lvl, :sk, "
        ":dn, :del_at, :crt)"
    )
    inserted = 0
    for rec in dino_records:
        if not isinstance(rec, dict):
            continue
        order_id = str(rec.get("order_id") or "").strip()
        item_id = str(rec.get("item_id") or "").strip()
        level = int(rec.get("level") or 0)
        id1 = _as_u32(rec.get("dino_id1"))
        id2 = _as_u32(rec.get("dino_id2"))
        if not order_id or level not in _ALLOWED_LEVELS:
            continue
        if id1 == 0 and id2 == 0:
            continue
        canon = canonical_id(id1, id2)
        species = str(rec.get("species_key") or "").strip() or species_key_from_item_id(item_id)
        entry = lookup_catalog_entry(catalog, item_id) or lookup_catalog_entry(catalog, species)
        gender_digit = resolve_gender_digit(
            payload_gender=rec.get("gender", rec.get("Gender")),
            item_id=item_id or species,
            catalog_entry=entry,
        )
        # Garante letra da família registada antes de alocar
        parse_species_key(species)  # side-effect via family_letter on allocate
        reserved = str(rec.get("public_code") or "").strip()
        if reserved:
            public = reserved
            _consume_public_code_reservation(db, public_code=public, order_id=order_id)
        else:
            taken = _take_next_reservation_for_order(db, order_id=order_id)
            public = taken or _allocate_public_code(
                db, species_key=species, gender_digit=gender_digit
            )
        result = db.execute(
            text(insert_sql),
            {
                "id1": id1,
                "id2": id2,
                "canon": canon,
                "pcode": public,
                "gd": gender_digit,
                "oid": order_id,
                "sid": steam_id,
                "iid": item_id or species,
                "lvl": level,
                "sk": species,
                "dn": display,
                "del_at": now_naive,
                "crt": now_naive,
            },
        )
        try:
            if int(result.rowcount or 0) > 0:
                inserted += 1
        except Exception:
            inserted += 1
    return inserted


def public_display_name(name: str | None) -> str:
    """Nome completo para auditoria pública — nunca Steam ID64 cru."""
    src = (name or "").strip()
    if not src or _STEAMID_RE.match(src):
        return "Jogador"
    return src


def list_public_catalog_dinos(
    db: Session,
    *,
    level: int | None = None,
    species: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Lista pública — sem Steam ID64; display_name completo (auditoria intencional)."""
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 50)))
    clauses = ["level IN (1, 200)"]
    params: dict[str, Any] = {}
    if level in _ALLOWED_LEVELS:
        clauses = ["level = :lvl"]
        params["lvl"] = int(level)
    if species:
        clauses.append("(species_key LIKE :sp OR public_code LIKE :sp OR item_id LIKE :sp)")
        params["sp"] = f"%{str(species).strip()}%"
    where_sql = " WHERE " + " AND ".join(clauses)
    total = int(
        db.execute(
            text(f"SELECT COUNT(*) FROM catalog_dino_generations{where_sql}"),
            params,
        ).scalar()
        or 0
    )
    pages = max(1, (total + page_size - 1) // page_size) if total else 1
    if page > pages:
        page = pages
    offset = (page - 1) * page_size
    params_q = dict(params)
    params_q["lim"] = page_size
    params_q["off"] = offset
    rows = db.execute(
        text(
            "SELECT canonical_id, public_code, gender_digit, item_id, level, "
            "species_key, display_name, delivered_at "
            f"FROM catalog_dino_generations{where_sql} "
            "ORDER BY delivered_at DESC, id DESC "
            "LIMIT :lim OFFSET :off"
        ),
        params_q,
    ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        raw_name = str(row[6] or "").strip() if len(row) > 6 else ""
        items.append(
            {
                "public_code": str(row[1] or ""),
                "canonical_id": str(row[0] or ""),
                "gender_digit": int(row[2] or 3),
                "item_id": str(row[3] or ""),
                "level": int(row[4] or 0),
                "species_key": str(row[5] or ""),
                "display_name": public_display_name(raw_name),
                "delivered_at": str(row[7] or "")[:19] if len(row) > 7 else "",
            }
        )
    return {
        "ok": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "items": items,
    }


def lookup_catalog_dino_by_identity(
    db: Session,
    *,
    dino_id1: int | None = None,
    dino_id2: int | None = None,
    canonical: str | None = None,
) -> dict[str, Any]:
    """Resolve public_code a partir de dino_id1/dino_id2 ou canonical_id.

    Usado pelo plugin (/checar) via X-API-Key. Não expõe steam_id.
    """
    id1: int | None = None
    id2: int | None = None
    if dino_id1 is not None and dino_id2 is not None:
        try:
            id1 = int(dino_id1) & 0xFFFFFFFF
            id2 = int(dino_id2) & 0xFFFFFFFF
        except (TypeError, ValueError):
            id1 = id2 = None
    if (id1 is None or id2 is None) and canonical:
        raw = str(canonical or "").strip().upper().replace(" ", "")
        if "-" in raw:
            left, right = raw.split("-", 1)
            try:
                id1 = int(left, 16) & 0xFFFFFFFF
                id2 = int(right, 16) & 0xFFFFFFFF
            except ValueError:
                try:
                    id1 = int(left) & 0xFFFFFFFF
                    id2 = int(right) & 0xFFFFFFFF
                except ValueError:
                    id1 = id2 = None
        elif len(raw) == 16 and all(c in "0123456789ABCDEF" for c in raw):
            try:
                id1 = int(raw[:8], 16) & 0xFFFFFFFF
                id2 = int(raw[8:], 16) & 0xFFFFFFFF
            except ValueError:
                id1 = id2 = None

    if id1 is None or id2 is None or (id1 == 0 and id2 == 0):
        return {"ok": False, "found": False, "error": "invalid_id"}

    canon = canonical_id(id1, id2)
    row = db.execute(
        text(
            "SELECT canonical_id, public_code, gender_digit, item_id, level, "
            "species_key, delivered_at "
            "FROM catalog_dino_generations "
            "WHERE (dino_id1 = :id1 AND dino_id2 = :id2) OR canonical_id = :canon "
            "LIMIT 1"
        ),
        {"id1": id1, "id2": id2, "canon": canon},
    ).fetchone()
    if not row:
        return {
            "ok": True,
            "found": False,
            "canonical_id": canon,
            "dino_id1": id1,
            "dino_id2": id2,
        }
    public = str(row[1] or "").strip()
    if not public:
        return {
            "ok": True,
            "found": False,
            "canonical_id": str(row[0] or canon),
            "dino_id1": id1,
            "dino_id2": id2,
            "error": "missing_public_code",
        }
    return {
        "ok": True,
        "found": True,
        "public_code": public,
        "canonical_id": str(row[0] or canon),
        "dino_id1": id1,
        "dino_id2": id2,
        "gender_digit": int(row[2] or 3),
        "item_id": str(row[3] or ""),
        "level": int(row[4] or 0),
        "species_key": str(row[5] or ""),
        "delivered_at": str(row[6] or "")[:19] if len(row) > 6 else "",
    }
