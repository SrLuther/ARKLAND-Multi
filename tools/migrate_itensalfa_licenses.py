#!/usr/bin/env python3
"""Migration idempotente — grupos de licença ItensAlfa (Delta→Exótico).

O que faz:
  1. Garante schema `player_entitlements` (MySQL ou SQLite via SQLAlchemy URL)
  2. Registra/atualiza linhas de catálogo de referência em tabela opcional
     `license_tier_catalog` (criada se não existir) — útil para admin/auditoria
  3. Imprime comandos RCON `Permissions.AddGroup` para provisionar no plugin Permissions

NÃO altera entitlements de jogadores existentes (só adiciona metadados de tier).

No boot do arkshop_web a mesma lógica corre via
`itensalfa_licenses_migrate.ensure_itensalfa_licenses_schema` em `_migrate_schema`.

Uso:
  set ARKSHOP_DATABASE_URL=mysql+pymysql://user:pass@127.0.0.1:3306/arkland_shop
  python tools/migrate_itensalfa_licenses.py
  python tools/migrate_itensalfa_licenses.py --dry-run
  python tools/migrate_itensalfa_licenses.py --print-rcon-only

SQL de referência: plugin/arkshop_web/migrations/itensalfa_licenses.sql
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin" / "arkshop_web"))

from itensalfa_licenses_migrate import (  # noqa: E402
    TIERS,
    ensure_itensalfa_licenses_schema,
    rcon_provision_commands,
)


def print_rcon() -> None:
    print("# Provisionar grupos no Permissions (RCON, um por linha):")
    for cmd in rcon_provision_commands():
        print(cmd)
    print("# Depois: Shop.Reload nos mapas / Sync TEK / Provisionar grupos na UI da Loja")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--print-rcon-only", action="store_true")
    ap.add_argument(
        "--database-url",
        default=os.environ.get("ARKSHOP_DATABASE_URL", ""),
        help="SQLAlchemy URL (default: env ARKSHOP_DATABASE_URL)",
    )
    args = ap.parse_args()

    print_rcon()
    if args.print_rcon_only:
        return 0

    url = (args.database_url or "").strip()
    if not url:
        print(
            "\n[aviso] Sem ARKSHOP_DATABASE_URL — só imprimiu RCON. "
            "Para gravar license_tier_catalog, defina a URL e rode de novo "
            "(ou reinicie o arkshop_web — a migration corre no boot)."
        )
        print("SQL de referência:", ROOT / "plugin" / "arkshop_web" / "migrations" / "itensalfa_licenses.sql")
        return 0

    if args.dry_run:
        print(f"\nDry-run: conectaria em {url!r} e faria upsert de {len(TIERS)} tiers.")
        return 0

    from sqlalchemy import create_engine

    engine = create_engine(url, pool_pre_ping=True)
    n = ensure_itensalfa_licenses_schema(engine)
    print(f"\nOK: {n} tiers em license_tier_catalog (idempotente).")
    print("Próximo: rodar Permissions.AddGroup (acima) ou botão Provisionar grupos na Loja.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
