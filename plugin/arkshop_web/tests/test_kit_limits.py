"""Testes para limite de resgates de kits (DefaultAmount)."""
from __future__ import annotations

import json

from kit_limits import (
    change_kit_amount,
    get_kit_remaining,
    kit_default_amount,
    kit_has_limit,
    kit_limit_status,
    kit_requires_license_group,
    parse_kit_stash,
    reset_kit_limit,
    reset_kit_limits_for_license,
)


def test_kit_default_amount_from_config():
    assert kit_default_amount({"DefaultAmount": 3}) == 3
    assert kit_default_amount({}) == 0
    assert kit_default_amount({"DefaultAmount": 0}) == 0


def test_kit_has_limit():
    assert kit_has_limit({"DefaultAmount": 3}) is True
    assert kit_has_limit({"DefaultAmount": 0}) is False
    assert kit_has_limit({}) is False


def test_get_kit_remaining_uses_default_when_no_stash():
    entry = {"DefaultAmount": 3, "Description": "Starter"}
    assert get_kit_remaining({}, "starter", entry) == 3


def test_get_kit_remaining_uses_stash_when_present():
    entry = {"DefaultAmount": 3}
    stash = {"starter": {"Amount": 1}}
    assert get_kit_remaining(stash, "starter", entry) == 1


def test_change_kit_amount_decrements_after_delivery():
    entry = {"DefaultAmount": 3}
    stash = change_kit_amount({}, "starter", -1, entry)
    assert stash["starter"]["Amount"] == 2


def test_change_kit_amount_clamps_at_zero():
    entry = {"DefaultAmount": 1}
    stash = change_kit_amount({"starter": {"Amount": 0}}, "starter", -1, entry)
    assert stash["starter"]["Amount"] == 0


def test_reset_kit_limit_restores_default():
    entry = {"DefaultAmount": 3}
    stash = {"starter": {"Amount": 0}}
    restored = reset_kit_limit(stash, "starter", entry)
    assert restored["starter"]["Amount"] == 3


def test_kit_limit_status_with_pending():
    entry = {"DefaultAmount": 3}
    status = kit_limit_status({"starter": {"Amount": 2}}, "starter", entry, pending_orders=1)
    assert status["limit"] == 3
    assert status["remaining"] == 2
    assert status["used"] == 1
    assert status["effective_remaining"] == 1


def test_parse_kit_stash_json_string():
    raw = json.dumps({"starter": {"Amount": 2}})
    assert parse_kit_stash(raw)["starter"]["Amount"] == 2


def test_kit_requires_license_group():
    alfa_kit = {"DefaultAmount": 1, "Permissions": "Admins,Alfa"}
    beta_kit = {"DefaultAmount": 1, "Permissions": "Admins,Beta"}
    assert kit_requires_license_group(alfa_kit, "Alfa") is True
    assert kit_requires_license_group(alfa_kit, "Beta") is False
    assert kit_requires_license_group(beta_kit, "Beta") is True
    assert kit_requires_license_group({"DefaultAmount": 1}, "Alfa") is False


def test_reset_kit_limits_for_license_only_matching_kits():
    catalog = {
        "kit_alfa": {
            "DefaultAmount": 1,
            "Permissions": "Admins,Alfa",
        },
        "kit_beta": {
            "DefaultAmount": 1,
            "Permissions": "Admins,Beta",
        },
        "kit_free": {
            "DefaultAmount": 0,
            "Permissions": "Admins,Alfa",
        },
    }
    stash = {"kit_alfa": {"Amount": 0}, "kit_beta": {"Amount": 0}}
    new_stash, reset_ids = reset_kit_limits_for_license(stash, catalog, "Alfa")
    assert reset_ids == ["kit_alfa"]
    assert get_kit_remaining(new_stash, "kit_alfa", catalog["kit_alfa"]) == 1
    assert get_kit_remaining(new_stash, "kit_beta", catalog["kit_beta"]) == 0
