"""SKU `licenca_*` ≠ PermissionGroup — TimedPoints UI e grant devem usar o grupo canónico."""
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

USER_STEAM = "76561198000000099"
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
    yield


def test_normalize_licenca_sku_to_permission_group():
    assert _app_module._normalize_entitlement_group("licenca_delta") == "Delta"
    assert _app_module._normalize_entitlement_group("licenca_gamma_renovacao") == "Gamma"
    assert _app_module._normalize_entitlement_group("Delta") == "Delta"
    assert _app_module._normalize_entitlement_group("keyvault") == "keyvault"
    assert _app_module._normalize_entitlement_group("licenca_imaterial") == "Imaterial"


def test_normalize_legacy_sku_variants_accents_case_whitespace():
    """Rows legadas com acento/caixa/espaços não podem escapar da normalização (+0 na UI)."""
    assert _app_module._normalize_entitlement_group("licença_delta") == "Delta"
    assert _app_module._normalize_entitlement_group("Licenca_Delta") == "Delta"
    assert _app_module._normalize_entitlement_group("LICENCA_DELTA") == "Delta"
    assert _app_module._normalize_entitlement_group(" licenca_delta ") == "Delta"
    assert _app_module._normalize_entitlement_group("licenca_delta\u00a0") == "Delta"
    assert _app_module._normalize_entitlement_group("Licença Delta") == "Delta"
    assert _app_module._normalize_entitlement_group("delta") == "Delta"
    assert _app_module._normalize_entitlement_group("licença_gamma_renovacao") == "Gamma"
    # keyvault continua sem alias forçado nem bónus.
    assert _app_module._normalize_entitlement_group("licenca_nuvem") == "keyvault"
    assert _app_module._timed_points_bonus_for_group("licença_delta") == 5
    assert _app_module._timed_points_bonus_for_group("keyvault") == 0


def test_grant_licenca_delta_sku_stores_canonical_delta():
    db = _app_module._SessionLocal()
    try:
        _app_module._apply_entitlement_grant_tx(
            db, USER_STEAM, "licenca_delta", 30, source="sku-test", notes="web:licenca_delta",
        )
        db.commit()
        row = db.execute(
            text(
                "SELECT group_name FROM player_entitlements "
                "WHERE steam_id = :s"
            ),
            {"s": USER_STEAM},
        ).fetchone()
    finally:
        _app_module._release_db_session(db)

    assert row is not None
    assert row[0] == "Delta"


def test_ui_bonus_for_legacy_sku_row_shows_delta_amount():
    """Linha legada `licenca_delta` deve aparecer como Delta +5 (não +0)."""
    future = (datetime.now(timezone.utc) + timedelta(days=20)).replace(tzinfo=None)
    db = _app_module._SessionLocal()
    try:
        db.execute(
            text(
                "INSERT INTO player_entitlements "
                "(steam_id, group_name, expires, source, notes) "
                "VALUES (:s, 'licenca_delta', :exp, 'legacy', 'sku')"
            ),
            {"s": USER_STEAM, "exp": future},
        )
        db.execute(
            text(
                "INSERT INTO player_entitlements "
                "(steam_id, group_name, expires, source, notes) "
                "VALUES (:s, 'keyvault', :exp, 'nuvem', 'k')"
            ),
            {"s": USER_STEAM, "exp": future},
        )
        db.commit()
    finally:
        _app_module._release_db_session(db)

    ents = _app_module._get_player_entitlements(USER_STEAM)
    by_g = {e["group"]: e for e in ents}
    assert "Delta" in by_g
    assert "licenca_delta" not in by_g
    assert by_g["Delta"]["timed_points_bonus"] == 5
    assert by_g["keyvault"]["timed_points_bonus"] == 0


def test_timed_total_with_sku_delta_and_imaterial():
    # StackRewards=true: Default 25 + Moderacao 500 + Imaterial 180 + Delta 5 = 710
    assert _app_module._compute_timed_points_total(
        ["Moderacao", "keyvault", "Imaterial", "licenca_delta"]
    ) == 710
    # Só Delta + Default = 30
    assert _app_module._compute_timed_points_total(["licenca_delta"]) == 30
    # Felipe Alfa+Delta: 25 + 75 + 5 = 105
    assert _app_module._compute_timed_points_total(["Alfa", "Delta"]) == 105


def test_repair_renames_sku_group_in_db():
    future = (datetime.now(timezone.utc) + timedelta(days=15)).replace(tzinfo=None)
    db = _app_module._SessionLocal()
    try:
        db.execute(
            text(
                "INSERT INTO player_entitlements "
                "(steam_id, group_name, expires, source, notes) "
                "VALUES (:s, 'licenca_exotico', :exp, 'x', 'sku')"
            ),
            {"s": USER_STEAM, "exp": future},
        )
        db.commit()
    finally:
        _app_module._release_db_session(db)

    n = _app_module._repair_entitlement_sku_group_names(_app_module._ENGINE)
    assert n >= 1
    db = _app_module._SessionLocal()
    try:
        row = db.execute(
            text(
                "SELECT group_name FROM player_entitlements WHERE steam_id = :s"
            ),
            {"s": USER_STEAM},
        ).fetchone()
    finally:
        _app_module._release_db_session(db)
    assert row[0] == "Exotico"


def test_api_entitlements_legacy_sku_row_returns_canonical_delta():
    """GET /api/player/entitlements com row legada `licenca_delta`:
    UI recebe Delta + bónus configurado e total inclui o tier (30 = 25 Default + 5 Delta)."""
    future = (datetime.now(timezone.utc) + timedelta(days=20)).replace(tzinfo=None)
    db = _app_module._SessionLocal()
    try:
        db.execute(
            text(
                "INSERT INTO player_entitlements "
                "(steam_id, group_name, expires, source, notes) "
                "VALUES (:s, 'licenca_delta', :exp, 'legacy', 'sku')"
            ),
            {"s": USER_STEAM, "exp": future},
        )
        db.commit()
    finally:
        _app_module._release_db_session(db)

    expected_bonus = _app_module._timed_points_groups_amounts().get(
        "Delta", _app_module.LICENSE_TIMED_BONUS["Delta"]
    )
    with _app_module.app.test_client() as client:
        with client.session_transaction() as sess:
            sess["steam_id"] = USER_STEAM
        r = client.get("/api/player/entitlements")
        assert r.status_code == 200
        d = r.get_json()
    assert d["ok"] is True
    groups = {e["group"]: e for e in d["entitlements"]}
    assert "Delta" in groups
    assert "licenca_delta" not in groups
    assert groups["Delta"]["timed_points_bonus"] == expected_bonus
    default = _app_module._timed_points_groups_amounts().get("Default", 25)
    assert d["timed_points_total"] == default + expected_bonus


def test_repair_renames_accented_legacy_sku_row():
    """Row legada com acento («licença_delta») também é reparada para Delta."""
    future = (datetime.now(timezone.utc) + timedelta(days=15)).replace(tzinfo=None)
    db = _app_module._SessionLocal()
    try:
        db.execute(
            text(
                "INSERT INTO player_entitlements "
                "(steam_id, group_name, expires, source, notes) "
                "VALUES (:s, :grp, :exp, 'legacy', 'sku-acentuado')"
            ),
            {"s": USER_STEAM, "grp": "licença_delta", "exp": future},
        )
        db.commit()
    finally:
        _app_module._release_db_session(db)

    n = _app_module._repair_entitlement_sku_group_names(_app_module._ENGINE)
    assert n >= 1
    db = _app_module._SessionLocal()
    try:
        row = db.execute(
            text("SELECT group_name FROM player_entitlements WHERE steam_id = :s"),
            {"s": USER_STEAM},
        ).fetchone()
    finally:
        _app_module._release_db_session(db)
    assert row[0] == "Delta"


def test_all_paid_license_skus_map_to_timed_bonus():
    expected = {
        "licenca_delta": 5,
        "licenca_gamma": 25,
        "licenca_beta": 50,
        "licenca_alfa": 75,
        "licenca_omega": 90,
        "licenca_transcendente": 105,
        "licenca_etereo": 120,
        "licenca_universal": 135,
        "licenca_onipotente": 150,
        "licenca_surreal": 165,
        "licenca_imaterial": 180,
        "licenca_exotico": 200,
    }
    for sku, amount in expected.items():
        g = _app_module._normalize_entitlement_group(sku)
        assert g in _app_module.PAID_LICENSE_GROUPS
        assert _app_module._timed_points_bonus_for_group(sku) == amount
        assert _app_module.LICENSE_TIMED_BONUS[g] == amount
