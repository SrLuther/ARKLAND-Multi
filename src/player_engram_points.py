"""Pontos de engrama por nível — multiplicador sobre o vanilla (8 pts/nível)."""
from __future__ import annotations

ARK_VANILLA_ENGRAM_POINTS_PER_LEVEL = 8


def engram_points_per_level(multiplier: float) -> int:
    mult = float(multiplier or 1.0)
    if mult <= 0:
        return ARK_VANILLA_ENGRAM_POINTS_PER_LEVEL
    return max(1, int(round(ARK_VANILLA_ENGRAM_POINTS_PER_LEVEL * mult)))


def _read_multiplier(cfg: object) -> float:
    gs = getattr(cfg, "game_settings", None)
    if gs is not None and hasattr(gs, "player_engram_points_multiplier"):
        return float(getattr(gs, "player_engram_points_multiplier", 1.0) or 1.0)
    return float(getattr(cfg, "player_engram_points_multiplier", 1.0) or 1.0)


def should_apply_engram_multiplier(cfg: object) -> bool:
    mult = _read_multiplier(cfg)
    return mult > 0 and abs(mult - 1.0) >= 0.001


def resolve_max_level_for_engrams(cfg: object) -> int:
    from .player_level_ascension import resolve_max_player_level

    level = int(resolve_max_player_level(cfg) or 0)
    return max(1, level)


def build_engram_points_ini_lines(cfg: object) -> list[str]:
    """Linhas OverridePlayerLevelEngramPoints=… (uma por nível)."""
    if not should_apply_engram_multiplier(cfg):
        return []
    mult = _read_multiplier(cfg)
    max_lvl = resolve_max_level_for_engrams(cfg)
    pts = engram_points_per_level(mult)
    return [f"OverridePlayerLevelEngramPoints={pts}"] * max_lvl
