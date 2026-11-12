"""Conteúdo extra Game.ini / GameUserSettings.ini — mapeamento de seções."""
from __future__ import annotations

from pathlib import Path

from src.asm_engine.asm_ini_manager import (
    _GAME_MODE_SECTION,
    inject_raw_ini_text,
    seed_managed_ini_options,
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


def test_write_ini_removes_engrm_flags_when_disabled(tmp_path):
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.auto_unlock_all_engrams = False
    cfg.only_allow_specified_engrams = False

    game_path = _game_path(tmp_path)
    game_path.parent.mkdir(parents=True)
    pre = (
        f"[{_GAME_MODE_SECTION}]\r\n"
        "bAutoUnlockAllEngrams=True\r\n"
        "bOnlyAllowSpecifiedEngrams=True\r\n"
    )
    game_path.write_bytes(b"\xff\xfe" + pre.encode("utf-16-le"))

    write_ini(cfg)

    text = game_path.read_text(encoding="utf-16")
    block = _section_block(text, _GAME_MODE_SECTION).lower()
    assert "bautounlockallengrams" not in block
    assert "bonlyallowspecifiedengrams" not in block


def test_removed_custom_gus_option_stays_removed_after_profile_reload_and_recreate(tmp_path):
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.custom_gus_ini_raw = (
        "[CreatureFinderDeluxe]\n"
        "FindAllCreatures=1000\n"
        "ShowOnlyTamed=True\n"
    )
    gus_path = _gus_path(tmp_path)
    gus_path.parent.mkdir(parents=True)
    gus_path.write_text(
        "[CreatureFinderDeluxe]\nExternalPluginOption=keep\n",
        encoding="utf-8",
    )

    write_ini(cfg)
    # Simula o save: guarda a propriedade anterior antes de a UI substituir
    # o conteúdo do editor, depois remove uma das opções.
    seed_managed_ini_options(cfg)
    cfg.custom_gus_ini_raw = (
        "[CreatureFinderDeluxe]\n"
        "ShowOnlyTamed=False\n"
    )
    write_ini(cfg)

    text = gus_path.read_text(encoding="utf-8")
    assert "FindAllCreatures" not in text
    assert "ShowOnlyTamed=False" in text
    assert "ExternalPluginOption=keep" in text
    assert text.count("ShowOnlyTamed=") == 1

    # O manifesto pertence ao perfil e sobrevive ao reinício do aplicativo.
    cfg = AsmServerConfig.from_dict(cfg.to_dict())
    gus_path.unlink()
    write_ini(cfg)
    recreated = gus_path.read_text(encoding="utf-16")
    assert "FindAllCreatures" not in recreated
    assert "ShowOnlyTamed=False" in recreated
    write_ini(cfg)
    assert gus_path.read_text(encoding="utf-16").count("ShowOnlyTamed=") == 1


def test_removed_custom_game_and_engine_options_are_reconciled(tmp_path):
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.custom_game_ini_raw = (
        f"[{_GAME_MODE_SECTION}]\nManagedGameOption=old\n"
    )
    cfg.custom_engine_ini_raw = "[Core.System]\nManagedEngineOption=old\n"
    write_ini(cfg)

    seed_managed_ini_options(cfg)
    cfg.custom_game_ini_raw = ""
    cfg.custom_engine_ini_raw = ""
    write_ini(cfg)

    game = _game_path(tmp_path).read_text(encoding="utf-16")
    engine = (tmp_path / "ShooterGame/Saved/Config/WindowsServer/Engine.ini").read_text(encoding="utf-16")
    assert "ManagedGameOption" not in game
    assert "ManagedEngineOption" not in engine


def test_managed_ini_ownership_is_isolated_between_server_profiles(tmp_path):
    first = AsmServerConfig()
    first.install_dir = str(tmp_path / "first")
    first.custom_gus_ini_raw = "[FirstPlugin]\nFirstOption=1\n"
    second = AsmServerConfig()
    second.install_dir = str(tmp_path / "second")
    second.custom_gus_ini_raw = "[SecondPlugin]\nSecondOption=2\n"

    write_ini(first)
    write_ini(second)
    seed_managed_ini_options(first)
    first.custom_gus_ini_raw = ""
    write_ini(first)

    first_text = _gus_path(tmp_path / "first").read_text(encoding="utf-16")
    second_text = _gus_path(tmp_path / "second").read_text(encoding="utf-16")
    assert "FirstOption" not in first_text
    assert "SecondOption=2" in second_text


def test_grouped_custom_sections_are_seeded_and_removed_without_touching_external(tmp_path):
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    cfg.custom_ini_sections = {
        "gus": [{
            "section": "ModSection",
            "entries": [{"key": "ManagedOption", "value": "old"}],
        }],
    }
    path = _gus_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(
        "[ModSection]\nManagedOption=old\nExternalOption=keep\n",
        encoding="utf-8",
    )

    seed_managed_ini_options(cfg)
    cfg.custom_ini_sections = {"gus": []}
    cfg = AsmServerConfig.from_dict(cfg.to_dict())
    write_ini(cfg)

    text = path.read_text(encoding="utf-8")
    assert "ManagedOption" not in text
    assert "ExternalOption=keep" in text
    assert not any(
        item["section"] == "ModSection" and item["key"] == "ManagedOption"
        for item in cfg.managed_ini_options["GUS"]
    )


def test_default_structured_values_are_omitted_and_old_managed_value_is_cleared(tmp_path):
    cfg = AsmServerConfig()
    cfg.install_dir = str(tmp_path)
    gus_path = _gus_path(tmp_path)
    gus_path.parent.mkdir(parents=True)
    gus_path.write_text(
        "[ServerSettings]\nXPMultiplier=2.0\nExternalPluginOption=keep\n",
        encoding="utf-8",
    )

    write_ini(cfg)

    text = gus_path.read_text(encoding="utf-8")
    assert "XPMultiplier=" not in text
    assert "ExternalPluginOption=keep" in text
    assert "RCONEnabled=" in text  # explicit always_write option
