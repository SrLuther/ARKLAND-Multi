#!/usr/bin/env python3
"""Export legacy player points from ArkShop / CustomShop MySQL .ibd tablespaces.

Reads orphaned InnoDB .ibd files (no running MySQL required) and writes a staging
CSV/JSON with steam_id + positive points only.

Sources scanned (under --data-dir):
  arkshop/arkshopplayers.ibd  — ArkShop legacy (SteamId BIGINT, Points INT, Kits LONGTEXT)
  arkshop/players.ibd         — CustomShop (steam_id VARCHAR, points INT)

Dedup: when the same steam_id appears in multiple sources/rows, keeps the MAX points.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

STEAM_ID64_MIN = 76561197960265728
STEAM_ID64_MAX = 76561202255233023
STEAM_ID64_RE = re.compile(r"7656119\d{10}")
# ArkShop Kits column JSON (distinctive kit keys)
ARKSHOP_KITS_RE = re.compile(
    rb'\{"(?:acro_pack10|starter2?|vip_bronze|diamante|kit_blindado)[^}]{0,4000}\}'
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = Path(r"C:\Users\Ciano\Pictures\data")
DEFAULT_OUT_DIR = ROOT / "data" / "migration_staging"


@dataclass
class Row:
    steam_id: str
    points: int
    source: str


@dataclass
class ExportSummary:
    sources: list[str] = field(default_factory=list)
    rows_raw: int = 0
    rows_positive: int = 0
    rows_exported: int = 0
    total_points: int = 0
    min_points: int = 0
    max_points: int = 0
    samples: list[Row] = field(default_factory=list)


def is_valid_steam_id64(value: int) -> bool:
    return STEAM_ID64_MIN <= value <= STEAM_ID64_MAX


def steam_from_uint64(value: int) -> str:
    return str(value)


def parse_arkshop_ibd(path: Path) -> list[Row]:
    """Parse ArkShop arkshopplayers.ibd — SteamId as BIGINT LE, Points as INT after Kits JSON."""
    data = path.read_bytes()
    rows: list[Row] = []
    seen_offsets: set[int] = set()

    for match in ARKSHOP_KITS_RE.finditer(data):
        kits_start = match.start()
        if kits_start in seen_offsets:
            continue
        seen_offsets.add(kits_start)

        steam_id: str | None = None
        # SteamId column sits immediately before Kits in the InnoDB row (8 bytes LE).
        for back in range(8, 64):
            pos = kits_start - back
            if pos < 0:
                break
            candidate = struct.unpack_from("<Q", data, pos)[0]
            if is_valid_steam_id64(candidate):
                steam_id = steam_from_uint64(candidate)
                break

        if not steam_id:
            continue

        kits_end = match.end()
        points = 0
        # Points INT follows Kits blob; scan a small window after JSON.
        for fwd in range(0, 32, 4):
            pos = kits_end + fwd
            if pos + 4 > len(data):
                break
            candidate = struct.unpack_from("<i", data, pos)[0]
            if 0 <= candidate <= 50_000_000:
                points = candidate
                break

        rows.append(Row(steam_id=steam_id, points=points, source=path.name))

    # Fallback: scan all uint64 steam ids and pair with nearest plausible points.
    if not rows:
        rows = _heuristic_uint64_scan(data, path.name)

    return rows


def parse_customshop_ibd(path: Path) -> list[Row]:
    """Parse CustomShop players.ibd — steam_id as VARCHAR, points as INT nearby."""
    data = path.read_bytes()
    rows: list[Row] = []

    for match in STEAM_ID64_RE.finditer(data.decode("latin-1", errors="ignore")):
        steam_id = match.group()
        pos = match.start()
        # points column typically follows null-terminated steam_id string
        after = data[pos + len(steam_id) : pos + len(steam_id) + 24]
        points = 0
        for off in range(0, len(after) - 3, 1):
            candidate = struct.unpack_from("<i", after, off)[0]
            if 0 <= candidate <= 50_000_000:
                points = candidate
                break
        rows.append(Row(steam_id=steam_id, points=points, source=path.name))

    if not rows:
        rows = _heuristic_uint64_scan(data, path.name)

    return rows


def _heuristic_uint64_scan(data: bytes, source: str) -> list[Row]:
    """Last-resort: find uint64 steam ids and nearest plausible int32 points."""
    by_steam: dict[str, int] = {}
    for i in range(len(data) - 12):
        steam = struct.unpack_from("<Q", data, i)[0]
        if not is_valid_steam_id64(steam):
            continue
        sid = steam_from_uint64(steam)
        for j in range(8, 120, 4):
            if i + j + 4 > len(data):
                break
            pts = struct.unpack_from("<i", data, i + j)[0]
            if 1 <= pts <= 50_000_000:
                by_steam[sid] = max(by_steam.get(sid, 0), pts)
                break
    return [Row(steam_id=s, points=p, source=source) for s, p in by_steam.items()]


def dedupe_max(rows: Iterable[Row]) -> list[Row]:
    merged: dict[str, Row] = {}
    for row in rows:
        prev = merged.get(row.steam_id)
        if prev is None or row.points > prev.points:
            merged[row.steam_id] = row
    return sorted(merged.values(), key=lambda r: (-r.points, r.steam_id))


def positive_only(rows: Iterable[Row]) -> list[Row]:
    return [r for r in rows if r.points > 0]


def discover_sources(data_dir: Path) -> list[tuple[str, Path]]:
    mapping = [
        ("arkshop", data_dir / "arkshop" / "arkshopplayers.ibd"),
        ("customshop", data_dir / "arkshop" / "players.ibd"),
    ]
    found = []
    for kind, path in mapping:
        if path.is_file():
            found.append((kind, path))
    return found


def export(data_dir: Path, out_dir: Path) -> ExportSummary:
    summary = ExportSummary()
    all_rows: list[Row] = []

    sources = discover_sources(data_dir)
    if not sources:
        raise FileNotFoundError(
            f"Nenhum arquivo .ibd reconhecido em {data_dir}. "
            "Esperado: arkshop/arkshopplayers.ibd e/ou arkshop/players.ibd"
        )

    parsers = {
        "arkshop": parse_arkshop_ibd,
        "customshop": parse_customshop_ibd,
    }

    for kind, path in sources:
        summary.sources.append(f"{kind}:{path}")
        parsed = parsers[kind](path)
        summary.rows_raw += len(parsed)
        all_rows.extend(parsed)

    positive = positive_only(all_rows)
    summary.rows_positive = len(positive)
    deduped = dedupe_max(positive)
    summary.rows_exported = len(deduped)

    if deduped:
        points_vals = [r.points for r in deduped]
        summary.total_points = sum(points_vals)
        summary.min_points = min(points_vals)
        summary.max_points = max(points_vals)
        summary.samples = deduped[:5]

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "player_points_legacy.csv"
    json_path = out_dir / "player_points_legacy.json"

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["steam_id", "points"])
        for row in deduped:
            writer.writerow([row.steam_id, row.points])

    payload = {
        "summary": {
            "sources": summary.sources,
            "rows_raw": summary.rows_raw,
            "rows_positive": summary.rows_positive,
            "rows_exported": summary.rows_exported,
            "total_points": summary.total_points,
            "min_points": summary.min_points,
            "max_points": summary.max_points,
            "dedupe_logic": "max(points) per steam_id across all sources",
        },
        "players": [{"steam_id": r.steam_id, "points": r.points} for r in deduped],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    summary._csv_path = csv_path  # type: ignore[attr-defined]
    summary._json_path = json_path  # type: ignore[attr-defined]
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Pasta com dados legados (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Pasta de saída staging (default: {DEFAULT_OUT_DIR})",
    )
    args = parser.parse_args()

    if not args.data_dir.is_dir():
        print(f"ERRO: pasta não encontrada: {args.data_dir}", file=sys.stderr)
        return 1

    try:
        summary = export(args.data_dir, args.out_dir)
    except FileNotFoundError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    print("=== Exportação legado (staging) ===")
    print(f"Fontes: {len(summary.sources)}")
    for src in summary.sources:
        print(f"  - {src}")
    print(f"Linhas brutas lidas: {summary.rows_raw}")
    print(f"Com pontos > 0: {summary.rows_positive}")
    print(f"Exportadas (dedupe max): {summary.rows_exported}")
    print(f"Total pontos: {summary.total_points:,}")
    if summary.rows_exported:
        print(f"Min/Max: {summary.min_points:,} / {summary.max_points:,}")
    print(f"CSV: {summary._csv_path}")  # type: ignore[attr-defined]
    print(f"JSON: {summary._json_path}")  # type: ignore[attr-defined]
    if summary.samples:
        print("\nAmostra (verificação steam_id ↔ points):")
        for row in summary.samples:
            print(f"  {row.steam_id} -> {row.points:,}  ({row.source})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
