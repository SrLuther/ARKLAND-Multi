#!/usr/bin/env python3
"""Export player points from live MySQL/MariaDB (READ-ONLY).

Preferred over tools/export_legacy_points.py — heuristic .ibd parsing is NOT
suitable for migration (uniform false-positive point values).

Resolution order for connection:
  1. CLI --database-url or host/user/password/database flags
  2. ARKSHOP_DATABASE_URL environment variable
  3. plugin/arkshop_web/settings.json
  4. %APPDATA%/ARKLAND-ServerManager/db_server_prefs.json (shop_db)

Tables queried (first match wins):
  - arkshopplayers (ArkShop legacy: SteamId BIGINT, Points INT)
  - ArkShopPlayers (case variant)
  - players (CustomShop / arkland_shop: steam_id VARCHAR, points INT)
  - store_users (new stack, if present on same MySQL)

Optional Path B: --import-ibd copies arkshopplayers.ibd into local MariaDB
datadir and runs IMPORT TABLESPACE (requires local root in db_server_prefs).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, unquote_plus, urlparse

try:
    import pymysql
except ImportError:
    pymysql = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "data" / "migration_staging"
DEFAULT_CSV = DEFAULT_OUT_DIR / "player_points_legacy.csv"
DEFAULT_JSON = DEFAULT_OUT_DIR / "player_points_mysql.json"
HEURISTIC_BAK = DEFAULT_OUT_DIR / "player_points_legacy_ibd_heuristic.csv.bak"
HEURISTIC_README = DEFAULT_OUT_DIR / "README_player_points_legacy.md"
SETTINGS_JSON = ROOT / "plugin" / "arkshop_web" / "settings.json"
ADMIN_STEAM_ID = "76561198171864983"
DEFAULT_IBD = Path(r"C:\Users\Ciano\Pictures\data\arkshop\arkshopplayers.ibd")

ARKSHOP_PLAYERS_DDL = """
CREATE TABLE IF NOT EXISTS {db}.arkshopplayers (
  Id INT NOT NULL AUTO_INCREMENT,
  SteamId BIGINT(20) UNSIGNED NOT NULL DEFAULT 0,
  Kits LONGTEXT NOT NULL,
  Points INT DEFAULT 0,
  TotalSpent INT DEFAULT 0,
  PRIMARY KEY (Id),
  UNIQUE KEY SteamId_UNIQUE (SteamId)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 ROW_FORMAT=DYNAMIC
"""


@dataclass
class DbTarget:
    host: str
    port: int
    user: str
    password: str
    database: str
    label: str = ""


@dataclass
class PlayerRow:
    steam_id: str
    points: int
    total_spent: int | None = None
    source_table: str = ""
    source_host: str = ""


@dataclass
class ExportResult:
    source: str
    target: DbTarget
    table: str
    rows: list[PlayerRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def admin(self) -> PlayerRow | None:
        for row in self.rows:
            if row.steam_id == ADMIN_STEAM_ID:
                return row
        return None

    @property
    def admin_rank(self) -> int | None:
        admin = self.admin
        if not admin:
            return None
        return 1 + sum(1 for r in self.rows if r.points > admin.points)


def _appdata_prefs() -> dict:
    appdata = os.environ.get("APPDATA", "")
    path = Path(appdata) / "ARKLAND-ServerManager" / "db_server_prefs.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _parse_database_url(url: str) -> DbTarget | None:
    url = (url or "").strip()
    if not url:
        return None
    parsed = urlparse(url.replace("mysql+pymysql://", "mysql://", 1))
    if not parsed.hostname:
        return None
    user = unquote_plus(parsed.username or "")
    password = unquote_plus(parsed.password or "")
    database = (parsed.path or "").lstrip("/").split("?")[0]
    port = parsed.port or 3306
    return DbTarget(parsed.hostname, port, user, password, database, label="database_url")


def _target_from_settings() -> DbTarget | None:
    if not SETTINGS_JSON.is_file():
        return None
    data = json.loads(SETTINGS_JSON.read_text(encoding="utf-8"))
    url = (data.get("database_url") or "").strip()
    if url:
        t = _parse_database_url(url)
        if t:
            t.label = "settings.json"
            return t
    host = (data.get("db_host") or "").strip()
    if not host:
        return None
    return DbTarget(
        host=host,
        port=int(data.get("db_port") or 3306),
        user=(data.get("db_user") or "").strip(),
        password=(data.get("db_password") or "").strip(),
        database=(data.get("db_name") or "arkland_shop").strip(),
        label="settings.json",
    )


def _targets_from_prefs() -> list[DbTarget]:
    prefs = _appdata_prefs()
    out: list[DbTarget] = []
    shop = prefs.get("shop_db") or {}
    if shop.get("host") and shop.get("user"):
        out.append(
            DbTarget(
                host=str(shop["host"]),
                port=int(shop.get("port") or 3306),
                user=str(shop["user"]),
                password=str(shop.get("password") or ""),
                database=str(shop.get("database") or "arkland_shop"),
                label="db_server_prefs.shop_db",
            )
        )
    root_pw = prefs.get("root_password", "")
    if root_pw:
        out.append(
            DbTarget(
                host="127.0.0.1",
                port=3306,
                user="root",
                password=root_pw,
                database="arkland_shop",
                label="db_server_prefs.root@local",
            )
        )
    return out


def collect_targets(args: argparse.Namespace) -> list[DbTarget]:
    seen: set[tuple] = set()
    targets: list[DbTarget] = []

    def add(t: DbTarget | None) -> None:
        if not t or not t.host or not t.user:
            return
        key = (t.host, t.port, t.user, t.database)
        if key in seen:
            return
        seen.add(key)
        targets.append(t)

    if args.database_url:
        add(_parse_database_url(args.database_url))
    if args.host and args.user:
        add(
            DbTarget(
                host=args.host,
                port=args.port,
                user=args.user,
                password=args.password or "",
                database=args.database or "arkland_shop",
                label="cli",
            )
        )

    env_url = os.environ.get("ARKSHOP_DATABASE_URL", "").strip()
    if env_url:
        t = _parse_database_url(env_url)
        if t:
            t.label = "ARKSHOP_DATABASE_URL"
            add(t)

    add(_target_from_settings())
    for t in _targets_from_prefs():
        add(t)

    # Fallback hosts for legacy arkshop DB
    bases = list(targets)
    for base in bases:
        for host in ("192.168.15.51", "127.0.0.1"):
            if host != base.host:
                add(
                    DbTarget(
                        host=host,
                        port=base.port,
                        user=base.user,
                        password=base.password,
                        database=base.database,
                        label=f"{base.label}@{host}",
                    )
                )
        for db in ("arkshop", "arkland_shop"):
            if db != base.database:
                add(
                    DbTarget(
                        host=base.host,
                        port=base.port,
                        user=base.user,
                        password=base.password,
                        database=db,
                        label=f"{base.label}:{db}",
                    )
                )
    return targets


def connect(target: DbTarget, timeout: int = 15):
    if pymysql is None:
        raise RuntimeError("pymysql não instalado — pip install pymysql")
    return pymysql.connect(
        host=target.host,
        port=target.port,
        user=target.user,
        password=target.password,
        database=target.database,
        charset="utf8mb4",
        connect_timeout=timeout,
        read_timeout=timeout,
        cursorclass=pymysql.cursors.DictCursor,
    )


def list_tables(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute("SHOW TABLES")
        rows = cur.fetchall()
    if not rows:
        return []
    key = next(iter(rows[0]))
    return [str(r[key]) for r in rows]


def query_arkshopplayers(conn, table: str, host: str) -> list[PlayerRow]:
    sql = (
        f"SELECT CAST(SteamId AS CHAR) AS steam_id, Points AS points, "
        f"TotalSpent AS total_spent FROM `{table}` WHERE Points > 0 "
        f"ORDER BY Points DESC"
    )
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    return [
        PlayerRow(
            steam_id=str(r["steam_id"]),
            points=int(r["points"]),
            total_spent=int(r["total_spent"]) if r.get("total_spent") is not None else None,
            source_table=table,
            source_host=host,
        )
        for r in rows
    ]


def query_players(conn, table: str, host: str) -> list[PlayerRow]:
    sql = (
        f"SELECT steam_id, points FROM `{table}` WHERE points > 0 "
        f"ORDER BY points DESC"
    )
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    return [
        PlayerRow(
            steam_id=str(r["steam_id"]),
            points=int(r["points"]),
            source_table=table,
            source_host=host,
        )
        for r in rows
    ]


def query_store_users(conn, table: str, host: str) -> list[PlayerRow]:
    sql = (
        f"SELECT steam_id, points FROM `{table}` WHERE points > 0 "
        f"ORDER BY points DESC"
    )
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    return [
        PlayerRow(
            steam_id=str(r["steam_id"]),
            points=int(r["points"]),
            source_table=table,
            source_host=host,
        )
        for r in rows
    ]


TABLE_QUERIES = [
    ("arkshopplayers", query_arkshopplayers),
    ("ArkShopPlayers", query_arkshopplayers),
    ("players", query_players),
    ("store_users", query_store_users),
]


def try_export_from_target(target: DbTarget, timeout: int) -> tuple[ExportResult | None, str]:
    result = ExportResult(source="", target=target, table="")
    try:
        conn = connect(target, timeout=timeout)
    except Exception as exc:
        msg = f"connect {target.host}:{target.port}/{target.database}: {exc}"
        result.errors.append(msg)
        return None, msg

    try:
        tables = {t.lower(): t for t in list_tables(conn)}
        empty_notes: list[str] = []
        for name, query_fn in TABLE_QUERIES:
            real = tables.get(name.lower())
            if not real:
                continue
            rows = query_fn(conn, real, target.host)
            if rows:
                result.source = f"mysql:{target.host}:{target.port}/{target.database}.{real}"
                result.table = real
                result.rows = rows
                return result, "ok"
            empty_notes.append(f"{real}=0 rows")
        msg = (
            f"conectou {target.host}/{target.database} mas sem pontos > 0 "
            f"({'; '.join(empty_notes) or 'sem tabelas conhecidas'}; "
            f"todas: {sorted(tables.values())})"
        )
        result.errors.append(msg)
        return None, msg
    except Exception as exc:
        msg = f"query {target.host}/{target.database}: {exc}"
        result.errors.append(msg)
        return None, msg
    finally:
        conn.close()


def mariadb_data_dir() -> Path:
    return Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager" / "mariadb_data"


def import_ibd_tablespace(ibd_path: Path, root_password: str) -> tuple[bool, str]:
    """Path B — local MariaDB IMPORT TABLESPACE (destructive on local arkshop DB only)."""
    if not ibd_path.is_file():
        return False, f"IBD não encontrado: {ibd_path}"
    data_dir = mariadb_data_dir()
    if not data_dir.is_dir():
        return False, f"datadir local ausente: {data_dir}"

    conn = pymysql.connect(
        host="127.0.0.1",
        port=3306,
        user="root",
        password=root_password,
        charset="utf8mb4",
        autocommit=True,
    )
    cur = conn.cursor()
    cur.execute("CREATE DATABASE IF NOT EXISTS arkshop CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cur.execute("DROP TABLE IF EXISTS arkshop.arkshopplayers")
    cur.execute(ARKSHOP_PLAYERS_DDL.format(db="arkshop"))
    cur.execute("ALTER TABLE arkshop.arkshopplayers DROP INDEX SteamId_UNIQUE")
    cur.execute("ALTER TABLE arkshop.arkshopplayers DISCARD TABLESPACE")

    dest_dir = data_dir / "arkshop"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_ibd = dest_dir / "arkshopplayers.ibd"
    shutil.copy2(ibd_path, dest_ibd)

    try:
        cur.execute("ALTER TABLE arkshop.arkshopplayers IMPORT TABLESPACE")
    except Exception as exc:
        conn.close()
        return False, f"IMPORT TABLESPACE falhou: {exc}"
    conn.close()
    return True, str(dest_ibd)


def backup_heuristic_csv() -> None:
    if DEFAULT_CSV.is_file() and not HEURISTIC_BAK.is_file():
        shutil.copy2(DEFAULT_CSV, HEURISTIC_BAK)


def write_readme(warning: str) -> None:
    HEURISTIC_README.write_text(
        "\n".join(
            [
                "# Player points migration staging",
                "",
                "## Fonte autoritativa",
                "",
                "Use **`tools/export_player_points_mysql.py`** — export READ-ONLY de MySQL/MariaDB.",
                "",
                "## NÃO usar para migração",
                "",
                "- `player_points_legacy_ibd_heuristic.csv.bak` — export heurístico de `.ibd`",
                "  (`tools/export_legacy_points.py`). Valores uniformes (~263–766) são **incorretos**.",
                "",
                "## Status",
                "",
                warning,
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_outputs(result: ExportResult, all_errors: list[str]) -> dict[str, Any]:
    DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)
    backup_heuristic_csv()

    with DEFAULT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["steam_id", "points", "total_spent", "source_table", "source_host"])
        for row in result.rows:
            writer.writerow(
                [row.steam_id, row.points, row.total_spent or "", row.source_table, row.source_host]
            )

    points = [r.points for r in result.rows]
    admin = result.admin
    summary: dict[str, Any] = {
        "source": result.source,
        "connection": {
            "host": result.target.host,
            "port": result.target.port,
            "database": result.target.database,
            "table": result.table,
            "label": result.target.label,
        },
        "admin_steam_id": ADMIN_STEAM_ID,
        "admin_points": admin.points if admin else None,
        "admin_rank": result.admin_rank,
        "total_users_positive": len(result.rows),
        "total_points": sum(points),
        "min_points": min(points) if points else 0,
        "max_points": max(points) if points else 0,
        "top10": [
            {"steam_id": r.steam_id, "points": r.points, "total_spent": r.total_spent}
            for r in result.rows[:10]
        ],
        "connection_errors": all_errors[-20:],
        "heuristic_backup": str(HEURISTIC_BAK) if HEURISTIC_BAK.is_file() else None,
    }
    DEFAULT_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    if result.rows:
        write_readme(
            f"Último export SQL: `{result.source}` em {len(result.rows)} jogadores, "
            f"faixa {summary['min_points']}–{summary['max_points']} pts."
        )
    else:
        write_readme(
            "Nenhum export SQL bem-sucedido nesta execução. "
            "Conecte à LAN (192.168.15.51) ou use `--import-ibd` com MariaDB local."
        )
    return summary


def print_summary(summary: dict[str, Any]) -> None:
    print("=" * 60)
    print("EXPORT PLAYER POINTS — MySQL")
    print("=" * 60)
    print(f"Fonte:     {summary.get('source') or 'NENHUMA'}")
    conn = summary.get("connection") or {}
    print(f"Host:      {conn.get('host')}:{conn.get('port')}/{conn.get('database')}")
    print(f"Tabela:    {conn.get('table')}")
    print(f"Jogadores: {summary.get('total_users_positive', 0)}")
    print(
        f"Faixa:     {summary.get('min_points')} – {summary.get('max_points')} "
        f"(soma {summary.get('total_points')})"
    )
    print(f"Admin:     {ADMIN_STEAM_ID} = {summary.get('admin_points')} pts (rank #{summary.get('admin_rank')})")
    print("\nTop 10:")
    for i, row in enumerate(summary.get("top10") or [], 1):
        print(f"  {i:2}. {row['steam_id']}: {row['points']:,}")
    if not summary.get("source"):
        print("\nErros de conexão (últimos):")
        for err in summary.get("connection_errors") or []:
            print(f"  - {err}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export player points from MySQL (READ-ONLY)")
    p.add_argument("--database-url", help="mysql+pymysql://user:pass@host:port/db")
    p.add_argument("--host")
    p.add_argument("--port", type=int, default=3306)
    p.add_argument("--user")
    p.add_argument("--password", default="")
    p.add_argument("--database", default="arkland_shop")
    p.add_argument("--timeout", type=int, default=15, help="Connection timeout seconds")
    p.add_argument("--import-ibd", nargs="?", const=str(DEFAULT_IBD), metavar="PATH",
                   help="Path B: import arkshopplayers.ibd into local MariaDB then query")
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    global DEFAULT_OUT_DIR, DEFAULT_CSV, DEFAULT_JSON, HEURISTIC_BAK, HEURISTIC_README
    DEFAULT_OUT_DIR = args.out_dir
    DEFAULT_CSV = DEFAULT_OUT_DIR / "player_points_legacy.csv"
    DEFAULT_JSON = DEFAULT_OUT_DIR / "player_points_mysql.json"
    HEURISTIC_BAK = DEFAULT_OUT_DIR / "player_points_legacy_ibd_heuristic.csv.bak"
    HEURISTIC_README = DEFAULT_OUT_DIR / "README_player_points_legacy.md"

    all_errors: list[str] = []
    result = ExportResult(source="", target=DbTarget("", 0, "", "", ""), table="")

    if args.import_ibd:
        prefs = _appdata_prefs()
        root_pw = prefs.get("root_password", "")
        if not root_pw:
            print("ERRO: --import-ibd requer root_password em db_server_prefs.json", file=sys.stderr)
            return 2
        ok, msg = import_ibd_tablespace(Path(args.import_ibd), root_pw)
        print(f"import-ibd: {'OK' if ok else 'FALHOU'} — {msg}")
        if ok:
            local = DbTarget("127.0.0.1", 3306, "root", root_pw, "arkshop", "import-ibd")
            got, note = try_export_from_target(local, args.timeout)
            if got:
                result = got
            else:
                all_errors.append(note)

    if not result.rows:
        for target in collect_targets(args):
            got, note = try_export_from_target(target, args.timeout)
            if got and got.rows:
                result = got
                break
            all_errors.append(f"{target.label}: {note}")

    summary = write_outputs(result, all_errors)
    print_summary(summary)
    return 0 if result.rows else 1


if __name__ == "__main__":
    sys.exit(main())
