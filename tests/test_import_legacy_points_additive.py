"""Tests for tools/import_legacy_points_additive.py (CSV parse + sqlite apply)."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from import_legacy_points_additive import (  # noqa: E402
    aggregate_points,
    apply_additive_import,
    parse_csv_rows,
    CsvRow,
)


class SqliteCursorAdapter:
    """Translate pymysql-style %s placeholders for sqlite tests."""

    def __init__(self, cur: sqlite3.Cursor) -> None:
        self._cur = cur

    def execute(self, sql: str, params=None):
        return self._cur.execute(sql.replace("%s", "?"), params or ())

    def fetchall(self):
        return self._cur.fetchall()

    def fetchone(self):
        return self._cur.fetchone()


@pytest.fixture
def csv_file(tmp_path: Path) -> Path:
    path = tmp_path / "points.csv"
    path.write_text(
        "\n".join(
            [
                "steam_id,points,groups",
                "76561198000000001,100,VIPBronze",
                "76561198000000002,50,",
                "76561198000000001,25,VIPPrata",
                "76561198000000003,0,",
                "76561198000000004,908022460,Admins,Staff",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_parse_csv_and_aggregate(csv_file: Path) -> None:
    rows, warnings = parse_csv_rows(csv_file)
    assert len(warnings) == 0
    assert len(rows) == 5
    deltas, groups, merged = aggregate_points(rows)
    assert merged == 1
    assert deltas["76561198000000001"] == 125
    assert deltas["76561198000000002"] == 50
    assert deltas["76561198000000003"] == 0
    assert groups["76561198000000001"] == "VIPPrata"
    assert "Admins" in groups["76561198000000004"]


def test_apply_skips_missing_and_zero(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE players (steam_id TEXT PRIMARY KEY, points INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute(
        "INSERT INTO players (steam_id, points) VALUES ('76561198000000001', 1000)"
    )
    conn.commit()
    cur = SqliteCursorAdapter(conn.cursor())

    deltas = {
        "76561198000000001": 200,
        "76561198000000099": 500,
        "76561198000000003": 0,
    }
    report = apply_additive_import(cur, deltas, dry_run=False)
    conn.commit()

    assert report.matched_in_db == 1
    assert report.updated == 1
    assert report.skipped_not_in_db == 1
    assert report.zero_points_skipped == 1

    row = conn.execute(
        "SELECT points FROM players WHERE steam_id = '76561198000000001'"
    ).fetchone()
    assert row[0] == 1200


def test_dry_run_no_write() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE players (steam_id TEXT PRIMARY KEY, points INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute("INSERT INTO players (steam_id, points) VALUES ('111', 10)")
    conn.commit()
    cur = SqliteCursorAdapter(conn.cursor())

    report = apply_additive_import(cur, {"111": 5}, dry_run=True)
    row = conn.execute("SELECT points FROM players WHERE steam_id = '111'").fetchone()
    assert row[0] == 10
    assert report.updated == 1
    assert report.dry_run is True


def test_max_points_skips_insane() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE players (steam_id TEXT PRIMARY KEY, points INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute("INSERT INTO players (steam_id, points) VALUES ('111', 10)")
    conn.commit()
    cur = SqliteCursorAdapter(conn.cursor())

    report = apply_additive_import(cur, {"111": 999_999_999}, max_points=1_000_000)
    assert report.skipped_over_max == 1
    assert report.updated == 0


def test_max_points_cap() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE players (steam_id TEXT PRIMARY KEY, points INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute("INSERT INTO players (steam_id, points) VALUES ('111', 10)")
    conn.commit()
    cur = SqliteCursorAdapter(conn.cursor())

    report = apply_additive_import(
        cur, {"111": 5000}, max_points=1000, cap_over_max=True, dry_run=False
    )
    conn.commit()
    assert report.capped_over_max == 1
    assert report.updated == 1
    row = conn.execute("SELECT points FROM players WHERE steam_id = '111'").fetchone()
    assert row[0] == 1010
