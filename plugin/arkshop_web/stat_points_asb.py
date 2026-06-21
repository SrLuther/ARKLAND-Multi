"""Port parcial do ASB StatValueCalculation — valor ↔ pontos de breeding."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

# Índices ASB (Stats.cs)
STAT_HEALTH = 0
STAT_STAMINA = 1
STAT_OXYGEN = 3
STAT_FOOD = 4
STAT_WEIGHT = 7
STAT_MELEE = 8
STAT_SPEED = 9

STAT_KEY_TO_INDEX: dict[str, int] = {
    "health": STAT_HEALTH,
    "stamina": STAT_STAMINA,
    "oxygen": STAT_OXYGEN,
    "food": STAT_FOOD,
    "weight": STAT_WEIGHT,
    "melee": STAT_MELEE,
    "speed": STAT_SPEED,
}

PERCENTAGE_STATS = {STAT_MELEE, STAT_SPEED}

_DATA = Path(__file__).resolve().parent / "data" / "asb_species_subset.json"


def _precision(stat_index: int) -> int:
    return 3 if stat_index in PERCENTAGE_STATS else 1


def _is_percentage(stat_index: int) -> bool:
    return stat_index in PERCENTAGE_STATS


def _parse_stat_raw(raw: list | None) -> dict[str, float] | None:
    if not raw or len(raw) < 3:
        return None
    base = float(raw[0])
    inc_wild = float(raw[1])
    inc_tamed = float(raw[2]) if len(raw) > 2 and raw[2] is not None else 0.0
    mut_factor = float(raw[3]) if len(raw) > 3 and raw[3] is not None else 1.0
    mult_affinity = float(raw[4]) if len(raw) > 4 and raw[4] is not None else 0.0
    return {
        "base": base,
        "inc_wild": inc_wild,
        "inc_tamed": inc_tamed,
        "mut_factor": mut_factor,
        "mult_affinity": mult_affinity,
    }


def load_asb_subset() -> dict[str, Any]:
    if not _DATA.is_file():
        return {"species": {}}
    return json.loads(_DATA.read_text(encoding="utf-8"))


def get_species_data(species_key: str) -> dict[str, Any] | None:
    data = load_asb_subset()
    return (data.get("species") or {}).get(species_key)


def _stat_def(species: dict[str, Any], stat_index: int) -> dict[str, float] | None:
    raw_list = species.get("fullStatsRaw") or []
    if stat_index >= len(raw_list):
        return None
    parsed = _parse_stat_raw(raw_list[stat_index])
    if not parsed:
        return None
    parsed["increase_pct"] = _is_percentage(stat_index) or (
        parsed["base"] <= 10 and parsed["inc_wild"] < 1
    )
    return parsed


def calculate_value(
    species: dict[str, Any],
    stat_index: int,
    level_wild: int,
    level_mut: int,
    level_dom: int,
    *,
    dom: bool = True,
    taming_eff: float = 1.0,
    imprint_bonus: float = 1.0,
) -> float:
    st = _stat_def(species, stat_index)
    if not st:
        return 0.0
    if level_wild < 0:
        return -1.0

    add = 0.0
    dom_mult = 1.0
    imprint_m = 1.0
    tamed_base_hp = 1.0
    if dom:
        add = 0.0
        dom_mult_aff = st["mult_affinity"]
        if dom_mult_aff >= 0:
            dom_mult_aff *= taming_eff
        dom_mult = 1.0 + dom_mult_aff if taming_eff >= 0 else 1.0
        if imprint_bonus > 0 and stat_index == STAT_HEALTH:
            imprint_m = 1.0 + 0.2 * imprint_bonus  # Rex default ~0.2 imprint mult on HP
        if stat_index == STAT_HEALTH:
            tamed_base_hp = float(species.get("TamedBaseHealthMultiplier") or 1.0)
    else:
        level_dom = 0

    inc_mut = st["inc_wild"] * st["mut_factor"]
    wild_inc = level_wild * st["inc_wild"] + level_mut * inc_mut
    dom_inc = level_dom * st["inc_tamed"]

    if st["increase_pct"]:
        result = (
            (st["base"] * (1.0 + wild_inc) * tamed_base_hp * imprint_m + add)
            * dom_mult
            * (1.0 + dom_inc)
        )
    else:
        result = (
            ((st["base"] + wild_inc) * tamed_base_hp * imprint_m + add) * dom_mult + dom_inc
        )

    if result <= 0:
        return 0.0
    return round(result, _precision(stat_index))


def _display_aberration(target: float, stat_index: int) -> float:
    if _is_percentage(stat_index):
        return max(0.001, 0.06 * 0.01)
    return max(0.001, 0.06)


def _targets_for_value(value: float, stat_index: int) -> list[float]:
    """Cryopod pode armazenar multiplier ou percentual exibido."""
    out = [value]
    if _is_percentage(stat_index):
        out.extend([value / 100.0, value * 100.0])
    return out


def invert_stat_levels(
    species_key: str,
    stat_key: str,
    max_value: float,
    *,
    imprint_pct: float = 1.0,
    max_wild: int = 450,
    max_mut: int = 58,
    max_dom: int = 88,
) -> tuple[int, int, int] | None:
    """Busca wild/mut/dom que reproduzem max_value (fallback ASB §4.5.2 S3)."""
    species = get_species_data(species_key)
    if not species:
        return None
    stat_index = STAT_KEY_TO_INDEX.get(stat_key)
    if stat_index is None:
        return None

    targets = _targets_for_value(float(max_value), stat_index)
    tol = _display_aberration(max_value, stat_index)
    imprint_bonus = max(0.0, min(1.0, imprint_pct))

    best: tuple[int, int, int] | None = None
    best_err = float("inf")

    for lw in range(max_wild + 1):
        for lm in range(max_mut + 1):
            cap_dom = min(max_dom, lw + lm)
            for ld in range(cap_dom + 1):
                calc = calculate_value(
                    species,
                    stat_index,
                    lw,
                    lm,
                    ld,
                    dom=True,
                    taming_eff=1.0,
                    imprint_bonus=imprint_bonus,
                )
                for tgt in targets:
                    err = abs(calc - tgt)
                    if err <= tol:
                        return lw, lm, ld
                    if err < best_err:
                        best_err = err
                        best = (lw, lm, ld)
    if best and best_err <= tol * 5:
        return best
    return None


def enrich_stats_with_points(
    species_key: str,
    stats_max: dict[str, Any],
    *,
    imprint_pct: float = 1.0,
) -> dict[str, Any]:
    """Preenche stats_max[*].points via cálculo inverso ASB."""
    out: dict[str, Any] = {}
    for sk, val in stats_max.items():
        if isinstance(val, dict):
            entry = dict(val)
            value = float(entry.get("value") or 0)
            if entry.get("points_base") is not None:
                pb = int(entry["points_base"])
                pa = int(entry.get("points_added") or 0)
                entry["points"] = pb + pa
                out[sk] = entry
                continue
            pts = entry.get("points")
            if pts is None and value > 0:
                levels = invert_stat_levels(species_key, sk, value, imprint_pct=imprint_pct)
                if levels:
                    lw, lm, ld = levels
                    entry["points_base"] = int(lw + lm)
                    entry["points_added"] = int(ld)
                    entry["points"] = int(lw + lm + ld)
                    entry["levels_wild"] = lw
                    entry["levels_mut"] = lm
                    entry["levels_dom"] = ld
                else:
                    entry["points"] = 0
            out[sk] = entry
        else:
            out[sk] = val
    return out
