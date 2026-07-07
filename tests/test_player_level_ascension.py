"""Testes do modelo de níveis do jogador."""
from __future__ import annotations

from dataclasses import dataclass

from src.player_level_ascension import (
    ARK_DEFAULT_BASE_LEVEL,
    ASCENSION_BOSSES,
    EXTRA_BONUSES,
    calc_total_player_level,
    level_to_xp,
    resolve_max_player_level,
    xp_to_level,
)
from src.server_config_snapshot import compute_max_player_level


def test_vanilla_reference_total_220():
    """Referência wiki: 105 base + 6×15 bosses + extras até 220 (Steam)."""
    bosses = {bid: 0 for bid, _, _ in ASCENSION_BOSSES}
    for bid in ("island", "scorched", "aberration", "genesis1", "genesis2"):
        bosses[bid] = 3  # alpha
    extras = {
        "explorer_notes": True,
        "fjordur_runes": True,
        "chibi": True,
        "aquatica": False,
        "pygocentrus": True,
    }
    total = calc_total_player_level(ARK_DEFAULT_BASE_LEVEL, bosses, extras)
    # 105 + 5*15 + 10 + 10 + 5 + 15 = 105 + 75 + 40 = 220
    assert total == 220


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


def test_engram_points_multiplier_5x():
    from dataclasses import dataclass, field

    from src.player_engram_points import (
        build_engram_points_ini_lines,
        engram_points_per_level,
        strip_engram_points_from_raw,
    )

    assert engram_points_per_level(5.0) == 40
    assert engram_points_per_level(1.0) == 8

    raw = (
        "LevelExperienceRampOverrides=(ExperiencePointsForLevel[0]=10)\n"
        "OverridePlayerLevelEngramPoints=8\n"
        "OverridePlayerLevelEngramPoints=8\n"
    )
    stripped = strip_engram_points_from_raw(raw)
    assert "OverridePlayerLevelEngramPoints" not in stripped
    assert "LevelExperienceRampOverrides" in stripped

    @dataclass
    class _Gs:
        player_base_level: int = 105
        player_engram_points_multiplier: float = 5.0
        override_official_difficulty: float = 5.0

    @dataclass
    class _Srv:
        game_settings: _Gs = field(default_factory=_Gs)

    lines = build_engram_points_ini_lines(_Srv())
    assert len(lines) == 105
    assert lines[0] == "OverridePlayerLevelEngramPoints=40"
    assert all(ln == "OverridePlayerLevelEngramPoints=40" for ln in lines)


def test_engram_points_asm_tek_difficulty_180_levels():
    from dataclasses import dataclass

    from src.player_engram_points import build_engram_points_ini_lines

    @dataclass
    class _AsmTek:
        enable_difficulty_override: bool = True
        override_official_difficulty: float = 5.0
        player_engram_points_multiplier: float = 5.0
        player_base_level: int = 0
        player_ascension_state: str = ""

    lines = build_engram_points_ini_lines(_AsmTek())
    assert len(lines) == 180
    assert all(ln == "OverridePlayerLevelEngramPoints=40" for ln in lines)
