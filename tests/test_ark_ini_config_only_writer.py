from pathlib import Path

from src.ark_ini import ArkIniManager, _write_config_only_ini
from src.asm_engine.ini_document import IniDocument, sanitize_ini_bytes
from src.server_config import ServerConfig


def _assert_configuration_only(data: bytes) -> None:
    document = IniDocument.parse(data)
    assert all(
        line.kind in {"section", "key"}
        or (line.kind == "comment" and "MOD CONFIGS" in line.raw)
        for line in document.lines
    )
    assert all(line.raw.strip() for line in document.lines)


def test_sanitizer_keeps_ini_configuration_and_repeated_keys():
    raw = (
        "; comment\r\n[ServerSettings]\r\n\r\nKey=one\r\nKey=two\r\n"
        "invalid prose\r\n# another comment\r\n[SessionSettings]\r\nName=ARK\r\n"
    ).encode("utf-8")

    sanitized = sanitize_ini_bytes(raw)
    _assert_configuration_only(sanitized)
    text = sanitized.decode("utf-8")
    assert text.count("Key=") == 2
    assert "invalid prose" not in text
    assert "; comment" not in text


def test_mod_ini_writer_does_not_emit_comments_or_explanatory_text(tmp_path: Path):
    manager = ArkIniManager(str(tmp_path))
    manager.apply_mod_ini_configs({
        "123": {
            "game_ini": "; Mod note\n[ExampleMod]\nEnabled=True\nThis is prose",
            "gus_ini": "# note\n[ServerSettings]\nExampleOption=1",
        }
    })

    game = (tmp_path / "ShooterGame/Saved/Config/WindowsServer/Game.ini").read_bytes()
    gus = (tmp_path / "ShooterGame/Saved/Config/WindowsServer/GameUserSettings.ini").read_bytes()
    assert game.startswith(b"\xff\xfe")
    assert gus.startswith(b"\xff\xfe")
    _assert_configuration_only(game)
    _assert_configuration_only(gus)
    game_doc = IniDocument.parse(game)
    gus_doc = IniDocument.parse(gus)
    assert game_doc.find_values("ExampleMod", "Enabled") == ["True"]
    assert gus_doc.find_values("ServerSettings", "ExampleOption") == ["1"]
    assert "BEGIN MOD CONFIGS" in game_doc.to_config_text()
    assert "END MOD CONFIGS" in game_doc.to_config_text()
    assert "BEGIN MOD CONFIGS" in gus_doc.to_config_text()
    assert "END MOD CONFIGS" in gus_doc.to_config_text()


def test_config_only_writer_preserves_existing_utf8_without_bom(tmp_path: Path):
    path = tmp_path / "existing.ini"
    path.write_bytes("[External]\nNome=ação\n".encode("utf-8"))

    _write_config_only_ini(path, "[External]\nNome=alteração\n")

    written = path.read_bytes()
    assert not written.startswith((b"\xff\xfe", b"\xfe\xff", b"\xef\xbb\xbf"))
    assert written.decode("utf-8") == "[External]\nNome=alteração\n"


def test_classic_writer_removes_mapped_values_that_return_to_declared_defaults(tmp_path: Path):
    cfg = ServerConfig(install_dir=str(tmp_path))
    gus = tmp_path / "ShooterGame/Saved/Config/WindowsServer/GameUserSettings.ini"
    game = tmp_path / "ShooterGame/Saved/Config/WindowsServer/Game.ini"
    gus.parent.mkdir(parents=True)
    gus.write_text(
        "[ServerSettings]\nXPMultiplier=3.0\nExternalPluginOption=keep\n",
        encoding="utf-8",
    )
    game.write_text(
        "[/Script/ShooterGame.ShooterGameMode]\n"
        "BabyMatureSpeedMultiplier=5.0\nExternalGameOption=keep\n",
        encoding="utf-8",
    )

    ArkIniManager(str(tmp_path)).save_all(cfg)

    gus_doc = IniDocument.parse(gus.read_bytes())
    game_doc = IniDocument.parse(game.read_bytes())
    assert gus_doc.find_values("ServerSettings", "XPMultiplier") == []
    assert IniDocument.parse(gus.read_bytes()).find_values(
        "ServerSettings", "ExternalPluginOption"
    ) == ["keep"]
    assert game_doc.find_values(
        "/Script/ShooterGame.ShooterGameMode", "BabyMatureSpeedMultiplier"
    ) == []
    assert IniDocument.parse(game.read_bytes()).find_values(
        "/Script/ShooterGame.ShooterGameMode", "ExternalGameOption"
    ) == ["keep"]

