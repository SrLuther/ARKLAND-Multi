"""Testes da rampa de XP e cap efetivo do jogador."""
from __future__ import annotations

from dataclasses import dataclass, field

from src.player_engram_points import build_engram_points_ini_lines
from src.player_level_ascension import (
    ARK_DEFAULT_BASE_LEVEL,
    ASCENSION_BOSSES,
    calc_total_player_level,
    resolve_max_player_level,
    resolve_theoretical_player_level,
)
from src.player_level_ramp import (
    XP_CURVE_VANILLA,
    build_ramp_ini_lines,
    build_ramp_values,
    cumulative_xp_on_ramp,
    export_ramp_raw,
    parse_ramp_from_text,
    resolve_effective_ingame_cap,
    sync_config_player_level,
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


def test_vanilla_ramp_matches_level_to_xp_at_base():
    base = 120
    values = build_ramp_values(base, mode=XP_CURVE_VANILLA)
    assert len(values) == base
    assert cumulative_xp_on_ramp(values, base) > 0
    lines = build_ramp_ini_lines(values)
    assert len(lines) == base
    assert "ExperiencePointsForLevel[0]" in lines[0]


def test_resolve_effective_cap_uses_min_of_theoretical_ramp_and_xp():
    from src.player_level_ascension import serialize_ascension_state

    values = build_ramp_values(230, mode=XP_CURVE_VANILLA)
    bosses = {bid: 0 for bid, _, _ in ASCENSION_BOSSES}
    for bid in ("island", "scorched", "aberration", "genesis1", "genesis2"):
        bosses[bid] = 3
    extras = {
        "explorer_notes": True,
        "fjordur_runes": True,
        "chibi": True,
        "aquatica": False,
        "pygocentrus": True,
    }
    theoretical = calc_total_player_level(120, bosses, extras)
    assert theoretical > 230
    asc_json = serialize_ascension_state(bosses, extras)

    @dataclass
    class _Srv:
        player_base_level: int = 120
        player_ascension_state: str = asc_json
        override_max_xp_player: int = 0
        player_ramp_entry_count: int = 230
        player_level_stats_raw: str = field(default_factory=lambda: export_ramp_raw(values))
        player_xp_curve_mode: str = XP_CURVE_VANILLA

    srv = _Srv()
    # Cap de XP alinhado ao fim da rampa (230), não só ao nível base.
    srv.override_max_xp_player = cumulative_xp_on_ramp(values, 230)
    effective = resolve_effective_ingame_cap(srv)
    assert effective == 230
    assert resolve_max_player_level(srv) == 230
    assert resolve_theoretical_player_level(srv) == theoretical


def test_sync_config_player_level_sets_xp_at_base_not_total():
    bosses = {bid: 0 for bid, _, _ in ASCENSION_BOSSES}
    for bid in ("island", "scorched"):
        bosses[bid] = 3

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
    srv.player_ascension_state = (
        '{"bosses":{"island":3,"scorched":3},'
        '"extras":{"explorer_notes":false,"fjordur_runes":false,"chibi":false,'
        '"aquatica":false,"pygocentrus":false}}'
    )
    derived = sync_config_player_level(srv)
    total = calc_total_player_level(105, bosses, {})
    assert derived["theoretical_total"] == total
    assert derived["ramp_entries"] == 105
    assert srv.override_max_xp_player == cumulative_xp_on_ramp(
        build_ramp_values(105, mode=XP_CURVE_VANILLA), 105
    )
    assert srv.player_ramp_entry_count == 105


def test_engram_lines_match_base_level_not_theoretical_total():
    @dataclass
    class _Srv:
        player_base_level: int = 120
        player_engram_points_multiplier: float = 5.0
        player_ascension_state: str = ""
        override_max_xp_player: int = 0

    lines = build_engram_points_ini_lines(_Srv())
    assert len(lines) == 120


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
