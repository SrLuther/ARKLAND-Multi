from src.asm_engine.asm_ini_manager import _write_ini_file
from src.asm_engine.asm_ini_manager import read_ini_from_paths
from src.asm_engine.asm_server_config import AsmServerConfig
from src.asm_engine.asm_game_list_ini import build_repeated_game_lines
from src.asm_engine.ini_document import IniDocument
from src.ark_ini_fields import GUS_SECTION_ORDER


def test_writer_keeps_unknown_configuration_but_strips_comments_and_raw_lines(tmp_path):
    path = tmp_path / "Game.ini"
    original = (
        "; keep header\r\n"
        "[ShooterGameMode]\r\n"
        "; keep comment\r\n"
        "UnknownOption=do not touch\r\n"
        "Managed = old  \r\n"
        "RawUnparsedLine(...)\r\n"
        "Managed=stale\r\n"
        "[CustomRepeatedSection]\r\n"
        "Keep=second block\r\n"
    ).encode("utf-8-sig")
    path.write_bytes(original)

    _write_ini_file(path, {"ShooterGameMode": {"Managed": "new"}})

    result = path.read_bytes()
    document = IniDocument.parse(result)
    text = document.to_text()
    assert result.startswith(b"\xef\xbb\xbf")
    assert document.find_values("ShooterGameMode", "Managed") == ["new  "]
    assert "; keep header" not in text
    assert "; keep comment" not in text
    assert "UnknownOption=do not touch\r\n" in text
    assert "RawUnparsedLine(...)" not in text
    assert "[CustomRepeatedSection]\r\nKeep=second block\r\n" in text


def test_writer_removes_only_requested_keys_and_keeps_unmanaged_duplicate_sections(tmp_path):
    path = tmp_path / "Game.ini"
    path.write_text(
        "[ShooterGameMode]\nDisableMe=true\nKeep=one\n"
        "[ShooterGameMode]\nKeep=two\n",
        encoding="utf-8",
    )

    _write_ini_file(
        path,
        {"ShooterGameMode": {"NewManaged": "yes"}},
        remove_options=[("ShooterGameMode", "DisableMe")],
    )

    text = path.read_text(encoding="utf-8")
    document = IniDocument.parse(text)
    assert document.find_values("ShooterGameMode", "DisableMe") == []
    assert document.find_values("ShooterGameMode", "Keep") == ["one", "two"]
    assert document.find_values("ShooterGameMode", "NewManaged") == ["yes"]
    assert text.count("[ShooterGameMode]") == 1


def test_writer_keeps_required_gus_skeleton_and_uses_ark_encoding_for_new_file(tmp_path):
    path = tmp_path / "GameUserSettings.ini"

    _write_ini_file(path, {"SessionSettings": {"SessionName": "ARKLAND"}})

    data = path.read_bytes()
    assert data.startswith(b"\xff\xfe")
    document = IniDocument.parse(data)
    text = document.to_text()
    assert document.find_values(GUS_SECTION_ORDER[0], "Version") == ["5"]
    assert document.find_values("SessionSettings", "SessionName") == ["ARKLAND"]
    for section in GUS_SECTION_ORDER:
        assert f"[{section}]" in text


def test_real_ark_style_repeated_keys_can_be_imported(tmp_path):
    gus = tmp_path / "GameUserSettings.ini"
    game = tmp_path / "Game.ini"
    gus.write_text(
        "[SessionSettings]\nSessionName=First\nSessionName=Second\n",
        encoding="utf-8",
    )
    game.write_text(
        "[/Script/ShooterGame.ShooterGameMode]\n"
        "LevelExperienceRampOverrides=(ExperiencePointsForLevel[0]=0,ExperiencePointsForLevel[1]=10)\n"
        "LevelExperienceRampOverrides=(ExperiencePointsForLevel[0]=0,ExperiencePointsForLevel[1]=20)\n"
        "OverridePlayerLevelEngramPoints=4\n"
        "OverridePlayerLevelEngramPoints=8\n",
        encoding="utf-8",
    )

    config = AsmServerConfig()
    read_ini_from_paths(config, str(gus), str(game))

    assert config.session_name == "Second"
    assert config.player_ramp_entry_count == 2
    assert config.player_level_progressions_enabled is True
    assert "ExperiencePointsForLevel[1]=10" in config.player_level_stats_raw
    assert "ExperiencePointsForLevel[1]=20" in config.dino_level_stats_raw
    assert config.dino_level_progressions_enabled is True
    assert config.player_engram_points == [4, 8]


def test_player_and_tame_ramps_are_written_as_first_and_second_ark_directive():
    config = AsmServerConfig(
        player_level_progressions_enabled=True,
        player_level_stats_raw=(
            "LevelExperienceRampOverrides=(ExperiencePointsForLevel[0]=0,"
            "ExperiencePointsForLevel[1]=10)"
        ),
        player_level_xp_thresholds=[0, 10],
        dino_level_progressions_enabled=True,
        dino_level_stats_raw=(
            "LevelExperienceRampOverrides=(ExperiencePointsForLevel[0]=0,"
            "ExperiencePointsForLevel[1]=20)"
        ),
    )

    ramps = [line for line in build_repeated_game_lines(config)
             if line.startswith("LevelExperienceRampOverrides=")]

    assert len(ramps) == 2
    assert "ExperiencePointsForLevel[1]=10" in ramps[0]
    assert "ExperiencePointsForLevel[1]=20" in ramps[1]
