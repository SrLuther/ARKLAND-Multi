"""Testes da rampa de XP e cap efetivo do jogador."""
from __future__ import annotations

from dataclasses import dataclass, field

from src.player_engram_points import build_engram_points_ini_lines
from src.player_level_ascension import (
    ARK_TOTAL_BONUS_LEVELS,
    calc_max_total_level,
    resolve_max_player_level,
    resolve_theoretical_player_level,
)
from src.player_level_ramp import (
    ARK_ASCENSION_RAMP_SLOTS,
    XP_CURVE_CUSTOM,
    XP_CURVE_VANILLA,
    apply_inferred_xp_curve,
    build_ramp_ini_lines,
    build_ramp_values,
    cumulative_xp_on_ramp,
    export_ramp_raw,
    infer_xp_curve_from_ramp,
    parse_ramp_from_text,
    populate_player_ramp_from_game_ini,
    resolve_effective_ingame_cap,
    sync_config_player_level,
    total_ramp_slots,
    xp_to_level_on_ramp,
)
from src.server_config_snapshot import compute_max_player_level


def test_parse_ramp_counts_entries_and_max_index():
    raw = "\n".join(
        f"LevelExperienceRampOverrides=(ExperiencePointsForLevel[{i}]={10 + i})"
        for i in (0, 1, 2, 5, 229)
    )
    parsed = parse_ramp_from_text(raw)
    assert parsed["entry_count"] == 230
    assert parsed["max_index"] == 229
    assert len(parsed["indices"]) == 5


def test_vanilla_ramp_includes_base_plus_75_ascension():
    base = 120
    values = build_ramp_values(base, mode=XP_CURVE_VANILLA)
    assert len(values) == total_ramp_slots(base)
    assert len(values) == base + ARK_ASCENSION_RAMP_SLOTS
    assert cumulative_xp_on_ramp(values, base) > 0
    lines = build_ramp_ini_lines(values)
    assert len(lines) == total_ramp_slots(base)
    assert "ExperiencePointsForLevel[0]" in lines[0]


def test_resolve_effective_cap_is_base_plus_100():
    @dataclass
    class _Srv:
        player_base_level: int = 120
        player_ascension_state: str = ""
        override_max_xp_player: int = 0
        player_ramp_entry_count: int = 0
        player_level_stats_raw: str = ""
        player_xp_curve_mode: str = XP_CURVE_VANILLA

    srv = _Srv()
    sync_config_player_level(srv)
    assert resolve_theoretical_player_level(srv) == 220
    assert resolve_max_player_level(srv) == 220
    assert compute_max_player_level(srv) == 220
    assert srv.player_ramp_entry_count == total_ramp_slots(120)


def test_sync_config_player_level_sets_xp_at_base_not_total():
    @dataclass
    class _Srv:
        player_base_level: int = 105
        player_ascension_state: str = ""
        override_max_xp_player: int = 0
        player_level_stats_raw: str = ""
        player_ramp_entry_count: int = 0
        player_ramp_max_index: int = -1
        player_xp_curve_mode: str = XP_CURVE_VANILLA

    srv = _Srv()
    derived = sync_config_player_level(srv)
    assert derived["theoretical_total"] == calc_max_total_level(105)
    assert derived["ascension_bonus"] == ARK_TOTAL_BONUS_LEVELS
    assert derived["ramp_entries"] == total_ramp_slots(105)
    assert srv.override_max_xp_player == cumulative_xp_on_ramp(
        build_ramp_values(105, mode=XP_CURVE_VANILLA), 105
    )


def test_engram_lines_match_ramp_slots_not_base_only():
    @dataclass
    class _Srv:
        player_base_level: int = 120
        player_engram_points_multiplier: float = 5.0
        player_ascension_state: str = ""
        override_max_xp_player: int = 0

    lines = build_engram_points_ini_lines(_Srv())
    assert len(lines) == total_ramp_slots(120)
    assert all(ln == "OverridePlayerLevelEngramPoints=400" for ln in lines)


def test_xp_to_level_on_ramp():
    values = [10, 20, 30]
    assert xp_to_level_on_ramp(values, 5) == 1
    assert xp_to_level_on_ramp(values, 10) == 2
    assert xp_to_level_on_ramp(values, 100) == 4


def test_compute_max_player_level_difficulty_fallback_unchanged():
    @dataclass
    class _TekSrv:
        enable_difficulty_override: bool = True
        override_official_difficulty: float = 5.0
        override_max_xp_player: int = 0
        player_base_level: int = 0
        player_ascension_state: str = ""

    assert compute_max_player_level(_TekSrv()) == 180


LEGACY_GEOMETRIC_GUS_XP = 4_201_966_627_760


def test_infer_geometric_curve_from_legacy_ramp():
    values = build_ramp_values(165, mode=XP_CURVE_CUSTOM, xp_base=70, xp_mult=1.15)
    inferred = infer_xp_curve_from_ramp(values)
    assert inferred["mode"] == XP_CURVE_CUSTOM
    assert inferred["xp_base"] == 70
    assert abs(inferred["xp_mult"] - 1.15) < 0.01


def test_sync_preserves_geometric_cap_for_legacy_server():
    @dataclass
    class _Srv:
        player_base_level: int = 165
        player_ascension_state: str = ""
        override_max_xp_player: int = LEGACY_GEOMETRIC_GUS_XP
        player_level_stats_raw: str = ""
        player_ramp_entry_count: int = 0
        player_ramp_max_index: int = -1
        player_xp_curve_mode: str = XP_CURVE_VANILLA
        player_xp_curve_base: int = 70
        player_xp_curve_mult: float = 1.15
        player_xp_curve_formula: str = "base * (mult ** i)"

    srv = _Srv()
    srv.player_level_stats_raw = export_ramp_raw(
        build_ramp_values(165, mode=XP_CURVE_CUSTOM, xp_base=70, xp_mult=1.15)
    )
    srv.player_ramp_entry_count = total_ramp_slots(165)
    apply_inferred_xp_curve(srv, build_ramp_values(165, mode=XP_CURVE_CUSTOM))
    assert srv.player_xp_curve_mode == XP_CURVE_CUSTOM

    derived = sync_config_player_level(srv)
    assert srv.override_max_xp_player == LEGACY_GEOMETRIC_GUS_XP
    assert derived["override_xp"] == LEGACY_GEOMETRIC_GUS_XP
    assert derived["theoretical_total"] == calc_max_total_level(165)


def test_vanilla_ramp_stays_vanilla_on_infer():
    values = build_ramp_values(120, mode=XP_CURVE_VANILLA)
    assert infer_xp_curve_from_ramp(values)["mode"] == XP_CURVE_VANILLA
