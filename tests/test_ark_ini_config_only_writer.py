from pathlib import Path

from src.ark_ini import ArkIniManager
from src.asm_engine.ini_document import IniDocument, sanitize_ini_bytes


def _assert_configuration_only(data: bytes) -> None:
    document = IniDocument.parse(data)
    assert all(line.kind in {"section", "key"} for line in document.lines)
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
    _assert_configuration_only(game)
    _assert_configuration_only(gus)
    assert b"Enabled=True" in game
    assert b"ExampleOption=1" in gus

