from __future__ import annotations

from pathlib import Path

import pytest

from src.asm_engine.asm_ini_manager import write_ini
from src.asm_engine.asm_server_config import AsmServerConfig


def _ini_path(root: Path, name: str) -> Path:
    return root / "ShooterGame" / "Saved" / "Config" / "WindowsServer" / name


def _replace_ini_text_bytes(data: bytes, old: str, new: str) -> bytes:
    if data.startswith(b"\xff\xfe"):
        return b"\xff\xfe" + data[2:].decode("utf-16-le").replace(old, new).encode("utf-16-le")
    if data.startswith(b"\xfe\xff"):
        return b"\xfe\xff" + data[2:].decode("utf-16-be").replace(old, new).encode("utf-16-be")
    if data.startswith(b"\xef\xbb\xbf"):
        return b"\xef\xbb\xbf" + data[3:].decode("utf-8").replace(old, new).encode("utf-8")
    return data.decode("utf-8").replace(old, new).encode("utf-8")


def test_mod_ini_blocks_keep_repeated_keys_encoding_and_external_lines(tmp_path):
    cfg = AsmServerConfig(install_dir=str(tmp_path))
    cfg.mod_ini_configs = {
        "12345": {
            "game_ini": (
                "[ModSection]\n"
                "ConfigOverrideItemMaxQuantity=(ItemClassString=\"A\",Quantity=(MaxItemQuantity=10))\n"
                "ConfigOverrideItemMaxQuantity=(ItemClassString=\"B\",Quantity=(MaxItemQuantity=20))\n"
            ),
        },
    }
    game_path = _ini_path(tmp_path, "Game.ini")
    game_path.parent.mkdir(parents=True)
    game_path.write_bytes("; outside\r\n[ModSection]\r\nExternal=keep\r\n".encode("utf-8"))

    write_ini(cfg)
    saved = game_path.read_bytes()
    assert not saved.startswith((b"\xff\xfe", b"\xfe\xff", b"\xef\xbb\xbf"))
    text = saved.decode("utf-8")
    assert text.count("ConfigOverrideItemMaxQuantity=") == 2
    assert "External=keep" in text
    assert "; outside\r\n" in text
    assert [
        (item["mod_id"], item["file"], bool(item.get("content_hash")))
        for item in cfg.managed_mod_ini_blocks
    ] == [("12345", "Game", True)]

    cfg = AsmServerConfig.from_dict(cfg.to_dict())
    cfg.mod_ini_configs["12345"]["game_ini"] = "[ModSection]\nRepeated=one\nRepeated=two\n"
    write_ini(cfg)
    text = game_path.read_bytes().decode("utf-8")
    assert text.count("Repeated=") == 2
    assert "ConfigOverrideItemMaxQuantity=" not in text
    assert "External=keep" in text


@pytest.mark.parametrize("encoding, bom", [("utf-8", b""), ("utf-16", b"\xff\xfe")])
def test_removing_mod_config_removes_owned_block_only(tmp_path, encoding, bom):
    cfg = AsmServerConfig(install_dir=str(tmp_path))
    cfg.mod_ini_configs = {"mod-A": {"gus_ini": "[SharedSection]\nOwned=old\n"}}
    gus_path = _ini_path(tmp_path, "GameUserSettings.ini")
    gus_path.parent.mkdir(parents=True)
    original_text = "[SharedSection]\nExternal=keep\n"
    if encoding == "utf-16":
        gus_path.write_bytes(bom + original_text.encode("utf-16-le"))
    else:
        gus_path.write_bytes(original_text.encode(encoding))

    write_ini(cfg)
    cfg = AsmServerConfig.from_dict(cfg.to_dict())
    cfg.mod_ini_configs = {}
    write_ini(cfg)

    result = gus_path.read_bytes()
    assert result.startswith(bom)
    decoded = result[len(bom):].decode("utf-16-le" if encoding == "utf-16" else encoding)
    assert "Owned=old" not in decoded
    assert "External=keep" in decoded
    assert "ARKLAND-TEK-MOD" not in decoded
    assert cfg.managed_mod_ini_blocks == []


def test_incomplete_owned_mod_block_fails_without_rewriting_ini(tmp_path):
    cfg = AsmServerConfig(install_dir=str(tmp_path))
    cfg.mod_ini_configs = {"mod-A": {"gus_ini": "[Mod]\nNew=2\n"}}
    cfg.managed_mod_ini_blocks = [{"mod_id": "mod-A", "file": "GUS"}]
    path = _ini_path(tmp_path, "GameUserSettings.ini")
    path.parent.mkdir(parents=True)
    original = b"; ARKLAND-TEK-MOD:BEGIN:bW9kLUE:GUS\nOld=1\n"
    path.write_bytes(original)

    with pytest.raises(ValueError, match="Bloco INI TEK incompleto"):
        write_ini(cfg)

    assert path.read_bytes() == original


def test_manual_edit_inside_owned_mod_block_is_detected_and_preserved(tmp_path):
    cfg = AsmServerConfig(install_dir=str(tmp_path))
    cfg.mod_ini_configs = {"mod-A": {"gus_ini": "[Mod]\nOwned=1\n"}}
    path = _ini_path(tmp_path, "GameUserSettings.ini")
    path.parent.mkdir(parents=True)
    write_ini(cfg)

    edited = _replace_ini_text_bytes(path.read_bytes(), "Owned=1", "Owned=manually-edited")
    path.write_bytes(edited)
    cfg = AsmServerConfig.from_dict(cfg.to_dict())
    cfg.mod_ini_configs["mod-A"]["gus_ini"] = "[Mod]\nOwned=2\n"

    with pytest.raises(ValueError, match="editado fora do perfil"):
        write_ini(cfg)

    assert path.read_bytes() == edited


def test_missing_owned_marker_fails_closed_instead_of_duplicating_block(tmp_path):
    cfg = AsmServerConfig(install_dir=str(tmp_path))
    cfg.mod_ini_configs = {"mod-A": {"gus_ini": "[Mod]\nOwned=1\n"}}
    path = _ini_path(tmp_path, "GameUserSettings.ini")
    path.parent.mkdir(parents=True)
    write_ini(cfg)
    damaged = _replace_ini_text_bytes(
        path.read_bytes(), "ARKLAND-TEK-MOD:BEGIN:", "ARKLAND-OTHER-MOD:BEGIN:"
    )
    path.write_bytes(damaged)
    cfg = AsmServerConfig.from_dict(cfg.to_dict())

    with pytest.raises(ValueError, match="Marcador de propriedade ausente"):
        write_ini(cfg)

    assert path.read_bytes() == damaged


def test_game_ini_conflict_is_detected_before_gus_is_written(tmp_path):
    cfg = AsmServerConfig(install_dir=str(tmp_path))
    cfg.mod_ini_configs = {
        "mod-A": {
            "gus_ini": "[ModGUS]\nOwnedGUS=1\n",
            "game_ini": "[ModGame]\nOwnedGame=1\n",
        }
    }
    gus_path = _ini_path(tmp_path, "GameUserSettings.ini")
    game_path = _ini_path(tmp_path, "Game.ini")
    gus_path.parent.mkdir(parents=True)
    write_ini(cfg)
    gus_before = gus_path.read_bytes()
    edited_game = _replace_ini_text_bytes(
        game_path.read_bytes(), "OwnedGame=1", "OwnedGame=manual"
    )
    game_path.write_bytes(edited_game)

    cfg = AsmServerConfig.from_dict(cfg.to_dict())
    cfg.mod_ini_configs["mod-A"]["gus_ini"] = "[ModGUS]\nOwnedGUS=2\n"
    cfg.mod_ini_configs["mod-A"]["game_ini"] = "[ModGame]\nOwnedGame=2\n"
    with pytest.raises(ValueError, match="editado fora do perfil"):
        write_ini(cfg)

    assert gus_path.read_bytes() == gus_before
    assert game_path.read_bytes() == edited_game
