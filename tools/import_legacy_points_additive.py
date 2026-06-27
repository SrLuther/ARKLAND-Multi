#!/usr/bin/env python3
"""Import legacy player points additively into arkland_shop.players (CustomShop).

Reads steam_id + points from CSV and runs::

    UPDATE players SET points = points + :delta WHERE steam_id = :sid

Only existing rows are updated. Unknown steam_ids are skipped silently.
New players are never inserted.

Duplicate steam_ids in the CSV are **summed** before apply (see README).

Connection resolution (first match):
  1. CLI --database-url or --host/--user/--password
  2. ARKSHOP_DATABASE_URL
  3. plugin/arkshop_web/settings.json
  4. %%APPDATA%%/ARKLAND-ServerManager/db_server_prefs.json (shop_db)

Groups column is parsed when present but not applied to the DB (future work).
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

try:
    import pymysql
except ImportError:
    pymysql = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
DEFAULT_CSV = ROOT / "plugin" / "CustomShop" / "configs" / "jogadores_pontos_grupos.csv"

STEAM_COLS = ("steam_id", "steamid", "steamid64")
POINTS_COLS = ("points", "pontos", "Points")
GROUPS_COLS = ("groups", "grupos", "group", "permissiongroups")

DEFAULT_INSANE_WARN = 10_000_000


class DbCursor(Protocol):
    def execute(self, sql: str, params: Any = None) -> Any: ...
    def fetchall(self) -> list[Any]: ...
    def fetchone(self) -> Any: ...


@dataclass
class CsvRow:
    steam_id: str
    points: int
    groups: str = ""
    line_no: int = 0


@dataclass
class ImportReport:
    csv_rows: int = 0
    unique_steam_ids: int = 0
    duplicate_rows_merged: int = 0
    zero_points_skipped: int = 0
    invalid_rows_skipped: int = 0
    matched_in_db: int = 0
    updated: int = 0
    skipped_not_in_db: int = 0
    skipped_over_max: int = 0
    capped_over_max: int = 0
    insane_warnings: list[str] = field(default_factory=list)
    sample_updates: list[dict[str, Any]] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "csv_rows": self.csv_rows,
            "unique_steam_ids": self.unique_steam_ids,
            "duplicate_rows_merged": self.duplicate_rows_merged,
            "zero_points_skipped": self.zero_points_skipped,
            "invalid_rows_skipped": self.invalid_rows_skipped,
            "matched_in_db": self.matched_in_db,
            "updated": self.updated,
            "skipped_not_in_db": self.skipped_not_in_db,
            "skipped_over_max": self.skipped_over_max,
            "capped_over_max": self.capped_over_max,
            "dry_run": self.dry_run,
            "insane_warnings": self.insane_warnings,
            "sample_updates": self.sample_updates,
        }


def _norm_header(name: str) -> str:
    return (name or "").strip().lower().replace(" ", "_")


def _pick_column(headers: list[str], candidates: tuple[str, ...]) -> str | None:
    norm = {_norm_header(h): h for h in headers}
    for cand in candidates:
        if cand in norm:
            return norm[cand]
    return None


def parse_csv_rows(path: Path) -> tuple[list[CsvRow], list[str]]:
    """Parse CSV; extra comma-separated fields after points are joined as groups."""
    warnings: list[str] = []
    if not path.is_file():
        raise FileNotFoundError(f"CSV não encontrado: {path}")

    rows: list[CsvRow] = []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        try:
            raw_headers = next(reader)
        except StopIteration:
            return [], ["CSV vazio"]

        headers = [h.strip() for h in raw_headers]
        steam_col = _pick_column(headers, STEAM_COLS)
        points_col = _pick_column(headers, POINTS_COLS)
        groups_col = _pick_column(headers, GROUPS_COLS)

        if not steam_col or not points_col:
            raise ValueError(
                f"CSV precisa de colunas steam_id e points (headers: {headers})"
            )

        steam_idx = headers.index(steam_col)
        points_idx = headers.index(points_col)
        groups_idx = headers.index(groups_col) if groups_col else None

        for line_no, fields in enumerate(reader, start=2):
            if not fields or all(not (c or "").strip() for c in fields):
                continue
            if len(fields) <= max(steam_idx, points_idx):
                warnings.append(f"linha {line_no}: colunas insuficientes — ignorada")
                continue

            steam_id = (fields[steam_idx] or "").strip()
            if not steam_id.isdigit():
                warnings.append(f"linha {line_no}: steam_id inválido '{steam_id}' — ignorada")
                continue

            raw_points = (fields[points_idx] or "").strip().replace(",", "")
            try:
                points = int(float(raw_points))
            except ValueError:
                warnings.append(f"linha {line_no}: points inválido '{raw_points}' — ignorada")
                continue

            groups = ""
            if groups_idx is not None and groups_idx < len(fields):
                groups = (fields[groups_idx] or "").strip()
            tail_start = max(steam_idx, points_idx, groups_idx or -1) + 1
            if tail_start < len(fields):
                extra = [c.strip() for c in fields[tail_start:] if c.strip()]
                if extra:
                    extra_joined = ",".join(extra)
                    groups = f"{groups},{extra_joined}".strip(",") if groups else extra_joined

            rows.append(CsvRow(steam_id=steam_id, points=points, groups=groups, line_no=line_no))

    return rows, warnings


def aggregate_points(rows: list[CsvRow]) -> tuple[dict[str, int], dict[str, str], int]:
    """Sum duplicate steam_ids. Returns (deltas, groups_last, merged_count)."""
    deltas: dict[str, int] = {}
    groups_last: dict[str, str] = {}
    merged = 0
    for row in rows:
        if row.steam_id in deltas:
            merged += 1
        deltas[row.steam_id] = deltas.get(row.steam_id, 0) + row.points
        if row.groups:
            groups_last[row.steam_id] = row.groups
    return deltas, groups_last, merged


def _adjust_delta(
    steam_id: str,
    delta: int,
    *,
    max_points: int | None,
    cap_over_max: bool,
    insane_warn: int,
    report: ImportReport,
) -> int | None:
    if delta == 0:
        return None
    if max_points is not None and delta > max_points:
        if cap_over_max:
            report.capped_over_max += 1
            report.insane_warnings.append(
                f"{steam_id}: delta {delta:,} limitado a {max_points:,} (--cap-over-max)"
            )
            return max_points
        report.skipped_over_max += 1
        report.insane_warnings.append(
            f"{steam_id}: delta {delta:,} acima de --max-points {max_points:,} — ignorado"
        )
        return None
    if max_points is None and delta >= insane_warn:
        report.insane_warnings.append(
            f"{steam_id}: delta {delta:,} muito alto (>= {insane_warn:,}) — aplicando mesmo assim"
        )
    return delta


def fetch_existing_points(cur: DbCursor, steam_ids: list[str], chunk: int = 500) -> dict[str, int]:
    found: dict[str, int] = {}
    for i in range(0, len(steam_ids), chunk):
        batch = steam_ids[i : i + chunk]
        placeholders = ",".join(["%s"] * len(batch))
        cur.execute(
            f"SELECT steam_id, points FROM players WHERE steam_id IN ({placeholders})",
            batch,
        )
        for row in cur.fetchall():
            if isinstance(row, dict):
                sid = str(row["steam_id"])
                pts = int(row["points"])
            else:
                sid, pts = str(row[0]), int(row[1])
            found[sid] = pts
    return found


def apply_additive_import(
    cur: DbCursor,
    deltas: dict[str, int],
    *,
    dry_run: bool = False,
    max_points: int | None = None,
    cap_over_max: bool = False,
    insane_warn: int = DEFAULT_INSANE_WARN,
    sample_limit: int = 15,
) -> ImportReport:
    report = ImportReport(dry_run=dry_run)
    report.unique_steam_ids = len(deltas)

    effective: dict[str, int] = {}
    for steam_id, delta in deltas.items():
        adj = _adjust_delta(
            steam_id,
            delta,
            max_points=max_points,
            cap_over_max=cap_over_max,
            insane_warn=insane_warn,
            report=report,
        )
        if adj is None:
            if delta == 0:
                report.zero_points_skipped += 1
            continue
        effective[steam_id] = adj

    if not effective:
        return report

    existing = fetch_existing_points(cur, list(effective.keys()))
    report.matched_in_db = len(existing)
    report.skipped_not_in_db = len(effective) - len(existing)

    for steam_id, delta in effective.items():
        before = existing.get(steam_id)
        if before is None:
            continue
        after = before + delta
        if len(report.sample_updates) < sample_limit:
            report.sample_updates.append(
                {
                    "steam_id": steam_id,
                    "points_before": before,
                    "delta": delta,
                    "points_after": after,
                }
            )
        if dry_run:
            report.updated += 1
            continue
        cur.execute(
            "UPDATE players SET points = points + %s WHERE steam_id = %s",
            (delta, steam_id),
        )
        report.updated += 1

    return report


def print_report(report: ImportReport, parse_warnings: list[str], csv_path: Path) -> None:
    print("=" * 60)
    print("IMPORT LEGACY POINTS — aditivo (CustomShop players)")
    print("=" * 60)
    print(f"CSV:       {csv_path}")
    print(f"Modo:      {'DRY-RUN' if report.dry_run else 'APLICADO'}")
    print(f"Linhas:    {report.csv_rows}")
    print(f"Únicos:    {report.unique_steam_ids} steam_id(s)")
    if report.duplicate_rows_merged:
        print(f"Duplicatas somadas: {report.duplicate_rows_merged}")
    print(f"Zero pts:  {report.zero_points_skipped} ignorado(s)")
    print(f"No DB:     {report.matched_in_db} encontrado(s)")
    print(f"Atualiz.:  {report.updated}")
    print(f"Skip (404): {report.skipped_not_in_db} não existem em players")
    if report.skipped_over_max:
        print(f"Skip max:  {report.skipped_over_max}")
    if report.capped_over_max:
        print(f"Cap max:   {report.capped_over_max}")

    if parse_warnings:
        print("\nAvisos CSV:")
        for w in parse_warnings[:20]:
            print(f"  - {w}")
        if len(parse_warnings) > 20:
            print(f"  ... +{len(parse_warnings) - 20} aviso(s)")

    if report.insane_warnings:
        print("\nAvisos valores altos:")
        for w in report.insane_warnings[:20]:
            print(f"  - {w}")

    if report.sample_updates:
        print("\nAmostra de updates:")
        for row in report.sample_updates:
            print(
                f"  {row['steam_id']}: {row['points_before']:,} + {row['delta']:,} "
                f"→ {row['points_after']:,}"
            )


def resolve_connection(args: argparse.Namespace):
    """Reuse export tool target resolution; return first connectable target."""
    from export_player_points_mysql import collect_targets, connect

    targets = collect_targets(args)
    errors: list[str] = []
    for target in targets:
        if target.database not in ("arkland_shop", ""):
            continue
        try:
            conn = connect(target, timeout=args.timeout)
            return conn, target, errors
        except Exception as exc:
            errors.append(f"{target.label}: {exc}")
    if not targets:
        raise RuntimeError("Nenhum alvo de conexão configurado")
    for target in targets:
        try:
            conn = connect(target, timeout=args.timeout)
            return conn, target, errors
        except Exception as exc:
            errors.append(f"{target.label}: {exc}")
    raise RuntimeError("Falha ao conectar:\n  " + "\n  ".join(errors[-10:]))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Importa pontos legacy de CSV (somente UPDATE aditivo em players)"
    )
    p.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help=f"Caminho do CSV (default: {DEFAULT_CSV})",
    )
    p.add_argument("--dry-run", action="store_true", help="Simula sem UPDATE")
    p.add_argument("--database-url", help="mysql+pymysql://user:pass@host:port/arkland_shop")
    p.add_argument("--host")
    p.add_argument("--port", type=int, default=3306)
    p.add_argument("--user")
    p.add_argument("--password", default="")
    p.add_argument("--database", default="arkland_shop")
    p.add_argument("--timeout", type=int, default=15)
    p.add_argument(
        "--max-points",
        type=int,
        default=None,
        metavar="N",
        help="Ignora deltas acima de N (use --cap-over-max para limitar em vez de ignorar)",
    )
    p.add_argument(
        "--cap-over-max",
        action="store_true",
        help="Com --max-points, limita delta ao teto em vez de ignorar",
    )
    p.add_argument(
        "--insane-warn",
        type=int,
        default=DEFAULT_INSANE_WARN,
        help=f"Aviso quando delta >= N sem --max-points (default {DEFAULT_INSANE_WARN:,})",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if pymysql is None:
        print("ERRO: pymysql não instalado — pip install pymysql", file=sys.stderr)
        return 2

    try:
        raw_rows, parse_warnings = parse_csv_rows(args.csv)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2

    deltas, _groups, merged = aggregate_points(raw_rows)
    report = ImportReport(
        csv_rows=len(raw_rows),
        duplicate_rows_merged=merged,
        invalid_rows_skipped=len(parse_warnings),
    )

    if not deltas:
        print("Nenhum steam_id válido no CSV.", file=sys.stderr)
        return 1

    try:
        conn, target, conn_errors = resolve_connection(args)
    except RuntimeError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2

    print(f"Conectado: {target.host}:{target.port}/{target.database} ({target.label})")
    if conn_errors:
        print(f"(tentativas falhas: {len(conn_errors)})")

    try:
        with conn.cursor() as cur:
            apply_report = apply_additive_import(
                cur,
                deltas,
                dry_run=args.dry_run,
                max_points=args.max_points,
                cap_over_max=args.cap_over_max,
                insane_warn=args.insane_warn,
            )
        if not args.dry_run:
            conn.commit()
        else:
            conn.rollback()
    finally:
        conn.close()

    report.matched_in_db = apply_report.matched_in_db
    report.updated = apply_report.updated
    report.skipped_not_in_db = apply_report.skipped_not_in_db
    report.zero_points_skipped = apply_report.zero_points_skipped
    report.skipped_over_max = apply_report.skipped_over_max
    report.capped_over_max = apply_report.capped_over_max
    report.insane_warnings = apply_report.insane_warnings
    report.sample_updates = apply_report.sample_updates
    report.dry_run = args.dry_run
    report.unique_steam_ids = apply_report.unique_steam_ids

    print_report(report, parse_warnings, args.csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
