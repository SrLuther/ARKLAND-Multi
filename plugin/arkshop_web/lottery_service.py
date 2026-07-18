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
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

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
NUMBER_SOURCES = frozenset({
    "DONATION", "AMBER_RANDOM", "AMBER_RESERVE", "FIXED_REGISTERED", "TEAM",
})
LOTTERY_REGULAMENTO_VERSION = "1.5"
FIXED_NUMBER_CHANGE_COST = 5000
CONFIRMATION_DEADLINE_HOURS = 2
TEAM_HOLDER_PREFIX = "team:"
DEFAULT_TEAM_SHORTFALL_REFUND = 5000
# Após COMPLETED: próximo sorteio (auto-chain) nasce DRAFT e só vira ACTIVE após esta janela.
CHAIN_PREP_HOURS = 24
DONATION_AMBER_PER_REAL = 100  # R$ 1 doado = +100 Âmbares no prêmio total do sorteio
RULES_SUMMARY = (
    "R$ 5 = 1 número · cada real doado soma +100 Âmbares ao prêmio · "
    "compra 1.000 Âmbares (máx. 5) · reserva 2.000 Âmbares · "
    "número fixo gratuito (confirme em Minha Área) · troca de número fixo 5.000 Âmbares · "
    "até 5 sorteados · prêmio (Âmbares + kits/licenças opcionais) dividido entre titulares."
)
TZ_LABEL = "Horário de Brasília (UTC-3)"
TZ_OFFSET = timezone(timedelta(hours=-3))
_MAX_RANDOM_ATTEMPTS = 50
ALLOWED_CATALOG_PRIZE_KINDS = frozenset({"kit", "license"})
MAX_CATALOG_PRIZES = 10

_credit_fn: Callable[[Session, str, int], int] | None = None
_debit_fn: Callable[[Session, str, int], int] | None = None
_settings_fn: Callable[[], dict[str, Any]] | None = None
_save_settings_fn: Callable[[dict[str, Any]], None] | None = None
# resolve(kind, item_id) -> {item_id, label, ...} ou None se inválido
_resolve_catalog_prize_fn: Callable[[str, str], dict[str, Any] | None] | None = None
# deliver(db, steam_id, prize, *, campaign_id, winning_number) -> {order_id, ...}
_deliver_catalog_prize_fn: Callable[..., dict[str, Any]] | None = None
_prize_options_fn: Callable[[], dict[str, Any]] | None = None
# pós-commit: sync Permissions de licenças [(steam_id, group, days), ...]
_sync_license_permissions_fn: Callable[[str, str, int], Any] | None = None


def configure_lottery(
    *,
    credit_fn: Callable[[Session, str, int], int],
    debit_fn: Callable[[Session, str, int], int],
    settings_fn: Callable[[], dict[str, Any]] | None = None,
    save_settings_fn: Callable[[dict[str, Any]], None] | None = None,
    resolve_catalog_prize_fn: Callable[[str, str], dict[str, Any] | None] | None = None,
    deliver_catalog_prize_fn: Callable[..., dict[str, Any]] | None = None,
    prize_options_fn: Callable[[], dict[str, Any]] | None = None,
    sync_license_permissions_fn: Callable[[str, str, int], Any] | None = None,
) -> None:
    global _credit_fn, _debit_fn, _settings_fn, _save_settings_fn
    global _resolve_catalog_prize_fn, _deliver_catalog_prize_fn, _prize_options_fn
    global _sync_license_permissions_fn
    _credit_fn = credit_fn
    _debit_fn = debit_fn
    _settings_fn = settings_fn
    _save_settings_fn = save_settings_fn
    _resolve_catalog_prize_fn = resolve_catalog_prize_fn
    _deliver_catalog_prize_fn = deliver_catalog_prize_fn
    _prize_options_fn = prize_options_fn
    _sync_license_permissions_fn = sync_license_permissions_fn


def get_prize_options() -> dict[str, Any]:
    """Opções de kits/licenças para o admin configurar prémios de catálogo."""
    if _prize_options_fn is None:
        return {"kits": [], "licenses": []}
    try:
        raw = _prize_options_fn() or {}
    except Exception as exc:
        log.warning("lottery prize_options_fn: %s", exc)
        return {"kits": [], "licenses": [], "errors": [str(exc)]}
    out: dict[str, Any] = {
        "kits": list(raw.get("kits") or []),
        "licenses": list(raw.get("licenses") or []),
    }
    if raw.get("errors"):
        out["errors"] = list(raw["errors"])
    return out


def normalize_catalog_prizes(raw: Any, *, resolve: bool = True) -> list[dict[str, Any]]:
    """Valida e normaliza prémios de catálogo (kits / licenças).

    Formato aceite por item: {kind|type: 'kit'|'license', item_id, amount?}
    """
    if raw is None or raw == "":
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("invalid_prize_catalog") from exc
    if not isinstance(raw, list):
        raise ValueError("invalid_prize_catalog")
    if len(raw) > MAX_CATALOG_PRIZES:
        raise ValueError("too_many_catalog_prizes")
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("invalid_prize_catalog_entry")
        kind = str(entry.get("kind") or entry.get("type") or "").strip().lower()
        if kind in ("licenca", "licença", "licence"):
            kind = "license"
        if kind not in ALLOWED_CATALOG_PRIZE_KINDS:
            raise ValueError("unsupported_prize_kind")
        item_id = str(entry.get("item_id") or entry.get("id") or "").strip()
        if not item_id:
            raise ValueError("prize_item_id_required")
        try:
            amount = max(1, min(99, int(entry.get("amount") or 1)))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_prize_amount") from exc
        label = str(entry.get("label") or entry.get("display_name") or "").strip()
        resolved_amber: int | None = None
        if resolve and _resolve_catalog_prize_fn is not None:
            resolved = _resolve_catalog_prize_fn(kind, item_id)
            if not resolved:
                raise ValueError(f"prize_not_found:{kind}:{item_id}")
            item_id = str(resolved.get("item_id") or item_id)
            label = str(resolved.get("label") or label or item_id)
            if resolved.get("amber_price") is not None:
                try:
                    resolved_amber = max(0, int(resolved["amber_price"]))
                except (TypeError, ValueError):
                    resolved_amber = None
        key = (kind, item_id)
        if key in seen:
            continue
        seen.add(key)
        item: dict[str, Any] = {
            "kind": kind,
            "item_id": item_id,
            "amount": amount,
            "label": label or item_id,
        }
        for price_key in ("amber_price", "amber_value", "price"):
            if entry.get(price_key) is not None:
                try:
                    item["amber_price"] = max(0, int(entry.get(price_key)))
                    break
                except (TypeError, ValueError):
                    pass
        if "amber_price" not in item and resolved_amber is not None:
            item["amber_price"] = resolved_amber
        out.append(item)
    return out


def _parse_prize_catalog_row(row: Any) -> list[dict[str, Any]]:
    raw = _row_val(row, "prize_catalog_json", None)
    if raw is None or raw == "":
        return []
    try:
        return normalize_catalog_prizes(raw, resolve=False)
    except ValueError:
        if isinstance(raw, str):
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return []
        else:
            data = raw
        if not isinstance(data, list):
            return []
        cleaned: list[dict[str, Any]] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            kind = str(entry.get("kind") or "").strip().lower()
            item_id = str(entry.get("item_id") or "").strip()
            if kind not in ALLOWED_CATALOG_PRIZE_KINDS or not item_id:
                continue
            cleaned.append({
                "kind": kind,
                "item_id": item_id,
                "amount": max(1, int(entry.get("amount") or 1)),
                "label": str(entry.get("label") or item_id),
            })
        return cleaned


def lottery_meta() -> dict[str, Any]:
    return {
        "regulamento_version": LOTTERY_REGULAMENTO_VERSION,
        "number_min": NUMBER_MIN,
        "number_max": NUMBER_MAX,
        "rules_summary": RULES_SUMMARY,
        "timezone_label": TZ_LABEL,
        "fixed_number_change_cost": FIXED_NUMBER_CHANGE_COST,
        "confirmation_deadline_hours": CONFIRMATION_DEADLINE_HOURS,
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


def _row_val(row: Any, key: str, default: Any = None) -> Any:
    """Acesso seguro a colunas — schema parcial (pré-migração) não derruba rotas públicas."""
    try:
        return row._mapping.get(key, default)
    except Exception:
        try:
            return getattr(row, key, default)
        except Exception:
            return default


def _table_has_column(db: Session, table: str, column: str) -> bool:
    """Verifica coluna em schema parcial — evita SQL com colunas ausentes."""
    bind = db.get_bind()
    is_sqlite = "sqlite" in str(bind.url).lower()
    if is_sqlite:
        cols = {str(r[1]) for r in db.execute(text(f"PRAGMA table_info({table})")).fetchall()}
        return column in cols
    row = db.execute(
        text(f"SHOW COLUMNS FROM `{table}` LIKE :col"),
        {"col": column},
    ).fetchone()
    return row is not None


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
              starts_at DATETIME NULL,
              winning_numbers_count INTEGER NOT NULL DEFAULT 1,
              prize_amber_base INTEGER NOT NULL DEFAULT 5000,
              prize_amber_rollover_in INTEGER NOT NULL DEFAULT 0,
              prize_amber_from_purchases INTEGER NOT NULL DEFAULT 0,
              prize_amber_from_donations INTEGER NOT NULL DEFAULT 0,
              prize_amber_from_market INTEGER NOT NULL DEFAULT 0,
              prize_amber_paid INTEGER NOT NULL DEFAULT 0,
              prize_amber_subsidy INTEGER NOT NULL DEFAULT 0,
              prize_pool_fully_distributed INTEGER NOT NULL DEFAULT 0,
              matched_winners_count INTEGER NOT NULL DEFAULT 0,
              prize_amber_rollover_out INTEGER NOT NULL DEFAULT 0,
              prize_catalog_json TEXT NOT NULL DEFAULT '[]',
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
              team_id INTEGER NULL,
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
              ledger_idempotency_key VARCHAR(128) NOT NULL,
              catalog_orders_json TEXT NOT NULL DEFAULT '[]'
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
            """
            CREATE TABLE IF NOT EXISTS lottery_campaign_confirmations (
              campaign_id INTEGER NOT NULL,
              steam_id VARCHAR(32) NOT NULL,
              fixed_number INTEGER NOT NULL,
              confirmed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (campaign_id, steam_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_lot_conf_steam ON lottery_campaign_confirmations (steam_id)",
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
              starts_at DATETIME(3) NULL,
              winning_numbers_count TINYINT NOT NULL DEFAULT 1,
              prize_amber_base INT NOT NULL DEFAULT 5000,
              prize_amber_rollover_in INT NOT NULL DEFAULT 0,
              prize_amber_from_purchases INT NOT NULL DEFAULT 0,
              prize_amber_from_donations INT NOT NULL DEFAULT 0,
              prize_amber_from_market INT NOT NULL DEFAULT 0,
              prize_amber_paid INT NOT NULL DEFAULT 0,
              prize_amber_subsidy INT NOT NULL DEFAULT 0,
              prize_pool_fully_distributed TINYINT(1) NOT NULL DEFAULT 0,
              matched_winners_count TINYINT NOT NULL DEFAULT 0,
              prize_amber_rollover_out INT NOT NULL DEFAULT 0,
              prize_catalog_json JSON NULL,
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
              team_id BIGINT NULL,
              UNIQUE KEY uq_lot_camp_num (campaign_id, number_value),
              KEY idx_lot_num_camp (campaign_id, steam_id),
              KEY idx_lot_num_pay (payment_id),
              KEY idx_lot_num_team (team_id)
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
              ledger_idempotency_key VARCHAR(128) NOT NULL,
              catalog_orders_json JSON NULL
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
            """
            CREATE TABLE IF NOT EXISTS lottery_campaign_confirmations (
              campaign_id BIGINT UNSIGNED NOT NULL,
              steam_id VARCHAR(32) NOT NULL,
              fixed_number SMALLINT NOT NULL,
              confirmed_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
              PRIMARY KEY (campaign_id, steam_id),
              KEY idx_lot_conf_steam (steam_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        ]
    with engine.connect() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))
        conn.commit()
    _migrate_lottery_columns(engine)
    backfill_fixed_lottery_numbers(engine)


def _store_users_has_fixed_column(engine: Engine) -> bool:
    is_sqlite = "sqlite" in str(engine.url).lower()
    with engine.connect() as conn:
        if is_sqlite:
            cols = {
                str(r[1])
                for r in conn.execute(text("PRAGMA table_info(store_users)")).fetchall()
            }
            return "fixed_lottery_number" in cols
        row = conn.execute(
            text("SHOW COLUMNS FROM `store_users` LIKE 'fixed_lottery_number'")
        ).fetchone()
        return row is not None


def backfill_fixed_lottery_numbers(engine: Engine) -> int:
    """Atribui número fixo a jogadores registrados que ainda não possuem."""
    if not _store_users_has_fixed_column(engine):
        return 0
    Session = sessionmaker(bind=engine)
    db = Session()
    assigned = 0
    try:
        rows = db.execute(
            text(
                "SELECT steam_id FROM store_users "
                "WHERE fixed_lottery_number IS NULL ORDER BY steam_id ASC"
            )
        ).fetchall()
        for row in rows:
            sid = str(row.steam_id)
            try:
                ensure_fixed_lottery_number(db, sid)
                assigned += 1
            except Exception as exc:
                log.warning("backfill fixed_lottery_number %s: %s", sid, exc)
        if assigned:
            db.commit()
            log.info("backfill fixed_lottery_number: %s jogadores", assigned)
    except Exception as exc:
        db.rollback()
        log.warning("backfill fixed_lottery_numbers falhou: %s", exc)
    finally:
        db.close()
    return assigned


def _global_occupied_fixed_numbers(db: Session) -> set[int]:
    if not _store_users_has_fixed_column(db.get_bind()):
        return set()
    rows = db.execute(
        text(
            "SELECT fixed_lottery_number FROM store_users "
            "WHERE fixed_lottery_number IS NOT NULL"
        )
    ).fetchall()
    return {int(r[0]) for r in rows if r[0] is not None}


def _pick_unique_fixed_number(db: Session, *, occupied: set[int] | None = None) -> int:
    if occupied is None:
        occupied = _global_occupied_fixed_numbers(db)
    if len(occupied) >= 900:
        raise ValueError("fixed_pool_exhausted")
    rng = secrets.SystemRandom()
    for _ in range(_MAX_RANDOM_ATTEMPTS):
        n = rng.randint(NUMBER_MIN, NUMBER_MAX)
        if n not in occupied:
            return n
    free = [n for n in range(NUMBER_MIN, NUMBER_MAX + 1) if n not in occupied]
    if not free:
        raise ValueError("fixed_pool_exhausted")
    return rng.choice(free)


def _get_fixed_lottery_number(db: Session, steam_id: str) -> int | None:
    if not _store_users_has_fixed_column(db.get_bind()):
        return None
    row = db.execute(
        text("SELECT fixed_lottery_number FROM store_users WHERE steam_id = :sid"),
        {"sid": steam_id},
    ).fetchone()
    if not row or row[0] is None:
        return None
    return int(row[0])


def ensure_fixed_lottery_number(db: Session, steam_id: str) -> int:
    """Garante número fixo único para jogador registrado — nunca altera automaticamente."""
    existing = _get_fixed_lottery_number(db, steam_id)
    if existing is not None:
        return existing
    user_row = db.execute(
        text("SELECT 1 FROM store_users WHERE steam_id = :sid"),
        {"sid": steam_id},
    ).fetchone()
    if not user_row:
        raise ValueError("not_registered")
    n = _pick_unique_fixed_number(db)
    try:
        db.execute(
            text("UPDATE store_users SET fixed_lottery_number = :n WHERE steam_id = :sid"),
            {"n": n, "sid": steam_id},
        )
    except IntegrityError:
        raise ValueError("fixed_pool_exhausted") from None
    _audit_safe(db, "lottery_fixed_number_assigned", {"steam_id": steam_id, "number": n})
    return n


def _confirmation_deadline(campaign_row: Any) -> datetime | None:
    """Último instante para confirmar: draw_at − 2h (confirmação bloqueada em ou após esse horário)."""
    draw = _parse_dt(_row_val(campaign_row, "draw_at"))
    if not draw:
        return None
    return draw - timedelta(hours=CONFIRMATION_DEADLINE_HOURS)


def _confirmation_deadline_ok(campaign_row: Any) -> bool:
    deadline = _confirmation_deadline(campaign_row)
    if not deadline:
        return False
    return _utcnow() < deadline


def _campaign_confirmation_row(db: Session, campaign_id: int, steam_id: str) -> Any | None:
    if not _table_has_column(db, "lottery_campaign_confirmations", "campaign_id"):
        return None
    return db.execute(
        text(
            "SELECT * FROM lottery_campaign_confirmations "
            "WHERE campaign_id = :cid AND steam_id = :sid"
        ),
        {"cid": campaign_id, "sid": steam_id},
    ).fetchone()


def _is_number_taken_in_campaign(
    db: Session, campaign_id: int, number_value: int, *, exclude_steam_id: str | None = None,
) -> bool:
    row = db.execute(
        text(
            "SELECT steam_id FROM lottery_numbers "
            "WHERE campaign_id = :cid AND number_value = :num AND status = 'ACTIVE' LIMIT 1"
        ),
        {"cid": campaign_id, "num": number_value},
    ).fetchone()
    if not row:
        return False
    if exclude_steam_id and str(row.steam_id) == exclude_steam_id:
        return False
    return True


def confirm_campaign_participation(db: Session, steam_id: str) -> dict[str, Any]:
    """Confirma participação na campanha ativa com o número fixo (gratuito)."""
    if not _is_enabled():
        raise ValueError("lottery_disabled")
    campaign = get_active_campaign(db)
    if not campaign or str(campaign.status) != "ACTIVE":
        raise ValueError("no_active_campaign")
    if not _confirmation_deadline_ok(campaign):
        raise ValueError("confirmation_deadline_passed")
    cid = int(campaign.id)
    if _campaign_confirmation_row(db, cid, steam_id):
        raise ValueError("already_confirmed")
    fixed = ensure_fixed_lottery_number(db, steam_id)
    if _is_number_taken_in_campaign(db, cid, fixed, exclude_steam_id=steam_id):
        raise ValueError("number_unavailable_in_campaign")
    now = _naive(_utcnow())
    db.execute(
        text(
            "INSERT INTO lottery_campaign_confirmations "
            "(campaign_id, steam_id, fixed_number, confirmed_at) "
            "VALUES (:cid, :sid, :num, :now)"
        ),
        {"cid": cid, "sid": steam_id, "num": fixed, "now": now},
    )
    existing_active = db.execute(
        text(
            "SELECT id FROM lottery_numbers "
            "WHERE campaign_id = :cid AND steam_id = :sid AND number_value = :num "
            "AND source = 'FIXED_REGISTERED' AND status = 'ACTIVE'"
        ),
        {"cid": cid, "sid": steam_id, "num": fixed},
    ).fetchone()
    if not existing_active:
        _insert_number(
            db,
            campaign_id=cid,
            steam_id=steam_id,
            number_value=fixed,
            source="FIXED_REGISTERED",
            amber_cost=0,
        )
    _audit_safe(
        db, "lottery_participation_confirmed",
        {"steam_id": steam_id, "number": fixed},
        campaign_id=cid,
    )
    return {
        "fixed_number": fixed,
        "campaign_id": cid,
        "confirmed_at": _iso_display(_utcnow()),
        "campaign": _campaign_public_dict(campaign, db=db),
    }


def change_fixed_lottery_number(db: Session, steam_id: str, new_number: int) -> dict[str, Any]:
    """Troca vitalícia do número fixo — custo em Âmbares."""
    if not _is_enabled():
        raise ValueError("lottery_disabled")
    new_number = int(new_number)
    if new_number < NUMBER_MIN or new_number > NUMBER_MAX:
        raise ValueError("invalid_number")
    current = ensure_fixed_lottery_number(db, steam_id)
    if new_number == current:
        raise ValueError("same_number")
    taken_global = db.execute(
        text(
            "SELECT steam_id FROM store_users "
            "WHERE fixed_lottery_number = :n AND steam_id != :sid LIMIT 1"
        ),
        {"n": new_number, "sid": steam_id},
    ).fetchone()
    if taken_global:
        raise ValueError("number_unavailable")
    campaign = get_active_campaign(db)
    cid: int | None = None
    has_confirmation = False
    within_deadline = False
    if campaign and str(campaign.status) == "ACTIVE":
        cid = int(campaign.id)
        has_confirmation = _campaign_confirmation_row(db, cid, steam_id) is not None
        within_deadline = _confirmation_deadline_ok(campaign)
        if has_confirmation and within_deadline:
            if _is_number_taken_in_campaign(db, cid, new_number, exclude_steam_id=steam_id):
                raise ValueError("number_unavailable_in_campaign")
    if _player_balance(db, steam_id) < FIXED_NUMBER_CHANGE_COST:
        raise ValueError("insufficient_balance")
    if _debit_fn is None:
        raise RuntimeError("lottery_not_configured")
    _debit_fn(db, steam_id, FIXED_NUMBER_CHANGE_COST)
    try:
        from amber_ledger import record_lottery_amber_purchase

        record_lottery_amber_purchase(
            db,
            campaign_id=cid or 0,
            steam_id=steam_id,
            amount=FIXED_NUMBER_CHANGE_COST,
            source="FIXED_NUMBER_CHANGE",
            number_value=new_number,
        )
    except Exception as exc:
        log.warning("Ledger fixed number change: %s", exc)
    db.execute(
        text("UPDATE store_users SET fixed_lottery_number = :n WHERE steam_id = :sid"),
        {"n": new_number, "sid": steam_id},
    )
    if cid and has_confirmation and within_deadline:
        db.execute(
            text(
                "UPDATE lottery_numbers SET status = 'REVOKED', revoked_at = :now, "
                "revoke_reason = 'fixed_change' "
                "WHERE campaign_id = :cid AND steam_id = :sid AND source = 'FIXED_REGISTERED' "
                "AND status = 'ACTIVE'"
            ),
            {"now": _naive(_utcnow()), "cid": cid, "sid": steam_id},
        )
        _insert_number(
            db,
            campaign_id=cid,
            steam_id=steam_id,
            number_value=new_number,
            source="FIXED_REGISTERED",
            amber_cost=0,
        )
        db.execute(
            text(
                "UPDATE lottery_campaign_confirmations SET fixed_number = :n "
                "WHERE campaign_id = :cid AND steam_id = :sid"
            ),
            {"n": new_number, "cid": cid, "sid": steam_id},
        )
    _audit_safe(
        db, "lottery_fixed_number_changed",
        {"steam_id": steam_id, "from": current, "to": new_number, "cost": FIXED_NUMBER_CHANGE_COST},
        campaign_id=cid,
    )
    return {
        "fixed_number": new_number,
        "previous_number": current,
        "amber_cost": FIXED_NUMBER_CHANGE_COST,
        "new_balance": _player_balance(db, steam_id),
    }


def _migrate_lottery_columns(engine: Engine) -> None:
    """Adiciona colunas ausentes em instalações parciais (MySQL/SQLite)."""
    is_sqlite = "sqlite" in str(engine.url).lower()
    campaign_cols = {
        "starts_at": "DATETIME NULL",
        "prize_amber_from_purchases": "INTEGER NOT NULL DEFAULT 0",
        "prize_amber_from_donations": "INTEGER NOT NULL DEFAULT 0",
        "prize_amber_from_market": "INTEGER NOT NULL DEFAULT 0",
        "prize_amber_paid": "INTEGER NOT NULL DEFAULT 0",
        "prize_amber_subsidy": "INTEGER NOT NULL DEFAULT 0",
        "prize_pool_fully_distributed": "INTEGER NOT NULL DEFAULT 0",
        "matched_winners_count": "INTEGER NOT NULL DEFAULT 0",
        "prize_amber_rollover_out": "INTEGER NOT NULL DEFAULT 0",
        "prize_catalog_json": "TEXT NULL",
        "amber_random_price": "INTEGER NOT NULL DEFAULT 1000",
        "amber_reserve_price": "INTEGER NOT NULL DEFAULT 2000",
        "amber_random_max_per_player": "INTEGER NOT NULL DEFAULT 5",
        "regulamento_version": "VARCHAR(16) NOT NULL DEFAULT '1.0'",
        "allow_staff_participation": "INTEGER NOT NULL DEFAULT 1",
        "auto_chain_enabled": "INTEGER NOT NULL DEFAULT 1",
        "next_campaign_draw_offset_hours": "INTEGER NOT NULL DEFAULT 168",
        "previous_campaign_id": "INTEGER NULL",
        "completed_at": "DATETIME NULL",
    }
    number_cols = {
        "amber_cost": "INTEGER NOT NULL DEFAULT 0",
        "assigned_at": "DATETIME NULL",
        "revoked_at": "DATETIME NULL",
        "revoke_reason": "VARCHAR(64) NULL",
        "team_id": "INTEGER NULL",
    }
    winner_cols = {
        "catalog_orders_json": "TEXT NULL",
    }
    with engine.connect() as conn:
        if is_sqlite:
            existing_camp = {
                str(r[1])
                for r in conn.execute(text("PRAGMA table_info(lottery_campaigns)")).fetchall()
            }
            for col, ddl in campaign_cols.items():
                if col not in existing_camp:
                    conn.execute(text(f"ALTER TABLE lottery_campaigns ADD COLUMN {col} {ddl}"))
            existing_num = {
                str(r[1])
                for r in conn.execute(text("PRAGMA table_info(lottery_numbers)")).fetchall()
            }
            for col, ddl in number_cols.items():
                if col not in existing_num:
                    conn.execute(text(f"ALTER TABLE lottery_numbers ADD COLUMN {col} {ddl}"))
            existing_win = {
                str(r[1])
                for r in conn.execute(text("PRAGMA table_info(lottery_winners)")).fetchall()
            }
            for col, ddl in winner_cols.items():
                if col not in existing_win:
                    conn.execute(text(f"ALTER TABLE lottery_winners ADD COLUMN {col} {ddl}"))
        else:
            for col, ddl in campaign_cols.items():
                row = conn.execute(text(f"SHOW COLUMNS FROM lottery_campaigns LIKE '{col}'")).fetchone()
                if row is None:
                    conn.execute(text(f"ALTER TABLE lottery_campaigns ADD COLUMN {col} {ddl}"))
            for col, ddl in number_cols.items():
                row = conn.execute(text(f"SHOW COLUMNS FROM lottery_numbers LIKE '{col}'")).fetchone()
                if row is None:
                    conn.execute(text(f"ALTER TABLE lottery_numbers ADD COLUMN {col} {ddl}"))
            for col, ddl in winner_cols.items():
                row = conn.execute(text(f"SHOW COLUMNS FROM lottery_winners LIKE '{col}'")).fetchone()
                if row is None:
                    conn.execute(text(f"ALTER TABLE lottery_winners ADD COLUMN {col} {ddl}"))
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


def _audit_safe(db: Session, event_type: str, payload: dict[str, Any], *, campaign_id: int | None = None) -> None:
    try:
        _audit(db, event_type, payload, campaign_id=campaign_id)
    except Exception as exc:
        log.warning("lottery audit %s falhou: %s", event_type, exc)


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
        int(_row_val(row, "prize_amber_base", 0) or 0)
        + int(_row_val(row, "prize_amber_rollover_in", 0) or 0)
        + int(_row_val(row, "prize_amber_from_purchases", 0) or 0)
        + int(_row_val(row, "prize_amber_from_donations", 0) or 0)
        + int(_row_val(row, "prize_amber_from_market", 0) or 0)
    )


def _campaign_public_dict(row: Any, *, db: Session | None = None) -> dict[str, Any]:
    draw = _parse_dt(_row_val(row, "draw_at"))
    starts = _parse_dt(_row_val(row, "starts_at"))
    now = _utcnow()
    secs = max(0, int((draw - now).total_seconds())) if draw and draw > now else 0
    secs_until_start = 0
    if starts and starts > now:
        secs_until_start = max(0, int((starts - now).total_seconds()))
    issued = 0
    participants = 0
    donated = 0.0
    if db is not None:
        issued = _numbers_issued_count(db, int(_row_val(row, "id", 0)))
        participants = _participant_count(db, int(_row_val(row, "id", 0)))
        donated = _total_donated_brl(db, int(_row_val(row, "id", 0)))
    status = str(_row_val(row, "status", ""))
    prev_id = _row_val(row, "previous_campaign_id", None)
    prep_window = status == "DRAFT" and secs_until_start > 0
    return {
        "id": int(_row_val(row, "id", 0)),
        "sequence_number": int(_row_val(row, "sequence_number", 0)),
        "title": str(_row_val(row, "title", "")),
        "status": status,
        "draw_at_utc": _iso_utc(draw),
        "draw_at_display": _iso_display(draw),
        "starts_at_utc": _iso_utc(starts),
        "starts_at_display": _iso_display(starts),
        "seconds_until_start": secs_until_start,
        "prep_window": prep_window,
        "previous_campaign_id": int(prev_id) if prev_id else None,
        "timezone_label": TZ_LABEL,
        "seconds_remaining": secs,
        "prize_amber_total": _prize_total(row),
        "prize_amber_base": int(_row_val(row, "prize_amber_base", 0) or 0),
        "prize_amber_rollover_in": int(_row_val(row, "prize_amber_rollover_in", 0) or 0),
        "prize_amber_from_purchases": int(_row_val(row, "prize_amber_from_purchases", 0) or 0),
        "prize_amber_from_donations": int(_row_val(row, "prize_amber_from_donations", 0) or 0),
        "prize_amber_from_market": int(_row_val(row, "prize_amber_from_market", 0) or 0),
        "prize_catalog": _parse_prize_catalog_row(row),
        "amber_random_price": int(_row_val(row, "amber_random_price", 1000) or 1000),
        "amber_reserve_price": int(_row_val(row, "amber_reserve_price", 2000) or 2000),
        "amber_random_max_per_player": int(_row_val(row, "amber_random_max_per_player", 5) or 5),
        "numbers_available_count": 900 - issued,
        "winning_numbers_count": int(_row_val(row, "winning_numbers_count", 1) or 1),
        "participant_count": participants,
        "numbers_issued_count": issued,
        "total_donated_brl": round(donated, 2),
        "regulamento_version": str(_row_val(row, "regulamento_version") or LOTTERY_REGULAMENTO_VERSION),
        "rules_summary": RULES_SUMMARY,
        "results_pending": status == "DRAWING",
        "editable": status in ("DRAFT", "ACTIVE"),
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


def team_holder_steam_id(team_id: int) -> str:
    """Synthetic steam_id for TEAM-owned lottery numbers (linked to team, not a player)."""
    return f"{TEAM_HOLDER_PREFIX}{int(team_id)}"


def parse_team_id_from_holder(steam_id: str) -> int | None:
    sid = str(steam_id or "")
    if not sid.startswith(TEAM_HOLDER_PREFIX):
        return None
    try:
        return int(sid[len(TEAM_HOLDER_PREFIX):])
    except (TypeError, ValueError):
        return None


def catalog_prizes_amber_value(prizes: list[dict[str, Any]] | None) -> int:
    """Convert catalog prize list to Âmbares (for team wins — items are never delivered)."""
    total = 0
    for prize in prizes or []:
        if not isinstance(prize, dict):
            continue
        amount = max(1, int(prize.get("amount") or 1))
        explicit = prize.get("amber_value")
        if explicit is None:
            explicit = prize.get("amber_price")
        if explicit is None:
            explicit = prize.get("price")
        if explicit is not None:
            try:
                total += max(0, int(explicit)) * amount
                continue
            except (TypeError, ValueError):
                pass
        kind = str(prize.get("kind") or "").strip().lower()
        item_id = str(prize.get("item_id") or "").strip()
        if _resolve_catalog_prize_fn and kind and item_id:
            try:
                resolved = _resolve_catalog_prize_fn(kind, item_id) or {}
                price = resolved.get("amber_price")
                if price is None:
                    price = resolved.get("price")
                if price is not None:
                    total += max(0, int(price)) * amount
                    continue
            except Exception as exc:
                log.warning("catalog_prizes_amber_value resolve failed: %s", exc)
        total += 0
    return max(0, int(total))


def _insert_number(
    db: Session,
    *,
    campaign_id: int,
    steam_id: str,
    number_value: int,
    source: str,
    payment_id: str | None = None,
    amber_cost: int = 0,
    team_id: int | None = None,
) -> None:
    now = _naive(_utcnow())
    has_team_col = _table_has_column(db, "lottery_numbers", "team_id")
    existing = db.execute(
        text(
            "SELECT id, status FROM lottery_numbers "
            "WHERE campaign_id = :cid AND number_value = :num LIMIT 1"
        ),
        {"cid": campaign_id, "num": number_value},
    ).fetchone()
    if existing:
        status = str(existing.status)
        if status == "ACTIVE":
            raise ValueError("number_unavailable")
        if status == "REVOKED":
            if has_team_col:
                db.execute(
                    text(
                        "UPDATE lottery_numbers SET steam_id = :sid, payment_id = :pid, source = :src, "
                        "amber_cost = :cost, team_id = :tid, status = 'ACTIVE', assigned_at = :now, "
                        "revoked_at = NULL, revoke_reason = NULL WHERE id = :id"
                    ),
                    {
                        "id": int(existing.id),
                        "sid": steam_id,
                        "pid": payment_id,
                        "src": source,
                        "cost": amber_cost,
                        "tid": int(team_id) if team_id is not None else None,
                        "now": now,
                    },
                )
            else:
                db.execute(
                    text(
                        "UPDATE lottery_numbers SET steam_id = :sid, payment_id = :pid, source = :src, "
                        "amber_cost = :cost, status = 'ACTIVE', assigned_at = :now, "
                        "revoked_at = NULL, revoke_reason = NULL WHERE id = :id"
                    ),
                    {
                        "id": int(existing.id),
                        "sid": steam_id,
                        "pid": payment_id,
                        "src": source,
                        "cost": amber_cost,
                        "now": now,
                    },
                )
            return
        raise ValueError("number_unavailable")
    try:
        if has_team_col:
            db.execute(
                text(
                    "INSERT INTO lottery_numbers "
                    "(campaign_id, steam_id, payment_id, source, number_value, amber_cost, "
                    "status, assigned_at, team_id) "
                    "VALUES (:cid, :sid, :pid, :src, :num, :cost, 'ACTIVE', :now, :tid)"
                ),
                {
                    "cid": campaign_id,
                    "sid": steam_id,
                    "pid": payment_id,
                    "src": source,
                    "num": number_value,
                    "cost": amber_cost,
                    "now": now,
                    "tid": int(team_id) if team_id is not None else None,
                },
            )
        else:
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
                    "now": now,
                },
            )
    except IntegrityError:
        raise ValueError("number_unavailable") from None


def allocate_team_numbers(
    db: Session,
    *,
    campaign_id: int,
    team_id: int,
    count: int,
) -> dict[str, Any]:
    """Assign up to `count` free TEAM numbers. Shortfall is returned (no exception).

    Q12: caller reimburses team bank for each number that could not be allocated.
    """
    count = max(0, int(count))
    if count <= 0:
        return {"assigned": [], "numbers": [], "requested": 0, "shortfall": 0}
    if not _is_enabled():
        raise ValueError("lottery_disabled")
    cid = int(campaign_id)
    tid = int(team_id)
    holder = team_holder_steam_id(tid)
    occupied = _occupied_numbers(db, cid)
    assigned: list[int] = []
    for _ in range(count):
        if len(occupied) >= 900:
            break
        try:
            n = _pick_random_free(db, cid, occupied)
        except ValueError:
            break
        try:
            _insert_number(
                db,
                campaign_id=cid,
                steam_id=holder,
                number_value=n,
                source="TEAM",
                team_id=tid,
            )
        except ValueError:
            occupied.add(n)
            continue
        occupied.add(n)
        assigned.append(n)
    shortfall = count - len(assigned)
    if assigned:
        _audit(
            db,
            "lottery_team_numbers_assigned",
            {
                "team_id": tid,
                "numbers": assigned,
                "requested": count,
                "shortfall": shortfall,
            },
            campaign_id=cid,
        )
    return {
        "assigned": assigned,
        "numbers": assigned,
        "requested": count,
        "shortfall": shortfall,
    }


def list_team_numbers(db: Session, *, campaign_id: int, team_id: int) -> list[int]:
    holder = team_holder_steam_id(int(team_id))
    has_team_col = _table_has_column(db, "lottery_numbers", "team_id")
    if has_team_col:
        rows = db.execute(
            text(
                "SELECT number_value FROM lottery_numbers "
                "WHERE campaign_id = :cid AND status = 'ACTIVE' "
                "AND (team_id = :tid OR (source = 'TEAM' AND steam_id = :sid)) "
                "ORDER BY number_value"
            ),
            {"cid": int(campaign_id), "tid": int(team_id), "sid": holder},
        ).fetchall()
    else:
        rows = db.execute(
            text(
                "SELECT number_value FROM lottery_numbers "
                "WHERE campaign_id = :cid AND steam_id = :sid AND source = 'TEAM' "
                "AND status = 'ACTIVE' ORDER BY number_value"
            ),
            {"cid": int(campaign_id), "sid": holder},
        ).fetchall()
    return [int(r[0]) for r in rows]


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
    tid = parse_team_id_from_holder(steam_id)
    if tid is not None:
        try:
            row = db.execute(
                text("SELECT name, tag FROM teams WHERE id = :id LIMIT 1"),
                {"id": tid},
            ).fetchone()
            if row:
                name = str(row[0] or f"Equipe #{tid}")
                tag = str(row[1] or "").strip()
                return f"[{tag}] {name}" if tag else name
        except Exception:
            return f"Equipe #{tid}"
        return f"Equipe #{tid}"
    try:
        row = db.execute(
            text(
                "SELECT market_display_name, steam_persona FROM store_users "
                "WHERE steam_id = :sid LIMIT 1"
            ),
            {"sid": steam_id},
        ).fetchone()
    except OperationalError:
        return "Jogador"
    if row:
        for col in (_row_val(row, "market_display_name"), _row_val(row, "steam_persona")):
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
    cid = int(campaign.id)

    # Idempotência: verifica se payment_id já foi processado
    already_numbers = db.execute(
        text(
            "SELECT COUNT(*) FROM lottery_numbers WHERE payment_id = :pid AND status = 'ACTIVE'"
        ),
        {"pid": payment_id},
    ).fetchone()
    idem_prize_key = f"lottery:donation_prize:{cid}:{payment_id}"
    already_prize = False
    try:
        already_prize = bool(
            db.execute(
                text("SELECT 1 FROM amber_ledger WHERE idempotency_key = :k LIMIT 1"),
                {"k": idem_prize_key},
            ).fetchone()
        )
    except Exception:
        pass  # amber_ledger pode não existir ainda

    if (already_numbers and int(already_numbers[0]) > 0) or already_prize:
        return {"skipped": True, "reason": "already_assigned"}

    # --- Prêmio total: R$ 1 doado = +DONATION_AMBER_PER_REAL Âmbares no pool ---
    prize_contribution = int(round(float(amount_brl) * DONATION_AMBER_PER_REAL))
    if prize_contribution > 0:
        db.execute(
            text(
                "UPDATE lottery_campaigns "
                "SET prize_amber_from_donations = prize_amber_from_donations + :contrib "
                "WHERE id = :cid"
            ),
            {"contrib": prize_contribution, "cid": cid},
        )
        try:
            from amber_ledger import record_lottery_donation_prize_contribution

            record_lottery_donation_prize_contribution(
                db,
                campaign_id=cid,
                payment_id=payment_id,
                steam_id=steam_id,
                amount=prize_contribution,
            )
        except Exception as exc:
            log.warning("Ledger lottery donation prize: %s", exc)
    else:
        prize_contribution = 0

    # --- Atribuição de números da sorte: R$5 = 1 número ---
    qty = int(math.floor(float(amount_brl) / 5.0))
    numbers: list[int] = []
    if qty > 0:
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
            {
                "payment_id": payment_id,
                "steam_id": steam_id,
                "numbers": numbers,
                "qty": len(numbers),
                "prize_contribution_amber": prize_contribution,
            },
            campaign_id=cid,
        )

    return {
        "assigned": len(numbers),
        "numbers": numbers,
        "prize_contribution_amber": prize_contribution,
    }


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
    _audit_safe(db, "lottery_amber_random_purchased", {"steam_id": steam_id, "number": n}, campaign_id=cid)
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
            "SELECT id, status FROM lottery_numbers WHERE campaign_id = :cid AND number_value = :num "
            "LIMIT 1"
        ),
        {"cid": cid, "num": number},
    ).fetchone()
    if taken and str(taken.status) == "ACTIVE":
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
    _insert_number(
        db, campaign_id=cid, steam_id=steam_id, number_value=number,
        source="AMBER_RESERVE", amber_cost=price,
    )
    db.execute(
        text(
            "UPDATE lottery_campaigns SET prize_amber_from_purchases = prize_amber_from_purchases + :amt, "
            "updated_at = :now WHERE id = :id"
        ),
        {"amt": price, "now": _naive(_utcnow()), "id": cid},
    )
    row = _fetch_campaign_row(db, cid)
    _audit_safe(db, "lottery_amber_reserved", {"steam_id": steam_id, "number": number}, campaign_id=cid)
    return {
        "number": {"value": number, "source": "AMBER_RESERVE", "amber_cost": price},
        "prize_amber_total": _prize_total(row) if row else 0,
        "new_balance": _player_balance(db, steam_id),
    }


def contribute_market_pair_to_prize(
    db: Session,
    *,
    amount: int,
    listing_id: int,
    tx_id: int,
    seller_steam_id: str | None = None,
) -> dict[str, Any]:
    """Destina 0,40×S ao ARKBANK (tesouraria) — deixa de alimentar o pote do sorteio.

    Cutover opção A (docs/ARKBANK_SPEC.md §7): prize_amber_from_market fica congelado;
    o crédito de sistema vai para arkbank_transactions (market_pair_share).
    Não depende de campanha ativa. Idempotente via arkbank:pair:{tx_id}.
    """
    amount = max(0, int(amount))
    if amount <= 0:
        return {
            "credited": 0,
            "campaign_id": None,
            "prize_amber_total": 0,
            "destination": "arkbank",
        }
    ark_result: dict[str, Any] = {}
    try:
        from arkbank_service import credit_market_pair_share

        ark_result = credit_market_pair_share(
            db,
            amount=amount,
            listing_id=listing_id,
            tx_id=tx_id,
            seller_steam_id=seller_steam_id,
            commit=False,
        )
    except Exception as exc:
        log.warning(
            "ARKBANK market pair share falhou listing=%s tx=%s: %s",
            listing_id,
            tx_id,
            exc,
        )
        return {
            "credited": 0,
            "campaign_id": None,
            "prize_amber_total": 0,
            "destination": "arkbank",
            "error": str(exc),
        }

    try:
        from amber_ledger import record_lottery_market_pair_contribution

        # Mantém Âmbarômetro (gross) — destino económico é ARKBANK, não o pote.
        campaign = get_active_campaign(db)
        cid = int(campaign.id) if campaign else 0
        record_lottery_market_pair_contribution(
            db,
            campaign_id=cid or 0,
            listing_id=listing_id,
            tx_id=tx_id,
            amount=amount,
            seller_steam_id=seller_steam_id,
        )
    except Exception as exc:
        log.warning("Ledger market pair contribution: %s", exc)

    campaign = get_active_campaign(db)
    cid = int(campaign.id) if campaign else None
    row = _fetch_campaign_row(db, cid) if cid else None
    _audit_safe(
        db,
        "arkbank_market_pair_share",
        {
            "listing_id": listing_id,
            "tx_id": tx_id,
            "amount": amount,
            "destination": "arkbank",
            "duplicate": bool(ark_result.get("duplicate")),
        },
        campaign_id=cid,
    )
    return {
        "credited": amount if ark_result.get("applied") or ark_result.get("duplicate") else 0,
        "campaign_id": cid,
        "prize_amber_total": _prize_total(row) if row else 0,
        "destination": "arkbank",
        "arkbank_balance_after": ark_result.get("balance_after"),
        "duplicate": bool(ark_result.get("duplicate")),
    }


def _last_completed_results_payload(db: Session, *, prefer_campaign_id: int | None = None) -> dict[str, Any] | None:
    """Último sorteio COMPLETED com números sorteados/vencedores (para UI pós auto-chain)."""
    camp_row = None
    if prefer_campaign_id:
        camp_row = _fetch_campaign_row(db, int(prefer_campaign_id))
        if camp_row and str(_row_val(camp_row, "status", "")) != "COMPLETED":
            camp_row = None
    if camp_row is None:
        order_col = (
            "completed_at DESC, id DESC"
            if _table_has_column(db, "lottery_campaigns", "completed_at")
            else "id DESC"
        )
        camp_row = db.execute(
            text(
                f"SELECT * FROM lottery_campaigns WHERE status = 'COMPLETED' "
                f"ORDER BY {order_col} LIMIT 1"
            )
        ).fetchone()
    if not camp_row:
        return None
    cid = int(_row_val(camp_row, "id", 0))
    try:
        res = get_campaign_results(db, cid)
    except ValueError:
        return None
    return {
        **res,
        "title": str(_row_val(camp_row, "title", "")),
        "sequence_number": int(_row_val(camp_row, "sequence_number", 0) or 0),
        "completed_at": _iso_display(_parse_dt(_row_val(camp_row, "completed_at"))),
        "draw_at_display": _iso_display(_parse_dt(_row_val(camp_row, "draw_at"))),
    }


def get_scheduled_draft_campaign(db: Session) -> Any | None:
    """Próxima campanha DRAFT (janela de preparação / agendada)."""
    has_starts = _table_has_column(db, "lottery_campaigns", "starts_at")
    if has_starts:
        return db.execute(
            text(
                "SELECT * FROM lottery_campaigns WHERE status = 'DRAFT' "
                "ORDER BY CASE WHEN starts_at IS NULL THEN 1 ELSE 0 END, "
                "starts_at ASC, id ASC LIMIT 1"
            )
        ).fetchone()
    return db.execute(
        text(
            "SELECT * FROM lottery_campaigns WHERE status = 'DRAFT' "
            "ORDER BY id ASC LIMIT 1"
        )
    ).fetchone()


def get_public_current(db: Session) -> dict[str, Any]:
    row = get_active_campaign(db)
    base = {
        "regulamento_version": LOTTERY_REGULAMENTO_VERSION,
        "regulamento_url": "/api/public/lottery/regulamento",
    }
    prefer_prev = int(_row_val(row, "previous_campaign_id", 0) or 0) if row else None
    upcoming_row = None if row else get_scheduled_draft_campaign(db)
    if not prefer_prev and upcoming_row:
        prefer_prev = int(_row_val(upcoming_row, "previous_campaign_id", 0) or 0) or None
    last_completed = _last_completed_results_payload(
        db, prefer_campaign_id=prefer_prev or None,
    )
    upcoming = _campaign_public_dict(upcoming_row, db=db) if upcoming_row else None
    if not row:
        return {
            "ok": True,
            "campaign": None,
            "upcoming": upcoming,
            "enabled": _is_enabled(),
            "last_completed": last_completed,
            **base,
        }
    return {
        "ok": True,
        "campaign": _campaign_public_dict(row, db=db),
        "upcoming": None,
        "enabled": _is_enabled(),
        "last_completed": last_completed,
        **base,
    }


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
    bind = db.get_bind()
    is_sqlite = "sqlite" in str(bind.url).lower()
    has_assigned_at = _table_has_column(db, "lottery_numbers", "assigned_at")
    sort_key = "MAX(ln.assigned_at)" if has_assigned_at else "MAX(ln.id)"
    if is_sqlite:
        agg_sql = (
            f"SELECT ln.steam_id, "
            f"GROUP_CONCAT(ln.number_value || ':' || ln.source) AS nums, "
            f"{sort_key} AS last_at "
            f"FROM lottery_numbers ln "
            f"WHERE ln.campaign_id = :cid AND ln.status = 'ACTIVE' "
            f"GROUP BY ln.steam_id{having} "
            f"ORDER BY {sort_key} DESC LIMIT :lim OFFSET :off"
        )
    else:
        agg_sql = (
            f"SELECT ln.steam_id, "
            f"GROUP_CONCAT(CONCAT(ln.number_value, ':', ln.source) ORDER BY ln.number_value) AS nums, "
            f"{sort_key} AS last_at "
            f"FROM lottery_numbers ln "
            f"WHERE ln.campaign_id = :cid AND ln.status = 'ACTIVE' "
            f"GROUP BY ln.steam_id{having} "
            f"ORDER BY {sort_key} DESC LIMIT :lim OFFSET :off"
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
    fixed_number = _get_fixed_lottery_number(db, steam_id)
    if fixed_number is None:
        try:
            fixed_number = ensure_fixed_lottery_number(db, steam_id)
        except ValueError:
            fixed_number = None
    row = get_active_campaign(db)
    if not row:
        return {
            "ok": True,
            "campaign": None,
            "numbers": [],
            "enabled": _is_enabled(),
            "fixed_number": fixed_number,
            "fixed_number_change_cost": FIXED_NUMBER_CHANGE_COST,
            "campaign_confirmation": None,
        }
    cid = int(row.id)
    nums = db.execute(
        text(
            "SELECT number_value, source, amber_cost, assigned_at, payment_id "
            "FROM lottery_numbers WHERE campaign_id = :cid AND steam_id = :sid AND status = 'ACTIVE' "
            "ORDER BY assigned_at ASC"
        ),
        {"cid": cid, "sid": steam_id},
    ).fetchall()
    by_source: dict[str, list[int]] = {
        "DONATION": [], "AMBER_RANDOM": [], "AMBER_RESERVE": [], "FIXED_REGISTERED": [],
    }
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
    max_p = int(_row_val(row, "amber_random_max_per_player", 5) or 5)
    random_count = len(by_source.get("AMBER_RANDOM", []))
    fixed_number = _get_fixed_lottery_number(db, steam_id)
    if fixed_number is None:
        try:
            fixed_number = ensure_fixed_lottery_number(db, steam_id)
        except ValueError:
            fixed_number = None
    conf_row = _campaign_confirmation_row(db, cid, steam_id)
    can_confirm = (
        str(_row_val(row, "status", "")) == "ACTIVE"
        and _confirmation_deadline_ok(row)
        and conf_row is None
    )
    return {
        "ok": True,
        "enabled": _is_enabled(),
        "campaign": _campaign_public_dict(row, db=db),
        "numbers": items,
        "by_source": by_source,
        "donated_brl": round(donated_brl, 2),
        "amber_random_count": random_count,
        "amber_random_remaining": max(0, max_p - random_count),
        "fixed_number": fixed_number,
        "fixed_number_change_cost": FIXED_NUMBER_CHANGE_COST,
        "campaign_confirmation": {
            "confirmed": conf_row is not None,
            "confirmed_at": _iso_display(_parse_dt(_row_val(conf_row, "confirmed_at"))) if conf_row else None,
            "can_confirm": can_confirm,
            "confirmation_deadline_hours": CONFIRMATION_DEADLINE_HOURS,
        },
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
        catalog_orders: list[dict[str, Any]] = []
        raw_orders = _row_val(w, "catalog_orders_json", None)
        if raw_orders:
            try:
                catalog_orders = json.loads(raw_orders) if isinstance(raw_orders, str) else list(raw_orders)
            except (json.JSONDecodeError, TypeError):
                catalog_orders = []
        winners.append({
            "display_name_masked": mask_display_name(name),
            "winning_number": int(w.winning_number),
            "prize_amber": int(w.prize_amber),
            "catalog_orders": catalog_orders,
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
        "prize_catalog": _parse_prize_catalog_row(camp),
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
    starts_at = _parse_dt(data.get("starts_at"))
    if starts_at is None:
        starts_at = _utcnow() + timedelta(hours=24)
    prize_catalog = normalize_catalog_prizes(
        data.get("prize_catalog", data.get("prize_catalog_json")),
        resolve=True,
    )
    catalog_json = json.dumps(prize_catalog, ensure_ascii=False)
    has_pcat = _table_has_column(db, "lottery_campaigns", "prize_catalog_json")
    if has_pcat:
        db.execute(
            text(
                "INSERT INTO lottery_campaigns "
                "(sequence_number, title, status, draw_at, starts_at, winning_numbers_count, prize_amber_base, "
                "prize_amber_rollover_in, prize_catalog_json, amber_random_price, amber_reserve_price, "
                "amber_random_max_per_player, regulamento_version, allow_staff_participation, "
                "auto_chain_enabled, next_campaign_draw_offset_hours, created_at, updated_at) "
                "VALUES (:seq, :title, 'DRAFT', :draw, :starts, :wnc, :base, :rol, :pcat, :arp, :aresv, :armax, "
                ":reg, :staff, :chain, :offset, :now, :now)"
            ),
            {
                "seq": seq,
                "title": str(data.get("title") or f"Sorteio ARKLAND #{seq}"),
                "draw": _naive(draw_at),
                "starts": _naive(starts_at),
                "wnc": max(1, min(5, int(data.get("winning_numbers_count") or 1))),
                "base": int(data.get("prize_amber_base") or 5000),
                "rol": int(data.get("prize_amber_rollover_in") or 0),
                "pcat": catalog_json,
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
    else:
        if prize_catalog:
            raise ValueError("prize_catalog_not_supported")
        db.execute(
            text(
                "INSERT INTO lottery_campaigns "
                "(sequence_number, title, status, draw_at, starts_at, winning_numbers_count, prize_amber_base, "
                "prize_amber_rollover_in, amber_random_price, amber_reserve_price, "
                "amber_random_max_per_player, regulamento_version, allow_staff_participation, "
                "auto_chain_enabled, next_campaign_draw_offset_hours, created_at, updated_at) "
                "VALUES (:seq, :title, 'DRAFT', :draw, :starts, :wnc, :base, :rol, :arp, :aresv, :armax, "
                ":reg, :staff, :chain, :offset, :now, :now)"
            ),
            {
                "seq": seq,
                "title": str(data.get("title") or f"Sorteio ARKLAND #{seq}"),
                "draw": _naive(draw_at),
                "starts": _naive(starts_at),
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
    _audit(db, "lottery_campaign_created", {"admin": admin_steam_id, "prize_catalog": prize_catalog}, campaign_id=cid)
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
    starts_at = _parse_dt(_row_val(row, "starts_at"))
    if starts_at is None:
        starts_at = _utcnow() + timedelta(hours=24)
    db.execute(
        text(
            "UPDATE lottery_campaigns SET status = 'ACTIVE', starts_at = :starts, updated_at = :now "
            "WHERE id = :id"
        ),
        {"starts": _naive(starts_at), "now": now, "id": campaign_id},
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
    if "starts_at" in patch:
        dt = _parse_dt(patch["starts_at"])
        if dt:
            fields.append("starts_at = :starts_at")
            params["starts_at"] = _naive(dt)
    if "winning_numbers_count" in patch:
        fields.append("winning_numbers_count = :wnc")
        params["wnc"] = max(1, min(5, int(patch["winning_numbers_count"])))
    if "prize_amber_base" in patch:
        fields.append("prize_amber_base = :base")
        params["base"] = int(patch["prize_amber_base"])
    if "prize_catalog" in patch or "prize_catalog_json" in patch:
        if not _table_has_column(db, "lottery_campaigns", "prize_catalog_json"):
            raise ValueError("prize_catalog_not_supported")
        prize_catalog = normalize_catalog_prizes(
            patch.get("prize_catalog", patch.get("prize_catalog_json")),
            resolve=True,
        )
        fields.append("prize_catalog_json = :pcat")
        params["pcat"] = json.dumps(prize_catalog, ensure_ascii=False)
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


def _numbers_by_source(db: Session, campaign_id: int) -> dict[str, int]:
    rows = db.execute(
        text(
            "SELECT source, COUNT(*) AS cnt FROM lottery_numbers "
            "WHERE campaign_id = :cid AND status = 'ACTIVE' GROUP BY source"
        ),
        {"cid": campaign_id},
    ).fetchall()
    out = {"DONATION": 0, "AMBER_RANDOM": 0, "AMBER_RESERVE": 0, "FIXED_REGISTERED": 0}
    for r in rows:
        out[str(r.source)] = int(r.cnt)
    return out


def get_campaign_admin_report(db: Session, campaign_id: int) -> dict[str, Any]:
    """Relatório admin: estatísticas da campanha + participantes com nick Steam."""
    row = _fetch_campaign_row(db, campaign_id)
    if not row:
        raise ValueError("campaign_not_found")
    cid = int(campaign_id)
    issued = _numbers_issued_count(db, cid)
    participants_count = _participant_count(db, cid)
    by_source = _numbers_by_source(db, cid)
    num_rows = db.execute(
        text(
            "SELECT steam_id, number_value, source, payment_id, amber_cost, assigned_at "
            "FROM lottery_numbers WHERE campaign_id = :cid AND status = 'ACTIVE' "
            "ORDER BY assigned_at ASC, number_value ASC"
        ),
        {"cid": cid},
    ).fetchall()
    grouped: dict[str, dict[str, Any]] = {}
    for r in num_rows:
        sid = str(r.steam_id)
        entry = grouped.setdefault(
            sid,
            {"steam_id": sid, "steam_nickname": "", "numbers": [], "number_count": 0},
        )
        entry["numbers"].append({
            "value": int(r.number_value),
            "source": str(r.source),
            "amber_cost": int(r.amber_cost or 0),
            "payment_id": r.payment_id,
            "assigned_at": _iso_display(_parse_dt(r.assigned_at)),
        })
        entry["number_count"] += 1
    participants = []
    for sid, entry in grouped.items():
        entry["steam_nickname"] = _resolve_display_name(db, sid)
        entry["numbers"].sort(key=lambda n: n["value"])
        participants.append(entry)
    participants.sort(key=lambda p: (-p["number_count"], p["steam_nickname"].lower()))
    draw_results: dict[str, Any] | None = None
    status = str(_row_val(row, "status", ""))
    if status in ("COMPLETED", "DRAWING"):
        try:
            public_res = get_campaign_results(db, cid)
            winners_rows = db.execute(
                text(
                    "SELECT * FROM lottery_winners WHERE campaign_id = :cid "
                    "ORDER BY winning_number"
                ),
                {"cid": cid},
            ).fetchall()
            admin_winners = []
            for w in winners_rows:
                sid = str(w.steam_id)
                catalog_orders: list[dict[str, Any]] = []
                raw_orders = _row_val(w, "catalog_orders_json", None)
                if raw_orders:
                    try:
                        catalog_orders = (
                            json.loads(raw_orders) if isinstance(raw_orders, str) else list(raw_orders)
                        )
                    except (json.JSONDecodeError, TypeError):
                        catalog_orders = []
                admin_winners.append({
                    "steam_id": sid,
                    "steam_nickname": _resolve_display_name(db, sid),
                    "display_name_masked": mask_display_name(_resolve_display_name(db, sid)),
                    "winning_number": int(w.winning_number),
                    "prize_amber": int(w.prize_amber),
                    "share_per_match": int(w.share_per_match or 0),
                    "credited": bool(int(_row_val(w, "credited", 0) or 0)),
                    "catalog_orders": catalog_orders,
                })
            draw_results = {
                "winning_numbers": public_res["winning_numbers"],
                "winning_numbers_count": public_res["winning_numbers_count"],
                "matched_count": public_res["matched_count"],
                "share_per_match": public_res["share_per_match"],
                "prize_amber_total": public_res["prize_amber_total"],
                "prize_amber_paid": public_res["prize_amber_paid"],
                "prize_amber_subsidy": public_res["prize_amber_subsidy"],
                "prize_pool_fully_distributed": public_res["prize_pool_fully_distributed"],
                "prize_catalog": public_res.get("prize_catalog") or [],
                "winners": admin_winners,
                "unmatched_drawn_numbers": public_res.get("unmatched_drawn_numbers") or [],
                "rollover_next": public_res.get("rollover_next", 0),
                "draw_audit": public_res.get("draw_audit"),
            }
        except ValueError:
            draw_results = None
    return {
        "ok": True,
        "campaign": _campaign_public_dict(row, db=db),
        "summary": {
            "numbers_issued": issued,
            "numbers_available": 900 - issued,
            "numbers_total": 900,
            "participant_count": participants_count,
            "total_donated_brl": round(_total_donated_brl(db, cid), 2),
            "by_source": by_source,
        },
        "participants": participants,
        "draw_results": draw_results,
    }


def get_campaign_admin_participants(db: Session, campaign_id: int) -> dict[str, Any]:
    """Lista plana de números ativos (admin) com nick Steam."""
    row = _fetch_campaign_row(db, campaign_id)
    if not row:
        raise ValueError("campaign_not_found")
    cid = int(campaign_id)
    rows = db.execute(
        text(
            "SELECT steam_id, number_value, source, payment_id, amber_cost, assigned_at "
            "FROM lottery_numbers WHERE campaign_id = :cid AND status = 'ACTIVE' "
            "ORDER BY assigned_at DESC"
        ),
        {"cid": cid},
    ).fetchall()
    items = []
    for r in rows:
        sid = str(r.steam_id)
        items.append({
            "steam_id": sid,
            "steam_nickname": _resolve_display_name(db, sid),
            "number_value": int(r.number_value),
            "source": str(r.source),
            "payment_id": r.payment_id,
            "amber_cost": int(r.amber_cost or 0),
            "assigned_at": str(r.assigned_at),
        })
    return {"ok": True, "campaign_id": cid, "participants": items}


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
    has_team_col = _table_has_column(db, "lottery_numbers", "team_id")
    if has_team_col:
        holders = db.execute(
            text(
                "SELECT steam_id, number_value, source, team_id FROM lottery_numbers "
                "WHERE campaign_id = :cid AND status = 'ACTIVE'"
            ),
            {"cid": cid},
        ).fetchall()
    else:
        holders = db.execute(
            text(
                "SELECT steam_id, number_value, source FROM lottery_numbers "
                "WHERE campaign_id = :cid AND status = 'ACTIVE'"
            ),
            {"cid": cid},
        ).fetchall()
    holder_map: dict[int, dict[str, Any]] = {}
    for h in holders:
        tid_raw = _row_val(h, "team_id", None) if has_team_col else None
        parsed_tid = parse_team_id_from_holder(str(h.steam_id))
        team_id_val = int(tid_raw) if tid_raw is not None else parsed_tid
        holder_map[int(h.number_value)] = {
            "steam_id": str(h.steam_id),
            "source": str(_row_val(h, "source", "") or ""),
            "team_id": team_id_val,
        }
    matched_winners = [
        {
            "steam_id": holder_map[n]["steam_id"],
            "winning_number": n,
            "source": holder_map[n]["source"],
            "team_id": holder_map[n]["team_id"],
        }
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
    catalog_prizes = _parse_prize_catalog_row(row)
    catalog_amber = catalog_prizes_amber_value(catalog_prizes)
    pending_license_sync: list[tuple[str, str, int]] = []
    team_payouts: list[dict[str, Any]] = []
    if _credit_fn and matched_count > 0:
        for mw in matched_winners:
            sid = mw["steam_id"]
            num = mw["winning_number"]
            idem = f"lottery:prize:{cid}:{num}"
            team_id_win = mw.get("team_id")
            if team_id_win is None and str(mw.get("source") or "") == "TEAM":
                team_id_win = parse_team_id_from_holder(str(sid))
            is_team = str(mw.get("source") or "") == "TEAM" and team_id_win is not None
            if is_team and team_id_win:
                payout = _payout_team_lottery_win(
                    db,
                    campaign_id=cid,
                    draw_result_id=draw_id,
                    team_id=int(team_id_win),
                    winning_number=num,
                    share_amber=share,
                    catalog_amber=catalog_amber,
                    catalog_prizes=catalog_prizes,
                    now=now,
                    idempotency_key=idem,
                )
                team_payouts.append(payout)
                continue

            catalog_orders: list[dict[str, Any]] = []
            if catalog_prizes and _deliver_catalog_prize_fn is not None:
                for prize in catalog_prizes:
                    try:
                        delivered = _deliver_catalog_prize_fn(
                            db,
                            sid,
                            prize,
                            campaign_id=cid,
                            winning_number=num,
                        ) or {}
                        catalog_orders.append({
                            "kind": prize.get("kind"),
                            "item_id": prize.get("item_id"),
                            "amount": prize.get("amount", 1),
                            "label": prize.get("label"),
                            "order_id": delivered.get("order_id"),
                            "skipped": bool(delivered.get("skipped")),
                        })
                        lic_group = delivered.get("license_group")
                        if lic_group:
                            pending_license_sync.append(
                                (sid, str(lic_group), int(delivered.get("license_days") or 30))
                            )
                    except Exception as exc:
                        log.warning(
                            "Lottery catalog prize failed campaign=%s winner=%s prize=%s: %s",
                            cid, num, prize.get("item_id"), exc,
                        )
                        catalog_orders.append({
                            "kind": prize.get("kind"),
                            "item_id": prize.get("item_id"),
                            "error": str(exc),
                        })
            has_catalog_col = _table_has_column(db, "lottery_winners", "catalog_orders_json")
            if has_catalog_col:
                db.execute(
                    text(
                        "INSERT INTO lottery_winners "
                        "(campaign_id, draw_result_id, steam_id, winning_number, prize_amber, "
                        "share_per_match, credited, credited_at, ledger_idempotency_key, catalog_orders_json) "
                        "VALUES (:cid, :did, :sid, :num, :prize, :share, 0, NULL, :idem, :cat)"
                    ),
                    {
                        "cid": cid, "did": draw_id, "sid": sid, "num": num,
                        "prize": share, "share": share, "idem": idem,
                        "cat": json.dumps(catalog_orders, ensure_ascii=False),
                    },
                )
            else:
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
        {
            "winning_numbers": winning,
            "matched_count": matched_count,
            "split": split,
            "prize_catalog": catalog_prizes,
            "team_payouts": team_payouts,
        },
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
        "prize_catalog": catalog_prizes,
        "team_payouts": team_payouts,
        "next_campaign_id": next_id,
        "pending_license_sync": list(pending_license_sync),
    }


def _payout_team_lottery_win(
    db: Session,
    *,
    campaign_id: int,
    draw_result_id: int,
    team_id: int,
    winning_number: int,
    share_amber: int,
    catalog_amber: int,
    catalog_prizes: list[dict[str, Any]],
    now: datetime,
    idempotency_key: str,
) -> dict[str, Any]:
    """Q10/R5–R7: team win → Â only; catalog→Â; equal split; remainder → team bank."""
    holder = team_holder_steam_id(team_id)
    pool = max(0, int(share_amber)) + max(0, int(catalog_amber))
    members = db.execute(
        text(
            "SELECT steam_id FROM team_members "
            "WHERE team_id = :tid AND status = 'ACTIVE' ORDER BY steam_id"
        ),
        {"tid": int(team_id)},
    ).fetchall()
    member_ids = [str(r[0]) for r in members]
    n_members = len(member_ids)
    if n_members <= 0:
        per_member = 0
        remainder = pool
    else:
        per_member = pool // n_members
        remainder = pool % n_members

    catalog_orders = [{
        "converted_to_amber": True,
        "amber_from_catalog": int(catalog_amber),
        "amber_share": int(share_amber),
        "team_prize_pool": pool,
        "per_member": per_member,
        "remainder_to_bank": remainder,
        "active_members": n_members,
        "prizes": [
            {"kind": p.get("kind"), "item_id": p.get("item_id"), "amount": p.get("amount", 1)}
            for p in (catalog_prizes or [])
        ],
    }]
    has_catalog_col = _table_has_column(db, "lottery_winners", "catalog_orders_json")
    if has_catalog_col:
        db.execute(
            text(
                "INSERT INTO lottery_winners "
                "(campaign_id, draw_result_id, steam_id, winning_number, prize_amber, "
                "share_per_match, credited, credited_at, ledger_idempotency_key, catalog_orders_json) "
                "VALUES (:cid, :did, :sid, :num, :prize, :share, 0, NULL, :idem, :cat)"
            ),
            {
                "cid": campaign_id, "did": draw_result_id, "sid": holder, "num": winning_number,
                "prize": pool, "share": share_amber, "idem": idempotency_key,
                "cat": json.dumps(catalog_orders, ensure_ascii=False),
            },
        )
    else:
        db.execute(
            text(
                "INSERT INTO lottery_winners "
                "(campaign_id, draw_result_id, steam_id, winning_number, prize_amber, "
                "share_per_match, credited, credited_at, ledger_idempotency_key) "
                "VALUES (:cid, :did, :sid, :num, :prize, :share, 0, NULL, :idem)"
            ),
            {
                "cid": campaign_id, "did": draw_result_id, "sid": holder, "num": winning_number,
                "prize": pool, "share": share_amber, "idem": idempotency_key,
            },
        )

    if _credit_fn and per_member > 0:
        for mid in member_ids:
            member_idem = f"{idempotency_key}:m:{mid}"
            _credit_fn(db, mid, per_member)
            try:
                from amber_ledger import record_lottery_prize

                record_lottery_prize(
                    db, campaign_id=campaign_id, steam_id=mid, amount=per_member,
                    winning_number=winning_number, idempotency_key=member_idem,
                )
            except Exception as exc:
                log.warning("Ledger team lottery member prize: %s", exc)

    if remainder > 0:
        try:
            from team_service import credit_team_bank_amber

            credit_team_bank_amber(
                db,
                team_id=int(team_id),
                amount=remainder,
                entry_type="LOTTERY_PRIZE_REMAINDER",
                note=f"Resto sorteio campanha {campaign_id} nº {winning_number}",
                actor_steam_id="",
                idempotency_key=f"{idempotency_key}:bank",
                commit=False,
            )
        except Exception as exc:
            log.warning("Team bank remainder credit failed team=%s: %s", team_id, exc)

    db.execute(
        text(
            "UPDATE lottery_winners SET credited = 1, credited_at = :now "
            "WHERE campaign_id = :cid AND winning_number = :num"
        ),
        {"now": now, "cid": campaign_id, "num": winning_number},
    )
    return {
        "team_id": int(team_id),
        "winning_number": int(winning_number),
        "pool": pool,
        "per_member": per_member,
        "remainder_to_bank": remainder,
        "active_members": n_members,
        "catalog_amber": int(catalog_amber),
    }


def _create_chained_campaign(db: Session, prev_row: Any, rollover_in: int) -> int | None:
    """Cria próximo sorteio em DRAFT: editável na janela de preparação; ACTIVE só após starts_at."""
    seq = _next_sequence(db)
    now = _utcnow()
    offset_h = int(prev_row.next_campaign_draw_offset_hours or 168)
    starts_at = now + timedelta(hours=CHAIN_PREP_HOURS)
    # draw sugerido: offset da campanha anterior, nunca antes de starts_at + 1h
    draw_at = now + timedelta(hours=max(offset_h, CHAIN_PREP_HOURS + 1))
    if draw_at <= starts_at:
        draw_at = starts_at + timedelta(hours=1)
    ts = _naive(now)
    catalog_json = json.dumps(_parse_prize_catalog_row(prev_row), ensure_ascii=False)
    has_pcat = _table_has_column(db, "lottery_campaigns", "prize_catalog_json")
    if has_pcat:
        db.execute(
            text(
                "INSERT INTO lottery_campaigns "
                "(sequence_number, title, status, draw_at, starts_at, winning_numbers_count, prize_amber_base, "
                "prize_amber_rollover_in, prize_amber_from_purchases, prize_catalog_json, "
                "amber_random_price, amber_reserve_price, "
                "amber_random_max_per_player, regulamento_version, allow_staff_participation, "
                "auto_chain_enabled, next_campaign_draw_offset_hours, previous_campaign_id, created_at, updated_at) "
                "VALUES (:seq, :title, 'DRAFT', :draw, :starts, :wnc, :base, :rol, 0, :pcat, :arp, :aresv, :armax, "
                ":reg, :staff, :chain, :offset, :prev, :now, :now)"
            ),
            {
                "seq": seq,
                "title": f"Sorteio ARKLAND #{seq}",
                "draw": _naive(draw_at),
                "starts": _naive(starts_at),
                "wnc": int(prev_row.winning_numbers_count or 1),
                "base": int(prev_row.prize_amber_base or 5000),
                "rol": int(rollover_in),
                "pcat": catalog_json,
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
    else:
        db.execute(
            text(
                "INSERT INTO lottery_campaigns "
                "(sequence_number, title, status, draw_at, starts_at, winning_numbers_count, prize_amber_base, "
                "prize_amber_rollover_in, prize_amber_from_purchases, amber_random_price, amber_reserve_price, "
                "amber_random_max_per_player, regulamento_version, allow_staff_participation, "
                "auto_chain_enabled, next_campaign_draw_offset_hours, previous_campaign_id, created_at, updated_at) "
                "VALUES (:seq, :title, 'DRAFT', :draw, :starts, :wnc, :base, :rol, 0, :arp, :aresv, :armax, "
                ":reg, :staff, :chain, :offset, :prev, :now, :now)"
            ),
            {
                "seq": seq,
                "title": f"Sorteio ARKLAND #{seq}",
                "draw": _naive(draw_at),
                "starts": _naive(starts_at),
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
    next_id = int(row.id) if row else None
    if next_id:
        _audit(
            db,
            "lottery_campaign_chained_draft",
            {
                "previous_campaign_id": int(prev_row.id),
                "starts_at": _iso_utc(starts_at),
                "draw_at": _iso_utc(draw_at),
                "prep_hours": CHAIN_PREP_HOURS,
            },
            campaign_id=next_id,
        )
    return next_id


def process_due_activations(db: Session) -> int:
    """Ativa campanhas DRAFT cuja starts_at já passou (janela de preparação encerrada)."""
    if not _is_enabled():
        return 0
    now = _naive(_utcnow())
    if get_active_campaign(db):
        return 0
    rows = db.execute(
        text(
            "SELECT id FROM lottery_campaigns WHERE status = 'DRAFT' "
            "AND starts_at IS NOT NULL AND starts_at <= :now "
            "ORDER BY starts_at ASC, id ASC LIMIT 5"
        ),
        {"now": now},
    ).fetchall()
    activated = 0
    for r in rows:
        cid = int(r.id)
        try:
            if get_active_campaign(db):
                break
            publish_campaign(db, cid)
            db.commit()
            activated += 1
            break  # só uma ACTIVE de cada vez
        except Exception as exc:
            db.rollback()
            log.warning("Lottery auto-activate failed campaign=%s: %s", cid, exc)
    return activated


def process_due_draws(db: Session) -> int:
    """Job periódico — ativa DRAFTs com starts_at vencido e sorteia ACTIVE com draw_at vencido."""
    if not _is_enabled():
        return 0
    processed = process_due_activations(db)
    now = _naive(_utcnow())
    rows = db.execute(
        text(
            "SELECT id FROM lottery_campaigns WHERE status = 'ACTIVE' AND draw_at <= :now"
        ),
        {"now": now},
    ).fetchall()
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
            result = run_draw(db, cid, job_id=job_id)
            db.commit()
            pending = result.get("pending_license_sync") or []
            if pending and _sync_license_permissions_fn is not None:
                seen_sync: set[tuple[str, str]] = set()
                for sid, group, days in pending:
                    key = (sid, group)
                    if key in seen_sync:
                        continue
                    seen_sync.add(key)
                    try:
                        _sync_license_permissions_fn(sid, group, days)
                    except Exception as exc:
                        log.warning("Lottery license permissions sync %s/%s: %s", sid, group, exc)
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
