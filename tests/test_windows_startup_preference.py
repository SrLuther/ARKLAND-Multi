from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.config_manager import AppConfig, ConfigManager
from src.pages.save_global_config_tek import _save_startup_registry


def test_startup_enabled_by_default_for_new_configuration() -> None:
    cfg = AppConfig()
    assert cfg.startup_with_windows is True
    assert cfg.startup_with_windows_preference_version == 1


def test_old_saved_default_is_migrated_once_and_can_then_be_disabled(
    tmp_path, monkeypatch
) -> None:
    config_dir = tmp_path / "ARKLAND-ServerManager"
    config_dir.mkdir()
    config_path = config_dir / "config.json"
    config_path.write_text(
        json.dumps({"startup_with_windows": False, "remote_agent_token": "test-token"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("APPDATA", str(tmp_path))

    migrated = ConfigManager()
    assert migrated.config.startup_with_windows is True
    # Apenas carregar não grava o perfil; a preferência só é persistida ao salvar.
    assert json.loads(config_path.read_text(encoding="utf-8"))["startup_with_windows"] is False
    migrated.save()
    persisted = json.loads(config_path.read_text(encoding="utf-8"))
    assert persisted["startup_with_windows"] is True
    assert persisted["startup_with_windows_preference_version"] == 1

    # Simula o usuário desmarcando a opção e salvando; reiniciar não a reativa.
    persisted["startup_with_windows"] = False
    config_path.write_text(json.dumps(persisted), encoding="utf-8")
    reloaded = ConfigManager()
    assert reloaded.config.startup_with_windows is False


class _FakeRegistry:
    HKEY_CURRENT_USER = object()
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self) -> None:
        self.values: dict[str, object] = {}
        self.path = None

    def OpenKey(self, _root, path, _reserved, _access):  # noqa: N802 - winreg API
        self.path = path
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def SetValueEx(self, _key, name, _reserved, _kind, value):  # noqa: N802 - winreg API
        self.values[name] = value

    def DeleteValue(self, _key, name):  # noqa: N802 - winreg API
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]


def test_startup_setting_registers_and_removes_windows_entry() -> None:
    registry = _FakeRegistry()

    assert _save_startup_registry(None, SimpleNamespace(startup_with_windows=True), registry) is None
    assert registry.path == r"Software\Microsoft\Windows\CurrentVersion\Run"
    assert "ARKLAND-ServerManager" in registry.values
    assert "main.py" in str(registry.values["ARKLAND-ServerManager"])

    assert _save_startup_registry(None, SimpleNamespace(startup_with_windows=False), registry) is None
    assert "ARKLAND-ServerManager" not in registry.values


@pytest.mark.parametrize("enabled", [True, False])
def test_global_settings_checkbox_controls_startup_registry(enabled: bool) -> None:
    from src.pages.save_global_config_tek import save_global_config_tek

    registry = _FakeRegistry()
    registry.values["ARKLAND-ServerManager"] = "previous-entry"
    app = MagicMock()
    app.config_manager.config = AppConfig()
    app.config_manager.save = MagicMock()

    def fake_value(_app, name, _typ=None, strip=False):
        if name == "_cfg_startup_var":
            return enabled  # simula marcar ou desmarcar a caixa na interface
        if name == "_cfg_force_day_var":
            return "20"
        return "" if strip else False

    with (
        patch.dict(sys.modules, {"winreg": registry}),
        patch("src.pages.save_global_config_tek._g", side_effect=fake_value),
        patch("src.pages.save_global_config_tek._save_discord"),
        patch("src.pages.save_global_config_tek._save_backup"),
        patch("src.pages.save_global_config_tek._save_auto_update"),
        patch("src.pages.save_global_config_tek._save_shutdown"),
        patch("src.pages.save_global_config_tek._save_alert_messages"),
        patch("src.pages.save_global_config_tek._save_discord_bot"),
        patch("src.pages.save_global_config_tek._save_smtp"),
        patch("src.pages.save_global_config_tek.messagebox"),
    ):
        save_global_config_tek(app)

    assert app.config_manager.config.startup_with_windows is enabled
    if enabled:
        assert "ARKLAND-ServerManager" in registry.values
    else:
        assert "ARKLAND-ServerManager" not in registry.values
    app.config_manager.save.assert_called_once()
