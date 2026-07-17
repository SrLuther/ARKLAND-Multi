"""Testes de reconciliação player_entitlements ↔ ark_permission."""
from __future__ import annotations

from src.permission_entitlements_sync import (
    _build_target_from_entitlements,
    _is_player_perm_irregular,
    _parse_timed_groups,
    _preserved_manual_groups,
    normalize_entitlement_group,
    reconcile_entitlements_with_permission_db,
    sync_entitlements_to_permission_db,
)


def test_build_target_from_entitlements_mixed():
    ents = [
        {"group": "Alfa", "expires_at": "2026-12-31T00:00:00+00:00", "permanent": False},
        {"group": "STAFF", "expires_at": None, "permanent": True},
    ]
    perm, timed = _build_target_from_entitlements(ents)
    assert "STAFF" in perm
    assert "Alfa" in timed
    assert "Beta" not in timed


def test_is_irregular_detects_missing_timed_license():
    ents = [{"group": "Alfa", "expires_at": "2026-12-31T00:00:00+00:00", "permanent": False}]
    assert _is_player_perm_irregular(ents, "Default,", "") is True


def test_is_irregular_ok_when_matching():
    ents = [{"group": "Alfa", "expires_at": "2026-12-31T00:00:00+00:00", "permanent": False}]
    _, timed = _build_target_from_entitlements(ents)
    tpg = f"0;{timed['Alfa']};Alfa,"
    assert _is_player_perm_irregular(ents, "Default,", tpg) is False


def test_is_irregular_staff_alias_mod_vs_moderacao():
    ents = [{"group": "Moderacao", "expires_at": None, "permanent": True}]
    assert _is_player_perm_irregular(ents, "Default,Mod,", "") is False


def test_preserved_manual_groups():
    assert _preserved_manual_groups(["Default", "Admins", "VIP", "Alfa"]) == ["VIP"]


def test_reconcile_requires_mysql_url():
    res = reconcile_entitlements_with_permission_db("")
    assert res["ok"] is False


def test_sync_entitlements_requires_url():
    res = sync_entitlements_to_permission_db("", "76561199333584164", [])
    assert res["ok"] is False


def test_parse_timed_groups_roundtrip():
    raw = "0;1792799475;Alfa,"
    assert _parse_timed_groups(raw)["Alfa"] == 1792799475


def test_normalize_entitlement_group_legacy_sku():
    assert normalize_entitlement_group("licenca_delta") == "Delta"
    assert normalize_entitlement_group("licença_delta") == "Delta"
    assert normalize_entitlement_group("LICENCA_DELTA_RENOVACAO") == "Delta"
    assert normalize_entitlement_group("licenca_nuvem") == "keyvault"
    assert normalize_entitlement_group("Delta") == "Delta"
    assert normalize_entitlement_group("keyvault") == "keyvault"
    assert normalize_entitlement_group("Moderacao") == "Moderacao"
    assert normalize_entitlement_group("GrupoManual") == "GrupoManual"


def test_build_target_normalizes_legacy_sku_entitlement():
    """Entitlement legado `licenca_delta` deve virar timed Delta em ark_permission."""
    ents = [{"group": "licenca_delta", "expires_at": "2026-12-31T00:00:00+00:00", "permanent": False}]
    perm, timed = _build_target_from_entitlements(ents)
    assert "Delta" in timed
    assert "licenca_delta" not in timed
    assert "licenca_delta" not in perm


def test_is_irregular_detects_raw_sku_in_timed_groups():
    """TimedPermissionGroups com SKU cru (plugin dá +0) tem de ser reescrito."""
    ents = [{"group": "licenca_delta", "expires_at": "2026-12-31T00:00:00+00:00", "permanent": False}]
    _, timed = _build_target_from_entitlements(ents)
    tpg_raw_sku = "0;1792799475;licenca_delta,"
    assert _is_player_perm_irregular(ents, "Default,", tpg_raw_sku) is True
    tpg_ok = f"0;{timed['Delta']};Delta,"
    assert _is_player_perm_irregular(ents, "Default,", tpg_ok) is False


def test_preserved_manual_groups_drops_legacy_sku():
    assert _preserved_manual_groups(
        ["Default", "licenca_delta", "VIP", "Alfa"]
    ) == ["VIP"]
