"""Pontos de engrama por nível — valor fixo ARKLAND (400 pts/nível)."""
from __future__ import annotations

import re

ARK_ENGRAM_POINTS_PER_LEVEL = 400
# Legado — referência vanilla; não usado na geração automática.
ARK_VANILLA_ENGRAM_POINTS_PER_LEVEL = 8

_ENGRAM_RAW_LINE_RE = re.compile(
    r"^\s*overrideplayerlevelengrampoints\s*=",
    re.IGNORECASE,
)


def engram_points_per_level(_multiplier: float | None = None) -> int:
    """Pontos de engrama por level-up — fixo 400 no ARKLAND."""
    return ARK_ENGRAM_POINTS_PER_LEVEL


def should_apply_engram_overrides(cfg: object) -> bool:
    """Gera OverridePlayerLevelEngramPoints só com progressões custom e nível base."""
    from .player_level_ramp import _resolve_base_level, is_player_level_progressions_enabled

    return is_player_level_progressions_enabled(cfg) and _resolve_base_level(cfg) > 0


def should_apply_engram_multiplier(cfg: object) -> bool:
    """Alias legado."""
    return should_apply_engram_overrides(cfg)


def strip_engram_points_from_raw(raw: str) -> str:
    """Remove OverridePlayerLevelEngramPoints do bruto — gerado automaticamente."""
    if not raw or not str(raw).strip():
        return ""
    kept: list[str] = []
    for line in str(raw).splitlines():
        if _ENGRAM_RAW_LINE_RE.match(line.strip()):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def resolve_ramp_entries_for_engrams(cfg: object) -> int:
    """Uma linha de engrama por slot da rampa (base + 75 ascensão)."""
    from .player_level_ascension import _difficulty_fallback_level
    from .player_level_ramp import _resolve_base_level, get_ramp_entry_count, total_ramp_slots

    base = _resolve_base_level(cfg)
    if base > 0:
        return total_ramp_slots(base)
    ramp = get_ramp_entry_count(cfg)
    if ramp > 0:
        return ramp
    return max(1, _difficulty_fallback_level(cfg))


def resolve_max_level_for_engrams(cfg: object) -> int:
    return resolve_ramp_entries_for_engrams(cfg)


def build_engram_points_ini_lines(cfg: object) -> list[str]:
    """Linhas OverridePlayerLevelEngramPoints=400 (uma por nível na rampa)."""
    if not should_apply_engram_overrides(cfg):
        return []
    max_lvl = resolve_max_level_for_engrams(cfg)
    pts = engram_points_per_level()
    return [f"OverridePlayerLevelEngramPoints={pts}"] * max_lvl
