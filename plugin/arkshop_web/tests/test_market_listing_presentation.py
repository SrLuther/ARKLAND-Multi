"""Testes de personalização de anúncios do mercado."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

from market_listings import (
    CUSTOM_DESC_MAX,
    CUSTOM_NAME_MAX,
    validate_custom_description,
    validate_custom_name,
    validate_listing_category,
)

def test_validate_custom_name_max_length():
    ok = "A" * CUSTOM_NAME_MAX
    assert validate_custom_name(ok) == ok
    with pytest.raises(ValueError, match=str(CUSTOM_NAME_MAX)):
        validate_custom_name("A" * (CUSTOM_NAME_MAX + 1))


def test_validate_custom_description_strips_html():
    assert validate_custom_description("<b>Olá</b> mundo") == "Olá mundo"
    with pytest.raises(ValueError, match=str(CUSTOM_DESC_MAX)):
        validate_custom_description("x" * (CUSTOM_DESC_MAX + 1))


def test_validate_listing_category():
    assert validate_listing_category("S+") == "S+"
    assert validate_listing_category("") is None
    with pytest.raises(ValueError, match="Categoria inválida"):
        validate_listing_category("Z")

