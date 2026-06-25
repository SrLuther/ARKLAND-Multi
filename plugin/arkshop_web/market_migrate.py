"""Migração automática do schema do Mercado de Dinos (boot do arkshop_web)."""
from __future__ import annotations

import logging
import os
from typing import Any

from sqlalchemy import inspect, text

log = logging.getLogger("arkshop.market_migrate")

MARKET_SCHEMA_VERSION = "1.2.0"

MARKET_TABLES: tuple[str, ...] = (
    "market_species",
    "market_species_stat_multipliers",
    "market_species_aliases",
    "market_player_profile",
    "market_cryopod_vault",
    "market_listings",
    "market_transactions",
    "market_claims",
    "market_audit_events",
)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _is_mysql(engine: Any) -> bool:
    return "mysql" in str(engine.url).lower()


def _existing_tables(engine: Any) -> set[str]:
    insp = inspect(engine)
    try:
        return set(insp.get_table_names())
    except Exception:
        return set()


def _ensure_listing_presentation_columns(engine: Any) -> None:
    """Adiciona custom_name, category e custom_description em market_listings (idempotente)."""
    if "market_listings" not in _existing_tables(engine):
        return
    is_mysql = _is_mysql(engine)
    with engine.connect() as conn:
        insp = inspect(engine)
        cols = {c["name"] for c in insp.get_columns("market_listings")}
        alters: list[str] = []
        if "custom_name" not in cols:
            alters.append(
                "ADD COLUMN `custom_name` VARCHAR(80) NULL"
                if is_mysql
                else "ADD COLUMN custom_name VARCHAR(80)"
            )
        if "category" not in cols:
            alters.append(
                "ADD COLUMN `category` VARCHAR(16) NULL"
                if is_mysql
                else "ADD COLUMN category VARCHAR(16)"
            )
        if "custom_description" not in cols:
            alters.append(
                "ADD COLUMN `custom_description` VARCHAR(300) NULL"
                if is_mysql
                else "ADD COLUMN custom_description VARCHAR(300)"
            )
        for fragment in alters:
            conn.execute(text(f"ALTER TABLE market_listings {fragment}"))
        if alters:
            conn.commit()
            log.info("Mercado: colunas de personalização de anúncio adicionadas em market_listings")


def _ensure_claim_reservation_columns(engine: Any) -> None:
    """Adiciona claim_reserved_at, claim_expires_at e claim_status em market_claims (idempotente)."""
    if "market_claims" not in _existing_tables(engine):
        return
    is_mysql = _is_mysql(engine)
    with engine.connect() as conn:
        insp = inspect(engine)
        cols = {c["name"] for c in insp.get_columns("market_claims")}
        alters: list[str] = []
        if "claim_reserved_at" not in cols:
            alters.append(
                "ADD COLUMN `claim_reserved_at` DATETIME NULL"
                if is_mysql
                else "ADD COLUMN claim_reserved_at DATETIME"
            )
        if "claim_expires_at" not in cols:
            alters.append(
                "ADD COLUMN `claim_expires_at` DATETIME NULL"
                if is_mysql
                else "ADD COLUMN claim_expires_at DATETIME"
            )
        if "claim_status" not in cols:
            alters.append(
                "ADD COLUMN `claim_status` VARCHAR(32) NULL"
                if is_mysql
                else "ADD COLUMN claim_status VARCHAR(32)"
            )
        for fragment in alters:
            conn.execute(text(f"ALTER TABLE market_claims {fragment}"))
        if alters:
            conn.commit()
            log.info("Mercado: colunas de reserva de claim adicionadas em market_claims")

        # Backfill: claims PENDENTE/CLAIMED sem expiração ganham janela de 24h a partir de created_at
        if is_mysql:
            conn.execute(
                text(
                    "UPDATE market_claims SET "
                    "claim_reserved_at = COALESCE(claim_reserved_at, created_at), "
                    "claim_expires_at = COALESCE(claim_expires_at, DATE_ADD(created_at, INTERVAL 24 HOUR)), "
                    "claim_status = COALESCE(claim_status, 'pending') "
                    "WHERE status IN ('PENDENTE', 'CLAIMED') "
                    "AND (claim_expires_at IS NULL OR claim_status IS NULL)"
                )
            )
        else:
            conn.execute(
                text(
                    "UPDATE market_claims SET "
                    "claim_reserved_at = COALESCE(claim_reserved_at, created_at), "
                    "claim_expires_at = COALESCE(claim_expires_at, datetime(created_at, '+24 hours')), "
                    "claim_status = COALESCE(claim_status, 'pending') "
                    "WHERE status IN ('PENDENTE', 'CLAIMED') "
                    "AND (claim_expires_at IS NULL OR claim_status IS NULL)"
                )
            )
        conn.commit()


def _ensure_mysql_mediumblob(engine: Any) -> None:
    if not _is_mysql(engine):
        return
    with engine.connect() as conn:
        row = conn.execute(
            text("SHOW TABLES LIKE 'market_cryopod_vault'")
        ).fetchone()
        if not row:
            return
        col = conn.execute(
            text("SHOW COLUMNS FROM `market_cryopod_vault` LIKE 'item_blob'")
        ).fetchone()
        if col is None:
            return
        col_type = str(col[1]).lower() if len(col) > 1 else ""
        if "mediumblob" in col_type or "longblob" in col_type:
            return
        log.warning(
            "market_cryopod_vault.item_blob tipo %s — alterando para MEDIUMBLOB",
            col_type,
        )
        conn.execute(
            text(
                "ALTER TABLE `market_cryopod_vault` "
                "MODIFY COLUMN `item_blob` MEDIUMBLOB NOT NULL"
            )
        )
        conn.commit()


def _maybe_bootstrap_catalog(engine: Any) -> dict[str, Any] | None:
    """Sync inicial do catálogo quando não há espécies (opcional via env)."""
    if not _env_flag("MARKET_AUTO_SYNC_CATALOG", default=False):
        return None
    if "market_species" not in _existing_tables(engine):
        return None

    from app import MarketSpecies

    session_factory = None
    read_config = None
    try:
        import app as app_module

        session_factory = app_module._SessionLocal
        read_config = app_module._read_shop_config
    except Exception:
        return None

    if session_factory is None:
        return None

    db = session_factory()
    try:
        count = db.query(MarketSpecies).count()
        if count > 0:
            return {"skipped": True, "reason": "species_already_present", "count": count}
        from market_service import sync_catalog_to_db

        catalog = read_config() if read_config else {}
        result = sync_catalog_to_db(db, catalog, activate=_env_flag("MARKET_AUTO_ACTIVATE_SPECIES"))
        log.info(
            "MARKET bootstrap sync: created=%s updated=%s",
            result.get("created"),
            result.get("updated"),
        )
        return result
    except Exception as exc:
        log.warning("MARKET bootstrap sync falhou: %s", exc)
        return {"error": str(exc)}
    finally:
        db.close()


def ensure_market_schema(engine: Any, *, bootstrap: bool = True) -> dict[str, Any]:
    """
    Cria/atualiza tabelas do mercado via SQLAlchemy (idempotente).
    Chamado em todo boot após _migrate_schema base.
    """
    from app import Base

    before = _existing_tables(engine)
    missing_before = [t for t in MARKET_TABLES if t not in before]

    market_tables = [Base.metadata.tables[name] for name in MARKET_TABLES if name in Base.metadata.tables]
    if market_tables:
        Base.metadata.create_all(bind=engine, tables=market_tables)

    _ensure_mysql_mediumblob(engine)
    _ensure_claim_reservation_columns(engine)
    _ensure_listing_presentation_columns(engine)

    after = _existing_tables(engine)
    still_missing = [t for t in MARKET_TABLES if t not in after]

    result: dict[str, Any] = {
        "schema_version": MARKET_SCHEMA_VERSION,
        "created_tables": [t for t in MARKET_TABLES if t not in before and t in after],
        "missing_before": missing_before,
        "still_missing": still_missing,
        "ok": len(still_missing) == 0,
    }

    if still_missing:
        log.error("Mercado: tabelas ausentes após migrate: %s", still_missing)
    elif missing_before:
        log.info(
            "Mercado: schema v%s — tabelas criadas: %s",
            MARKET_SCHEMA_VERSION,
            result["created_tables"],
        )
    else:
        log.debug("Mercado: schema v%s OK", MARKET_SCHEMA_VERSION)

    if bootstrap and result["ok"]:
        boot = _maybe_bootstrap_catalog(engine)
        if boot:
            result["bootstrap"] = boot

    return result


def schema_status(engine: Any) -> dict[str, Any]:
    """Estado do schema para diagnóstico (admin / health)."""
    existing = _existing_tables(engine)
    return {
        "schema_version": MARKET_SCHEMA_VERSION,
        "tables": {name: name in existing for name in MARKET_TABLES},
        "ok": all(name in existing for name in MARKET_TABLES),
        "auto_sync_catalog": _env_flag("MARKET_AUTO_SYNC_CATALOG"),
        "auto_activate_species": _env_flag("MARKET_AUTO_ACTIVATE_SPECIES"),
    }
