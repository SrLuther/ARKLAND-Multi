from pathlib import Path

import pytest

from src.ini_sync import diff_ini_bytes, diff_ini_entries, merge_ini_sections, sync_ini_targets


def test_diff_counts_only_ini_entries_and_preserves_repeated_keys():
    source = b"; config comment\r\n[ServerSettings]\r\nA=1\r\nModIDS=10\r\nModIDS=11\r\n"
    destination = b"[ServerSettings]\nA=2\nModIDS=10\nExtra=1\n"

    assert diff_ini_bytes(source, destination) == (2, 2)


def test_diff_ini_entries_shows_changes_and_redacts_credentials():
    source = b"[ServerSettings]\nServerAdminPassword=new-secret\nDifficultyOffset=2\n"
    destination = b"[serversettings]\nserveradminpassword=old-secret\nDifficultyOffset=1\n"

    added, removed = diff_ini_entries(source, destination)

    assert added == [
        "[ServerSettings] ServerAdminPassword=<oculto>",
        "[ServerSettings] DifficultyOffset=2",
    ]
    assert removed == [
        "[serversettings] serveradminpassword=<oculto>",
        "[serversettings] DifficultyOffset=1",
    ]


def test_merge_selected_sections_replaces_only_selected_and_preserves_other_sections():
    source = (
        b"; source note\r\n[ServerSettings]\r\nDifficultyOffset=2\r\n"
        b"[SessionSettings]\r\nSessionName=New\r\nSessionName=Second\r\n"
    )
    destination = (
        b"[ServerSettings]\nDifficultyOffset=1\nLocalSetting=keep\n"
        b"[SessionSettings]\nSessionName=Old\n[LocalMods]\nActiveMods=123\n"
    )

    merged = merge_ini_sections(source, destination, {"serversettings"})

    assert merged == (
        b"[ServerSettings]\nDifficultyOffset=2\n"
        b"[SessionSettings]\nSessionName=Old\n[LocalMods]\nActiveMods=123\n"
    )


def test_merge_selected_section_removes_destination_section_missing_from_source():
    source = b"[ServerSettings]\nA=2\n"
    destination = b"[ServerSettings]\nA=1\n[SessionSettings]\nName=local\n"

    merged = merge_ini_sections(source, destination, {"sessionsettings"})

    assert merged == b"[ServerSettings]\nA=1\n"


def test_merge_selected_sections_with_no_destination_uses_only_selected_sections():
    source = b"[A]\nValue=1\n[B]\nValue=2\n"

    merged = merge_ini_sections(source, None, {"B"})

    assert merged == b"[B]\nValue=2\n"


def test_sync_creates_persistent_backup_and_writes_config_only(tmp_path: Path):
    destination = tmp_path / "Game.ini"
    destination.write_bytes(b"[Old]\nValue=old\n")

    backups = sync_ini_targets(
        {destination: b"; remove prose\n[New]\nValue=ok\n"},
        timestamp="fixed",
    )

    assert destination.read_bytes() == b"[New]\nValue=ok\n"
    assert len(backups) == 1
    assert backups[0].read_bytes() == b"[Old]\nValue=old\n"
    assert backups[0].parent == tmp_path / "ArklandIniBackups"


def test_sync_rolls_back_prior_targets_when_a_later_write_fails(tmp_path: Path, monkeypatch):
    first = tmp_path / "first.ini"
    second = tmp_path / "second.ini"
    first.write_bytes(b"[S]\nK=old1\n")
    second.write_bytes(b"[S]\nK=old2\n")

    import src.ini_sync as sync_module

    real_atomic_write = sync_module._atomic_write

    def failing_write(path: Path, data: bytes) -> None:
        if path == second and data == b"[S]\nK=new2\n":
            raise OSError("simulated failure")
        real_atomic_write(path, data)

    monkeypatch.setattr(sync_module, "_atomic_write", failing_write)

    with pytest.raises(OSError, match="simulated failure"):
        sync_ini_targets({first: b"[S]\nK=new1\n", second: b"[S]\nK=new2\n"})

    assert first.read_bytes() == b"[S]\nK=old1\n"
    assert second.read_bytes() == b"[S]\nK=old2\n"
