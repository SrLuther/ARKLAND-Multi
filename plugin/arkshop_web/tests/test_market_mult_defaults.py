"""Defaults de multiplicadores — arquivo e endpoint."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market_economy import build_multipliers_from_defaults, load_defaults_file, load_tier_legend


def test_defaults_file_loads():
    data = load_defaults_file()
    assert isinstance(data.get("species"), list)
    assert len(data["species"]) >= 1
    assert "S+" in data.get("_tier_legend", {})


def test_load_tier_legend_order():
    legend = load_tier_legend()
    keys = list(legend.keys())
    assert keys.index("S+") < keys.index("B")
    assert legend["A"]


def test_build_multipliers_from_defaults_rex():
    mults = build_multipliers_from_defaults("rex")
    assert mults["melee"].multiplier > 0
    assert mults["melee"].enabled is True
    assert mults["food"].multiplier == 0 or not mults["food"].enabled
