#!/usr/bin/env python3
"""Export legacy players: steam_id, points, groups (READ-ONLY).

Joins ArkShop points (arkshopplayers / players) with VIP tiers and permission
groups from vip_players, player_entitlements, and/or ark_permission.players.

Run on ArkServerII (127.0.0.1) where MySQL is reachable:

  python tools/export_legacy_players_vip.py \\
    --host 127.0.0.1 --user arkshop --password PROMPT \\
    --database arkshop --permissions-database ark_permission

Password via env (recommended): ARKSHOP_MYSQL_PASSWORD=... python ...
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote_plus, urlparse

try:
    import pymysql
except ImportError:
    pymysql = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "migration_staging" / "legacy_players_vip.csv"
DEFAULT_JSON = ROOT / "data" / "migration_staging" / "legacy_players_vip.json"

STEAM_COL_CANDIDATES = ("steam_id", "steamid", "SteamId", "SteamID")
GROUP_COL_CANDIDATES = (
    "PermissionGroups",
    "permissiongroups",
    "GroupName",
    "groupname",
    "group_name",
    "tier",
    "Tier",
    "VipLevel",
    "viplevel",
    "groups",
    "Groups",
)
EXPIRES_COL_CANDIDATES = ("expires", "Expires", "expire_date", "ExpireDate")
NOTES_SKIP_GROUPS = frozenset({"", "default"})


@dataclass
class DbTarget:
    host: str
    port: int
    user: str
    password: str
    database: str


@dataclass
class ColumnMap:
    steam: str
    points: str | None = None
    groups: str | None = None
    expires: str | None = None


@dataclass
class ExportMeta:
    points_table: str = ""
    points_database: str = ""
    group_sources: list[str] = field(default_factory=list)
    total_rows: int = 0
    rows_with_groups: int = 0
    rows_with_points: int = 0
    errors: list[str] = field(default_factory=list)


def _parse_database_url(url: str) -> DbTarget | None:
    url = (url or "").strip()
    if not url:
        return None
    parsed = urlparse(url.replace("mysql+pymysql://", "mysql://", 1))
    if not parsed.hostname:
        return None
    database = (parsed.path or "").lstrip("/").split("?")[0]
    return DbTarget(
        host=parsed.hostname,
        port=parsed.port or 3306,
        user=unquote_plus(parsed.username or ""),
        password=unquote_plus(parsed.password or ""),
        database=database or "arkshop",
    )


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


def list_tables(conn) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute("SHOW TABLES")
        rows = cur.fetchall()
    if not rows:
        return {}
    key = next(iter(rows[0]))
    return {str(r[key]).lower(): str(r[key]) for r in rows}


def table_columns(conn, table: str) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute(f"SHOW COLUMNS FROM `{table}`")
        rows = cur.fetchall()
    return {str(r["Field"]).lower(): str(r["Field"]) for r in rows}


def pick_column(cols: dict[str, str], candidates: tuple[str, ...]) -> str | None:
    for name in candidates:
        if name.lower() in cols:
            return cols[name.lower()]
    return None


def normalize_steam_id(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if not s or s == "0":
        return ""
    if "." in s:
        s = s.split(".", 1)[0]
    return s


def split_groups(raw: Any) -> list[str]:
    if raw is None:
        return []
    text = str(raw).strip()
    if not text:
        return []
    parts: list[str] = []
    for chunk in text.replace(";", ",").split(","):
        g = chunk.strip()
        if g and g.lower() not in NOTES_SKIP_GROUPS:
            parts.append(g)
    return parts


def detect_points_table(conn) -> tuple[str, ColumnMap] | None:
    tables = list_tables(conn)
    specs = [
        ("arkshopplayers", ("SteamId", "steam_id"), "Points", None),
        ("arkshopplayers", ("SteamId",), "Points", None),
        ("players", ("steam_id", "SteamId"), "points", "Points"),
    ]
    for table_key, steam_candidates, *rest in specs:
        real = tables.get(table_key)
        if not real:
            continue
        cols = table_columns(conn, real)
        steam = pick_column(cols, steam_candidates)
        points = pick_column(cols, ("points", "Points"))
        if steam and points:
            return real, ColumnMap(steam=steam, points=points)
    return None


def detect_group_table(conn, table_keys: tuple[str, ...]) -> tuple[str, ColumnMap] | None:
    tables = list_tables(conn)
    for key in table_keys:
        real = tables.get(key.lower())
        if not real:
            continue
        cols = table_columns(conn, real)
        steam = pick_column(cols, STEAM_COL_CANDIDATES)
        groups = pick_column(cols, GROUP_COL_CANDIDATES)
        if not steam:
            continue
        expires = pick_column(cols, EXPIRES_COL_CANDIDATES)
        if groups:
            return real, ColumnMap(steam=steam, groups=groups, expires=expires)
    return None


def fetch_points(conn, table: str, cmap: ColumnMap) -> dict[str, int]:
    sql = (
        f"SELECT CAST(`{cmap.steam}` AS CHAR) AS sid, `{cmap.points}` AS pts "
        f"FROM `{table}` WHERE `{cmap.steam}` IS NOT NULL AND `{cmap.steam}` != 0"
    )
    out: dict[str, int] = {}
    with conn.cursor() as cur:
        cur.execute(sql)
        for row in cur.fetchall():
            sid = normalize_steam_id(row["sid"])
            if not sid:
                continue
            try:
                pts = int(row["pts"] or 0)
            except (TypeError, ValueError):
                pts = 0
            out[sid] = pts
    return out


def fetch_groups(conn, table: str, cmap: ColumnMap, label: str) -> dict[str, set[str]]:
    where = f"WHERE `{cmap.steam}` IS NOT NULL AND `{cmap.steam}` != ''"
    if cmap.expires:
        where += f" AND (`{cmap.expires}` IS NULL OR `{cmap.expires}` > NOW())"
    sql = (
        f"SELECT CAST(`{cmap.steam}` AS CHAR) AS sid, `{cmap.groups}` AS grp "
        f"FROM `{table}` {where}"
    )
    out: dict[str, set[str]] = defaultdict(set)
    with conn.cursor() as cur:
        cur.execute(sql)
        for row in cur.fetchall():
            sid = normalize_steam_id(row["sid"])
            if not sid:
                continue
            for g in split_groups(row.get("grp")):
                out[sid].add(g)
    return dict(out)


def fetch_entitlements(conn, table: str, cmap: ColumnMap) -> dict[str, set[str]]:
    """player_entitlements: one row per group — aggregate with GROUP_CONCAT logic in Python."""
    where = f"WHERE `{cmap.steam}` IS NOT NULL AND `{cmap.steam}` != ''"
    if cmap.expires:
        where += f" AND (`{cmap.expires}` IS NULL OR `{cmap.expires}` > NOW())"
    sql = (
        f"SELECT CAST(`{cmap.steam}` AS CHAR) AS sid, `{cmap.groups}` AS grp "
        f"FROM `{table}` {where}"
    )
    out: dict[str, set[str]] = defaultdict(set)
    with conn.cursor() as cur:
        cur.execute(sql)
        for row in cur.fetchall():
            sid = normalize_steam_id(row["sid"])
            if not sid:
                continue
            g = str(row.get("grp") or "").strip()
            if g and g.lower() not in NOTES_SKIP_GROUPS:
                out[sid].add(g)
    return dict(out)


def merge_group_maps(*maps: dict[str, set[str]]) -> dict[str, set[str]]:
    merged: dict[str, set[str]] = defaultdict(set)
    for m in maps:
        for sid, groups in m.items():
            merged[sid].update(groups)
    return dict(merged)


def build_rows(
    points: dict[str, int],
    groups: dict[str, set[str]],
) -> list[tuple[str, int, str]]:
    all_ids = set(points) | set(groups)
    rows: list[tuple[str, int, str]] = []
    for sid in sorted(all_ids, key=lambda x: (-points.get(x, 0), x)):
        grp_list = sorted(groups.get(sid, set()), key=str.lower)
        rows.append((sid, points.get(sid, 0), ",".join(grp_list)))
    return rows


def write_csv(path: Path, rows: list[tuple[str, int, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["steam_id", "points", "groups"])
        for sid, pts, grps in rows:
            writer.writerow([sid, pts, grps])


def run_export(
    shop_target: DbTarget,
    perm_target: DbTarget | None,
    timeout: int,
) -> tuple[list[tuple[str, int, str]], ExportMeta]:
    meta = ExportMeta()
    shop_conn = connect(shop_target, timeout=timeout)
    try:
        detected = detect_points_table(shop_conn)
        if not detected:
            meta.errors.append(
                f"Nenhuma tabela de pontos em {shop_target.database} "
                f"(esperado arkshopplayers ou players)"
            )
            return [], meta

        points_table, points_map = detected
        meta.points_table = points_table
        meta.points_database = shop_target.database
        points = fetch_points(shop_conn, points_table, points_map)

        group_maps: list[dict[str, set[str]]] = []
        group_specs = [
            (("vip_players",), "vip_players"),
            (("player_entitlements",), "player_entitlements"),
        ]
        for table_keys, label in group_specs:
            hit = detect_group_table(shop_conn, table_keys)
            if not hit:
                continue
            table, cmap = hit
            if label == "player_entitlements":
                gm = fetch_entitlements(shop_conn, table, cmap)
            else:
                gm = fetch_groups(shop_conn, table, cmap, label)
            if gm:
                meta.group_sources.append(f"{shop_target.database}.{table}")
                group_maps.append(gm)

        if perm_target and perm_target.database != shop_target.database:
            perm_conn = connect(perm_target, timeout=timeout)
            try:
                hit = detect_group_table(
                    perm_conn,
                    ("players", "arkpplayers", "ArkPPlayers"),
                )
                if hit:
                    table, cmap = hit
                    gm = fetch_groups(perm_conn, table, cmap, "permissions")
                    if gm:
                        meta.group_sources.append(f"{perm_target.database}.{table}")
                        group_maps.append(gm)
                else:
                    meta.errors.append(
                        f"Sem coluna de grupos em {perm_target.database}.players "
                        f"(esperado PermissionGroups ou GroupName)"
                    )
            finally:
                perm_conn.close()
        else:
            hit = detect_group_table(shop_conn, ("players", "arkpplayers"))
            if hit:
                table, cmap = hit
                if cmap.groups and cmap.groups.lower() not in ("points",):
                    gm = fetch_groups(shop_conn, table, cmap, "permissions_inline")
                    if gm:
                        meta.group_sources.append(f"{shop_target.database}.{table}")
                        group_maps.append(gm)

        merged_groups = merge_group_maps(*group_maps) if group_maps else {}
        rows = build_rows(points, merged_groups)
        meta.total_rows = len(rows)
        meta.rows_with_points = sum(1 for _, p, _ in rows if p > 0)
        meta.rows_with_groups = sum(1 for _, _, g in rows if g)
        return rows, meta
    finally:
        shop_conn.close()


def print_schema_help() -> None:
    print(
        """
Schema legado típico (ArkServerII / ASE):

  arkshop.arkshopplayers
    Id, SteamId BIGINT, Kits LONGTEXT, Points INT, TotalSpent INT

  arkshop.vip_players  (CustomShop — pode estar vazio no legado puro)
    steam_id VARCHAR(20) PK, expires DATETIME, tier VARCHAR(32), notes

  arkland_shop.player_entitlements  (stack novo)
    steam_id, group_name, expires, source, notes

  ark_permission.players  (Permissions.dll 2.x)
    Id, SteamId BIGINT, PermissionGroups VARCHAR (ex: "Default,VIP,Admin")
    TimedPermissionGroups VARCHAR (grupos temporários)

  ark_permission.permissiongroups
    definições de grupos (não lista jogadores)

Descobrir colunas no servidor:

  USE arkshop;
  SHOW TABLES;
  SHOW COLUMNS FROM arkshopplayers;
  SHOW COLUMNS FROM vip_players;
  SHOW COLUMNS FROM players;

  USE ark_permission;
  SHOW COLUMNS FROM players;
  SHOW COLUMNS FROM permissiongroups;
  SELECT SteamId, PermissionGroups FROM players LIMIT 5;
"""
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Export CSV steam_id, points, groups from legacy MySQL"
    )
    p.add_argument("--database-url", help="mysql+pymysql://user:pass@host:port/db")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=3306)
    p.add_argument("--user", default="arkshop")
    p.add_argument(
        "--password",
        default="",
        help="Prefer ARKSHOP_MYSQL_PASSWORD env var instead of CLI",
    )
    p.add_argument("--database", default="arkshop", help="DB with arkshopplayers")
    p.add_argument(
        "--permissions-database",
        default="ark_permission",
        help="DB with Permissions players table (empty to skip separate DB)",
    )
    p.add_argument("--timeout", type=int, default=15)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    p.add_argument("--schema-help", action="store_true", help="Print schema notes and exit")
    return p.parse_args()


def resolve_shop_target(args: argparse.Namespace) -> DbTarget:
    if args.database_url:
        t = _parse_database_url(args.database_url)
        if t:
            return t
    password = args.password or os.environ.get("ARKSHOP_MYSQL_PASSWORD", "")
    return DbTarget(
        host=args.host,
        port=args.port,
        user=args.user,
        password=password,
        database=args.database,
    )


def main() -> int:
    args = parse_args()
    if args.schema_help:
        print_schema_help()
        return 0

    shop = resolve_shop_target(args)
    if not shop.password:
        print(
            "AVISO: senha vazia — use --password ou ARKSHOP_MYSQL_PASSWORD",
            file=sys.stderr,
        )

    perm: DbTarget | None = None
    if args.permissions_database.strip():
        perm = DbTarget(
            host=shop.host,
            port=shop.port,
            user=shop.user,
            password=shop.password,
            database=args.permissions_database.strip(),
        )

    try:
        rows, meta = run_export(shop, perm, args.timeout)
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2

    if not rows:
        print("Nenhuma linha exportada.", file=sys.stderr)
        for err in meta.errors:
            print(f"  - {err}", file=sys.stderr)
        print_schema_help()
        return 1

    write_csv(args.out, rows)
    summary = {
        "output_csv": str(args.out),
        "connection": {
            "host": shop.host,
            "port": shop.port,
            "database": shop.database,
            "permissions_database": perm.database if perm else None,
        },
        "points_table": f"{meta.points_database}.{meta.points_table}",
        "group_sources": meta.group_sources,
        "total_rows": meta.total_rows,
        "rows_with_points_gt_0": meta.rows_with_points,
        "rows_with_groups": meta.rows_with_groups,
        "errors": meta.errors,
        "sample_vip": [
            {"steam_id": sid, "points": pts, "groups": grps}
            for sid, pts, grps in rows
            if grps
        ][:15],
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("=" * 60)
    print("EXPORT LEGACY PLAYERS + VIP GROUPS")
    print("=" * 60)
    print(f"Host:      {shop.host}:{shop.port}/{shop.database}")
    if perm:
        print(f"Perm DB:   {perm.database}")
    print(f"Pontos:    {meta.points_database}.{meta.points_table}")
    print(f"Grupos:    {', '.join(meta.group_sources) or 'nenhuma fonte'}")
    print(f"Linhas:    {meta.total_rows} ({meta.rows_with_groups} com grupos)")
    print(f"CSV:       {args.out}")
    print(f"JSON:      {args.json_out}")
    if meta.errors:
        print("\nAvisos:")
        for err in meta.errors:
            print(f"  - {err}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
