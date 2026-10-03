"""Defaults de multiplicadores — arquivo e endpoint."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market_economy import (
    STAT_KEYS,
    build_multipliers_from_defaults,
    invalidate_defaults_cache,
    load_defaults_file,
    load_tier_legend,
)


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
    """O defaults do repo (floor_quality, v1.10.19+) não traz ``multipliers`` por espécie.

    Os multiplicadores por stat só existem para o modo ``legacy_multipliers``; sem dados no
    JSON o builder devolve todos os stats com multiplicador 0 e desabilitados — nunca omite chaves.
    """
    species = {s["species_key"]: s for s in load_defaults_file()["species"]}
    assert "multipliers" not in species["rex"]
    assert species["rex"]["pricing_mode"] == "floor_quality"
    mults = build_multipliers_from_defaults("rex")
    assert set(mults) == set(STAT_KEYS)
    assert all(m.multiplier == 0 and m.enabled is False for m in mults.values())


def test_build_multipliers_from_explicit_legacy_defaults(tmp_path, monkeypatch):
    """Com ``multipliers`` no JSON (formato legado) o builder os respeita."""
    import market_economy as me

    path = tmp_path / "market_species_defaults.json"
    path.write_text(
        json.dumps(
            {
                "species": [
                    {
                        "species_key": "rex",
                        "multipliers": {"health": 84, "melee": 720, "weight": 108, "food": 0},
                    }
                ],
                "global_stat_labels": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(me, "_DEFAULTS_FILE", path)
    invalidate_defaults_cache()
    mults = build_multipliers_from_defaults("rex")
    assert mults["melee"].multiplier == 720
    assert mults["melee"].enabled is True
    assert mults["health"].multiplier == 84
    assert mults["food"].multiplier == 0 and not mults["food"].enabled
    invalidate_defaults_cache()
