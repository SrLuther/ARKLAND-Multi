"""Testes de sincronização arkland_shop → ark_permission."""
from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[3]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from src.permission_entitlements_sync import (
    _format_permission_groups,
    _format_timed_groups,
    _is_permanent_group,
    _parse_timed_groups,
    _split_csv_groups,
    grant_group_in_permission_db,
    sync_entitlements_to_permission_db,
)

def test_parse_and_format_timed_groups():
    raw = "0;1792799475;Alfa,0;1790643056;Beta,"
    parsed = _parse_timed_groups(raw)
    assert parsed["Alfa"] == 1792799475
    assert parsed["Beta"] == 1790643056
    out = _format_timed_groups(parsed)
    assert "0;1790643056;Beta" in out
    assert "0;1792799475;Alfa" in out


def test_format_permission_groups_always_default():
    assert _format_permission_groups(["STAFF"]) == "Default,STAFF,"
    assert _split_csv_groups("Default,Admins,STAFF,") == ["Default", "Admins", "STAFF"]


def test_is_permanent_group():
    assert _is_permanent_group("STAFF", 0) is True
    assert _is_permanent_group("Moderacao", 30) is True
    assert _is_permanent_group("Alfa", 30) is False
    assert _is_permanent_group("keyvault", 30) is False


def test_grant_requires_valid_url():
    res = grant_group_in_permission_db("", "76561199333584164", "Alfa", days=30)
    assert res["ok"] is False


def test_grant_extends_existing_timed_expiry(monkeypatch):
    """Renovação soma dias ao expiry actual em ark_permission (não substitui por now+days)."""
    import time
    from unittest.mock import MagicMock

    now = int(time.time())
    existing_exp = now + 17 * 86400
    captured: dict = {}

    class FakeConn:
        def execute(self, statement, params=None):
            sql = str(statement)
            if "SELECT Id FROM players" in sql:
                return MagicMock(fetchone=lambda: (1,))
            if "SELECT PermissionGroups" in sql:
                tpg = f"0;{existing_exp};keyvault,"
                return MagicMock(fetchone=lambda: ("Default,", tpg))
            if "UPDATE players SET" in sql:
                captured["params"] = dict(params or {})
                return MagicMock()
            return MagicMock(fetchone=lambda: None)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class FakeEngine:
        def begin(self):
            return FakeConn()

        def dispose(self):
            pass

    monkeypatch.setattr(
        "src.permission_entitlements_sync._perm_engine",
        lambda _url: FakeEngine(),
    )
    res = grant_group_in_permission_db(
        "mysql+pymysql://u:p@localhost/arkland_shop",
        "76561199333584164",
        "keyvault",
        days=30,
    )
    assert res["ok"] is True
    tpg = captured["params"]["tpg"]
    parsed = _parse_timed_groups(tpg)
    assert "keyvault" in parsed
    # ~17d residual + 30d ≈ 47d (tolerância 2h)
    expected = existing_exp + 30 * 86400
    assert abs(parsed["keyvault"] - expected) < 120


def test_sync_entitlements_builds_timed_and_staff():
    ents = [
        {"group": "Alfa", "expires_at": "2026-12-31T00:00:00+00:00", "permanent": False},
        {"group": "STAFF", "expires_at": None, "permanent": True},
    ]
    res = sync_entitlements_to_permission_db("", "76561199333584164", ents)
    assert res["ok"] is False
