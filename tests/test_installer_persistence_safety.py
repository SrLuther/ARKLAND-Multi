from pathlib import Path


def test_installer_does_not_delete_persistent_appdata_directories():
    installer = Path(__file__).resolve().parents[1] / "setup.iss"
    text = installer.read_text(encoding="utf-8-sig")

    assert "[InstallDelete]" not in text
    assert "asm_servers.json" not in text
    assert "Game.ini" not in text
    assert "GameUserSettings.ini" not in text
