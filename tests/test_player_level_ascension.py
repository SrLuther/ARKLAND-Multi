"""Testes do modelo de níveis do jogador."""
from __future__ import annotations

from dataclasses import dataclass

from src.player_level_ascension import (
    ARK_DEFAULT_BASE_LEVEL,
    ARK_TOTAL_BONUS_LEVELS,
    calc_max_total_level,
    calc_total_player_level,
    level_to_xp,
    resolve_max_player_level,
    xp_to_level,
)
from src.server_config_snapshot import compute_max_player_level


def test_max_total_level_base_plus_100():
    assert calc_max_total_level(120) == 220
    assert calc_max_total_level(ARK_DEFAULT_BASE_LEVEL) == ARK_DEFAULT_BASE_LEVEL + ARK_TOTAL_BONUS_LEVELS
    assert calc_total_player_level(120) == 220


def test_xp_level_roundtrip():
    lvl = 180
    xp = level_to_xp(lvl)
    assert xp_to_level(xp) == lvl


@dataclass
class _TekSrv:
    enable_difficulty_override: bool = True
    override_official_difficulty: float = 5.0
    override_max_xp_player: int = 0
    player_base_level: int = 0
    player_ascension_state: str = ""


def test_compute_max_player_level_difficulty_fallback():
    srv = _TekSrv()
    assert compute_max_player_level(srv) == 180


def test_engram_points_fixed_400():
    from dataclasses import dataclass, field

    from src.player_engram_points import (
        ARK_ENGRAM_POINTS_PER_LEVEL,
        build_engram_points_ini_lines,
        engram_points_per_level,
        strip_engram_points_from_raw,
    )
    from src.player_level_ramp import total_ramp_slots

    assert engram_points_per_level() == ARK_ENGRAM_POINTS_PER_LEVEL == 400

    raw = (
        "LevelExperienceRampOverrides=(ExperiencePointsForLevel[0]=10)\n"
        "OverridePlayerLevelEngramPoints=8\n"
    )
    stripped = strip_engram_points_from_raw(raw)
    assert "OverridePlayerLevelEngramPoints" not in stripped
    assert "LevelExperienceRampOverrides" in stripped

    @dataclass
    class _Gs:
        player_base_level: int = 120

    @dataclass
    class _Srv:
        game_settings: _Gs = field(default_factory=_Gs)
        player_base_level: int = 120

    lines = build_engram_points_ini_lines(_Srv())
    assert len(lines) == total_ramp_slots(120)
    assert all(ln == "OverridePlayerLevelEngramPoints=400" for ln in lines)
