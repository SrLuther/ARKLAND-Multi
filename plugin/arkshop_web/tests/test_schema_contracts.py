"""Contratos de tamanho de coluna — SQLite não valida VARCHAR(N); MySQL sim.

Ver SCHEMA_CONTRACTS.md. Estes testes falham se um ID de produção (ou pior caso
conhecido) exceder o length do modelo SQLAlchemy — mesmo sob SQLite.
"""
from __future__ import annotations

import re

import pytest

from app import Order, _ORDERS_ORIGINAL_ORDER_ID_WIDTH

# Fixtures reais de prod (Felipe Matt / SeasonLand claim DataError 1406).
_PROD_SEASON = "season-delta-20240715032535"
_ADMIN_SKIP_PREFIX = "__admin_skip_kit_limit__|"

_WORST_DINO_ID = (
    f"sp:{_PROD_SEASON}:premium:8:dino:sb_crystal_ember_l200"
)
_WORST_KIT_ID = (
    f"{_ADMIN_SKIP_PREFIX}sp:{_PROD_SEASON}:premium:10:kit:noglin_pack10"
)


def _sa_string_length(column) -> int:
    length = getattr(getattr(column, "type", None), "length", None)
    assert length is not None, f"{column} sem length (TEXT/ilimitado?)"
    return int(length)


def test_orders_original_order_id_width_constant_matches_model():
    assert _sa_string_length(Order.original_order_id) == _ORDERS_ORIGINAL_ORDER_ID_WIDTH
    assert _ORDERS_ORIGINAL_ORDER_ID_WIDTH >= 191


@pytest.mark.parametrize(
    "label,value",
    [
        ("dino_sp_idem", _WORST_DINO_ID),
        ("kit_skip_prefix_sp_idem", _WORST_KIT_ID),
    ],
)
def test_seasonland_prod_original_order_ids_fit_column(label, value):
    """IDs que rebentaram VARCHAR(64) em prod devem caber no modelo actual."""
    max_len = _sa_string_length(Order.original_order_id)
    assert len(value) > 64, f"{label}: fixture deve exceder o schema antigo ({len(value)})"
    assert len(value) <= max_len, (
        f"{label}: len={len(value)} > Order.original_order_id VARCHAR({max_len}) — "
        f"alarga a coluna / migrate (SQLite não apanha isto). value={value!r}"
    )


def test_seasonland_idem_builder_budget():
    """Budget explícito: sp + season longo + track + level + tipo + sku + skip kit."""
    season = _PROD_SEASON
    track, level, gtype, gid = "premium", 10, "kit", "noglin_pack10"
    raw = f"sp:{season}:{track}:{level}:{gtype}:{gid}"
    stored = f"{_ADMIN_SKIP_PREFIX}{raw}"
    max_len = _sa_string_length(Order.original_order_id)
    assert stored.startswith(_ADMIN_SKIP_PREFIX)
    assert re.fullmatch(r"sp:[^:]+:(?:free|premium):\d+:(?:kit|item|dino):.+", raw)
    assert len(stored) <= max_len
    # Margem para SKUs um pouco maiores que o caso Felipe (item_id até 128 no Order).
    headroom = max_len - len(stored)
    assert headroom >= 32, (
        f"pouca margem ({headroom}) para SKUs longos — considera VARCHAR maior"
    )
