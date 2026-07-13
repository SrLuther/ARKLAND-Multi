"""Rampa LevelExperienceRampOverrides — escrita Game.ini e patch por seção."""
from __future__ import annotations

from pathlib import Path

from src.asm_engine.asm_game_list_ini import (
    _GAME_MODE_SECTION,
    count_ramp_lines_in_section,
    extract_ini_section_text,
    patch_game_ini_repeated_lines,
)
from src.asm_engine.asm_ini_manager import write_ini
from src.asm_engine.asm_server_config import AsmServerConfig
from src.player_level_ramp import build_ramp_ini_line, parse_ramp_from_text, total_ramp_slots


def _game_path(tmp_path) -> Path:
    return tmp_path / "ShooterGame/Saved/Config/WindowsServer/Game.ini"


def test_write_ini_writes_full_ramp_inside_shooter_game_mode(tmp_path):
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.player_base_level = 160
    cfg.player_level_progressions_enabled = True
    write_ini(cfg)

    text = _game_path(tmp_path).read_text(encoding="utf-16")
    assert count_ramp_lines_in_section(text, _GAME_MODE_SECTION) == total_ramp_slots(160)


def test_patch_inserts_ramp_inside_section_when_other_sections_follow(tmp_path):
    path = _game_path(tmp_path)
    path.parent.mkdir(parents=True)
    pre = (
        f"[{_GAME_MODE_SECTION}]\r\n"
        "Foo=1\r\n"
        "LevelExperienceRampOverrides=(ExperiencePointsForLevel[0]=1)\r\n"
        "[/Script/Engine.GameSession]\r\n"
        "MaxPlayers=70\r\n"
    )
    path.write_bytes(b"\xff\xfe" + pre.encode("utf-16-le"))

    ramp_lines = [
        f"LevelExperienceRampOverrides=(ExperiencePointsForLevel[{i}]={10 + i})"
        for i in range(5)
    ]
    patch_game_ini_repeated_lines(path, ramp_lines)

    text = path.read_text(encoding="utf-16")
    assert count_ramp_lines_in_section(text, _GAME_MODE_SECTION) == 5
    session_block = text.lower().split("[/script/engine.gamesession]")[-1]
    assert "levelexperiencerampoverrides" not in session_block.split("[")[0]


def test_get_ramp_values_prefers_base_over_collapsed_raw():
    from dataclasses import dataclass

    from src.player_level_ramp import get_ramp_values_from_cfg

    @dataclass
    class _Srv:
        player_base_level: int = 160
        player_ramp_entry_count: int = 1
        player_level_stats_raw: str = (
            "LevelExperienceRampOverrides=(ExperiencePointsForLevel[0]=70)"
        )
        player_xp_curve_mode: str = "vanilla"
        player_level_progressions_enabled: bool = True

    values = get_ramp_values_from_cfg(_Srv())
    assert len(values) == total_ramp_slots(160)


def test_parse_ramp_single_line_official_format():
    raw = (
        "LevelExperienceRampOverrides=("
        "ExperiencePointsForLevel[0]=1,"
        "ExperiencePointsForLevel[1]=3,"
        "ExperiencePointsForLevel[2]=5)"
    )
    parsed = parse_ramp_from_text(raw)
    assert parsed["entry_count"] == 3
    assert parsed["slots"] == {0: 1, 1: 3, 2: 5}


def test_write_ini_vanilla_stock_base_105_skips_ramp_and_max_xp(tmp_path):
    """Base ≤105 sem progressões: Game.ini sem rampa/OverrideMaxXP (vanilla stock)."""
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.player_base_level = 105
    cfg.player_level_progressions_enabled = False
    cfg.override_max_xp_player = 0

    path = _game_path(tmp_path)
    path.parent.mkdir(parents=True)
    pre = (
        f"[{_GAME_MODE_SECTION}]\r\n"
        "LevelExperienceRampOverrides=(ExperiencePointsForLevel[0]=70)\r\n"
        "OverridePlayerLevelEngramPoints=400\r\n"
    )
    path.write_bytes(b"\xff\xfe" + pre.encode("utf-16-le"))

    write_ini(cfg)

    text = path.read_text(encoding="utf-16")
    block = extract_ini_section_text(text, _GAME_MODE_SECTION).lower()
    assert "levelexperiencerampoverrides" not in block
    assert "overrideplayerlevelengrampoints" not in block
    assert "overridemaxexperiencepointsplayer" not in block
    assert count_ramp_lines_in_section(text, _GAME_MODE_SECTION) == 0


def test_write_ini_writes_single_line_ramp(tmp_path):
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.player_base_level = 160
    cfg.player_level_progressions_enabled = True
    write_ini(cfg)

    text = _game_path(tmp_path).read_text(encoding="utf-16")
    block = extract_ini_section_text(text, _GAME_MODE_SECTION)
    ramp_physical_lines = sum(
        1 for ln in block.splitlines()
        if ln.strip().lower().startswith("levelexperiencerampoverrides=")
    )
    assert ramp_physical_lines == 1
    assert count_ramp_lines_in_section(text, _GAME_MODE_SECTION) == total_ramp_slots(160)
    assert "OverrideMaxExperiencePointsPlayer=" in block


def test_patch_accepts_single_line_ramp(tmp_path):
    path = _game_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(
        b"\xff\xfe" + f"[{_GAME_MODE_SECTION}]\r\n".encode("utf-16-le")
    )
    ramp_line = build_ramp_ini_line([10 + i for i in range(5)])
    patch_game_ini_repeated_lines(path, [ramp_line])

    text = path.read_text(encoding="utf-16")
    assert count_ramp_lines_in_section(text, _GAME_MODE_SECTION) == 5


def test_write_ini_base_160_progressions_off_clears_game_ini_overrides(tmp_path):
    """Base >105 com toggle OFF: limpa rampa/OverrideMaxXP/engrams; remove GUS legado."""
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.player_base_level = 160
    cfg.player_level_progressions_enabled = False
    cfg.override_max_xp_player = 0

    path = _game_path(tmp_path)
    path.parent.mkdir(parents=True)
    pre = (
        f"[{_GAME_MODE_SECTION}]\r\n"
        "LevelExperienceRampOverrides=(ExperiencePointsForLevel[0]=70,"
        "ExperiencePointsForLevel[1]=80)\r\n"
        "OverrideMaxExperiencePointsPlayer=999\r\n"
        "OverridePlayerLevelEngramPoints=400\r\n"
    )
    path.write_bytes(b"\xff\xfe" + pre.encode("utf-16-le"))

    gus_path = tmp_path / "ShooterGame/Saved/Config/WindowsServer/GameUserSettings.ini"
    gus_pre = "[ServerSettings]\r\nOverrideMaxExperiencePointsPlayer=999\r\n"
    gus_path.write_bytes(b"\xff\xfe" + gus_pre.encode("utf-16-le"))

    write_ini(cfg)

    assert cfg.player_level_progressions_enabled is False
    text = path.read_text(encoding="utf-16")
    block = extract_ini_section_text(text, _GAME_MODE_SECTION).lower()
    assert "levelexperiencerampoverrides" not in block
    assert "overridemaxexperiencepointsplayer" not in block
    assert "overrideplayerlevelengrampoints" not in block
    assert count_ramp_lines_in_section(text, _GAME_MODE_SECTION) == 0

    gus_text = gus_path.read_text(encoding="utf-16")
    assert "OverrideMaxExperiencePointsPlayer" not in gus_text


def test_write_ini_base_160_progressions_on_writes_game_ini_ramp(tmp_path):
    """Progressões ON: rampa + OverrideMaxXP + engrams no Game.ini (não GUS)."""
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.player_base_level = 160
    cfg.player_level_progressions_enabled = True
    cfg.override_max_xp_player = 0

    path = _game_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(
        b"\xff\xfe" + f"[{_GAME_MODE_SECTION}]\r\n".encode("utf-16-le")
    )

    gus_path = tmp_path / "ShooterGame/Saved/Config/WindowsServer/GameUserSettings.ini"
    gus_pre = "[ServerSettings]\r\nOverrideMaxExperiencePointsPlayer=999\r\n"
    gus_path.write_bytes(b"\xff\xfe" + gus_pre.encode("utf-16-le"))

    write_ini(cfg)

    text = path.read_text(encoding="utf-16")
    block = extract_ini_section_text(text, _GAME_MODE_SECTION)
    block_l = block.lower()
    assert "levelexperiencerampoverrides" in block_l
    assert count_ramp_lines_in_section(text, _GAME_MODE_SECTION) == total_ramp_slots(160)
    assert "overridemaxexperiencepointsplayer=" in block_l
    assert "overrideplayerlevelengrampoints=400" in block_l

    gus_text = gus_path.read_text(encoding="utf-16")
    assert "OverrideMaxExperiencePointsPlayer" not in gus_text
