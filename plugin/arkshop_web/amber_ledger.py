"""Âmbarômetro — ledger unificado de movimentação de Âmbares (gross turnover)."""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

try:
    from zoneinfo import ZoneInfo

    _SP_TZ = ZoneInfo("America/Sao_Paulo")
except Exception:
    _SP_TZ = timezone(timedelta(hours=-3))

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

log = logging.getLogger("arkshop_web.amber_ledger")

_PUBLIC_STATS_TTL = 60.0
_public_stats_lock = threading.Lock()
_public_stats_cache: dict[str, Any] = {"data": None, "expires": 0.0}
_schema_verified_engines: set[int] = set()
_schema_lock = threading.Lock()

COVERAGE_NOTE = "Inclui doações, loja web, mercado P2P, ajustes admin e enquetes."


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _naive_utc(dt: datetime | str | None) -> datetime:
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


def _sp_start_of_today_utc() -> datetime:
    now_sp = datetime.now(_SP_TZ)
    start_sp = now_sp.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_sp.astimezone(timezone.utc).replace(tzinfo=None)


def ensure_amber_schema(engine: Engine, *, run_backfill: bool = True) -> None:
    """Cria tabelas amber_ledger e amber_stats_cache (idempotente)."""
    is_sqlite = "sqlite" in str(engine.url).lower()
    if is_sqlite:
        ledger_ddl = """
        CREATE TABLE IF NOT EXISTS amber_ledger (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          occurred_at DATETIME NOT NULL,
          channel VARCHAR(32) NOT NULL,
          event_type VARCHAR(64) NOT NULL,
          gross_amount INTEGER NOT NULL,
          signed_delta INTEGER NOT NULL,
          steam_id VARCHAR(32) NULL,
          counterparty_id VARCHAR(32) NULL,
          source_table VARCHAR(64) NULL,
          source_id VARCHAR(128) NULL,
          idempotency_key VARCHAR(128) NOT NULL UNIQUE,
          metadata_json TEXT NULL
        )
        """
        cache_ddl = """
        CREATE TABLE IF NOT EXISTS amber_stats_cache (
          stat_key VARCHAR(64) PRIMARY KEY NOT NULL,
          stat_value BIGINT NOT NULL DEFAULT 0,
          computed_at DATETIME NOT NULL,
          period_start DATETIME NULL,
          period_end DATETIME NULL
        )
        """
        idx = [
            "CREATE INDEX IF NOT EXISTS idx_ledger_time ON amber_ledger (occurred_at)",
            "CREATE INDEX IF NOT EXISTS idx_ledger_channel_time ON amber_ledger (channel, occurred_at)",
        ]
    else:
        ledger_ddl = """
        CREATE TABLE IF NOT EXISTS amber_ledger (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          occurred_at DATETIME(3) NOT NULL,
          channel VARCHAR(32) NOT NULL,
          event_type VARCHAR(64) NOT NULL,
          gross_amount INT NOT NULL,
          signed_delta INT NOT NULL,
          steam_id VARCHAR(32) NULL,
          counterparty_id VARCHAR(32) NULL,
          source_table VARCHAR(64) NULL,
          source_id VARCHAR(128) NULL,
          idempotency_key VARCHAR(128) NOT NULL,
          metadata_json JSON NULL,
          INDEX idx_ledger_time (occurred_at),
          INDEX idx_ledger_channel_time (channel, occurred_at),
          UNIQUE KEY uq_ledger_idempotency (idempotency_key)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        cache_ddl = """
        CREATE TABLE IF NOT EXISTS amber_stats_cache (
          stat_key VARCHAR(64) PRIMARY KEY NOT NULL,
          stat_value BIGINT NOT NULL DEFAULT 0,
          computed_at DATETIME(3) NOT NULL,
          period_start DATETIME(3) NULL,
          period_end DATETIME(3) NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        idx = []

    with engine.connect() as conn:
        conn.execute(text(ledger_ddl))
        conn.execute(text(cache_ddl))
        for stmt in idx:
            conn.execute(text(stmt))
        conn.commit()

    if run_backfill:
        Session = __import__("sqlalchemy.orm", fromlist=["sessionmaker"]).sessionmaker(bind=engine)
        db = Session()
        try:
            row = db.execute(text("SELECT COUNT(*) FROM amber_ledger")).fetchone()
            if int(row[0] if row else 0) == 0:
                backfill_historical(db)
                db.commit()
        except Exception as exc:
            db.rollback()
            log.warning("Âmbarômetro backfill inicial falhou: %s", exc)
        finally:
            db.close()


def _cache_incr(db: Session, stat_key: str, delta: int, *, occurred_at: datetime) -> None:
    if delta <= 0:
        return
    now = _naive_utc(_utcnow())
    occ = _naive_utc(occurred_at)
    existing = db.execute(
        text("SELECT stat_value FROM amber_stats_cache WHERE stat_key = :k"),
        {"k": stat_key},
    ).fetchone()
    if existing:
        db.execute(
            text(
                "UPDATE amber_stats_cache SET stat_value = stat_value + :d, computed_at = :now "
                "WHERE stat_key = :k"
            ),
            {"d": delta, "now": now, "k": stat_key},
        )
    else:
        db.execute(
            text(
                "INSERT INTO amber_stats_cache (stat_key, stat_value, computed_at) "
                "VALUES (:k, :d, :now)"
            ),
            {"k": stat_key, "d": delta, "now": now},
        )

    start_today = _sp_start_of_today_utc()
    if occ >= start_today:
        _cache_incr_key(db, "total_gross_today", delta, now=now)
    cutoff_7d = _naive_utc(_utcnow() - timedelta(days=7))
    if occ >= cutoff_7d:
        _cache_incr_key(db, "total_gross_7d", delta, now=now)
    cutoff_30d = _naive_utc(_utcnow() - timedelta(days=30))
    if occ >= cutoff_30d:
        _cache_incr_key(db, "total_gross_30d", delta, now=now)


def _cache_incr_key(db: Session, stat_key: str, delta: int, *, now: datetime) -> None:
    existing = db.execute(
        text("SELECT stat_value FROM amber_stats_cache WHERE stat_key = :k"),
        {"k": stat_key},
    ).fetchone()
    if existing:
        db.execute(
            text(
                "UPDATE amber_stats_cache SET stat_value = stat_value + :d, computed_at = :now "
                "WHERE stat_key = :k"
            ),
            {"d": delta, "now": now, "k": stat_key},
        )
    else:
        db.execute(
            text(
                "INSERT INTO amber_stats_cache (stat_key, stat_value, computed_at) "
                "VALUES (:k, :d, :now)"
            ),
            {"k": stat_key, "d": delta, "now": now},
        )


def record_movement(
    db: Session,
    *,
    channel: str,
    event_type: str,
    signed_delta: int,
    idempotency_key: str,
    steam_id: str | None = None,
    counterparty_id: str | None = None,
    source_table: str | None = None,
    source_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
    commit: bool = False,
) -> bool:
    """Registra movimentação no ledger. Retorna True se inseriu, False se duplicata ou zero."""
    gross = abs(int(signed_delta or 0))
    if gross <= 0:
        return False
    key = str(idempotency_key or "").strip()
    if not key:
        return False
    channel = str(channel or "").strip()[:32]
    event_type = str(event_type or "").strip()[:64]
    occ = _naive_utc(occurred_at or _utcnow())
    meta_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
    is_sqlite = "sqlite" in str(getattr(db, "bind", None).url if getattr(db, "bind", None) else "").lower()

    exists = db.execute(
        text("SELECT 1 FROM amber_ledger WHERE idempotency_key = :k LIMIT 1"),
        {"k": key},
    ).fetchone()
    if exists:
        return False

    try:
        if is_sqlite:
            db.execute(
                text(
                    "INSERT INTO amber_ledger "
                    "(occurred_at, channel, event_type, gross_amount, signed_delta, "
                    "steam_id, counterparty_id, source_table, source_id, idempotency_key, metadata_json) "
                    "VALUES (:occ, :ch, :et, :gross, :delta, :sid, :cp, :st, :src, :key, :meta)"
                ),
                {
                    "occ": occ,
                    "ch": channel,
                    "et": event_type,
                    "gross": gross,
                    "delta": int(signed_delta),
                    "sid": steam_id,
                    "cp": counterparty_id,
                    "st": source_table,
                    "src": source_id,
                    "key": key,
                    "meta": meta_json,
                },
            )
        else:
            params = {
                "occ": occ,
                "ch": channel,
                "et": event_type,
                "gross": gross,
                "delta": int(signed_delta),
                "sid": steam_id,
                "cp": counterparty_id,
                "st": source_table,
                "src": source_id,
                "key": key,
            }
            if meta_json:
                db.execute(
                    text(
                        "INSERT INTO amber_ledger "
                        "(occurred_at, channel, event_type, gross_amount, signed_delta, "
                        "steam_id, counterparty_id, source_table, source_id, idempotency_key, metadata_json) "
                        "VALUES (:occ, :ch, :et, :gross, :delta, :sid, :cp, :st, :src, :key, CAST(:meta AS JSON))"
                    ),
                    {**params, "meta": meta_json},
                )
            else:
                db.execute(
                    text(
                        "INSERT INTO amber_ledger "
                        "(occurred_at, channel, event_type, gross_amount, signed_delta, "
                        "steam_id, counterparty_id, source_table, source_id, idempotency_key) "
                        "VALUES (:occ, :ch, :et, :gross, :delta, :sid, :cp, :st, :src, :key)"
                    ),
                    params,
                )
        _cache_incr(db, "total_gross_all_time", gross, occurred_at=occ)
        _cache_incr(db, f"channel:{channel}", gross, occurred_at=occ)
        if commit:
            db.commit()
        _invalidate_public_cache()
        return True
    except IntegrityError:
        return False
    except Exception as exc:
        log.warning("record_movement falhou key=%s: %s", key, exc)
        return False


def _invalidate_public_cache() -> None:
    with _public_stats_lock:
        _public_stats_cache["data"] = None
        _public_stats_cache["expires"] = 0.0


def record_donation(db: Session, *, payment_id: str, steam_id: str, points: int, **kw: Any) -> bool:
    return record_movement(
        db,
        channel="donation",
        event_type="pix_credited",
        signed_delta=points,
        idempotency_key=f"donation:{payment_id}",
        steam_id=steam_id,
        source_table="point_payments",
        source_id=payment_id,
        **kw,
    )


def record_shop_debit(db: Session, *, order_id: str, steam_id: str, points: int, **kw: Any) -> bool:
    return record_movement(
        db,
        channel="shop_web",
        event_type="purchase_debit",
        signed_delta=-points,
        idempotency_key=f"shop:order:{order_id}:debit",
        steam_id=steam_id,
        source_table="orders",
        source_id=order_id,
        **kw,
    )


def record_shop_refund(db: Session, *, order_id: str, steam_id: str, refund: int, event_type: str, **kw: Any) -> bool:
    return record_movement(
        db,
        channel="shop_web",
        event_type=event_type,
        signed_delta=refund,
        idempotency_key=f"shop:refund:{order_id}:{event_type}",
        steam_id=steam_id,
        source_table="orders",
        source_id=order_id,
        **kw,
    )


def record_admin_adjust(
    db: Session,
    *,
    steam_id: str,
    delta: int,
    event_type: str,
    idempotency_key: str,
    **kw: Any,
) -> bool:
    return record_movement(
        db,
        channel="admin",
        event_type=event_type,
        signed_delta=delta,
        idempotency_key=idempotency_key,
        steam_id=steam_id,
        source_table="players",
        source_id=steam_id,
        **kw,
    )


def record_market_purchase(
    db: Session,
    *,
    tx_id: int,
    listing_id: int,
    buyer_steam_id: str,
    seller_steam_id: str,
    price: int,
    **kw: Any,
) -> None:
    record_movement(
        db,
        channel="market",
        event_type="market_purchase_buyer",
        signed_delta=-price,
        idempotency_key=f"market:tx:{tx_id}:buyer",
        steam_id=buyer_steam_id,
        counterparty_id=seller_steam_id,
        source_table="market_transactions",
        source_id=str(tx_id),
        metadata={"listing_id": listing_id, "leg": "buyer"},
        **kw,
    )
    record_movement(
        db,
        channel="market",
        event_type="market_purchase_seller",
        signed_delta=price,
        idempotency_key=f"market:tx:{tx_id}:seller",
        steam_id=seller_steam_id,
        counterparty_id=buyer_steam_id,
        source_table="market_transactions",
        source_id=str(tx_id),
        metadata={"listing_id": listing_id, "leg": "seller"},
        **kw,
    )


def record_market_claim_refund(
    db: Session,
    *,
    listing_id: int,
    claim_id: int,
    buyer_steam_id: str,
    seller_steam_id: str,
    refund: int,
    seller_debited: int,
    **kw: Any,
) -> None:
    if refund > 0 and buyer_steam_id:
        record_movement(
            db,
            channel="market",
            event_type="market_claim_refund_buyer",
            signed_delta=refund,
            idempotency_key=f"market:claim:{claim_id}:buyer_refund",
            steam_id=buyer_steam_id,
            counterparty_id=seller_steam_id,
            source_table="market_claims",
            source_id=str(claim_id),
            metadata={"listing_id": listing_id, "refund": refund},
            **kw,
        )
    if seller_debited > 0 and seller_steam_id:
        record_movement(
            db,
            channel="market",
            event_type="market_claim_refund_seller",
            signed_delta=-seller_debited,
            idempotency_key=f"market:claim:{claim_id}:seller_debit",
            steam_id=seller_steam_id,
            counterparty_id=buyer_steam_id,
            source_table="market_claims",
            source_id=str(claim_id),
            metadata={"listing_id": listing_id, "seller_debited": seller_debited},
            **kw,
        )


def record_poll_reward(
    db: Session,
    *,
    poll_id: int,
    steam_id: str,
    reward: int,
    **kw: Any,
) -> bool:
    return record_movement(
        db,
        channel="community",
        event_type="poll_reward",
        signed_delta=reward,
        idempotency_key=f"poll:vote:{poll_id}:{steam_id}",
        steam_id=steam_id,
        source_table="community_poll_votes",
        source_id=f"{poll_id}:{steam_id}",
        metadata={"poll_id": poll_id},
        **kw,
    )


def record_lottery_prize(
    db: Session,
    *,
    campaign_id: int,
    steam_id: str,
    amount: int,
    winning_number: int,
    idempotency_key: str,
    **kw: Any,
) -> bool:
    return record_movement(
        db,
        channel="lottery",
        event_type="lottery_prize_credited",
        signed_delta=amount,
        idempotency_key=idempotency_key,
        steam_id=steam_id,
        source_table="lottery_winners",
        source_id=f"{campaign_id}:{winning_number}",
        metadata={"campaign_id": campaign_id, "winning_number": winning_number},
        **kw,
    )


def record_lottery_amber_purchase(
    db: Session,
    *,
    campaign_id: int,
    steam_id: str,
    amount: int,
    source: str,
    number_value: int,
    **kw: Any,
) -> bool:
    return record_movement(
        db,
        channel="lottery",
        event_type="lottery_amber_purchase",
        signed_delta=-amount,
        idempotency_key=f"lottery:purchase:{campaign_id}:{steam_id}:{number_value}",
        steam_id=steam_id,
        source_table="lottery_numbers",
        source_id=f"{campaign_id}:{number_value}",
        metadata={"campaign_id": campaign_id, "source": source, "number_value": number_value},
        **kw,
    )


def record_lottery_donation_prize_contribution(
    db: Session,
    *,
    campaign_id: int,
    payment_id: str,
    steam_id: str,
    amount: int,
    **kw: Any,
) -> bool:
    """Registra contribuição ao prize pool via doação (legado — mantido para compatibilidade)."""
    return record_movement(
        db,
        channel="lottery",
        event_type="lottery_donation_prize_contribution",
        signed_delta=amount,
        idempotency_key=f"lottery:donation_prize:{campaign_id}:{payment_id}",
        steam_id=steam_id,
        source_table="lottery_campaigns",
        source_id=str(campaign_id),
        metadata={
            "campaign_id": campaign_id,
            "payment_id": payment_id,
            "note": "prize_pool_contribution",
        },
        **kw,
    )


def record_lottery_donation_amber(
    db: Session,
    *,
    campaign_id: int,
    payment_id: str,
    steam_id: str,
    amount: int,
    amount_brl: float,
    **kw: Any,
) -> bool:
    """Registra crédito de Âmbares ao jogador por doação (R$ 1 = 100 Âmbares na conta)."""
    return record_movement(
        db,
        channel="lottery",
        event_type="lottery_donation_amber_credited",
        signed_delta=amount,
        idempotency_key=f"lottery:donation:amber:{campaign_id}:{payment_id}",
        steam_id=steam_id,
        source_table="point_payments",
        source_id=payment_id,
        metadata={
            "campaign_id": campaign_id,
            "payment_id": payment_id,
            "amount_brl": amount_brl,
            "amber_per_real": 100,
        },
        **kw,
    )


def record_lottery_prize_subsidy(
    db: Session,
    *,
    campaign_id: int,
    amount: int,
    **kw: Any,
) -> bool:
    return record_movement(
        db,
        channel="lottery",
        event_type="lottery_prize_subsidy",
        signed_delta=amount,
        idempotency_key=f"lottery:subsidy:{campaign_id}",
        counterparty_id="house",
        source_table="lottery_campaigns",
        source_id=str(campaign_id),
        metadata={"campaign_id": campaign_id},
        **kw,
    )


def _cache_get(db: Session, stat_key: str) -> int:
    row = db.execute(
        text("SELECT stat_value FROM amber_stats_cache WHERE stat_key = :k"),
        {"k": stat_key},
    ).fetchone()
    return int(row[0] if row else 0)


def _sum_since(db: Session, since: datetime) -> int:
    row = db.execute(
        text(
            "SELECT COALESCE(SUM(gross_amount), 0) FROM amber_ledger "
            "WHERE occurred_at >= :since"
        ),
        {"since": _naive_utc(since)},
    ).fetchone()
    return int(row[0] if row else 0)


def _sum_channel_all_time(db: Session) -> dict[str, int]:
    rows = db.execute(
        text(
            "SELECT channel, COALESCE(SUM(gross_amount), 0) AS total "
            "FROM amber_ledger GROUP BY channel"
        )
    ).fetchall()
    return {str(r.channel): int(r.total) for r in rows}


def _ensure_schema_ready(db: Session) -> None:
    """Garante tabelas do Âmbarômetro (corrige corrida com migrate assíncrono no boot)."""
    engine = db.get_bind()
    if engine is None:
        return
    engine_id = id(engine)
    if engine_id in _schema_verified_engines:
        return
    with _schema_lock:
        if engine_id in _schema_verified_engines:
            return
        try:
            db.execute(text("SELECT 1 FROM amber_stats_cache LIMIT 1"))
            _schema_verified_engines.add(engine_id)
        except Exception:
            db.rollback()
            ensure_amber_schema(engine, run_backfill=True)
            _schema_verified_engines.add(engine_id)


def degraded_public_stats(
    *,
    message: str = "Dados temporariamente indisponíveis",
    currency: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Payload público seguro quando o ledger ainda não está pronto."""
    curr = currency or {}
    return {
        "ok": True,
        "degraded": True,
        "error": message,
        "currency": curr,
        "updated_at": datetime.now(_SP_TZ).isoformat(timespec="seconds"),
        "coverage_note": COVERAGE_NOTE,
        "total_gross_all_time": 0,
        "total_gross_today": 0,
        "total_gross_7d": 0,
        "total_gross_30d": 0,
        "channels": {
            "donation": 0,
            "shop_web": 0,
            "market": 0,
            "ingame_shop": None,
            "community": 0,
            "admin": 0,
        },
        "display": {
            "label": "Âmbares movimentados",
            "sublabel": "Todas as transações do cluster ARKLAND",
        },
    }


def _reconcile_rolling_windows(db: Session) -> None:
    """Atualiza cache de janelas rolantes a partir do ledger."""
    now = _naive_utc(_utcnow())
    windows = {
        "total_gross_today": _sp_start_of_today_utc(),
        "total_gross_7d": _naive_utc(_utcnow() - timedelta(days=7)),
        "total_gross_30d": _naive_utc(_utcnow() - timedelta(days=30)),
    }
    for key, since in windows.items():
        total = _sum_since(db, since)
        existing = db.execute(
            text("SELECT stat_key FROM amber_stats_cache WHERE stat_key = :k"),
            {"k": key},
        ).fetchone()
        if existing:
            db.execute(
                text(
                    "UPDATE amber_stats_cache SET stat_value = :v, computed_at = :now "
                    "WHERE stat_key = :k"
                ),
                {"v": total, "now": now, "k": key},
            )
        else:
            db.execute(
                text(
                    "INSERT INTO amber_stats_cache (stat_key, stat_value, computed_at, period_start) "
                    "VALUES (:k, :v, :now, :ps)"
                ),
                {"k": key, "v": total, "now": now, "ps": since},
            )


def get_public_stats(
    db: Session,
    *,
    currency: Callable[[], dict[str, str]] | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Retorna payload público do Âmbarômetro (sem PII)."""
    now_mono = time.monotonic()
    with _public_stats_lock:
        if (
            not force_refresh
            and _public_stats_cache["data"] is not None
            and now_mono < float(_public_stats_cache["expires"] or 0)
        ):
            return dict(_public_stats_cache["data"])

    _ensure_schema_ready(db)
    _reconcile_rolling_windows(db)
    db.commit()

    all_time = _cache_get(db, "total_gross_all_time")
    if all_time <= 0:
        row = db.execute(text("SELECT COALESCE(SUM(gross_amount), 0) FROM amber_ledger")).fetchone()
        all_time = int(row[0] if row else 0)

    channel_totals = _sum_channel_all_time(db)
    channels: dict[str, int | None] = {
        "donation": channel_totals.get("donation", _cache_get(db, "channel:donation")),
        "shop_web": channel_totals.get("shop_web", _cache_get(db, "channel:shop_web")),
        "market": channel_totals.get("market", _cache_get(db, "channel:market")),
        "ingame_shop": None,
        "community": channel_totals.get("community", _cache_get(db, "channel:community")),
        "admin": channel_totals.get("admin", _cache_get(db, "channel:admin")),
    }

    now_sp = datetime.now(_SP_TZ)
    updated_at = now_sp.isoformat(timespec="seconds")
    curr = currency() if currency else {}
    payload = {
        "ok": True,
        "currency": curr,
        "updated_at": updated_at,
        "coverage_note": COVERAGE_NOTE,
        "total_gross_all_time": all_time,
        "total_gross_today": _cache_get(db, "total_gross_today"),
        "total_gross_7d": _cache_get(db, "total_gross_7d"),
        "total_gross_30d": _cache_get(db, "total_gross_30d"),
        "channels": channels,
        "display": {
            "label": "Âmbares movimentados",
            "sublabel": "Todas as transações do cluster ARKLAND",
        },
    }
    with _public_stats_lock:
        _public_stats_cache["data"] = payload
        _public_stats_cache["expires"] = now_mono + _PUBLIC_STATS_TTL
    return dict(payload)


def backfill_historical(db: Session) -> dict[str, int]:
    """Importa histórico de point_payments, orders, market e audit elegíveis."""
    counts = {"donation": 0, "shop_web": 0, "market": 0, "admin": 0, "community": 0}

    try:
        rows = db.execute(
            text(
                "SELECT payment_id, steam_id, points, created_at FROM point_payments "
                "WHERE credited = 1 AND points > 0"
            )
        ).fetchall()
        for r in rows:
            if record_donation(
                db,
                payment_id=str(r.payment_id),
                steam_id=str(r.steam_id),
                points=int(r.points),
                occurred_at=r.created_at,
            ):
                counts["donation"] += 1
    except Exception as exc:
        log.debug("backfill point_payments: %s", exc)

    try:
        rows = db.execute(
            text(
                "SELECT order_id, steam_id, points_spent, created_at FROM orders "
                "WHERE points_spent > 0"
            )
        ).fetchall()
        for r in rows:
            if record_shop_debit(
                db,
                order_id=str(r.order_id),
                steam_id=str(r.steam_id),
                points=int(r.points_spent),
                occurred_at=r.created_at,
            ):
                counts["shop_web"] += 1
    except Exception as exc:
        log.debug("backfill orders: %s", exc)

    try:
        audit_rows = db.execute(
            text(
                "SELECT event_type, order_id, target_steam_id, actor_steam_id, "
                "payload_json, created_at FROM audit_events "
                "WHERE event_type IN ('order_cancelled', 'admin_refund')"
            )
        ).fetchall()
        for r in audit_rows:
            try:
                payload = json.loads(r.payload_json or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                payload = {}
            refund = int(
                payload.get("price")
                or payload.get("refunded")
                or payload.get("refund")
                or 0
            )
            if refund <= 0:
                continue
            steam_id = str(r.target_steam_id or r.actor_steam_id or "")
            if record_shop_refund(
                db,
                order_id=str(r.order_id or ""),
                steam_id=steam_id,
                refund=refund,
                event_type=str(r.event_type),
                occurred_at=r.created_at,
            ):
                counts["shop_web"] += 1
    except Exception as exc:
        log.debug("backfill audit refunds: %s", exc)

    try:
        tx_rows = db.execute(
            text(
                "SELECT id, listing_id, buyer_steam_id, seller_steam_id, price_paid, created_at "
                "FROM market_transactions WHERE price_paid > 0"
            )
        ).fetchall()
        for r in tx_rows:
            if record_movement(
                db,
                channel="market",
                event_type="market_purchase_buyer",
                signed_delta=-int(r.price_paid),
                idempotency_key=f"market:tx:{r.id}:buyer",
                steam_id=str(r.buyer_steam_id),
                counterparty_id=str(r.seller_steam_id),
                source_table="market_transactions",
                source_id=str(r.id),
                occurred_at=r.created_at,
            ):
                counts["market"] += 1
            if record_movement(
                db,
                channel="market",
                event_type="market_purchase_seller",
                signed_delta=int(r.price_paid),
                idempotency_key=f"market:tx:{r.id}:seller",
                steam_id=str(r.seller_steam_id),
                counterparty_id=str(r.buyer_steam_id),
                source_table="market_transactions",
                source_id=str(r.id),
                occurred_at=r.created_at,
            ):
                counts["market"] += 1
    except Exception as exc:
        log.debug("backfill market_transactions: %s", exc)

    try:
        claim_rows = db.execute(
            text(
                "SELECT id, listing_id, claim_id, steam_id, counterparty_steam_id, "
                "points_delta, metadata_json, created_at FROM market_audit_events "
                "WHERE event_type = 'MARKET_CLAIM_EXPIRED_REFUND' AND points_delta > 0"
            )
        ).fetchall()
        for r in claim_rows:
            try:
                meta = json.loads(r.metadata_json or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                meta = {}
            refund = int(r.points_delta or meta.get("refund_amount") or 0)
            seller_debited = int(meta.get("seller_debited") or 0)
            record_market_claim_refund(
                db,
                listing_id=int(r.listing_id or 0),
                claim_id=int(r.claim_id or r.id),
                buyer_steam_id=str(r.steam_id or ""),
                seller_steam_id=str(r.counterparty_steam_id or meta.get("seller_steam_id") or ""),
                refund=refund,
                seller_debited=seller_debited,
                occurred_at=r.created_at,
            )
    except Exception as exc:
        log.debug("backfill market claim refunds: %s", exc)

    try:
        admin_rows = db.execute(
            text(
                "SELECT event_type, target_steam_id, actor_steam_id, amount, "
                "status_before, status_after, payload_json, created_at, id "
                "FROM audit_events WHERE event_type IN ("
                "'admin_player_points_add', 'admin_player_points_subtract', "
                "'admin_player_points_set', 'admin_points_add', 'admin_points_set'"
                ")"
            )
        ).fetchall()
        for r in admin_rows:
            try:
                payload = json.loads(r.payload_json or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                payload = {}
            delta = payload.get("delta")
            if delta is None:
                if r.event_type in ("admin_points_add", "admin_player_points_add"):
                    delta = int(r.amount or payload.get("amount") or 0)
                elif r.event_type in ("admin_player_points_subtract",):
                    delta = -int(payload.get("amount") or r.amount or 0)
                elif r.event_type in ("admin_points_set", "admin_player_points_set"):
                    try:
                        before = int(r.status_before or 0)
                        after = int(r.status_after or r.amount or 0)
                        delta = after - before
                    except (TypeError, ValueError):
                        delta = 0
                else:
                    delta = 0
            else:
                delta = int(delta)
            if delta == 0:
                continue
            steam_id = str(r.target_steam_id or r.actor_steam_id or "")
            if record_admin_adjust(
                db,
                steam_id=steam_id,
                delta=delta,
                event_type=str(r.event_type),
                idempotency_key=f"admin:audit:{r.id}",
                occurred_at=r.created_at,
            ):
                counts["admin"] += 1
    except Exception as exc:
        log.debug("backfill admin audit: %s", exc)

    try:
        vote_rows = db.execute(
            text(
                "SELECT v.poll_id, v.steam_id, p.reward_amber, v.created_at "
                "FROM community_poll_votes v "
                "JOIN community_polls p ON p.id = v.poll_id "
                "WHERE v.reward_granted = 1 AND p.reward_amber > 0"
            )
        ).fetchall()
        for r in vote_rows:
            if record_poll_reward(
                db,
                poll_id=int(r.poll_id),
                steam_id=str(r.steam_id),
                reward=int(r.reward_amber),
                occurred_at=r.created_at,
            ):
                counts["community"] += 1
    except Exception as exc:
        log.debug("backfill poll rewards: %s", exc)

    _reconcile_rolling_windows(db)
    log.info("Âmbarômetro backfill: %s", counts)
    return counts
