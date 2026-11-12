from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from src.asm_engine import asm_config_manager as asm_config_module
from src.asm_engine.asm_config_manager import AsmConfigManager
from src.asm_engine.asm_server_config import AsmServerConfig


@pytest.fixture
def managers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    first = AsmConfigManager()
    first.add_server(AsmServerConfig(name="Alps"))
    second = AsmConfigManager()
    return tmp_path / "ARKLAND-ServerManager" / "asm_servers.json", first, second


def test_concurrent_manager_instances_do_not_share_temp_file(managers):
    profile, first, second = managers

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(manager.save) for manager in (first, second) for _ in range(40)]
        for future in futures:
            future.result()

    assert json.loads(profile.read_text(encoding="utf-8"))[0]["name"] == "Alps"
    assert not list(profile.parent.glob("asm_servers.json.*.tmp"))


def test_transient_windows_sharing_violation_retries_without_losing_profile(
    managers, monkeypatch: pytest.MonkeyPatch
):
    profile, manager, _ = managers
    original = profile.read_text(encoding="utf-8")
    real_replace = asm_config_module.os.replace
    calls = 0

    def replace_with_transient_lock(source, destination):
        nonlocal calls
        calls += 1
        if calls <= 2:
            error = PermissionError(32, "sharing violation")
            error.winerror = 32
            raise error
        real_replace(source, destination)

    monkeypatch.setattr(asm_config_module.os, "replace", replace_with_transient_lock)
    monkeypatch.setattr(asm_config_module.time, "sleep", lambda _seconds: None)
    manager.save()

    assert calls == 3
    assert json.loads(profile.read_text(encoding="utf-8"))[0]["name"] == "Alps"
    assert original


def test_persistent_windows_sharing_violation_preserves_old_json(
    managers, monkeypatch: pytest.MonkeyPatch
):
    profile, manager, _ = managers
    original = profile.read_bytes()

    def always_locked(_source, _destination):
        error = PermissionError(32, "sharing violation")
        error.winerror = 32
        raise error

    monkeypatch.setattr(asm_config_module.os, "replace", always_locked)
    monkeypatch.setattr(asm_config_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(PermissionError):
        manager.save()

    assert profile.read_bytes() == original
    assert not list(profile.parent.glob("asm_servers.json.*.tmp"))


def test_batch_profile_update_rolls_back_all_memory_changes_when_save_fails(managers, monkeypatch):
    profile_path, manager, _ = managers
    manager.add_server(AsmServerConfig(id="second", name="Before"))
    before_bytes = profile_path.read_bytes()
    before_profiles = manager.servers
    first, second = [AsmServerConfig.from_dict(item.to_dict()) for item in before_profiles]
    first.name = "Changed first"
    second.name = "Changed second"

    def fail_save():
        raise OSError("simulated profile save failure")

    monkeypatch.setattr(manager, "save", fail_save)
    with pytest.raises(OSError, match="simulated profile save failure"):
        manager.update_servers([first, second])

    assert manager.servers == before_profiles
    assert profile_path.read_bytes() == before_bytes


def test_unknown_profile_fields_survive_load_edit_and_save(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    profile_path = tmp_path / "ARKLAND-ServerManager" / "asm_servers.json"
    profile_path.parent.mkdir(parents=True)
    original = [{"id": "legacy", "name": "Legacy", "future_feature": {"enabled": True, "ids": [1, 2]}}]
    profile_path.write_text(json.dumps(original), encoding="utf-8")

    manager = AsmConfigManager()
    loaded = manager.get_server("legacy")
    assert loaded is not None
    loaded.name = "Edited"
    manager.update_server(loaded)

    saved = json.loads(profile_path.read_text(encoding="utf-8"))[0]
    assert saved["name"] == "Edited"
    assert saved["future_feature"] == {"enabled": True, "ids": [1, 2]}


def test_loading_legacy_profile_does_not_rewrite_json(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    profile_path = tmp_path / "ARKLAND-ServerManager" / "asm_servers.json"
    profile_path.parent.mkdir(parents=True)
    original = [{
        "id": "legacy-cap",
        "name": "Legacy cap",
        "player_xp_curve_mode": "custom",
        "player_base_level": 250,
        "player_level_progressions_enabled": True,
        "player_level_stats_raw": "",
    }]
    original_bytes = json.dumps(original, indent=2).encode("utf-8")
    profile_path.write_bytes(original_bytes)

    manager = AsmConfigManager()

    assert manager.get_server("legacy-cap").player_base_level == 150
    assert profile_path.read_bytes() == original_bytes
