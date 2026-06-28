"""Testes para limite de resgates de kits (DefaultAmount)."""
from __future__ import annotations

import json

from kit_limits import (
    change_kit_amount,
    get_kit_remaining,
    kit_default_amount,
    kit_has_limit,
    kit_limit_status,
    parse_kit_stash,
    reset_kit_limit,
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
