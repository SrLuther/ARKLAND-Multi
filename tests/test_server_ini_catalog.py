from src.ui.server_ini_catalog import load_server_ini_catalog, validate_catalog_value


def test_bundled_catalog_covers_documented_ase_game_ini_targets():
    from src.asm_engine.asm_game_list_ini import REPEATED_KEY_PREFIXES

    gus = load_server_ini_catalog("GameUserSettings.ini")
    game = load_server_ini_catalog("Game.ini")

    assert len(gus) == 185
    assert len(game) == 136
    assert all(entry["section"] and entry["key"] for entry in gus + game)
    assert any(entry["key"] == "XPMultiplier" for entry in gus)
    assert any(entry["key"] == "OverridePlayerLevelEngramPoints" for entry in game)
    repeatable = [entry for entry in game if entry.get("repeatable")]
    assert any(entry["key"] == "ConfigOverrideSupplyCrateItems" for entry in repeatable)
    mod_ids = next(entry for entry in game if entry["key"] == "ModIDS")
    assert mod_ids["section"] == "ModInstaller" and mod_ids["repeatable"]
    assert all(entry["key"].casefold() in REPEATED_KEY_PREFIXES for entry in repeatable)
    assert not any(entry["file"] == "DynamicConfig" for entry in gus + game)
    assert all(entry.get("description") for entry in gus + game)


def test_cli_catalog_has_official_ase_arguments_and_formats_templates():
    from src.ui.server_cli_catalog import build_cli_argument, load_server_cli_catalog

    entries = load_server_cli_catalog()
    assert len(entries) == 114
    assert all(entry.get("description") for entry in entries)
    event = next(entry for entry in entries if entry["argument"] == "-ActiveEvent=<eventname>")
    assert build_cli_argument(event, "FearEvolved") == "-ActiveEvent=FearEvolved"
    flag = next(entry for entry in entries if entry["argument"] == "-allowansel")
    assert build_cli_argument(flag) == "-allowansel"
    try:
        build_cli_argument(event)
    except ValueError as exc:
        assert "Informe um valor" in str(exc)
    else:
        raise AssertionError("argument template accepted without a value")


def test_catalog_scalar_validation_matches_documented_types():
    assert validate_catalog_value("True", "boolean") is None
    assert validate_catalog_value("1.5", "float") is None
    assert validate_catalog_value("42", "integer") is None
    assert validate_catalog_value("maybe", "boolean")
    assert validate_catalog_value("1.5", "integer")
    assert validate_catalog_value("1\nOtherKey=2", "string")


def test_catalog_supported_custom_keys_round_trip_to_the_two_ark_ini_files(tmp_path):
    from src.asm_engine.asm_ini_manager import write_ini
    from src.asm_engine.asm_server_config import AsmServerConfig
    from src.asm_engine.ini_document import IniDocument

    config = AsmServerConfig()
    config.install_dir = str(tmp_path)
    config.custom_gus_ini_raw = "[ServerSettings]\nAllowCaveBuildingPvP=True"
    config.custom_game_ini_raw = (
        "[/Script/ShooterGame.ShooterGameMode]\n"
        "bUseSingleplayerSettings=True\n"
        'DinoClassDamageMultipliers=(ClassName="Rex",Multiplier=1.5)\n'
        'DinoClassDamageMultipliers=(ClassName="Giga",Multiplier=0.5)\n'
        "[ModInstaller]\nModIDS=123456789\nModIDS=987654321"
    )
    write_ini(config)

    ini_dir = tmp_path / "ShooterGame/Saved/Config/WindowsServer"
    gus = IniDocument.from_file(str(ini_dir / "GameUserSettings.ini"))
    game = IniDocument.from_file(str(ini_dir / "Game.ini"))
    assert gus.find_values("ServerSettings", "AllowCaveBuildingPvP") == ["True"]
    assert game.find_values("/Script/ShooterGame.ShooterGameMode", "bUseSingleplayerSettings") == ["True"]
    assert len(game.find_values("/Script/ShooterGame.ShooterGameMode", "DinoClassDamageMultipliers")) == 2
    assert game.find_values("ModInstaller", "ModIDS") == ["123456789", "987654321"]
    assert all(line.kind in {"section", "key"} for path in ini_dir.glob("*.ini") for line in IniDocument.from_file(str(path)).lines)
