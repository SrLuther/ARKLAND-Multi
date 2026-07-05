"""
Sorteio de Doações ARKLAND — lógica de negócio (spec v1.6 MVP F1).

Touch list (integração cirúrgica):
  - app.py: ensure_lottery_schema, register_lottery_routes, _finalize_pix_payment hook,
            _retry_worker (process_due_draws), settings lottery_enabled
  - amber_ledger.py: record_lottery_prize, record_lottery_amber_purchase, record_lottery_prize_subsidy
  - static/index.html: #/sorteio, Minha Área, admin, home teaser
  - regulamento_service.py: gate opcional (regulamento_guard injetado nas rotas)
"""
from __future__ import annotations

import json
import logging
import math
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from lottery_draw import (
    ALGORITHM_VERSION,
    NUMBER_MAX,
    NUMBER_MIN,
    audit_blob_json,
    compute_prize_split,
    draw_winning_numbers,
)

log = logging.getLogger("arkshop_web.lottery")

CAMPAIGN_STATUSES = frozenset({"DRAFT", "ACTIVE", "DRAWING", "COMPLETED", "CANCELLED"})
NUMBER_SOURCES = frozenset({"DONATION", "AMBER_RANDOM", "AMBER_RESERVE"})
LOTTERY_REGULAMENTO_VERSION = "1.5"
RULES_SUMMARY = (
    "R$ 5 = 1 número · compra 1.000 Âmbares (máx. 5) · reserva 2.000 Âmbares · "
    "até 5 sorteados · prêmio dividido igualmente entre titulares dos sorteados."
)
TZ_LABEL = "Horário de Brasília (UTC-3)"
TZ_OFFSET = timezone(timedelta(hours=-3))
_MAX_RANDOM_ATTEMPTS = 50

_credit_fn: Callable[[Session, str, int], int] | None = None
_debit_fn: Callable[[Session, str, int], int] | None = None
_settings_fn: Callable[[], dict[str, Any]] | None = None
_save_settings_fn: Callable[[dict[str, Any]], None] | None = None


def configure_lottery(
    *,
    credit_fn: Callable[[Session, str, int], int],
    debit_fn: Callable[[Session, str, int], int],
    settings_fn: Callable[[], dict[str, Any]] | None = None,
    save_settings_fn: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    global _credit_fn, _debit_fn, _settings_fn, _save_settings_fn
    _credit_fn = credit_fn
    _debit_fn = debit_fn
    _settings_fn = settings_fn
    _save_settings_fn = save_settings_fn


def lottery_meta() -> dict[str, Any]:
    return {
        "regulamento_version": LOTTERY_REGULAMENTO_VERSION,
        "number_min": NUMBER_MIN,
        "number_max": NUMBER_MAX,
        "rules_summary": RULES_SUMMARY,
        "timezone_label": TZ_LABEL,
    }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


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
        try:
            dt = datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
            dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _iso_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _iso_display(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_OFFSET).isoformat()




def _maybe_enable_lottery_after_first_campaign(db: Session) -> None:
    if _settings_fn is None or _save_settings_fn is None:
        return
    settings = dict(_settings_fn())
    if settings.get("lottery_enabled"):
        return
    row = db.execute(text("SELECT COUNT(*) FROM lottery_campaigns")).fetchone()
    if int(row[0] if row else 0) < 1:
        return
    settings["lottery_enabled"] = True
    _save_settings_fn(settings)

def _is_enabled() -> bool:
    if _settings_fn is None:
        return False
    return bool(_settings_fn().get("lottery_enabled", False))


def ensure_lottery_schema(engine: Engine) -> None:
    """Cria tabelas do sorteio (idempotente — MySQL e SQLite)."""
    is_sqlite = "sqlite" in str(engine.url).lower()
    if is_sqlite:
        stmts = [
            """
            CREATE TABLE IF NOT EXISTS lottery_campaigns (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              sequence_number INTEGER NOT NULL UNIQUE,
              title VARCHAR(200) NOT NULL,
              status VARCHAR(16) NOT NULL DEFAULT 'DRAFT',
              draw_at DATETIME NOT NULL,
              winning_numbers_count INTEGER NOT NULL DEFAULT 1,
              prize_amber_base INTEGER NOT NULL DEFAULT 5000,
              prize_amber_rollover_in INTEGER NOT NULL DEFAULT 0,
              prize_amber_from_purchases INTEGER NOT NULL DEFAULT 0,
              prize_amber_paid INTEGER NOT NULL DEFAULT 0,
              prize_amber_subsidy INTEGER NOT NULL DEFAULT 0,
              prize_pool_fully_distributed INTEGER NOT NULL DEFAULT 0,
              matched_winners_count INTEGER NOT NULL DEFAULT 0,
              prize_amber_rollover_out INTEGER NOT NULL DEFAULT 0,
              amber_random_price INTEGER NOT NULL DEFAULT 1000,
              amber_reserve_price INTEGER NOT NULL DEFAULT 2000,
              amber_random_max_per_player INTEGER NOT NULL DEFAULT 5,
              regulamento_version VARCHAR(16) NOT NULL DEFAULT '1.0',
              allow_staff_participation INTEGER NOT NULL DEFAULT 1,
              auto_chain_enabled INTEGER NOT NULL DEFAULT 1,
              next_campaign_draw_offset_hours INTEGER NOT NULL DEFAULT 168,
              previous_campaign_id INTEGER NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              completed_at DATETIME NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS lottery_numbers (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              campaign_id INTEGER NOT NULL,
              steam_id VARCHAR(32) NOT NULL,
              payment_id VARCHAR(64) NULL,
              source VARCHAR(16) NOT NULL,
              number_value INTEGER NOT NULL,
              amber_cost INTEGER NOT NULL DEFAULT 0,
              status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
              assigned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              revoked_at DATETIME NULL,
              revoke_reason VARCHAR(64) NULL,
              UNIQUE(campaign_id, number_value)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS lottery_draw_results (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              campaign_id INTEGER NOT NULL UNIQUE,
              winning_numbers_json TEXT NOT NULL,
              seed_commit_hash VARCHAR(64) NOT NULL,
              seed_reveal VARCHAR(128) NULL,
              algorithm_version VARCHAR(16) NOT NULL,
              audit_blob_json TEXT NOT NULL,
              drawn_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              job_id VARCHAR(64) NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS lottery_winners (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              campaign_id INTEGER NOT NULL,
              draw_result_id INTEGER NOT NULL,
              steam_id VARCHAR(32) NOT NULL,
              winning_number INTEGER NOT NULL,
              prize_amber INTEGER NOT NULL,
              share_per_match INTEGER NOT NULL,
              credited INTEGER NOT NULL DEFAULT 0,
              credited_at DATETIME NULL,
              ledger_idempotency_key VARCHAR(128) NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS lottery_regulamento_acceptances (
              steam_id VARCHAR(32) NOT NULL,
              version VARCHAR(16) NOT NULL,
              accepted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              ip_hash VARCHAR(64) NULL,
              PRIMARY KEY (steam_id, version)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS lottery_audit_log (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              campaign_id INTEGER NULL,
              event_type VARCHAR(64) NOT NULL,
              payload_json TEXT NOT NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_lot_camp_status ON lottery_campaigns (status, draw_at)",
            "CREATE INDEX IF NOT EXISTS idx_lot_num_camp ON lottery_numbers (campaign_id, steam_id)",
            "CREATE INDEX IF NOT EXISTS idx_lot_num_pay ON lottery_numbers (payment_id)",
        ]
    else:
        stmts = [
            """
            CREATE TABLE IF NOT EXISTS lottery_campaigns (
              id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
              sequence_number INT NOT NULL,
              title VARCHAR(200) NOT NULL,
              status VARCHAR(16) NOT NULL DEFAULT 'DRAFT',
              draw_at DATETIME(3) NOT NULL,
              winning_numbers_count TINYINT NOT NULL DEFAULT 1,
              prize_amber_base INT NOT NULL DEFAULT 5000,
              prize_amber_rollover_in INT NOT NULL DEFAULT 0,
              prize_amber_from_purchases INT NOT NULL DEFAULT 0,
              prize_amber_paid INT NOT NULL DEFAULT 0,
              prize_amber_subsidy INT NOT NULL DEFAULT 0,
              prize_pool_fully_distributed TINYINT(1) NOT NULL DEFAULT 0,
              matched_winners_count TINYINT NOT NULL DEFAULT 0,
              prize_amber_rollover_out INT NOT NULL DEFAULT 0,
              amber_random_price INT NOT NULL DEFAULT 1000,
              amber_reserve_price INT NOT NULL DEFAULT 2000,
              amber_random_max_per_player TINYINT NOT NULL DEFAULT 5,
              regulamento_version VARCHAR(16) NOT NULL DEFAULT '1.0',
              allow_staff_participation TINYINT(1) NOT NULL DEFAULT 1,
              auto_chain_enabled TINYINT(1) NOT NULL DEFAULT 1,
              next_campaign_draw_offset_hours INT NOT NULL DEFAULT 168,
              previous_campaign_id BIGINT UNSIGNED NULL,
              created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
              updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
              completed_at DATETIME(3) NULL,
              UNIQUE KEY uq_lot_seq (sequence_number),
              KEY idx_lot_camp_status (status, draw_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS lottery_numbers (
              id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
              campaign_id BIGINT UNSIGNED NOT NULL,
              steam_id VARCHAR(32) NOT NULL,
              payment_id VARCHAR(64) NULL,
              source VARCHAR(16) NOT NULL,
              number_value SMALLINT NOT NULL,
              amber_cost INT NOT NULL DEFAULT 0,
              status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
              assigned_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
              revoked_at DATETIME(3) NULL,
              revoke_reason VARCHAR(64) NULL,
              UNIQUE KEY uq_lot_camp_num (campaign_id, number_value),
              KEY idx_lot_num_camp (campaign_id, steam_id),
              KEY idx_lot_num_pay (payment_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS lottery_draw_results (
              id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
              campaign_id BIGINT UNSIGNED NOT NULL,
              winning_numbers_json JSON NOT NULL,
              seed_commit_hash VARCHAR(64) NOT NULL,
              seed_reveal VARCHAR(128) NULL,
              algorithm_version VARCHAR(16) NOT NULL,
              audit_blob_json JSON NOT NULL,
              drawn_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
              job_id VARCHAR(64) NOT NULL,
              UNIQUE KEY uq_lot_draw_camp (campaign_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS lottery_winners (
              id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
              campaign_id BIGINT UNSIGNED NOT NULL,
              draw_result_id BIGINT UNSIGNED NOT NULL,
              steam_id VARCHAR(32) NOT NULL,
              winning_number SMALLINT NOT NULL,
              prize_amber INT NOT NULL,
              share_per_match INT NOT NULL,
              credited TINYINT(1) NOT NULL DEFAULT 0,
              credited_at DATETIME(3) NULL,
              ledger_idempotency_key VARCHAR(128) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS lottery_regulamento_acceptances (
              steam_id VARCHAR(32) NOT NULL,
              version VARCHAR(16) NOT NULL,
              accepted_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
              ip_hash VARCHAR(64) NULL,
              PRIMARY KEY (steam_id, version)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS lottery_audit_log (
              id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
              campaign_id BIGINT UNSIGNED NULL,
              event_type VARCHAR(64) NOT NULL,
              payload_json JSON NOT NULL,
              created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
              KEY idx_lot_audit_camp (campaign_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        ]
    with engine.connect() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))
        conn.commit()


def _audit(db: Session, event_type: str, payload: dict[str, Any], *, campaign_id: int | None = None) -> None:
    db.execute(
        text(
            "INSERT INTO lottery_audit_log (campaign_id, event_type, payload_json, created_at) "
            "VALUES (:cid, :et, :pj, :now)"
        ),
        {
            "cid": campaign_id,
            "et": event_type,
            "pj": json.dumps(payload, ensure_ascii=False),
            "now": _naive(_utcnow()),
        },
    )


def mask_display_name(name: str) -> str:
    src = (name or "Jogador").strip() or "Jogador"
    if len(src) <= 3:
        return "***"
    tail_n = 0 if len(src) <= 6 else min(3, max(1, len(src) - 6))
    return src[:3] + "***" + (src[-tail_n:] if tail_n else "")


def _fetch_campaign_row(db: Session, campaign_id: int) -> Any | None:
    return db.execute(
        text("SELECT * FROM lottery_campaigns WHERE id = :id"),
        {"id": campaign_id},
    ).fetchone()


def get_active_campaign(db: Session) -> Any | None:
    return db.execute(
        text(
            "SELECT * FROM lottery_campaigns WHERE status IN ('ACTIVE', 'DRAWING') "
            "ORDER BY CASE status WHEN 'ACTIVE' THEN 0 ELSE 1 END, id DESC LIMIT 1"
        )
    ).fetchone()


def _prize_total(row: Any) -> int:
    return (
        int(row.prize_amber_base or 0)
        + int(row.prize_amber_rollover_in or 0)
        + int(row.prize_amber_from_purchases or 0)
    )


def _campaign_public_dict(row: Any, *, db: Session | None = None) -> dict[str, Any]:
    draw = _parse_dt(row.draw_at)
    now = _utcnow()
    secs = max(0, int((draw - now).total_seconds())) if draw and draw > now else 0
    issued = 0
    participants = 0
    donated = 0.0
    if db is not None:
        issued = _numbers_issued_count(db, int(row.id))
        participants = _participant_count(db, int(row.id))
        donated = _total_donated_brl(db, int(row.id))
    return {
        "id": int(row.id),
        "sequence_number": int(row.sequence_number),
        "title": str(row.title),
        "status": str(row.status),
        "draw_at_utc": _iso_utc(draw),
        "draw_at_display": _iso_display(draw),
        "timezone_label": TZ_LABEL,
        "seconds_remaining": secs,
        "prize_amber_total": _prize_total(row),
        "prize_amber_base": int(row.prize_amber_base or 0),
        "prize_amber_rollover_in": int(row.prize_amber_rollover_in or 0),
        "prize_amber_from_purchases": int(row.prize_amber_from_purchases or 0),
        "amber_random_price": int(row.amber_random_price or 1000),
        "amber_reserve_price": int(row.amber_reserve_price or 2000),
        "amber_random_max_per_player": int(row.amber_random_max_per_player or 5),
        "numbers_available_count": 900 - issued,
        "winning_numbers_count": int(row.winning_numbers_count or 1),
        "participant_count": participants,
        "numbers_issued_count": issued,
        "total_donated_brl": round(donated, 2),
        "regulamento_version": str(row.regulamento_version or LOTTERY_REGULAMENTO_VERSION),
        "rules_summary": RULES_SUMMARY,
        "results_pending": str(row.status) == "DRAWING",
    }


def _numbers_issued_count(db: Session, campaign_id: int) -> int:
    row = db.execute(
        text(
            "SELECT COUNT(*) FROM lottery_numbers "
            "WHERE campaign_id = :cid AND status = 'ACTIVE'"
        ),
        {"cid": campaign_id},
    ).fetchone()
    return int(row[0] if row else 0)


def _participant_count(db: Session, campaign_id: int) -> int:
    row = db.execute(
        text(
            "SELECT COUNT(DISTINCT steam_id) FROM lottery_numbers "
            "WHERE campaign_id = :cid AND status = 'ACTIVE'"
        ),
        {"cid": campaign_id},
    ).fetchone()
    return int(row[0] if row else 0)


def _total_donated_brl(db: Session, campaign_id: int) -> float:
    row = db.execute(
        text(
            "SELECT COUNT(*) FROM lottery_numbers "
            "WHERE campaign_id = :cid AND source = 'DONATION' AND status = 'ACTIVE'"
        ),
        {"cid": campaign_id},
    ).fetchone()
    return float(int(row[0] if row else 0) * 5)


def _occupied_numbers(db: Session, campaign_id: int) -> set[int]:
    rows = db.execute(
        text(
            "SELECT number_value FROM lottery_numbers "
            "WHERE campaign_id = :cid AND status = 'ACTIVE'"
        ),
        {"cid": campaign_id},
    ).fetchall()
    return {int(r.number_value) for r in rows}


def _pick_random_free(db: Session, campaign_id: int, occupied: set[int] | None = None) -> int:
    if occupied is None:
        occupied = _occupied_numbers(db, campaign_id)
    if len(occupied) >= 900:
        raise ValueError("pool_exhausted")
    rng = secrets.SystemRandom()
    for _ in range(_MAX_RANDOM_ATTEMPTS):
        n = rng.randint(NUMBER_MIN, NUMBER_MAX)
        if n not in occupied:
            return n
    free = [n for n in range(NUMBER_MIN, NUMBER_MAX + 1) if n not in occupied]
    if not free:
        raise ValueError("pool_exhausted")
    return rng.choice(free)


def _insert_number(
    db: Session,
    *,
    campaign_id: int,
    steam_id: str,
    number_value: int,
    source: str,
    payment_id: str | None = None,
    amber_cost: int = 0,
) -> None:
    db.execute(
        text(
            "INSERT INTO lottery_numbers "
            "(campaign_id, steam_id, payment_id, source, number_value, amber_cost, status, assigned_at) "
            "VALUES (:cid, :sid, :pid, :src, :num, :cost, 'ACTIVE', :now)"
        ),
        {
            "cid": campaign_id,
            "sid": steam_id,
            "pid": payment_id,
            "src": source,
            "num": number_value,
            "cost": amber_cost,
            "now": _naive(_utcnow()),
        },
    )


def _player_balance(db: Session, steam_id: str) -> int:
    row = db.execute(
        text("SELECT points FROM players WHERE steam_id = :sid"),
        {"sid": steam_id},
    ).fetchone()
    return int(row[0] if row else 0)


def _random_purchase_count(db: Session, campaign_id: int, steam_id: str) -> int:
    row = db.execute(
        text(
            "SELECT COUNT(*) FROM lottery_numbers "
            "WHERE campaign_id = :cid AND steam_id = :sid AND source = 'AMBER_RANDOM' AND status = 'ACTIVE'"
        ),
        {"cid": campaign_id, "sid": steam_id},
    ).fetchone()
    return int(row[0] if row else 0)


def _resolve_display_name(db: Session, steam_id: str) -> str:
    row = db.execute(
        text(
            "SELECT market_display_name, steam_persona FROM store_users "
            "WHERE steam_id = :sid LIMIT 1"
        ),
        {"sid": steam_id},
    ).fetchone()
    if row:
        for col in (row.market_display_name, row.steam_persona):
            if col and str(col).strip():
                return str(col).strip()
    return "Jogador"


def on_donation_credited(
    db: Session,
    *,
    payment_id: str,
    steam_id: str,
    amount_brl: float,
) -> dict[str, Any] | None:
    """Hook pós-crédito PIX — idempotente por payment_id."""
    if not _is_enabled():
        return None
    campaign = get_active_campaign(db)
    if not campaign or str(campaign.status) != "ACTIVE":
        return None
    existing = db.execute(
        text(
            "SELECT COUNT(*) FROM lottery_numbers WHERE payment_id = :pid AND status = 'ACTIVE'"
        ),
        {"pid": payment_id},
    ).fetchone()
    if existing and int(existing[0]) > 0:
        return {"skipped": True, "reason": "already_assigned"}
    qty = int(math.floor(float(amount_brl) / 5.0))
    if qty <= 0:
        return {"assigned": 0}
    cid = int(campaign.id)
    numbers: list[int] = []
    occupied = _occupied_numbers(db, cid)
    for _ in range(qty):
        if len(occupied) >= 900:
            _audit(db, "lottery_pool_exhausted", {"payment_id": payment_id}, campaign_id=cid)
            break
        n = _pick_random_free(db, cid, occupied)
        _insert_number(
            db, campaign_id=cid, steam_id=steam_id, number_value=n,
            source="DONATION", payment_id=payment_id,
        )
        occupied.add(n)
        numbers.append(n)
    _audit(
        db, "lottery_numbers_assigned",
        {"payment_id": payment_id, "steam_id": steam_id, "numbers": numbers, "qty": len(numbers)},
        campaign_id=cid,
    )
    return {"assigned": len(numbers), "numbers": numbers}


def revoke_lottery_numbers_for_payment(db: Session, *, payment_id: str) -> int:
    now = _naive(_utcnow())
    result = db.execute(
        text(
            "UPDATE lottery_numbers SET status = 'REVOKED', revoked_at = :now, revoke_reason = 'chargeback' "
            "WHERE payment_id = :pid AND source = 'DONATION' AND status = 'ACTIVE'"
        ),
        {"now": now, "pid": payment_id},
    )
    return int(getattr(result, "rowcount", 0) or 0)


def buy_random_number(db: Session, steam_id: str) -> dict[str, Any]:
    if not _is_enabled():
        raise ValueError("lottery_disabled")
    campaign = get_active_campaign(db)
    if not campaign or str(campaign.status) != "ACTIVE":
        raise ValueError("no_active_campaign")
    cid = int(campaign.id)
    max_p = int(campaign.amber_random_max_per_player or 5)
    price = int(campaign.amber_random_price or 1000)
    if _random_purchase_count(db, cid, steam_id) >= max_p:
        raise ValueError("random_limit_reached")
    if _player_balance(db, steam_id) < price:
        raise ValueError("insufficient_balance")
    if _debit_fn is None:
        raise RuntimeError("lottery_not_configured")
    n = _pick_random_free(db, cid)
    _debit_fn(db, steam_id, price)
    try:
        from amber_ledger import record_lottery_amber_purchase

        record_lottery_amber_purchase(
            db, campaign_id=cid, steam_id=steam_id, amount=price,
            source="AMBER_RANDOM", number_value=n,
        )
    except Exception as exc:
        log.warning("Ledger lottery purchase: %s", exc)
    _insert_number(
        db, campaign_id=cid, steam_id=steam_id, number_value=n,
        source="AMBER_RANDOM", amber_cost=price,
    )
    db.execute(
        text(
            "UPDATE lottery_campaigns SET prize_amber_from_purchases = prize_amber_from_purchases + :amt, "
            "updated_at = :now WHERE id = :id"
        ),
        {"amt": price, "now": _naive(_utcnow()), "id": cid},
    )
    remaining = max_p - _random_purchase_count(db, cid, steam_id)
    row = _fetch_campaign_row(db, cid)
    _audit(db, "lottery_amber_random_purchased", {"steam_id": steam_id, "number": n}, campaign_id=cid)
    return {
        "number": {"value": n, "source": "AMBER_RANDOM", "amber_cost": price},
        "amber_random_remaining": remaining,
        "prize_amber_total": _prize_total(row) if row else 0,
        "new_balance": _player_balance(db, steam_id),
    }


def reserve_number(db: Session, steam_id: str, number: int) -> dict[str, Any]:
    if not _is_enabled():
        raise ValueError("lottery_disabled")
    number = int(number)
    if number < NUMBER_MIN or number > NUMBER_MAX:
        raise ValueError("invalid_number")
    campaign = get_active_campaign(db)
    if not campaign or str(campaign.status) != "ACTIVE":
        raise ValueError("no_active_campaign")
    cid = int(campaign.id)
    price = int(campaign.amber_reserve_price or 2000)
    if _player_balance(db, steam_id) < price:
        raise ValueError("insufficient_balance")
    taken = db.execute(
        text(
            "SELECT id FROM lottery_numbers WHERE campaign_id = :cid AND number_value = :num "
            "AND status = 'ACTIVE' LIMIT 1"
        ),
        {"cid": cid, "num": number},
    ).fetchone()
    if taken:
        raise ValueError("number_unavailable")
    if _debit_fn is None:
        raise RuntimeError("lottery_not_configured")
    _debit_fn(db, steam_id, price)
    try:
        from amber_ledger import record_lottery_amber_purchase

        record_lottery_amber_purchase(
            db, campaign_id=cid, steam_id=steam_id, amount=price,
            source="AMBER_RESERVE", number_value=number,
        )
    except Exception as exc:
        log.warning("Ledger lottery reserve: %s", exc)
    try:
        _insert_number(
            db, campaign_id=cid, steam_id=steam_id, number_value=number,
            source="AMBER_RESERVE", amber_cost=price,
        )
    except Exception:
        raise ValueError("number_unavailable")
    db.execute(
        text(
            "UPDATE lottery_campaigns SET prize_amber_from_purchases = prize_amber_from_purchases + :amt, "
            "updated_at = :now WHERE id = :id"
        ),
        {"amt": price, "now": _naive(_utcnow()), "id": cid},
    )
    row = _fetch_campaign_row(db, cid)
    _audit(db, "lottery_amber_reserved", {"steam_id": steam_id, "number": number}, campaign_id=cid)
    return {
        "number": {"value": number, "source": "AMBER_RESERVE", "amber_cost": price},
        "prize_amber_total": _prize_total(row) if row else 0,
        "new_balance": _player_balance(db, steam_id),
    }


def get_public_current(db: Session) -> dict[str, Any]:
    row = get_active_campaign(db)
    base = {
        "regulamento_version": LOTTERY_REGULAMENTO_VERSION,
        "regulamento_url": "/api/public/lottery/regulamento",
    }
    if not row:
        return {"ok": True, "campaign": None, "enabled": _is_enabled(), **base}
    return {"ok": True, "campaign": _campaign_public_dict(row, db=db), "enabled": _is_enabled(), **base}


def get_number_grid(db: Session, campaign_id: int, *, viewer_steam_id: str | None = None) -> dict[str, Any]:
    occupied = _occupied_numbers(db, campaign_id)
    mine: set[int] = set()
    if viewer_steam_id:
        rows = db.execute(
            text(
                "SELECT number_value FROM lottery_numbers "
                "WHERE campaign_id = :cid AND steam_id = :sid AND status = 'ACTIVE'"
            ),
            {"cid": campaign_id, "sid": viewer_steam_id},
        ).fetchall()
        mine = {int(r.number_value) for r in rows}
    cells = []
    for n in range(NUMBER_MIN, NUMBER_MAX + 1):
        cell: dict[str, Any] = {
            "value": n,
            "status": "taken" if n in occupied else "available",
        }
        if n in mine:
            cell["is_mine"] = True
        cells.append(cell)
    return {
        "ok": True,
        "campaign_id": campaign_id,
        "cells": cells,
        "summary": {"available": 900 - len(occupied), "taken": len(occupied), "total": 900},
    }


def get_participants_public(
    db: Session,
    campaign_id: int,
    *,
    page: int = 1,
    page_size: int = 50,
    search_number: int | None = None,
) -> dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    params: dict[str, Any] = {"cid": campaign_id}
    having = ""
    if search_number is not None:
        having = " HAVING SUM(CASE WHEN ln.number_value = :snum THEN 1 ELSE 0 END) > 0"
        params["snum"] = int(search_number)
    count_row = db.execute(
        text(
            f"SELECT COUNT(*) FROM ("
            f"SELECT ln.steam_id FROM lottery_numbers ln "
            f"WHERE ln.campaign_id = :cid AND ln.status = 'ACTIVE' "
            f"GROUP BY ln.steam_id{having}"
            f") t"
        ),
        params,
    ).fetchone()
    total = int(count_row[0] if count_row else 0)
    offset = (page - 1) * page_size
    params["lim"] = page_size
    params["off"] = offset
    is_sqlite = "sqlite" in str(db.bind.url).lower()
    if is_sqlite:
        agg_sql = (
            f"SELECT ln.steam_id, "
            f"GROUP_CONCAT(ln.number_value || ':' || ln.source) AS nums, "
            f"MAX(ln.assigned_at) AS last_at "
            f"FROM lottery_numbers ln "
            f"WHERE ln.campaign_id = :cid AND ln.status = 'ACTIVE' "
            f"GROUP BY ln.steam_id{having} "
            f"ORDER BY last_at DESC LIMIT :lim OFFSET :off"
        )
    else:
        agg_sql = (
            f"SELECT ln.steam_id, "
            f"GROUP_CONCAT(CONCAT(ln.number_value, ':', ln.source) ORDER BY ln.number_value) AS nums, "
            f"MAX(ln.assigned_at) AS last_at "
            f"FROM lottery_numbers ln "
            f"WHERE ln.campaign_id = :cid AND ln.status = 'ACTIVE' "
            f"GROUP BY ln.steam_id{having} "
            f"ORDER BY last_at DESC LIMIT :lim OFFSET :off"
        )
    rows = db.execute(text(agg_sql), params).fetchall()
    participants = []
    for r in rows:
        sid = str(r.steam_id)
        name = _resolve_display_name(db, sid)
        numbers = []
        raw = str(r.nums or "")
        for part in raw.split(","):
            if ":" not in part:
                continue
            val_s, src = part.split(":", 1)
            numbers.append({"value": int(val_s), "source": src})
        participants.append({
            "display_name_masked": mask_display_name(name),
            "numbers": numbers,
            "last_assigned_at": _iso_display(_parse_dt(r.last_at)),
        })
    return {
        "ok": True,
        "campaign_id": campaign_id,
        "page": page,
        "page_size": page_size,
        "total": total,
        "participants": participants,
    }


def get_player_me(db: Session, steam_id: str) -> dict[str, Any]:
    row = get_active_campaign(db)
    if not row:
        return {"ok": True, "campaign": None, "numbers": [], "enabled": _is_enabled()}
    cid = int(row.id)
    nums = db.execute(
        text(
            "SELECT number_value, source, amber_cost, assigned_at, payment_id "
            "FROM lottery_numbers WHERE campaign_id = :cid AND steam_id = :sid AND status = 'ACTIVE' "
            "ORDER BY assigned_at ASC"
        ),
        {"cid": cid, "sid": steam_id},
    ).fetchall()
    by_source: dict[str, list[int]] = {"DONATION": [], "AMBER_RANDOM": [], "AMBER_RESERVE": []}
    items = []
    donated_brl = 0.0
    for n in nums:
        src = str(n.source)
        val = int(n.number_value)
        by_source.setdefault(src, []).append(val)
        items.append({
            "value": val,
            "source": src,
            "amber_cost": int(n.amber_cost or 0),
            "assigned_at": _iso_display(_parse_dt(n.assigned_at)),
        })
        if src == "DONATION":
            donated_brl += 5.0
    max_p = int(row.amber_random_max_per_player or 5)
    random_count = len(by_source.get("AMBER_RANDOM", []))
    return {
        "ok": True,
        "enabled": _is_enabled(),
        "campaign": _campaign_public_dict(row, db=db),
        "numbers": items,
        "by_source": by_source,
        "donated_brl": round(donated_brl, 2),
        "amber_random_count": random_count,
        "amber_random_remaining": max(0, max_p - random_count),
    }


def get_campaign_results(db: Session, campaign_id: int) -> dict[str, Any]:
    camp = _fetch_campaign_row(db, campaign_id)
    if not camp:
        raise ValueError("campaign_not_found")
    if str(camp.status) not in ("COMPLETED", "DRAWING"):
        raise ValueError("results_not_ready")
    draw = db.execute(
        text("SELECT * FROM lottery_draw_results WHERE campaign_id = :cid"),
        {"cid": campaign_id},
    ).fetchone()
    if not draw:
        raise ValueError("results_not_ready")
    winning = json.loads(str(draw.winning_numbers_json))
    winners_rows = db.execute(
        text(
            "SELECT * FROM lottery_winners WHERE campaign_id = :cid ORDER BY winning_number"
        ),
        {"cid": campaign_id},
    ).fetchall()
    winners = []
    for w in winners_rows:
        name = _resolve_display_name(db, str(w.steam_id))
        winners.append({
            "display_name_masked": mask_display_name(name),
            "winning_number": int(w.winning_number),
            "prize_amber": int(w.prize_amber),
        })
    matched = {int(w.winning_number) for w in winners_rows}
    unmatched = [n for n in winning if int(n) not in matched]
    audit = json.loads(str(draw.audit_blob_json))
    return {
        "ok": True,
        "campaign_id": campaign_id,
        "winning_numbers": winning,
        "winning_numbers_count": len(winning),
        "matched_count": int(camp.matched_winners_count or 0),
        "share_per_match": int(winners_rows[0].share_per_match) if winners_rows else 0,
        "prize_amber_total": _prize_total(camp),
        "prize_amber_paid": int(camp.prize_amber_paid or 0),
        "prize_amber_subsidy": int(camp.prize_amber_subsidy or 0),
        "prize_pool_fully_distributed": bool(int(camp.prize_pool_fully_distributed or 0)),
        "winners": winners,
        "unmatched_drawn_numbers": unmatched,
        "draw_audit": {
            "seed_hash": str(draw.seed_commit_hash),
            "algorithm": str(draw.algorithm_version),
            "drawn_at": _iso_utc(_parse_dt(draw.drawn_at)),
            "record_id": int(draw.id),
            **audit,
        },
        "rollover_next": int(camp.prize_amber_rollover_out or 0),
    }


def get_history(db: Session, *, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(50, page_size))
    offset = (page - 1) * page_size
    rows = db.execute(
        text(
            "SELECT * FROM lottery_campaigns WHERE status = 'COMPLETED' "
            "ORDER BY completed_at DESC, id DESC LIMIT :lim OFFSET :off"
        ),
        {"lim": page_size, "off": offset},
    ).fetchall()
    campaigns = []
    for row in rows:
        cid = int(row.id)
        try:
            res = get_campaign_results(db, cid)
        except ValueError:
            continue
        campaigns.append({
            "id": cid,
            "sequence_number": int(row.sequence_number),
            "title": str(row.title),
            "draw_at_display": _iso_display(_parse_dt(row.draw_at)),
            "winning_numbers": res["winning_numbers"],
            "winning_numbers_count": res["winning_numbers_count"],
            "matched_count": res["matched_count"],
            "share_per_match": res["share_per_match"],
            "prize_amber_total": res["prize_amber_total"],
            "prize_amber_paid": res["prize_amber_paid"],
            "prize_amber_subsidy": res["prize_amber_subsidy"],
            "prize_pool_fully_distributed": res["prize_pool_fully_distributed"],
            "winners": res["winners"],
            "unmatched_drawn_numbers": res.get("unmatched_drawn_numbers", []),
            "rollover_out": int(row.prize_amber_rollover_out or 0),
            "rollover_bonus_applied": int(row.matched_winners_count or 0) == 0,
        })
    return {"ok": True, "page": page, "campaigns": campaigns}


def _next_sequence(db: Session) -> int:
    row = db.execute(text("SELECT COALESCE(MAX(sequence_number), 0) + 1 FROM lottery_campaigns")).fetchone()
    return int(row[0] if row else 1)


def create_campaign_draft(db: Session, *, data: dict[str, Any], admin_steam_id: str | None = None) -> dict[str, Any]:
    seq = _next_sequence(db)
    now = _naive(_utcnow())
    draw_at = _parse_dt(data.get("draw_at")) or (_utcnow() + timedelta(days=7))
    db.execute(
        text(
            "INSERT INTO lottery_campaigns "
            "(sequence_number, title, status, draw_at, winning_numbers_count, prize_amber_base, "
            "prize_amber_rollover_in, amber_random_price, amber_reserve_price, "
            "amber_random_max_per_player, regulamento_version, allow_staff_participation, "
            "auto_chain_enabled, next_campaign_draw_offset_hours, created_at, updated_at) "
            "VALUES (:seq, :title, 'DRAFT', :draw, :wnc, :base, :rol, :arp, :aresv, :armax, "
            ":reg, :staff, :chain, :offset, :now, :now)"
        ),
        {
            "seq": seq,
            "title": str(data.get("title") or f"Sorteio ARKLAND #{seq}"),
            "draw": _naive(draw_at),
            "wnc": max(1, min(5, int(data.get("winning_numbers_count") or 1))),
            "base": int(data.get("prize_amber_base") or 5000),
            "rol": int(data.get("prize_amber_rollover_in") or 0),
            "arp": int(data.get("amber_random_price") or 1000),
            "aresv": int(data.get("amber_reserve_price") or 2000),
            "armax": int(data.get("amber_random_max_per_player") or 5),
            "reg": str(data.get("regulamento_version") or LOTTERY_REGULAMENTO_VERSION),
            "staff": 1 if data.get("allow_staff_participation", True) else 0,
            "chain": 1 if data.get("auto_chain_enabled", True) else 0,
            "offset": int(data.get("next_campaign_draw_offset_hours") or 168),
            "now": now,
        },
    )
    db.flush()
    row = db.execute(
        text("SELECT * FROM lottery_campaigns WHERE sequence_number = :seq ORDER BY id DESC LIMIT 1"),
        {"seq": seq},
    ).fetchone()
    cid = int(row.id)
    _audit(db, "lottery_campaign_created", {"admin": admin_steam_id}, campaign_id=cid)
    _maybe_enable_lottery_after_first_campaign(db)
    return _campaign_public_dict(row, db=db)


def publish_campaign(db: Session, campaign_id: int) -> dict[str, Any]:
    row = _fetch_campaign_row(db, campaign_id)
    if not row:
        raise ValueError("campaign_not_found")
    if str(row.status) != "DRAFT":
        raise ValueError("invalid_status")
    active = get_active_campaign(db)
    if active and str(active.status) == "ACTIVE":
        raise ValueError("active_campaign_exists")
    now = _naive(_utcnow())
    db.execute(
        text("UPDATE lottery_campaigns SET status = 'ACTIVE', updated_at = :now WHERE id = :id"),
        {"now": now, "id": campaign_id},
    )
    _audit(db, "lottery_campaign_published", {}, campaign_id=campaign_id)
    row = _fetch_campaign_row(db, campaign_id)
    return _campaign_public_dict(row, db=db)


def update_campaign(db: Session, campaign_id: int, patch: dict[str, Any]) -> dict[str, Any]:
    row = _fetch_campaign_row(db, campaign_id)
    if not row:
        raise ValueError("campaign_not_found")
    if str(row.status) not in ("DRAFT", "ACTIVE"):
        raise ValueError("invalid_status")
    fields = []
    params: dict[str, Any] = {"id": campaign_id, "now": _naive(_utcnow())}
    if "title" in patch:
        fields.append("title = :title")
        params["title"] = str(patch["title"])
    if "draw_at" in patch:
        dt = _parse_dt(patch["draw_at"])
        if dt:
            fields.append("draw_at = :draw_at")
            params["draw_at"] = _naive(dt)
    if "winning_numbers_count" in patch:
        fields.append("winning_numbers_count = :wnc")
        params["wnc"] = max(1, min(5, int(patch["winning_numbers_count"])))
    if "prize_amber_base" in patch:
        fields.append("prize_amber_base = :base")
        params["base"] = int(patch["prize_amber_base"])
    if "allow_staff_participation" in patch:
        fields.append("allow_staff_participation = :staff")
        params["staff"] = 1 if patch["allow_staff_participation"] else 0
    if not fields:
        return _campaign_public_dict(row, db=db)
    fields.append("updated_at = :now")
    db.execute(text(f"UPDATE lottery_campaigns SET {', '.join(fields)} WHERE id = :id"), params)
    row = _fetch_campaign_row(db, campaign_id)
    return _campaign_public_dict(row, db=db)


def cancel_campaign(db: Session, campaign_id: int, *, reason: str) -> dict[str, Any]:
    reason = str(reason or "").strip()
    if len(reason) < 20:
        raise ValueError("reason_too_short")
    row = _fetch_campaign_row(db, campaign_id)
    if not row:
        raise ValueError("campaign_not_found")
    if str(row.status) != "ACTIVE":
        raise ValueError("invalid_status")
    now = _naive(_utcnow())
    rollover = int(row.prize_amber_rollover_in or 0)
    db.execute(
        text(
            "UPDATE lottery_campaigns SET status = 'CANCELLED', prize_amber_rollover_out = :rol, "
            "updated_at = :now, completed_at = :now WHERE id = :id"
        ),
        {"rol": rollover, "now": now, "id": campaign_id},
    )
    db.execute(
        text(
            "UPDATE lottery_numbers SET status = 'REVOKED', revoked_at = :now, revoke_reason = 'cancelled' "
            "WHERE campaign_id = :cid AND status = 'ACTIVE'"
        ),
        {"now": now, "cid": campaign_id},
    )
    _audit(db, "lottery_campaign_cancelled", {"reason": reason}, campaign_id=campaign_id)
    row = _fetch_campaign_row(db, campaign_id)
    return _campaign_public_dict(row, db=db)


def list_campaigns_admin(db: Session, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = db.execute(
        text("SELECT * FROM lottery_campaigns ORDER BY id DESC LIMIT :lim"),
        {"lim": limit},
    ).fetchall()
    return [_campaign_public_dict(r, db=db) for r in rows]


def run_draw(db: Session, campaign_id: int, *, job_id: str) -> dict[str, Any]:
    """Executa sorteio + crédito prêmios + auto-chain."""
    row = _fetch_campaign_row(db, campaign_id)
    if not row:
        raise ValueError("campaign_not_found")
    if str(row.status) not in ("ACTIVE", "DRAWING"):
        raise ValueError("invalid_status")
    existing_draw = db.execute(
        text("SELECT id FROM lottery_draw_results WHERE campaign_id = :cid"),
        {"cid": campaign_id},
    ).fetchone()
    if existing_draw:
        raise ValueError("already_drawn")
    now = _naive(_utcnow())
    db.execute(
        text("UPDATE lottery_campaigns SET status = 'DRAWING', updated_at = :now WHERE id = :id"),
        {"now": now, "id": campaign_id},
    )
    cid = int(campaign_id)
    w_count = int(row.winning_numbers_count or 1)
    participants = _participant_count(db, cid)
    issued = _numbers_issued_count(db, cid)
    draw_at_iso = _iso_utc(_parse_dt(row.draw_at)) or ""
    winning, audit_blob = draw_winning_numbers(
        w_count,
        campaign_id=cid,
        draw_at_iso=draw_at_iso,
        participant_count=participants,
        numbers_issued_count=issued,
    )
    prize_total = _prize_total(row)
    holders = db.execute(
        text(
            "SELECT steam_id, number_value FROM lottery_numbers "
            "WHERE campaign_id = :cid AND status = 'ACTIVE' AND number_value IN :nums"
        ) if False else text(
            "SELECT steam_id, number_value FROM lottery_numbers "
            "WHERE campaign_id = :cid AND status = 'ACTIVE'"
        ),
        {"cid": cid},
    ).fetchall()
    holder_map = {int(h.number_value): str(h.steam_id) for h in holders}
    matched_winners = [
        {"steam_id": holder_map[n], "winning_number": n}
        for n in winning if n in holder_map
    ]
    matched_count = len(matched_winners)
    split = compute_prize_split(prize_total, matched_count)
    db.execute(
        text(
            "INSERT INTO lottery_draw_results "
            "(campaign_id, winning_numbers_json, seed_commit_hash, algorithm_version, "
            "audit_blob_json, drawn_at, job_id) "
            "VALUES (:cid, :wn, :sh, :alg, :ab, :now, :jid)"
        ),
        {
            "cid": cid,
            "wn": json.dumps(winning),
            "sh": audit_blob["seed_hash"],
            "alg": ALGORITHM_VERSION,
            "ab": audit_blob_json(audit_blob),
            "now": now,
            "jid": job_id,
        },
    )
    draw_row = db.execute(
        text("SELECT id FROM lottery_draw_results WHERE campaign_id = :cid"),
        {"cid": cid},
    ).fetchone()
    draw_id = int(draw_row.id)
    share = int(split["share_per_match"])
    if _credit_fn and matched_count > 0:
        for mw in matched_winners:
            sid = mw["steam_id"]
            num = mw["winning_number"]
            idem = f"lottery:prize:{cid}:{num}"
            db.execute(
                text(
                    "INSERT INTO lottery_winners "
                    "(campaign_id, draw_result_id, steam_id, winning_number, prize_amber, "
                    "share_per_match, credited, credited_at, ledger_idempotency_key) "
                    "VALUES (:cid, :did, :sid, :num, :prize, :share, 0, NULL, :idem)"
                ),
                {
                    "cid": cid, "did": draw_id, "sid": sid, "num": num,
                    "prize": share, "share": share, "idem": idem,
                },
            )
            _credit_fn(db, sid, share)
            try:
                from amber_ledger import record_lottery_prize

                record_lottery_prize(
                    db, campaign_id=cid, steam_id=sid, amount=share,
                    winning_number=num, idempotency_key=idem,
                )
            except Exception as exc:
                log.warning("Ledger lottery prize: %s", exc)
            db.execute(
                text(
                    "UPDATE lottery_winners SET credited = 1, credited_at = :now "
                    "WHERE campaign_id = :cid AND winning_number = :num"
                ),
                {"now": now, "cid": cid, "num": num},
            )
    subsidy = int(split["prize_amber_subsidy"])
    if subsidy > 0:
        try:
            from amber_ledger import record_lottery_prize_subsidy

            record_lottery_prize_subsidy(db, campaign_id=cid, amount=subsidy)
        except Exception as exc:
            log.warning("Ledger lottery subsidy: %s", exc)
    rollover_out = int(split["rollover_out"])
    db.execute(
        text(
            "UPDATE lottery_campaigns SET status = 'COMPLETED', "
            "prize_amber_paid = :paid, prize_amber_subsidy = :sub, "
            "prize_pool_fully_distributed = :pfd, matched_winners_count = :mc, "
            "prize_amber_rollover_out = :rol, updated_at = :now, completed_at = :now "
            "WHERE id = :id"
        ),
        {
            "paid": int(split["prize_amber_paid"]),
            "sub": subsidy,
            "pfd": 1 if split["prize_pool_fully_distributed"] else 0,
            "mc": matched_count,
            "rol": rollover_out,
            "now": now,
            "id": cid,
        },
    )
    _audit(
        db, "lottery_draw_completed",
        {"winning_numbers": winning, "matched_count": matched_count, "split": split},
        campaign_id=cid,
    )
    next_id = None
    if int(row.auto_chain_enabled or 0) and _is_enabled():
        next_id = _create_chained_campaign(db, row, rollover_out)
    return {
        "campaign_id": cid,
        "winning_numbers": winning,
        "matched_count": matched_count,
        "split": split,
        "next_campaign_id": next_id,
    }


def _create_chained_campaign(db: Session, prev_row: Any, rollover_in: int) -> int | None:
    seq = _next_sequence(db)
    now = _utcnow()
    offset_h = int(prev_row.next_campaign_draw_offset_hours or 168)
    draw_at = now + timedelta(hours=offset_h)
    ts = _naive(now)
    db.execute(
        text(
            "INSERT INTO lottery_campaigns "
            "(sequence_number, title, status, draw_at, winning_numbers_count, prize_amber_base, "
            "prize_amber_rollover_in, prize_amber_from_purchases, amber_random_price, amber_reserve_price, "
            "amber_random_max_per_player, regulamento_version, allow_staff_participation, "
            "auto_chain_enabled, next_campaign_draw_offset_hours, previous_campaign_id, created_at, updated_at) "
            "VALUES (:seq, :title, 'ACTIVE', :draw, :wnc, :base, :rol, 0, :arp, :aresv, :armax, "
            ":reg, :staff, :chain, :offset, :prev, :now, :now)"
        ),
        {
            "seq": seq,
            "title": f"Sorteio ARKLAND #{seq}",
            "draw": _naive(draw_at),
            "wnc": int(prev_row.winning_numbers_count or 1),
            "base": int(prev_row.prize_amber_base or 5000),
            "rol": int(rollover_in),
            "arp": int(prev_row.amber_random_price or 1000),
            "aresv": int(prev_row.amber_reserve_price or 2000),
            "armax": int(prev_row.amber_random_max_per_player or 5),
            "reg": str(prev_row.regulamento_version or LOTTERY_REGULAMENTO_VERSION),
            "staff": int(prev_row.allow_staff_participation or 1),
            "chain": int(prev_row.auto_chain_enabled or 1),
            "offset": offset_h,
            "prev": int(prev_row.id),
            "now": ts,
        },
    )
    row = db.execute(
        text("SELECT id FROM lottery_campaigns WHERE sequence_number = :seq ORDER BY id DESC LIMIT 1"),
        {"seq": seq},
    ).fetchone()
    return int(row.id) if row else None


def process_due_draws(db: Session) -> int:
    """Job periódico — sorteia campanhas ACTIVE com draw_at vencido."""
    if not _is_enabled():
        return 0
    now = _naive(_utcnow())
    rows = db.execute(
        text(
            "SELECT id FROM lottery_campaigns WHERE status = 'ACTIVE' AND draw_at <= :now"
        ),
        {"now": now},
    ).fetchall()
    processed = 0
    for r in rows:
        cid = int(r.id)
        try:
            is_sqlite = "sqlite" in str(db.bind.url).lower()
            if not is_sqlite:
                locked = db.execute(
                    text("SELECT id, status FROM lottery_campaigns WHERE id = :id FOR UPDATE"),
                    {"id": cid},
                ).fetchone()
                if not locked or str(locked.status) != "ACTIVE":
                    continue
            else:
                locked = db.execute(
                    text("SELECT id, status FROM lottery_campaigns WHERE id = :id"),
                    {"id": cid},
                ).fetchone()
                if not locked or str(locked.status) != "ACTIVE":
                    continue
            job_id = f"draw-{cid}-{_utcnow().strftime('%Y%m%d%H%M%S')}"
            run_draw(db, cid, job_id=job_id)
            db.commit()
            processed += 1
        except Exception as exc:
            db.rollback()
            log.warning("Lottery draw failed campaign=%s: %s", cid, exc)
    return processed


def regulamento_status(db: Session, steam_id: str) -> dict[str, Any]:
    row = db.execute(
        text(
            "SELECT 1 FROM lottery_regulamento_acceptances "
            "WHERE steam_id = :sid AND version = :ver LIMIT 1"
        ),
        {"sid": steam_id, "ver": LOTTERY_REGULAMENTO_VERSION},
    ).fetchone()
    return {
        "needs_accept": row is None,
        "version": LOTTERY_REGULAMENTO_VERSION,
    }


def accept_regulamento(db: Session, steam_id: str) -> dict[str, Any]:
    now = _naive(_utcnow())
    is_sqlite = "sqlite" in str(db.bind.url).lower()
    if is_sqlite:
        db.execute(
            text(
                "INSERT OR IGNORE INTO lottery_regulamento_acceptances "
                "(steam_id, version, accepted_at) VALUES (:sid, :ver, :now)"
            ),
            {"sid": steam_id, "ver": LOTTERY_REGULAMENTO_VERSION, "now": now},
        )
    else:
        db.execute(
            text(
                "INSERT IGNORE INTO lottery_regulamento_acceptances "
                "(steam_id, version, accepted_at) VALUES (:sid, :ver, :now)"
            ),
            {"sid": steam_id, "ver": LOTTERY_REGULAMENTO_VERSION, "now": now},
        )
    return {"accepted": True, "version": LOTTERY_REGULAMENTO_VERSION}
