"""ARKBANK — tesouraria simbólica do cluster (saldo da casa, pode ser negativo)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

log = logging.getLogger("arkshop_web.arkbank")

ARKBANK_DONATION_AMBER_PER_REAL = 1000

_ARKBANK_SCHEMA_READY_ENGINES: set[int] = set()
_ARKBANK_SCHEMA_LOCK = __import__("threading").Lock()

TX_CATALOG_SPEND = "catalog_spend"
TX_CATALOG_REFUND_CLAWBACK = "catalog_refund_clawback"
TX_MARKET_PAIR_SHARE = "market_pair_share"
TX_DINO_ORDER_PAY = "dino_order_pay"
TX_DINO_ORDER_REFUND_CLAWBACK = "dino_order_refund_clawback"
TX_DONATION_BRL = "donation_brl"
TX_DONATION_BRL_CLAWBACK = "donation_brl_clawback"
TX_TIMED_REWARD = "timed_reward"
TX_ADMIN_ADJUST = "admin_adjust"
TX_SEASON_PASS_PREMIUM = "season_pass_premium"

INFLOW_TYPES = frozenset({
    TX_CATALOG_SPEND,
    TX_MARKET_PAIR_SHARE,
    TX_DINO_ORDER_PAY,
    TX_DONATION_BRL,
    TX_SEASON_PASS_PREMIUM,
})
OUTFLOW_TYPES = frozenset({
    TX_CATALOG_REFUND_CLAWBACK,
    TX_DINO_ORDER_REFUND_CLAWBACK,
    TX_DONATION_BRL_CLAWBACK,
    TX_TIMED_REWARD,
})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _naive_utc(dt: datetime | str | None = None) -> datetime:
    if dt is None:
        dt = _utcnow()
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return _naive_utc(_utcnow())
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def ensure_arkbank_schema(engine: Engine) -> None:
    """Cria tabelas arkbank_* uma vez por engine — nunca DDL em cada request."""
    eid = id(engine)
    if eid in _ARKBANK_SCHEMA_READY_ENGINES:
        return
    with _ARKBANK_SCHEMA_LOCK:
        if eid in _ARKBANK_SCHEMA_READY_ENGINES:
            return
        _ensure_arkbank_schema_impl(engine)
        _ARKBANK_SCHEMA_READY_ENGINES.add(eid)


def _ensure_arkbank_schema_impl(engine: Engine) -> None:
    """Cria tabelas arkbank_state, arkbank_transactions e arkbank_timed_outbox."""
    is_sqlite = "sqlite" in str(engine.url).lower()
    if is_sqlite:
        state_ddl = """
        CREATE TABLE IF NOT EXISTS arkbank_state (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          balance INTEGER NOT NULL DEFAULT 0,
          updated_at DATETIME NOT NULL,
          version INTEGER NOT NULL DEFAULT 0
        )
        """
        tx_ddl = """
        CREATE TABLE IF NOT EXISTS arkbank_transactions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at DATETIME NOT NULL,
          tx_type VARCHAR(64) NOT NULL,
          amount INTEGER NOT NULL,
          balance_after INTEGER NOT NULL,
          steam_id VARCHAR(32) NULL,
          ref_table VARCHAR(64) NULL,
          ref_id VARCHAR(128) NULL,
          map_id VARCHAR(64) NULL,
          idempotency_key VARCHAR(128) NOT NULL UNIQUE,
          metadata_json TEXT NULL,
          created_by_admin VARCHAR(32) NULL
        )
        """
        outbox_ddl = """
        CREATE TABLE IF NOT EXISTS arkbank_timed_outbox (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at DATETIME NOT NULL,
          steam_id VARCHAR(32) NOT NULL,
          amount INTEGER NOT NULL,
          map_id VARCHAR(64) NOT NULL,
          cycle_key VARCHAR(64) NOT NULL,
          processed_at DATETIME NULL,
          UNIQUE (steam_id, map_id, cycle_key, amount)
        )
        """
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_arkbank_time ON arkbank_transactions (created_at)",
            "CREATE INDEX IF NOT EXISTS idx_arkbank_type_time ON arkbank_transactions (tx_type, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_arkbank_steam ON arkbank_transactions (steam_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_arkbank_outbox_pending ON arkbank_timed_outbox (processed_at, id)",
        ]
    else:
        state_ddl = """
        CREATE TABLE IF NOT EXISTS arkbank_state (
          id TINYINT NOT NULL PRIMARY KEY DEFAULT 1,
          balance BIGINT NOT NULL DEFAULT 0,
          updated_at DATETIME(3) NOT NULL,
          version BIGINT NOT NULL DEFAULT 0
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        tx_ddl = """
        CREATE TABLE IF NOT EXISTS arkbank_transactions (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          created_at DATETIME(3) NOT NULL,
          tx_type VARCHAR(64) NOT NULL,
          amount BIGINT NOT NULL,
          balance_after BIGINT NOT NULL,
          steam_id VARCHAR(32) NULL,
          ref_table VARCHAR(64) NULL,
          ref_id VARCHAR(128) NULL,
          map_id VARCHAR(64) NULL,
          idempotency_key VARCHAR(128) NOT NULL,
          metadata_json JSON NULL,
          created_by_admin VARCHAR(32) NULL,
          UNIQUE KEY uq_arkbank_idem (idempotency_key),
          INDEX idx_arkbank_time (created_at),
          INDEX idx_arkbank_type_time (tx_type, created_at),
          INDEX idx_arkbank_steam (steam_id, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        outbox_ddl = """
        CREATE TABLE IF NOT EXISTS arkbank_timed_outbox (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          created_at DATETIME(3) NOT NULL,
          steam_id VARCHAR(32) NOT NULL,
          amount INT NOT NULL,
          map_id VARCHAR(64) NOT NULL,
          cycle_key VARCHAR(64) NOT NULL,
          processed_at DATETIME(3) NULL,
          UNIQUE KEY uq_timed (steam_id, map_id, cycle_key, amount),
          INDEX idx_arkbank_outbox_pending (processed_at, id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        indexes = []

    with engine.connect() as conn:
        conn.execute(text(state_ddl))
        conn.execute(text(tx_ddl))
        conn.execute(text(outbox_ddl))
        for stmt in indexes:
            conn.execute(text(stmt))
        conn.commit()

    SessionLocal = __import__("sqlalchemy.orm", fromlist=["sessionmaker"]).sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        _ensure_state_row(db)
        db.commit()
    except Exception as exc:
        db.rollback()
        log.warning("ARKBANK ensure state row: %s", exc)
    finally:
        db.close()


def _ensure_state_row(db: Session) -> None:
    row = db.execute(text("SELECT id FROM arkbank_state WHERE id = 1")).fetchone()
    if row:
        return
    db.execute(
        text(
            "INSERT INTO arkbank_state (id, balance, updated_at, version) "
            "VALUES (1, 0, :now, 0)"
        ),
        {"now": _naive_utc()},
    )


def donation_amber_from_brl(amount_brl: float | int | None) -> int:
    """R$ 1,00 confirmado = 1.000 Âmbar na tesouraria."""
    try:
        brl = float(amount_brl or 0)
    except (TypeError, ValueError):
        return 0
    if brl <= 0:
        return 0
    return int(round(brl * ARKBANK_DONATION_AMBER_PER_REAL))


def get_balance(db: Session) -> int:
    _ensure_state_row(db)
    row = db.execute(text("SELECT balance FROM arkbank_state WHERE id = 1")).fetchone()
    return int(row[0] if row else 0)


def _fetch_by_idem(db: Session, idempotency_key: str) -> dict[str, Any] | None:
    row = db.execute(
        text(
            "SELECT id, created_at, tx_type, amount, balance_after, steam_id, "
            "ref_table, ref_id, map_id, idempotency_key, metadata_json, created_by_admin "
            "FROM arkbank_transactions WHERE idempotency_key = :k LIMIT 1"
        ),
        {"k": idempotency_key},
    ).fetchone()
    if not row:
        return None
    return _tx_row_to_dict(row)


def _tx_row_to_dict(row: Any) -> dict[str, Any]:
    meta = _row_val(row, "metadata_json")
    if isinstance(meta, str) and meta:
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {"raw": meta}
    return {
        "id": int(_row_val(row, "id", 0) or 0),
        "created_at": str(_row_val(row, "created_at", "") or ""),
        "tx_type": str(_row_val(row, "tx_type", "") or ""),
        "amount": int(_row_val(row, "amount", 0) or 0),
        "balance_after": int(_row_val(row, "balance_after", 0) or 0),
        "steam_id": _row_val(row, "steam_id"),
        "ref_table": _row_val(row, "ref_table"),
        "ref_id": _row_val(row, "ref_id"),
        "map_id": _row_val(row, "map_id"),
        "idempotency_key": str(_row_val(row, "idempotency_key", "") or ""),
        "metadata": meta if isinstance(meta, dict) else meta,
        "created_by_admin": _row_val(row, "created_by_admin"),
    }


def _row_val(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    if hasattr(row, "_mapping"):
        return row._mapping.get(key, default)
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except Exception:
        pass
    idx_map = {
        "id": 0,
        "created_at": 1,
        "tx_type": 2,
        "amount": 3,
        "balance_after": 4,
        "steam_id": 5,
        "ref_table": 6,
        "ref_id": 7,
        "map_id": 8,
        "idempotency_key": 9,
        "metadata_json": 10,
        "created_by_admin": 11,
    }
    if key in idx_map:
        try:
            return row[idx_map[key]]
        except Exception:
            return default
    return default


def _apply_delta(
    db: Session,
    *,
    tx_type: str,
    signed_amount: int,
    idempotency_key: str,
    steam_id: str | None = None,
    ref_table: str | None = None,
    ref_id: str | None = None,
    map_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    created_by_admin: str | None = None,
    commit: bool = False,
) -> dict[str, Any]:
    """Aplica delta ao saldo (pode ficar negativo). Idempotente por chave."""
    if not idempotency_key:
        raise ValueError("idempotency_key_required")
    existing = _fetch_by_idem(db, idempotency_key)
    if existing:
        return {**existing, "duplicate": True, "applied": False}

    signed_amount = int(signed_amount)
    if signed_amount == 0:
        return {
            "id": None,
            "tx_type": tx_type,
            "amount": 0,
            "balance_after": get_balance(db),
            "idempotency_key": idempotency_key,
            "duplicate": False,
            "applied": False,
            "skipped_zero": True,
        }

    _ensure_state_row(db)
    now = _naive_utc()
    meta_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
    # Savepoint: IntegrityError de idempotência não aborta a transação do caller.
    try:
        with db.begin_nested():
            db.execute(
                text(
                    "UPDATE arkbank_state SET balance = balance + :d, version = version + 1, "
                    "updated_at = :now WHERE id = 1"
                ),
                {"d": signed_amount, "now": now},
            )
            bal_row = db.execute(
                text("SELECT balance FROM arkbank_state WHERE id = 1")
            ).fetchone()
            balance_after = int(bal_row[0] if bal_row else 0)
            db.execute(
                text(
                    "INSERT INTO arkbank_transactions "
                    "(created_at, tx_type, amount, balance_after, steam_id, ref_table, ref_id, "
                    "map_id, idempotency_key, metadata_json, created_by_admin) "
                    "VALUES (:now, :tt, :amt, :bal, :sid, :rt, :rid, :mid, :idem, :meta, :admin)"
                ),
                {
                    "now": now,
                    "tt": tx_type,
                    "amt": signed_amount,
                    "bal": balance_after,
                    "sid": steam_id,
                    "rt": ref_table,
                    "rid": str(ref_id) if ref_id is not None else None,
                    "mid": map_id,
                    "idem": idempotency_key,
                    "meta": meta_json,
                    "admin": created_by_admin,
                },
            )
    except IntegrityError:
        existing = _fetch_by_idem(db, idempotency_key)
        if existing:
            return {**existing, "duplicate": True, "applied": False}
        raise

    if commit:
        db.commit()

    row = _fetch_by_idem(db, idempotency_key) or {
        "tx_type": tx_type,
        "amount": signed_amount,
        "balance_after": balance_after,
        "idempotency_key": idempotency_key,
    }
    return {**row, "duplicate": False, "applied": True}


def credit(
    db: Session,
    *,
    tx_type: str,
    amount: int,
    idempotency_key: str,
    steam_id: str | None = None,
    ref_table: str | None = None,
    ref_id: str | None = None,
    map_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    created_by_admin: str | None = None,
    commit: bool = False,
) -> dict[str, Any]:
    """Crédito (+amount) no ARKBANK. amount deve ser >= 0."""
    amount = max(0, int(amount))
    return _apply_delta(
        db,
        tx_type=tx_type,
        signed_amount=amount,
        idempotency_key=idempotency_key,
        steam_id=steam_id,
        ref_table=ref_table,
        ref_id=ref_id,
        map_id=map_id,
        metadata=metadata,
        created_by_admin=created_by_admin,
        commit=commit,
    )


def debit(
    db: Session,
    *,
    tx_type: str,
    amount: int,
    idempotency_key: str,
    steam_id: str | None = None,
    ref_table: str | None = None,
    ref_id: str | None = None,
    map_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    created_by_admin: str | None = None,
    commit: bool = False,
) -> dict[str, Any]:
    """Débito (−amount) no ARKBANK. Nunca bloqueia por saldo (pode ir negativo)."""
    amount = max(0, int(amount))
    return _apply_delta(
        db,
        tx_type=tx_type,
        signed_amount=-amount,
        idempotency_key=idempotency_key,
        steam_id=steam_id,
        ref_table=ref_table,
        ref_id=ref_id,
        map_id=map_id,
        metadata=metadata,
        created_by_admin=created_by_admin,
        commit=commit,
    )


# ── Convenience hooks ─────────────────────────────────────────────────────────


def credit_catalog_spend(
    db: Session,
    *,
    order_id: str,
    steam_id: str,
    points: int,
    commit: bool = False,
) -> dict[str, Any]:
    return credit(
        db,
        tx_type=TX_CATALOG_SPEND,
        amount=int(points),
        idempotency_key=f"arkbank:catalog:{order_id}",
        steam_id=steam_id,
        ref_table="orders",
        ref_id=str(order_id),
        metadata={"points": int(points)},
        commit=commit,
    )


def debit_catalog_refund_clawback(
    db: Session,
    *,
    order_id: str,
    steam_id: str,
    refunded: int,
    event: str = "cancel",
    commit: bool = False,
) -> dict[str, Any]:
    """Clawback do reembolso 80% — retenção 20% permanece no banco."""
    return debit(
        db,
        tx_type=TX_CATALOG_REFUND_CLAWBACK,
        amount=int(refunded),
        idempotency_key=f"arkbank:catalog_refund:{order_id}:{event}",
        steam_id=steam_id,
        ref_table="orders",
        ref_id=str(order_id),
        metadata={"refunded": int(refunded), "event": event},
        commit=commit,
    )


def credit_market_pair_share(
    db: Session,
    *,
    amount: int,
    listing_id: int,
    tx_id: int,
    seller_steam_id: str | None = None,
    commit: bool = False,
) -> dict[str, Any]:
    return credit(
        db,
        tx_type=TX_MARKET_PAIR_SHARE,
        amount=int(amount),
        idempotency_key=f"arkbank:pair:{tx_id}",
        steam_id=seller_steam_id,
        ref_table="market_transactions",
        ref_id=str(tx_id),
        metadata={"listing_id": int(listing_id), "amount": int(amount)},
        commit=commit,
    )


def credit_dino_order_pay(
    db: Session,
    *,
    order_id: str,
    steam_id: str,
    total: int,
    commit: bool = False,
) -> dict[str, Any]:
    return credit(
        db,
        tx_type=TX_DINO_ORDER_PAY,
        amount=int(total),
        idempotency_key=f"arkbank:dino_order:{order_id}",
        steam_id=steam_id,
        ref_table="orders",
        ref_id=str(order_id),
        metadata={"total": int(total)},
        commit=commit,
    )


def debit_dino_order_refund(
    db: Session,
    *,
    order_id: str,
    steam_id: str,
    refunded: int,
    commit: bool = False,
) -> dict[str, Any]:
    return debit(
        db,
        tx_type=TX_DINO_ORDER_REFUND_CLAWBACK,
        amount=int(refunded),
        idempotency_key=f"arkbank:dino_order_refund:{order_id}",
        steam_id=steam_id,
        ref_table="orders",
        ref_id=str(order_id),
        metadata={"refunded": int(refunded)},
        commit=commit,
    )


def credit_donation_brl(
    db: Session,
    *,
    payment_id: str,
    steam_id: str,
    amount_brl: float | int,
    payment_method: str | None = None,
    commit: bool = False,
) -> dict[str, Any]:
    amber = donation_amber_from_brl(amount_brl)
    return credit(
        db,
        tx_type=TX_DONATION_BRL,
        amount=amber,
        idempotency_key=f"arkbank:donation:{payment_id}",
        steam_id=steam_id,
        ref_table="point_payments",
        ref_id=str(payment_id),
        metadata={
            "amount_brl": float(amount_brl or 0),
            "payment_method": payment_method,
            "amber": amber,
        },
        commit=commit,
    )


def debit_donation_clawback(
    db: Session,
    *,
    payment_id: str,
    steam_id: str | None,
    amount_brl: float | int,
    commit: bool = False,
) -> dict[str, Any]:
    amber = donation_amber_from_brl(amount_brl)
    return debit(
        db,
        tx_type=TX_DONATION_BRL_CLAWBACK,
        amount=amber,
        idempotency_key=f"arkbank:donation_clawback:{payment_id}",
        steam_id=steam_id,
        ref_table="point_payments",
        ref_id=str(payment_id),
        metadata={"amount_brl": float(amount_brl or 0), "amber": amber},
        commit=commit,
    )


def debit_timed_reward(
    db: Session,
    *,
    steam_id: str,
    amount: int,
    map_id: str,
    cycle_key: str,
    commit: bool = False,
) -> dict[str, Any]:
    return debit(
        db,
        tx_type=TX_TIMED_REWARD,
        amount=int(amount),
        idempotency_key=f"arkbank:timed:{map_id}:{steam_id}:{cycle_key}",
        steam_id=steam_id,
        map_id=map_id,
        ref_table="arkbank_timed_outbox",
        ref_id=f"{map_id}:{cycle_key}",
        metadata={"award": int(amount), "cycle_key": cycle_key},
        commit=commit,
    )


def credit_season_pass_premium(
    db: Session,
    *,
    steam_id: str,
    amount: int,
    season_id: str,
    commit: bool = False,
) -> dict[str, Any]:
    """100% do preço Premium → cofre ARKBANK (SPEC §15.7)."""
    return credit(
        db,
        tx_type=TX_SEASON_PASS_PREMIUM,
        amount=int(amount),
        idempotency_key=f"arkbank:season_pass_premium:{season_id}:{steam_id}",
        steam_id=steam_id,
        ref_table="season_pass_progress",
        ref_id=str(season_id),
        metadata={"season_id": str(season_id), "price": int(amount)},
        commit=commit,
    )


def admin_adjust(
    db: Session,
    *,
    amount: int,
    admin_steam_id: str,
    reason: str,
    commit: bool = False,
) -> dict[str, Any]:
    """Top-up (amount>0) ou correção (amount<0). Motivo obrigatório."""
    amount = int(amount)
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("reason_required")
    if amount == 0:
        raise ValueError("amount_required")
    idem = f"arkbank:admin:{admin_steam_id}:{_naive_utc().isoformat()}:{amount}:{reason[:40]}"
    return _apply_delta(
        db,
        tx_type=TX_ADMIN_ADJUST,
        signed_amount=amount,
        idempotency_key=idem,
        created_by_admin=admin_steam_id,
        metadata={"reason": reason[:500]},
        commit=commit,
    )


# ── TimedPoints outbox ────────────────────────────────────────────────────────


def enqueue_timed_outbox(
    db: Session,
    *,
    steam_id: str,
    amount: int,
    map_id: str,
    cycle_key: str,
    commit: bool = False,
) -> dict[str, Any]:
    """Insere linha no outbox (idempotente pelo UNIQUE)."""
    amount = int(amount)
    if amount <= 0:
        return {"enqueued": False, "reason": "zero"}
    now = _naive_utc()
    try:
        db.execute(
            text(
                "INSERT INTO arkbank_timed_outbox "
                "(created_at, steam_id, amount, map_id, cycle_key, processed_at) "
                "VALUES (:now, :sid, :amt, :mid, :ck, NULL)"
            ),
            {
                "now": now,
                "sid": str(steam_id),
                "amt": amount,
                "mid": str(map_id or "unknown")[:64],
                "ck": str(cycle_key)[:64],
            },
        )
        if commit:
            db.commit()
        return {"enqueued": True}
    except IntegrityError:
        if commit:
            db.rollback()
        return {"enqueued": False, "duplicate": True}


def process_timed_outbox(
    db: Session,
    *,
    batch_size: int = 200,
    commit_every: int = 20,
) -> dict[str, Any]:
    """Consome outbox pendente, debita ARKBANK e credita Season Pass XP.

    commit_every encurta a transação (evita long_transaction com batch grande).
    """
    rows = db.execute(
        text(
            "SELECT id, steam_id, amount, map_id, cycle_key FROM arkbank_timed_outbox "
            "WHERE processed_at IS NULL ORDER BY id ASC LIMIT :lim"
        ),
        {"lim": max(1, min(1000, int(batch_size)))},
    ).fetchall()
    processed = 0
    duplicates = 0
    xp_applied = 0
    chunk = max(1, int(commit_every))
    for row in rows:
        oid = int(row[0])
        steam_id = str(row[1])
        amount = int(row[2])
        map_id = str(row[3])
        cycle_key = str(row[4])
        result = debit_timed_reward(
            db,
            steam_id=steam_id,
            amount=amount,
            map_id=map_id,
            cycle_key=cycle_key,
            commit=False,
        )
        if result.get("duplicate"):
            duplicates += 1
        try:
            from season_pass_service import add_timed_xp

            xp_res = add_timed_xp(
                db,
                steam_id=steam_id,
                amount=amount,
                map_id=map_id,
                cycle_key=cycle_key,
                commit=False,
            )
            if xp_res.get("applied"):
                xp_applied += 1
        except Exception as exc:
            log.warning(
                "season_pass XP from timed outbox failed sid=%s: %s",
                steam_id,
                exc,
            )
        try:
            from team_service import add_team_timed_xp

            add_team_timed_xp(
                db,
                steam_id=steam_id,
                amount=amount,
                map_id=map_id,
                cycle_key=cycle_key,
                commit=False,
            )
        except Exception as exc:
            log.warning(
                "team XP from timed outbox failed sid=%s: %s",
                steam_id,
                exc,
            )
        now = _naive_utc()
        db.execute(
            text("UPDATE arkbank_timed_outbox SET processed_at = :now WHERE id = :id"),
            {"now": now, "id": oid},
        )
        processed += 1
        if processed % chunk == 0:
            db.commit()
    if processed % chunk:
        db.commit()
    return {"processed": processed, "duplicates": duplicates, "season_pass_xp": xp_applied}


# ── Admin summary / list ──────────────────────────────────────────────────────


def list_transactions(
    db: Session,
    *,
    limit: int = 50,
    offset: int = 0,
    tx_type: str | None = None,
) -> list[dict[str, Any]]:
    limit = max(1, min(200, int(limit)))
    offset = max(0, int(offset))
    params: dict[str, Any] = {"lim": limit, "off": offset}
    where = ""
    if tx_type:
        where = "WHERE tx_type = :tt"
        params["tt"] = tx_type
    rows = db.execute(
        text(
            f"SELECT id, created_at, tx_type, amount, balance_after, steam_id, "
            f"ref_table, ref_id, map_id, idempotency_key, metadata_json, created_by_admin "
            f"FROM arkbank_transactions {where} "
            f"ORDER BY id DESC LIMIT :lim OFFSET :off"
        ),
        params,
    ).fetchall()
    return [_tx_row_to_dict(r) for r in rows]


def season_meta_inflow(
    db: Session,
    *,
    since: datetime | str,
    until: datetime | str | None = None,
    include_types: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Progresso da meta colectiva = Σ inflows ARKBANK na janela da season.

    ≠ saldo actual do cofre (balance = histórico in − out, pode ser negativo
    por timed_reward). Conta só ``INFLOW_TYPES`` (catálogo, market, dino order,
    doação BRL, Premium); exclui ``admin_adjust`` e outflows.
    """
    types = include_types if include_types is not None else INFLOW_TYPES
    if not types:
        return {
            "progress": 0,
            "by_type": {},
            "since": None,
            "until": None,
            "included_types": [],
            "definition": "season_inflow",
            "vs_balance": "progress_is_not_vault_balance",
        }
    since_n = _naive_utc(since)
    until_n = _naive_utc(until) if until is not None else None
    type_list = sorted(types)
    placeholders = ", ".join(f":t{i}" for i in range(len(type_list)))
    params: dict[str, Any] = {"since": since_n}
    for i, tt in enumerate(type_list):
        params[f"t{i}"] = tt
    where = f"tx_type IN ({placeholders}) AND created_at >= :since AND amount > 0"
    if until_n is not None:
        where += " AND created_at <= :until"
        params["until"] = until_n
    rows = db.execute(
        text(
            f"SELECT tx_type, COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
            f"FROM arkbank_transactions WHERE {where} GROUP BY tx_type"
        ),
        params,
    ).fetchall()
    by_type: dict[str, dict[str, int]] = {}
    progress = 0
    for r in rows:
        tt = str(r[0])
        total = int(r[1] or 0)
        cnt = int(r[2] or 0)
        by_type[tt] = {"total": total, "count": cnt}
        progress += total
    return {
        "progress": progress,
        "by_type": by_type,
        "since": since_n.isoformat(),
        "until": until_n.isoformat() if until_n else None,
        "included_types": type_list,
        "definition": "season_inflow",
        "vs_balance": "progress_is_not_vault_balance",
    }


def summary(db: Session, *, days: int = 7) -> dict[str, Any]:
    """Saldo + totais in/out no período + breakdown por tipo."""
    _ensure_state_row(db)
    balance = get_balance(db)
    days = max(1, min(90, int(days)))
    since = _naive_utc(_utcnow() - timedelta(days=days))
    rows = db.execute(
        text(
            "SELECT tx_type, SUM(amount) AS total, COUNT(*) AS cnt "
            "FROM arkbank_transactions WHERE created_at >= :since "
            "GROUP BY tx_type"
        ),
        {"since": since},
    ).fetchall()
    by_type: dict[str, dict[str, int]] = {}
    inflow = 0
    outflow = 0
    for r in rows:
        tt = str(r[0])
        total = int(r[1] or 0)
        cnt = int(r[2] or 0)
        by_type[tt] = {"total": total, "count": cnt}
        if total > 0:
            inflow += total
        elif total < 0:
            outflow += abs(total)
    since_24h = _naive_utc(_utcnow() - timedelta(hours=24))
    delta_24h_row = db.execute(
        text(
            "SELECT COALESCE(SUM(amount), 0) FROM arkbank_transactions "
            "WHERE created_at >= :since"
        ),
        {"since": since_24h},
    ).fetchone()
    delta_24h = int(delta_24h_row[0] if delta_24h_row else 0)
    return {
        "balance": balance,
        "delta_24h": delta_24h,
        "period_days": days,
        "inflow": inflow,
        "outflow": outflow,
        "net": inflow - outflow,
        "by_type": by_type,
        "health": "saudavel" if balance >= 0 else "deficitario",
    }
