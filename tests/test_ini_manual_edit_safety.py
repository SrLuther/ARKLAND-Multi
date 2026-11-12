from pathlib import Path
from types import SimpleNamespace

import pytest

from src.asm_engine.ini_document import IniDocument
from src.asm_ui.asm_file_manager import _managed_ini_changes
from src.ini_write_safety import find_install_conflicts, normalized_install_path, write_with_backup


@pytest.mark.parametrize(
    ("raw", "edited", "prefix"),
    [
        (b"[S]\nX=1\n", "[S]\nX=2\n", b""),
        (b"\xff\xfe" + "[S]\r\nX=1\r\n".encode("utf-16-le"), "[S]\r\nX=2\r\n", b"\xff\xfe"),
        (b"\xef\xbb\xbf[S]\nX=1\n", "[S]\nX=2\n", b"\xef\xbb\xbf"),
    ],
)
def test_editor_encodes_manual_changes_with_original_ini_encoding(raw, edited, prefix):
    encoded = IniDocument.parse(raw).encode_text_like_source(edited)
    assert encoded.startswith(prefix)
    assert IniDocument.parse(encoded).to_text() == edited


def test_editor_keeps_original_windows_newlines_when_text_widget_returns_lf():
    original = b"\xff\xfe" + "[S]\r\nX=1\r\n".encode("utf-16-le")
    encoded = IniDocument.parse(original).encode_text_like_source("[S]\nX=2\n")
    assert IniDocument.parse(encoded).to_text() == "[S]\r\nX=2\r\n"


def test_manifest_policy_blocks_managed_change_but_allows_external_mod_key():
    profile = SimpleNamespace(managed_ini_options={
        "GUS": [{"section": "ServerSettings", "key": "DifficultyOffset"}],
    })
    original = b"[ServerSettings]\nDifficultyOffset=1\n[ExternalMod]\nOption=old\n"
    external_edit = b"[ServerSettings]\nDifficultyOffset=1\n[ExternalMod]\nOption=new\n"
    managed_edit = b"[ServerSettings]\nDifficultyOffset=2\n[ExternalMod]\nOption=old\n"

    assert _managed_ini_changes("GameUserSettings.ini", original, external_edit, profile) == []
    assert _managed_ini_changes("GameUserSettings.ini", original, managed_edit, profile) == ["[serversettings] difficultyoffset"]


def test_install_conflicts_detect_windows_case_and_separators_and_samefile(tmp_path):
    profile = SimpleNamespace(id="other", name="Other", install_dir=r"C:\ARK\Server\..\One")
    target = r"c:/ark/one"
    assert normalized_install_path(profile.install_dir) == normalized_install_path(target)
    assert find_install_conflicts("target", target, [profile]) == [profile]

    real = tmp_path / "server"
    real.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(real, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Directory symlinks are unavailable: {exc}")
    other = SimpleNamespace(id="alias", name="Alias", install_dir=str(alias))
    assert find_install_conflicts("target", str(real), [other]) == [other]


def test_backup_is_byte_exact_and_written_before_atomic_replacement(tmp_path):
    target = tmp_path / "Game.ini"
    original = b"\xff\xfe" + "[External]\r\nKey=old\r\n".encode("utf-16-le")
    target.write_bytes(original)

    backup = write_with_backup(target, b"new", expected_original=original, timestamp="fixed")

    assert backup is not None
    assert backup.read_bytes() == original
    assert target.read_bytes() == b"new"


def test_changed_file_is_not_overwritten_by_stale_editor_and_no_backup_is_created(tmp_path):
    target = tmp_path / "Game.ini"
    target.write_bytes(b"[S]\nK=external\n")

    with pytest.raises(RuntimeError, match="mudou desde que foi aberto"):
        write_with_backup(target, b"[S]\nK=editor\n", expected_original=b"[S]\nK=opened\n")

    assert target.read_bytes() == b"[S]\nK=external\n"
    assert not (tmp_path / "ArklandIniBackups").exists()


def test_atomic_write_failure_keeps_original_and_recoverable_backup(tmp_path, monkeypatch):
    import src.ini_write_safety as safety

    target = tmp_path / "Game.ini"
    original = b"[S]\nK=old\n"
    target.write_bytes(original)
    real_replace = safety.os.replace

    def fail_only_target(source, destination):
        if Path(destination) == target:
            raise OSError("simulated replace failure")
        return real_replace(source, destination)

    monkeypatch.setattr(safety.os, "replace", fail_only_target)
    with pytest.raises(OSError, match="simulated replace failure"):
        write_with_backup(target, b"[S]\nK=new\n", expected_original=original, timestamp="fixed")

    assert target.read_bytes() == original
    assert (tmp_path / "ArklandIniBackups" / "Game.ini_fixed.bak").read_bytes() == original
    assert not list(tmp_path.glob(".*.tmp"))
