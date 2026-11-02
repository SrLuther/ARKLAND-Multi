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
