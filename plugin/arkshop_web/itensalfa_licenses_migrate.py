"""Migration idempotente — catálogo de licenças ItensAlfa (Delta→Exótico).

Chamado automaticamente em `_migrate_schema` do app.py no boot.
Também usável via CLI: `python tools/migrate_itensalfa_licenses.py`

NÃO altera entitlements de jogadores existentes — só schema + metadados de tier.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

log = logging.getLogger("arkshop.itensalfa_licenses")

TIERS: list[tuple[str, int, int, str]] = [
    # (group, price, bonus, access_note)
    ("Delta", 6000, 5, "apenas Delta"),
    ("Gamma", 50000, 25, "Gama + Delta"),
    ("Beta", 75000, 50, "Beta + Gama"),
    ("Alfa", 100000, 75, "Alfa + Beta"),
    ("Omega", 115000, 90, "Omega + Alfa"),
    ("Transcendente", 130000, 105, "Transcendente + Omega"),
    ("Etereo", 150000, 120, "Etereo + Transcendente"),
    ("Universal", 165000, 135, "Universal + Etereo"),
    ("Onipotente", 180000, 150, "Onipotente + Universal"),
    ("Surreal", 195000, 165, "Surreal + Onipotente"),
    ("Imaterial", 215000, 180, "Imaterial + Surreal"),
    ("Exotico", 230000, 200, "Exotico + Imaterial"),
]

DDL_MYSQL = """
CREATE TABLE IF NOT EXISTS license_tier_catalog (
  group_name VARCHAR(32) NOT NULL PRIMARY KEY,
  price_amber INT NOT NULL,
  timed_bonus INT NOT NULL,
  access_note VARCHAR(128) NOT NULL,
  renewal_discount_pct INT NOT NULL DEFAULT 20,
  recent_discount_pct INT NOT NULL DEFAULT 10,
  recent_window_days INT NOT NULL DEFAULT 7,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS license_tier_catalog (
  group_name TEXT NOT NULL PRIMARY KEY,
  price_amber INTEGER NOT NULL,
  timed_bonus INTEGER NOT NULL,
  access_note TEXT NOT NULL,
  renewal_discount_pct INTEGER NOT NULL DEFAULT 20,
  recent_discount_pct INTEGER NOT NULL DEFAULT 10,
  recent_window_days INTEGER NOT NULL DEFAULT 7,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

ENTITLEMENTS_MYSQL = """
CREATE TABLE IF NOT EXISTS player_entitlements (
  id INT AUTO_INCREMENT PRIMARY KEY,
  steam_id VARCHAR(20) NOT NULL,
  group_name VARCHAR(32) NOT NULL,
  expires DATETIME DEFAULT NULL,
  source VARCHAR(64) DEFAULT NULL,
  notes VARCHAR(255) DEFAULT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_steam_group (steam_id, group_name),
  INDEX idx_steam_expires (steam_id, expires)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

ENTITLEMENTS_SQLITE = """
CREATE TABLE IF NOT EXISTS player_entitlements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  steam_id TEXT NOT NULL,
  group_name TEXT NOT NULL,
  expires TEXT DEFAULT NULL,
  source TEXT DEFAULT NULL,
  notes TEXT DEFAULT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(steam_id, group_name)
);
"""


def upsert_tiers(conn: Any, *, is_mysql: bool) -> int:
    """Insere/atualiza tiers em license_tier_catalog. Retorna quantidade processada."""
    n = 0
    for group, price, bonus, note in TIERS:
        if is_mysql:
            conn.execute(
                text(
                    "INSERT INTO license_tier_catalog "
                    "(group_name, price_amber, timed_bonus, access_note, "
                    "renewal_discount_pct, recent_discount_pct, recent_window_days) "
                    "VALUES (:g, :p, :b, :n, 20, 10, 7) "
                    "ON DUPLICATE KEY UPDATE "
                    "price_amber=:p, timed_bonus=:b, access_note=:n, "
                    "renewal_discount_pct=20, recent_discount_pct=10, recent_window_days=7"
                ),
                {"g": group, "p": price, "b": bonus, "n": note},
            )
        else:
            conn.execute(
                text(
                    "INSERT INTO license_tier_catalog "
                    "(group_name, price_amber, timed_bonus, access_note, "
                    "renewal_discount_pct, recent_discount_pct, recent_window_days) "
                    "VALUES (:g, :p, :b, :n, 20, 10, 7) "
                    "ON CONFLICT(group_name) DO UPDATE SET "
                    "price_amber=excluded.price_amber, "
                    "timed_bonus=excluded.timed_bonus, "
                    "access_note=excluded.access_note, "
                    "renewal_discount_pct=20, recent_discount_pct=10, recent_window_days=7"
                ),
                {"g": group, "p": price, "b": bonus, "n": note},
            )
        n += 1
    return n


def ensure_itensalfa_licenses_schema(engine: Engine) -> int:
    """Garante player_entitlements + license_tier_catalog e upsert dos tiers.

    Idempotente — safe re-run no boot. Retorna número de tiers upsertados.
    """
    url = str(engine.url).lower()
    is_mysql = "mysql" in url
    with engine.begin() as conn:
        conn.execute(text(ENTITLEMENTS_MYSQL if is_mysql else ENTITLEMENTS_SQLITE))
        conn.execute(text(DDL_MYSQL if is_mysql else DDL_SQLITE))
        n = upsert_tiers(conn, is_mysql=is_mysql)
    log.info("ItensAlfa licenses: %s tiers em license_tier_catalog (idempotente)", n)
    return n


def rcon_provision_commands() -> list[str]:
    """Comandos RCON para provisionar grupos Permissions (não executados no boot)."""
    cmds = [f"Permissions.AddGroup {group}" for group, *_ in TIERS]
    cmds.append("Permissions.AddGroup keyvault")
    return cmds
