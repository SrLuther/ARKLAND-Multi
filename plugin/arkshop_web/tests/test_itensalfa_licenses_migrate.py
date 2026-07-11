"""Testes da migration ItensAlfa (license_tier_catalog) — SQLite in-memory."""
from __future__ import annotations

import os

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")

from sqlalchemy import create_engine, text

from itensalfa_licenses_migrate import TIERS, ensure_itensalfa_licenses_schema


def test_ensure_itensalfa_licenses_schema_idempotent() -> None:
    engine = create_engine("sqlite:///:memory:")
    n1 = ensure_itensalfa_licenses_schema(engine)
    assert n1 == len(TIERS)

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT group_name, price_amber, timed_bonus FROM license_tier_catalog ORDER BY price_amber")
        ).fetchall()
    assert len(rows) == len(TIERS)
    assert rows[0][0] == "Delta"
    assert rows[0][1] == 6000
    assert rows[-1][0] == "Exotico"
    assert rows[-1][1] == 230000

    # Re-run: same count, no duplicates
    n2 = ensure_itensalfa_licenses_schema(engine)
    assert n2 == len(TIERS)
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM license_tier_catalog")).scalar()
    assert count == len(TIERS)


def test_player_entitlements_created() -> None:
    engine = create_engine("sqlite:///:memory:")
    ensure_itensalfa_licenses_schema(engine)
    with engine.connect() as conn:
        # Table exists and accepts insert
        conn.execute(
            text(
                "INSERT INTO player_entitlements (steam_id, group_name) VALUES ('1', 'Delta')"
            )
        )
        conn.commit()
        n = conn.execute(text("SELECT COUNT(*) FROM player_entitlements")).scalar()
    assert n == 1
