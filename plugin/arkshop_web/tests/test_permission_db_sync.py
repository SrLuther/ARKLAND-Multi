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


def test_sync_entitlements_builds_timed_and_staff():
    ents = [
        {"group": "Alfa", "expires_at": "2026-12-31T00:00:00+00:00", "permanent": False},
        {"group": "STAFF", "expires_at": None, "permanent": True},
    ]
    res = sync_entitlements_to_permission_db("", "76561199333584164", ents)
    assert res["ok"] is False
