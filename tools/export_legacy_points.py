#!/usr/bin/env python3
"""DEPRECATED — Export legacy player points from ArkShop / CustomShop MySQL .ibd tablespaces.

*** NÃO USAR PARA MIGRAÇÃO ***
Heuristic .ibd parsing produz valores uniformes e incorretos (~263–766 pts).
Use tools/export_player_points_mysql.py (live MySQL READ-ONLY) em vez deste script.

Reads orphaned InnoDB .ibd files (no running MySQL required) and writes a staging
CSV/JSON with steam_id, points, metadata and confidence flags.

Sources scanned (under --data-dir):
  arkshop/arkshopplayers.ibd  — ArkShop legacy (SteamId BIGINT BE, Points INT LE @ -8)
  arkshop/players.ibd         — CustomShop (steam_id VARCHAR, points INT) — rarely populated

Dedup: when the same steam_id appears in multiple sources/rows, keeps the MAX points.

ArkShop schema (Michidu ArkShop MysqlDB.h): Id, SteamId, Kits, Points, TotalSpent.
InnoDB DYNAMIC stores trailing fixed cols (Points, TotalSpent) in the record header
immediately before SteamId; Kits LONGTEXT follows SteamId inline or as `{}` when empty.
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

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = Path(r"C:\Users\Ciano\Pictures\data")
DEFAULT_OUT_DIR = ROOT / "data" / "migration_staging"
MAX_SANE_POINTS = 500_000
# `{}` kit rows with ~33k points are InnoDB page-metadata false positives (hex-verified).
MAX_EMPTY_KITS_POINTS = 5_000

# InnoDB clustered row (arkshopplayers.ibd, verified by hex dump):
#   offset -8: Points (INT32 LE)
#   offset  0: SteamId (BIGINT UNSIGNED, big-endian on disk)
#   offset +8: Kits (LONGTEXT JSON, often `{}` or `{"kit":...}`)
ARKSHOP_POINTS_OFFSET = -8


@dataclass
class Candidate:
    steam_id: str
    points: int
    file_offset: int
    source_file: str
    kits_marker: str
    accepted: bool
    reject_reason: str = ""


@dataclass
class Row:
    steam_id: str
    points: int
    source_file: str
    total_spent: int | None = None
    confidence: str = "high"
    notes: str = ""
    empty_kits: bool = False


@dataclass
class ExportSummary:
    sources: list[str] = field(default_factory=list)
    rows_raw: int = 0
    rows_positive: int = 0
    rows_exported: int = 0
    rows_low_confidence: int = 0
    rows_recovered_empty_kits: int = 0
    total_points: int = 0
    min_points: int = 0
    max_points: int = 0
    samples: list[Row] = field(default_factory=list)
    csv_path: Path | None = None
    json_path: Path | None = None
    validation_path: Path | None = None
    rows_rejected_metadata: int = 0


def is_valid_steam_id64(value: int) -> bool:
    return STEAM_ID64_MIN <= value <= STEAM_ID64_MAX


def steam_from_uint64(value: int) -> str:
    return str(value)


def _read_le_i32(data: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 4 > len(data):
        return None
    return struct.unpack_from("<i", data, offset)[0]


def _kits_marker(data: bytes, offset: int) -> str | None:
    """Return kits marker at +8: json (`{"`) or empty (`{}`), else None."""
    if offset + 10 > len(data):
        return None
    chunk = data[offset + 8 : offset + 10]
    if chunk == b'{"':
        return "json"
    if chunk == b"{}":
        return "empty"
    return None


def _reject_arkshop_candidate(marker: str | None, points: int | None) -> str:
    if marker is None:
        return "invalid_kits_marker"
    if points is None:
        return "missing_points"
    if points < 0 or points > MAX_SANE_POINTS:
        return "points_out_of_range"
    if marker == "empty" and points > MAX_EMPTY_KITS_POINTS:
        return "empty_kits_metadata_false_positive"
    return ""


def scan_arkshop_candidates(path: Path) -> list[Candidate]:
    """Scan all SteamId-aligned hits in arkshopplayers.ibd (accepted + rejected)."""
    data = path.read_bytes()
    candidates: list[Candidate] = []
    seen: set[tuple[str, int]] = set()

    for i in range(len(data) - 10):
        steam_val = struct.unpack_from(">Q", data, i)[0]
        if not is_valid_steam_id64(steam_val):
            continue
        marker = _kits_marker(data, i)
        points = _read_le_i32(data, i + ARKSHOP_POINTS_OFFSET)
        steam_id = steam_from_uint64(steam_val)
        key = (steam_id, i)
        if key in seen:
            continue
        seen.add(key)

        reject = _reject_arkshop_candidate(marker, points)
        candidates.append(
            Candidate(
                steam_id=steam_id,
                points=points if points is not None else -1,
                file_offset=i,
                source_file=path.name,
                kits_marker=marker or data[i + 8 : i + 10].hex(),
                accepted=not reject,
                reject_reason=reject,
            )
        )

    return candidates


def candidates_to_rows(candidates: Iterable[Candidate]) -> list[Row]:
    rows: list[Row] = []
    for cand in candidates:
        if not cand.accepted:
            continue
        empty = cand.kits_marker == "empty"
        rows.append(
            Row(
                steam_id=cand.steam_id,
                points=cand.points,
                source_file=cand.source_file,
                total_spent=None,
                confidence="high",
                notes="empty_kits" if empty else "",
                empty_kits=empty,
            )
        )
    return rows


def parse_arkshop_ibd(path: Path) -> list[Row]:
    """Parse ArkShop arkshopplayers.ibd clustered data rows (SteamId + inline Kits)."""
    return candidates_to_rows(scan_arkshop_candidates(path))


def parse_customshop_ibd(path: Path) -> list[Row]:
    """Parse CustomShop players.ibd — steam_id VARCHAR, points INT after null byte."""
    data = path.read_bytes()
    rows: list[Row] = []

    text = data.decode("latin-1", errors="ignore")
    for match in STEAM_ID64_RE.finditer(text):
        steam_id = match.group()
        pos = match.start()
        end = pos + len(steam_id)
        if end < len(data) and data[end] == 0:
            end += 1
        points = _read_le_i32(data, end) or 0
        if points < 0 or points > MAX_SANE_POINTS:
            continue
        rows.append(
            Row(
                steam_id=steam_id,
                points=points,
                source_file=path.name,
                total_spent=None,
                confidence="low",
                notes="customshop_heuristic",
            )
        )

    return rows


def _source_priority(source: str) -> int:
    if "arkshopplayers" in source:
        return 2
    return 1


def dedupe_max(rows: Iterable[Row]) -> list[Row]:
    """Dedupe by steam_id; prefer arkshopplayers.ibd over players.ibd, else max points."""
    grouped: dict[str, list[Row]] = {}
    for row in rows:
        grouped.setdefault(row.steam_id, []).append(row)

    merged: list[Row] = []
    for steam_id, group in grouped.items():
        arkshop_rows = [r for r in group if _source_priority(r.source_file) == 2]
        pool = arkshop_rows if arkshop_rows else group

        # `{}` rows collide with InnoDB page metadata for players that also have
        # real kit JSON rows — prefer non-empty kit rows when both exist.
        json_rows = [r for r in pool if not r.empty_kits]
        if json_rows:
            pool = json_rows

        points_set = {r.points for r in pool}
        best = max(pool, key=lambda r: (r.points, _source_priority(r.source_file)))

        notes = [n for n in {r.notes for r in pool if r.notes} if n]
        if len(pool) > 1:
            notes.append(f"deduped_{len(pool)}_rows")
        if len(points_set) > 1:
            notes.append("duplicate_rows_disagreed_on_points")

        merged.append(
            Row(
                steam_id=best.steam_id,
                points=best.points,
                source_file=best.source_file,
                total_spent=best.total_spent,
                confidence="low" if best.confidence == "low" or len(points_set) > 1 else "high",
                notes=";".join(notes),
                empty_kits=any(r.empty_kits for r in pool),
            )
        )

    return sorted(merged, key=lambda r: (-r.points, r.steam_id))


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


def build_validation_report(
    arkshop_candidates: list[Candidate],
    chosen: list[Row],
) -> dict:
    """Per steam_id: all raw candidates and which row was exported."""
    by_steam: dict[str, list[dict]] = {}
    for cand in arkshop_candidates:
        by_steam.setdefault(cand.steam_id, []).append(
            {
                "points": cand.points,
                "file_offset": f"0x{cand.file_offset:x}",
                "kits_marker": cand.kits_marker,
                "accepted": cand.accepted,
                "reject_reason": cand.reject_reason or None,
            }
        )

    chosen_map = {r.steam_id: r for r in chosen}
    players = []
    for steam_id in sorted(by_steam, key=lambda s: (-chosen_map[s].points if s in chosen_map else 0, s)):
        entry = {
            "steam_id": steam_id,
            "candidates": sorted(by_steam[steam_id], key=lambda c: -c["points"]),
        }
        if steam_id in chosen_map:
            row = chosen_map[steam_id]
            entry["exported"] = {
                "points": row.points,
                "source_file": row.source_file,
                "confidence": row.confidence,
                "notes": row.notes,
            }
        else:
            entry["exported"] = None
        players.append(entry)

    return {
        "description": (
            "Todos os alinhamentos SteamId BIGINT BE encontrados em arkshopplayers.ibd, "
            "com candidatos aceitos/rejeitados. Valores ~33k em linhas empty_kits sao "
            "falsos positivos de metadata InnoDB (confirmado por hex dump)."
        ),
        "admin_steam_id": "76561198171864983",
        "players": players,
    }


def list_data_inventory(data_dir: Path) -> dict:
    """Summarize all files under the legacy data directory."""
    inventory: dict = {"root": str(data_dir), "groups": {}}
    if not data_dir.is_dir():
        return inventory

    for sub in sorted(data_dir.iterdir()):
        if not sub.is_dir():
            continue
        files = []
        for fp in sorted(sub.rglob("*")):
            if fp.is_file():
                files.append({"name": fp.name, "ext": fp.suffix.lower(), "bytes": fp.stat().st_size})
        inventory["groups"][sub.name] = files
    return inventory


def export(data_dir: Path, out_dir: Path) -> ExportSummary:
    summary = ExportSummary()
    all_rows: list[Row] = []
    arkshop_candidates: list[Candidate] = []

    sources = discover_sources(data_dir)
    if not sources:
        raise FileNotFoundError(
            f"Nenhum arquivo .ibd reconhecido em {data_dir}. "
            "Esperado: arkshop/arkshopplayers.ibd e/ou arkshop/players.ibd"
        )

    for kind, path in sources:
        summary.sources.append(f"{kind}:{path}")
        if kind == "arkshop":
            cands = scan_arkshop_candidates(path)
            arkshop_candidates.extend(cands)
            summary.rows_rejected_metadata += sum(
                1 for c in cands if c.reject_reason == "empty_kits_metadata_false_positive"
            )
            parsed = candidates_to_rows(cands)
        else:
            parsed = parse_customshop_ibd(path)
        summary.rows_raw += len(parsed)
        all_rows.extend(parsed)

    positive = positive_only(all_rows)
    summary.rows_positive = len(positive)
    deduped = dedupe_max(positive)
    summary.rows_exported = len(deduped)
    summary.rows_low_confidence = sum(1 for r in deduped if r.confidence == "low")
    summary.rows_recovered_empty_kits = sum(1 for r in deduped if r.empty_kits)

    if deduped:
        points_vals = [r.points for r in deduped]
        summary.total_points = sum(points_vals)
        summary.min_points = min(points_vals)
        summary.max_points = max(points_vals)
        summary.samples = deduped[:5]

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "player_points_legacy.csv"
    json_path = out_dir / "player_points_legacy.json"
    validation_path = out_dir / "player_points_validation.json"

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["steam_id", "points", "total_spent", "source_file", "confidence", "notes"]
        )
        for row in deduped:
            writer.writerow(
                [
                    row.steam_id,
                    row.points,
                    "" if row.total_spent is None else row.total_spent,
                    row.source_file,
                    row.confidence,
                    row.notes,
                ]
            )

    payload = {
        "summary": {
            "sources": summary.sources,
            "rows_raw": summary.rows_raw,
            "rows_positive": summary.rows_positive,
            "rows_exported": summary.rows_exported,
            "rows_low_confidence": summary.rows_low_confidence,
            "rows_recovered_empty_kits": summary.rows_recovered_empty_kits,
            "total_points": summary.total_points,
            "min_points": summary.min_points,
            "max_points": summary.max_points,
            "rows_rejected_metadata": summary.rows_rejected_metadata,
            "dedupe_logic": (
                "prefer arkshopplayers.ibd JSON kit rows over empty_kits; "
                "reject empty_kits with points > 5000 (InnoDB metadata false positives); "
                "otherwise max(points) per steam_id"
            ),
            "arkshop_layout": "Points INT32 LE at offset -8 before SteamId BIGINT BE; Kits at +8",
            "correction": (
                "Correcao 2026-06-26: os ~33k no topo do CSV eram FALSOS POSITIVOS — bytes de "
                "SteamId alinhados em metadata de pagina InnoDB com marcador Kits='{}'. "
                "Admin 76561198171864983 tem saldo real 282 na unica linha JSON valida "
                "(offset 0x182a5); hit 525056 @0x1408e e metadata (kits=0x8000). "
                "Max real no dump: 766 pts. Docker/MySQL indisponivel para IMPORT TABLESPACE."
            ),
            "inventory": list_data_inventory(data_dir),
        },
        "players": [
            {
                "steam_id": r.steam_id,
                "points": r.points,
                "total_spent": r.total_spent,
                "source_file": r.source_file,
                "confidence": r.confidence,
                "notes": r.notes,
            }
            for r in deduped
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    if arkshop_candidates:
        validation = build_validation_report(arkshop_candidates, deduped)
        validation_path.write_text(
            json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        summary.validation_path = validation_path

    summary.csv_path = csv_path
    summary.json_path = json_path
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
        help=f"Pasta de saida staging (default: {DEFAULT_OUT_DIR})",
    )
    args = parser.parse_args()

    if not args.data_dir.is_dir():
        print(f"ERRO: pasta nao encontrada: {args.data_dir}", file=sys.stderr)
        return 1

    try:
        summary = export(args.data_dir, args.out_dir)
    except FileNotFoundError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    print("=== Exportacao legado (staging) ===")
    print(f"Fontes: {len(summary.sources)}")
    for src in summary.sources:
        print(f"  - {src}")
    print(f"Linhas brutas lidas: {summary.rows_raw}")
    print(f"Com pontos > 0: {summary.rows_positive}")
    print(f"Exportadas (dedupe max): {summary.rows_exported}")
    print(f"Recuperadas (kits vazios): {summary.rows_recovered_empty_kits}")
    print(f"Rejeitadas (metadata ~33k): {summary.rows_rejected_metadata}")
    print(f"Baixa confianca: {summary.rows_low_confidence}")
    print(f"Total pontos: {summary.total_points:,}")
    if summary.rows_exported:
        print(f"Min/Max: {summary.min_points:,} / {summary.max_points:,}")
    print(f"CSV: {summary.csv_path}")
    print(f"JSON: {summary.json_path}")
    if summary.validation_path:
        print(f"Validacao: {summary.validation_path}")
    if summary.samples:
        print("\nAmostra (verificacao steam_id -> points):")
        for row in summary.samples:
            print(f"  {row.steam_id} -> {row.points:,}  ({row.source_file})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
