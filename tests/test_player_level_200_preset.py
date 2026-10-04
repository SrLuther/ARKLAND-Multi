"""A progressão de 200 níveis grava o mesmo bloco do Game.ini de referência."""
from __future__ import annotations

from pathlib import Path

from src.asm_engine.asm_game_list_ini import extract_ini_section_text
from src.asm_engine.asm_ini_manager import write_ini
from src.asm_engine.asm_server_config import AsmServerConfig
from src.player_engram_points import build_engram_points_ini_lines
from src.player_level_200 import level_200_relevant_ini_lines, preset_text
from src.player_level_ramp import (
    build_player_ramp_ini_lines,
    sync_config_player_level,
)

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "nivel200.txt"
_GAME_MODE = "/Script/ShooterGame.ShooterGameMode"
_KEYS = (
    "overridemaxexperiencepointsplayer=",
    "levelexperiencerampoverrides=",
    "overrideplayerlevelengrampoints=",
)


def _relevant_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        low = line.lower()
        if any(low.startswith(key) for key in _KEYS):
            lines.append(line)
    return lines


def _cfg(tmp_path, *, base: int, enabled: bool) -> AsmServerConfig:
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.player_base_level = base
    cfg.player_level_progressions_enabled = enabled
    cfg.player_xp_curve_mode = "custom"
    cfg.player_xp_curve_base = 5
    cfg.player_xp_curve_mult = 3.0
    cfg.override_max_xp_player = 0
    return cfg


def test_fixture_matches_packaged_table():
    assert _FIXTURE.read_text(encoding="utf-8") == preset_text()


def test_generator_matches_nivel200_fixture():
    fixture_lines = _relevant_lines(_FIXTURE.read_text(encoding="utf-8"))
    assert fixture_lines == level_200_relevant_ini_lines()

    cfg = _cfg(Path("."), base=199, enabled=True)
    produced = [
        f"OverrideMaxExperiencePointsPlayer={sync_config_player_level(cfg)['override_xp']}",
        *build_player_ramp_ini_lines(cfg),
        *build_engram_points_ini_lines(cfg),
    ]
    assert produced == fixture_lines
    assert cfg.player_level_progressions_enabled is True

    same = _cfg(Path("."), base=200, enabled=True)
    produced_200 = [
        f"OverrideMaxExperiencePointsPlayer={sync_config_player_level(same)['override_xp']}",
        *build_player_ramp_ini_lines(same),
        *build_engram_points_ini_lines(same),
    ]
    assert produced_200 == fixture_lines


def test_progressions_off_does_not_emit_level_200_table(tmp_path):
    cfg = _cfg(tmp_path, base=199, enabled=False)
    derived = sync_config_player_level(cfg)
    assert derived["override_xp"] == 0
    assert derived["ramp_entries"] == 0
    assert build_player_ramp_ini_lines(cfg) == []
    assert build_engram_points_ini_lines(cfg) == []
    assert cfg.player_level_progressions_enabled is False

    write_ini(cfg)
    game = tmp_path / "ShooterGame/Saved/Config/WindowsServer/Game.ini"
    text = game.read_text(encoding="utf-16")
    block = extract_ini_section_text(text, _GAME_MODE)
    assert _relevant_lines(block) == []


def test_write_ini_level_200_matches_fixture_and_can_be_removed(tmp_path):
    fixture_lines = _relevant_lines(_FIXTURE.read_text(encoding="utf-8"))
    cfg = _cfg(tmp_path, base=199, enabled=True)
    write_ini(cfg)

    game = tmp_path / "ShooterGame/Saved/Config/WindowsServer/Game.ini"
    text = game.read_text(encoding="utf-16")
    block = extract_ini_section_text(text, _GAME_MODE)
    assert _relevant_lines(block) == fixture_lines

    cfg.player_level_progressions_enabled = False
    write_ini(cfg)
    text_off = game.read_text(encoding="utf-16")
    block_off = extract_ini_section_text(text_off, _GAME_MODE)
    assert _relevant_lines(block_off) == []
    assert cfg.player_level_progressions_enabled is False
