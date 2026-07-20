"""Tiers pagos distintos ilimitados + stack +30d no mesmo SKU."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")
os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")

import app as _app_module
from app import _configure_database

USER_STEAM = "76561198000000002"
ADMIN_STEAM = "76561198000000001"
API_KEY = "test-api-key"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_API_KEY", API_KEY)
    monkeypatch.setattr(_app_module, "_ARKSHOP_API_KEY", API_KEY)
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(_app_module, "_PLAYERS_FILE", tmp_path / "players.json")
    monkeypatch.setattr(_app_module, "_SERVERS_FILE", tmp_path / "servers.json")
    monkeypatch.setattr(_app_module, "_migrate_schema", lambda _engine: None)
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]))
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(f"sqlite:///{db_path}")
    assert _app_module._ENGINE is not None
    _app_module.Base.metadata.create_all(bind=_app_module._ENGINE)
    with _app_module._ENGINE.connect() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS players ("
            "steam_id VARCHAR(20) PRIMARY KEY NOT NULL, "
            "points INTEGER NOT NULL DEFAULT 0, "
            "kits TEXT DEFAULT '{}')"
        ))
        conn.commit()
    db = _app_module._SessionLocal()
    try:
        _app_module._ensure_entitlements_schema(db)
        db.execute(
            text("INSERT INTO players (steam_id, points) VALUES (:s, 500000)"),
            {"s": USER_STEAM},
        )
        db.commit()
    finally:
        _app_module._release_db_session(db)
    _app_module._ENTITLEMENTS_SCHEMA_READY = True
    _app_module._invalidate_entitlements_cache()
    yield
    _app_module._invalidate_entitlements_cache()


def _expires_in(days: int) -> datetime:
    return (datetime.now(timezone.utc) + timedelta(days=days)).replace(tzinfo=None)


def test_two_distinct_paid_tiers_coexist():
    db = _app_module._SessionLocal()
    try:
        _app_module._apply_entitlement_grant_tx(
            db, USER_STEAM, "Gamma", 30, source="t1", notes="gamma",
        )
        _app_module._apply_entitlement_grant_tx(
            db, USER_STEAM, "Alfa", 30, source="t2", notes="alfa",
        )
        db.commit()
    finally:
        _app_module._release_db_session(db)

    ents = _app_module._get_player_entitlements(USER_STEAM)
    groups = {e["group"] for e in ents}
    assert "Gamma" in groups
    assert "Alfa" in groups


def test_third_distinct_tier_accepted():
    db = _app_module._SessionLocal()
    try:
        _app_module._apply_entitlement_grant_tx(
            db, USER_STEAM, "Gamma", 30, source="t1", notes="g",
        )
        _app_module._apply_entitlement_grant_tx(
            db, USER_STEAM, "Alfa", 30, source="t2", notes="a",
        )
        _app_module._apply_entitlement_grant_tx(
            db, USER_STEAM, "Beta", 30, source="t3", notes="b",
        )
        _app_module._apply_entitlement_grant_tx(
            db, USER_STEAM, "Delta", 30, source="t4", notes="d",
        )
        db.commit()
    finally:
        _app_module._release_db_session(db)

    ents = _app_module._get_player_entitlements(USER_STEAM)
    assert {e["group"] for e in ents} == {"Gamma", "Alfa", "Beta", "Delta"}


def test_same_tier_renewal_stacks_without_extra_slot():
    db = _app_module._SessionLocal()
    try:
        future = _expires_in(10)
        db.execute(
            text(
                "INSERT INTO player_entitlements "
                "(steam_id, group_name, expires, source, notes) "
                "VALUES (:s, 'Gamma', :exp, 'old', 'residual')"
            ),
            {"s": USER_STEAM, "exp": future},
        )
        _app_module._apply_entitlement_grant_tx(
            db, USER_STEAM, "Alfa", 30, source="other", notes="slot2",
        )
        _app_module._apply_entitlement_grant_tx(
            db, USER_STEAM, "Gamma", 30, source="renew", notes="stack",
        )
        db.commit()
        row = db.execute(
            text(
                "SELECT expires FROM player_entitlements "
                "WHERE steam_id=:s AND group_name='Gamma'"
            ),
            {"s": USER_STEAM},
        ).fetchone()
    finally:
        _app_module._release_db_session(db)

    assert row and row[0] is not None
    exp = row[0]
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp.replace("Z", "+00:00"))
    if getattr(exp, "tzinfo", None) is None:
        exp = exp.replace(tzinfo=timezone.utc)
    remaining = (exp - datetime.now(timezone.utc)).total_seconds()
    # ~10 + 30 ≈ 40 dias
    assert remaining >= 38 * 86400
    assert remaining <= 42 * 86400
    ents = _app_module._get_player_entitlements(USER_STEAM)
    assert {e["group"] for e in ents} == {"Gamma", "Alfa"}


def test_keyvault_does_not_count_toward_paid_cap():
    db = _app_module._SessionLocal()
    try:
        _app_module._apply_entitlement_grant_tx(
            db, USER_STEAM, "Gamma", 30, source="t1", notes="g",
        )
        _app_module._apply_entitlement_grant_tx(
            db, USER_STEAM, "Alfa", 30, source="t2", notes="a",
        )
        _app_module._apply_entitlement_grant_tx(
            db, USER_STEAM, "keyvault", 30, source="nuvem", notes="k",
        )
        db.commit()
    finally:
        _app_module._release_db_session(db)

    ents = _app_module._get_player_entitlements(USER_STEAM)
    assert {e["group"] for e in ents} == {"Gamma", "Alfa", "keyvault"}


def test_timed_points_all_licenses_sum():
    # StackRewards=true: Default + todos os bónus activos somam
    # Default 25 + Gamma 25 + Alfa 75 = 125
    assert _app_module._compute_timed_points_total(["Gamma", "Alfa"]) == 125
    assert _app_module._compute_timed_points_total(["Gamma"]) == 50
    assert _app_module._compute_timed_points_total([]) == 25
    # Felipe: Alfa + Delta (+ keyvault 0) = 25 + 75 + 5 = 105
    assert _app_module._compute_timed_points_total(
        ["Alfa", "Delta", "keyvault"],
    ) == 105
    # 3+ pagos: todos somam
    assert _app_module._compute_timed_points_total(
        ["Gamma", "Beta", "Alfa"],
    ) == 175  # 25 + 25 + 50 + 75
    assert _app_module._compute_timed_points_total(
        ["Gamma", "Beta", "Alfa", "STAFF"],
    ) == 1175  # 25 + 25 + 50 + 75 + 1000


def test_can_accept_helpers():
    db = _app_module._SessionLocal()
    try:
        ok, _ = _app_module._can_accept_paid_license_tx(db, USER_STEAM, "Gamma")
        assert ok is True
        _app_module._apply_entitlement_grant_tx(db, USER_STEAM, "Gamma", 30)
        _app_module._apply_entitlement_grant_tx(db, USER_STEAM, "Alfa", 30)
        db.commit()
        ok_renew, _ = _app_module._can_accept_paid_license_tx(db, USER_STEAM, "Gamma")
        assert ok_renew is True
        ok_third, err = _app_module._can_accept_paid_license_tx(db, USER_STEAM, "Beta")
        assert ok_third is True
        assert err == ""
    finally:
        _app_module._release_db_session(db)
