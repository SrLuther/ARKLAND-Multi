"""Conteúdo extra Game.ini / GameUserSettings.ini — mapeamento de seções."""
from __future__ import annotations

from pathlib import Path

from src.asm_engine.asm_ini_manager import (
    _GAME_MODE_SECTION,
    inject_raw_ini_text,
    write_ini,
)
from src.asm_engine.asm_server_config import AsmServerConfig

_GAME_INI = (
    "ShooterGame/Saved/Config/WindowsServer/Game.ini"
)
_GUS_INI = (
    "ShooterGame/Saved/Config/WindowsServer/GameUserSettings.ini"
)


def _game_path(tmp_path) -> Path:
    return tmp_path / _GAME_INI


def _gus_path(tmp_path) -> Path:
    return tmp_path / _GUS_INI


def _section_block(text: str, section: str) -> str:
    """Extrai linhas de uma seção INI (até a próxima ``[``)."""
    lines: list[str] = []
    in_section = False
    header = f"[{section}]"
    for raw in text.splitlines():
        line = raw.strip()
        if line.lower() == header.lower():
            in_section = True
            continue
        if in_section and line.startswith("["):
            break
        if in_section and line:
            lines.append(line)
    return "\n".join(lines)


def test_custom_game_ini_explicit_section(tmp_path):
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.custom_game_ini_raw = (
        f"[{_GAME_MODE_SECTION}]\n"
        "ConfigSubtractNPCSpawnEntriesContainer=TestValue\n"
    )
    write_ini(cfg)

    text = _game_path(tmp_path).read_text(encoding="utf-16")
    assert "[ServerSettings]" not in text
    assert "ConfigSubtractNPCSpawnEntriesContainer=TestValue" in text
    assert _section_block(text, _GAME_MODE_SECTION)  # seção existe


def test_custom_game_ini_without_section_defaults_to_shooter_game_mode(tmp_path):
    """Linhas sem [Seção] no Game.ini extra vão para ShooterGameMode, não ServerSettings."""
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.custom_game_ini_raw = "ConfigSubtractNPCSpawnEntriesContainer=NoHeader\n"
    write_ini(cfg)

    text = _game_path(tmp_path).read_text(encoding="utf-16")
    assert "[ServerSettings]" not in text
    assert "ConfigSubtractNPCSpawnEntriesContainer=NoHeader" in text


def test_custom_game_ini_bom_before_section_header(tmp_path):
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.custom_game_ini_raw = (
        f"\ufeff[{_GAME_MODE_SECTION}]\n"
        "ConfigSubtractNPCSpawnEntriesContainer=BomTest\n"
    )
    write_ini(cfg)

    text = _game_path(tmp_path).read_text(encoding="utf-16")
    assert "[ServerSettings]" not in text
    assert "ConfigSubtractNPCSpawnEntriesContainer=BomTest" in text


def test_custom_gus_ini_without_section_defaults_to_server_settings(tmp_path):
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.custom_gus_ini_raw = "CustomGusKey=GusValue\n"
    write_ini(cfg)

    text = _gus_path(tmp_path).read_text(encoding="utf-16")
    block = _section_block(text, "ServerSettings")
    assert "CustomGusKey=GusValue" in block


def test_custom_game_ini_non_repeated_key_in_shooter_game_mode_section(tmp_path):
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.custom_game_ini_raw = (
        f"[{_GAME_MODE_SECTION}]\n"
        "MyCustomScalarKey=42\n"
    )
    write_ini(cfg)

    text = _game_path(tmp_path).read_text(encoding="utf-16")
    assert "[ServerSettings]" not in text
    block = _section_block(text, _GAME_MODE_SECTION)
    assert "MyCustomScalarKey=42" in block


def test_inject_raw_ini_text_game_default_section():
    game: dict[str, dict[str, str]] = {}
    inject_raw_ini_text(
        "SomeGameKey=1",
        game,
        default_section=_GAME_MODE_SECTION,
    )
    assert _GAME_MODE_SECTION in game
    assert game[_GAME_MODE_SECTION]["SomeGameKey"] == "1"
    assert "ServerSettings" not in game
