"""Testes do ForceDay no start (config + worker RCON)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.config_manager import AppConfig, ConfigManager
from src.force_day_on_start import _apply_force_day_worker


def test_appconfig_force_day_defaults() -> None:
    cfg = AppConfig()
    assert cfg.force_day_on_start_enabled is False
    assert cfg.force_day_on_start == 20


def test_config_load_clamps_force_day(tmp_path, monkeypatch) -> None:
    cfg_dir = tmp_path / "ARKLAND-ServerManager"
    cfg_dir.mkdir()
    (cfg_dir / "config.json").write_text(
        '{"force_day_on_start_enabled": true, "force_day_on_start": -5}',
        encoding="utf-8",
    )
    monkeypatch.setenv("APPDATA", str(tmp_path))
    cm = ConfigManager()
    assert cm.config.force_day_on_start_enabled is True
    assert cm.config.force_day_on_start == 0


def test_apply_force_day_sends_setday_and_saveworld() -> None:
    logs: list[tuple[str, str]] = []

    class _FakeRcon:
        def __init__(self, *a, **k):
            pass

        def connect(self) -> None:
            return None

        def disconnect(self) -> None:
            return None

        def send_command_with_retry(self, command: str, retries: int = 3):
            return True, f"ok:{command}"

    with (
        patch("src.force_day_on_start._INITIAL_DELAY_S", 0),
        patch("src.force_day_on_start.time.sleep", lambda *_a, **_k: None),
        patch("src.rcon_client.RconClient", _FakeRcon),
    ):
        _apply_force_day_worker(
            server_id="srv1",
            server_name="TheIsland",
            rcon_host="127.0.0.1",
            rcon_port=27020,
            rcon_password="secret",
            day=20,
            on_log=lambda m, lv: logs.append((lv, m)),
            save_world=True,
        )

    assert any("SetDay 20 aplicado" in m for _, m in logs)
    assert any(lv == "info" for lv, m in logs if "SetDay 20" in m)


def test_apply_force_day_retries_then_succeeds() -> None:
    logs: list[tuple[str, str]] = []
    calls = {"n": 0}

    class _FlakyRcon:
        def __init__(self, *a, **k):
            pass

        def connect(self) -> None:
            calls["n"] += 1
            if calls["n"] < 3:
                raise OSError("connection refused")

        def disconnect(self) -> None:
            return None

        def send_command_with_retry(self, command: str, retries: int = 3):
            return True, "ok"

    with (
        patch("src.force_day_on_start._INITIAL_DELAY_S", 0),
        patch("src.force_day_on_start._MAX_WAIT_S", 60),
        patch("src.force_day_on_start._BACKOFF_START_S", 0.01),
        patch("src.force_day_on_start._BACKOFF_MAX_S", 0.01),
        patch("src.force_day_on_start.time.sleep", lambda *_a, **_k: None),
        patch("src.rcon_client.RconClient", _FlakyRcon),
    ):
        _apply_force_day_worker(
            server_id="srv1",
            server_name="Rag",
            rcon_host="127.0.0.1",
            rcon_port=27020,
            rcon_password="secret",
            day=42,
            on_log=lambda m, lv: logs.append((lv, m)),
            save_world=False,
        )

    assert calls["n"] >= 3
    assert any("SetDay 42 aplicado" in m for _, m in logs)


def test_clear_force_day_pending_skipped_during_restart() -> None:
    """Regressão: STOPPED atrasado não pode apagar pending do start seguinte."""
    from src.asm_engine.asm_server_manager import AsmServerManager

    mgr = AsmServerManager(on_status_change=None, on_log=lambda *_a, **_k: None)
    sid = "map-alps"
    mgr.begin_force_day_restart(sid)
    mgr.mark_force_day_pending(sid)
    mgr.clear_force_day_pending(sid)  # simula STOPPED atrasado
    assert mgr.consume_force_day_pending(sid) is True
    mgr.end_force_day_restart(sid)
    mgr.mark_force_day_pending(sid)
    mgr.clear_force_day_pending(sid)
    assert mgr.consume_force_day_pending(sid) is False
