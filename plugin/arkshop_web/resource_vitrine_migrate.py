"""Migração (idempotente) das tabelas da Vitrine de Recursos.

Tabelas definidas com SQLAlchemy Core (MetaData própria — não toca ``app.Base``) e criadas com
``create_all(checkfirst)`` em SQLite e MySQL. Chamado ao final de ``market_migrate.ensure_market_schema``.

Limites MySQL (utf8mb4 = 4 bytes/char): colunas em índices únicos ficam em VARCHAR ≤ 191
(``blueprint_key``) e chaves compostas bem abaixo de 3072 bytes.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    inspect,
    text,
)

log = logging.getLogger("arkshop.resource_vitrine_migrate")

RESOURCE_VITRINE_SCHEMA_VERSION = "1.0.0"

metadata = MetaData()

_MYSQL = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}

resource_catalog = Table(
    "market_resource_catalog",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("blueprint_key", String(191), nullable=False),
    Column("blueprint", String(255), nullable=False),
    Column("name", String(80), nullable=False),
    Column("stack_size", Integer, nullable=False, default=100),
    Column("min_lot_price", Integer, nullable=True),
    Column("max_lot_price", Integer, nullable=True),
    Column("enabled", Integer, nullable=False, default=1),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
    UniqueConstraint("blueprint_key", name="uq_mrc_blueprint_key"),
    **_MYSQL,
)

resource_settings = Table(
    "market_resource_settings",
    metadata,
    Column("setting_key", String(64), primary_key=True),
    Column("setting_value", String(255), nullable=False),
    Column("updated_at", DateTime, nullable=False),
    **_MYSQL,
)

resource_stock = Table(
    "market_resource_stock",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("steam_id", String(32), nullable=False),
    Column("resource_id", Integer, nullable=False),
    Column("quantity", Integer, nullable=False, default=0),
    Column("lot_size", Integer, nullable=True),
    Column("lot_price", Integer, nullable=True),
    Column("active", Integer, nullable=False, default=0),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
    UniqueConstraint("steam_id", "resource_id", name="uq_mrs_owner_resource"),
    Index("ix_mrs_resource", "resource_id"),
    **_MYSQL,
)

resource_uploads = Table(
    "market_resource_uploads",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("upload_id", String(64), nullable=False),
    Column("steam_id", String(32), nullable=False),
    Column("status", String(16), nullable=False),
    Column("lines_json", Text, nullable=True),
    Column("total_quantity", Integer, nullable=False, default=0),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
    UniqueConstraint("upload_id", name="uq_mru_upload_id"),
    Index("ix_mru_steam", "steam_id"),
    **_MYSQL,
)

resource_claims = Table(
    "market_resource_claims",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("kind", String(16), nullable=False),
    Column("recipient_steam_id", String(32), nullable=False),
    Column("seller_steam_id", String(32), nullable=True),
    Column("resource_id", Integer, nullable=False),
    Column("blueprint", String(255), nullable=False),
    Column("resource_name", String(80), nullable=False),
    Column("stack_size", Integer, nullable=False, default=100),
    Column("quantity", Integer, nullable=False),
    Column("tx_id", Integer, nullable=True),
    Column("status", String(16), nullable=False, default="PENDENTE"),
    Column("request_id", String(64), nullable=True),
    Column("claim_reserved_at", DateTime, nullable=False),
    Column("claim_expires_at", DateTime, nullable=False),
    Column("claimed_at", DateTime, nullable=True),
    Column("delivered_at", DateTime, nullable=True),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
    UniqueConstraint("recipient_steam_id", "request_id", name="uq_mrcl_recipient_request"),
    Index("ix_mrcl_recipient_status", "recipient_steam_id", "status"),
    Index("ix_mrcl_expires", "claim_expires_at"),
    **_MYSQL,
)

resource_transactions = Table(
    "market_resource_transactions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("request_id", String(64), nullable=True),
    Column("stock_id", Integer, nullable=False),
    Column("resource_id", Integer, nullable=False),
    Column("seller_steam_id", String(32), nullable=False),
    Column("buyer_steam_id", String(32), nullable=False),
    Column("blueprint", String(255), nullable=False),
    Column("resource_name", String(80), nullable=False),
    Column("lots", Integer, nullable=False),
    Column("lot_size", Integer, nullable=False),
    Column("lot_price", Integer, nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("price_paid", Integer, nullable=False),
    Column("fee_amount", Integer, nullable=False, default=0),
    Column("seller_credit", Integer, nullable=False, default=0),
    Column("buyer_points_before", Integer, nullable=True),
    Column("buyer_points_after", Integer, nullable=True),
    Column("seller_points_before", Integer, nullable=True),
    Column("seller_points_after", Integer, nullable=True),
    Column("status", String(16), nullable=False, default="COMPLETED"),
    Column("refund_amount", Integer, nullable=True),
    Column("seller_reversal", Integer, nullable=True),
    Column("refunded_at", DateTime, nullable=True),
    Column("market_trace_id", String(64), nullable=True),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("buyer_steam_id", "request_id", name="uq_mrt_buyer_request"),
    Index("ix_mrt_seller", "seller_steam_id"),
    Index("ix_mrt_buyer", "buyer_steam_id"),
    **_MYSQL,
)

RESOURCE_VITRINE_TABLES: tuple[str, ...] = tuple(
    t.name
    for t in (
        resource_catalog,
        resource_settings,
        resource_stock,
        resource_uploads,
        resource_claims,
        resource_transactions,
    )
)


def _existing_tables(engine: Any) -> set[str]:
    try:
        return set(inspect(engine).get_table_names())
    except Exception:
        return set()


def ensure_resource_vitrine_schema(engine: Any) -> dict[str, Any]:
    """Cria as tabelas da Vitrine de Recursos (idempotente) e grava a versão do schema."""
    before = _existing_tables(engine)
    metadata.create_all(bind=engine, checkfirst=True)
    after = _existing_tables(engine)
    created = [t for t in RESOURCE_VITRINE_TABLES if t not in before and t in after]
    missing = [t for t in RESOURCE_VITRINE_TABLES if t not in after]
    result: dict[str, Any] = {
        "schema_version": RESOURCE_VITRINE_SCHEMA_VERSION,
        "created_tables": created,
        "still_missing": missing,
        "ok": not missing,
    }
    if missing:
        log.error("Vitrine de Recursos: tabelas ausentes após migrate: %s", missing)
        return result
    try:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT setting_value FROM market_resource_settings WHERE setting_key = 'schema_version'")
            ).fetchone()
            if row is None:
                conn.execute(
                    resource_settings.insert().values(
                        setting_key="schema_version",
                        setting_value=RESOURCE_VITRINE_SCHEMA_VERSION,
                        updated_at=now,
                    )
                )
            elif str(row[0]) != RESOURCE_VITRINE_SCHEMA_VERSION:
                conn.execute(
                    resource_settings.update()
                    .where(resource_settings.c.setting_key == "schema_version")
                    .values(setting_value=RESOURCE_VITRINE_SCHEMA_VERSION, updated_at=now)
                )
    except Exception as exc:  # pragma: no cover - versão é informativa
        log.warning("Vitrine de Recursos: não gravou schema_version: %s", exc)
    if created:
        log.info("Vitrine de Recursos: schema v%s — tabelas criadas: %s", RESOURCE_VITRINE_SCHEMA_VERSION, created)
    return result


def schema_status(engine: Any) -> dict[str, Any]:
    existing = _existing_tables(engine)
    return {
        "schema_version": RESOURCE_VITRINE_SCHEMA_VERSION,
        "tables": {name: name in existing for name in RESOURCE_VITRINE_TABLES},
        "ok": all(name in existing for name in RESOURCE_VITRINE_TABLES),
    }
