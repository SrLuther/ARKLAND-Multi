"""Testes do ForceDay — SetDay via RCON desativado (crash ASE 361.7)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from src.config_manager import AppConfig, ConfigManager
from src.force_day_on_start import (
    FORCE_DAY_RCON_ENABLED,
    _apply_force_day_worker,
    schedule_force_day,
)


def test_forceday_rcon_kill_switch_off() -> None:
    assert FORCE_DAY_RCON_ENABLED is False


def test_appconfig_force_day_defaults() -> None:
    cfg = AppConfig()
    assert cfg.force_day_on_start_enabled is False
    assert cfg.force_day_on_start == 20


def test_config_load_forces_force_day_off(tmp_path, monkeypatch) -> None:
    """Configs antigas com ForceDay ligado devem ser forçadas OFF ao carregar."""
    cfg_dir = tmp_path / "ARKLAND-ServerManager"
    cfg_dir.mkdir()
    (cfg_dir / "config.json").write_text(
        '{"force_day_on_start_enabled": true, "force_day_on_start": -5}',
        encoding="utf-8",
    )
    monkeypatch.setenv("APPDATA", str(tmp_path))
    cm = ConfigManager()
    assert cm.config.force_day_on_start_enabled is False
    assert cm.config.force_day_on_start == 0
    # Persistência: ficheiro reescrito sem enabled=true.
    saved = json.loads((cfg_dir / "config.json").read_text(encoding="utf-8"))
    assert saved.get("force_day_on_start_enabled") is False


def test_schedule_force_day_does_not_send_setday() -> None:
    logs: list[tuple[str, str]] = []
    connect_calls = {"n": 0}

    class _FakeRcon:
        def __init__(self, *a, **k):
            pass

        def connect(self) -> None:
            connect_calls["n"] += 1

        def disconnect(self) -> None:
            return None

        def send_command_with_retry(self, command: str, retries: int = 3):
            raise AssertionError(f"RCON não deveria enviar: {command}")

    with patch("src.rcon_client.RconClient", _FakeRcon):
        schedule_force_day(
            server_id="srv1",
            server_name="TheIsland",
            rcon_host="127.0.0.1",
            rcon_port=27020,
            rcon_password="secret",
            day=20,
            on_log=lambda m, lv: logs.append((lv, m)),
            save_world=True,
        )
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

    assert connect_calls["n"] == 0
    assert any("BLOQUEADO" in m for _, m in logs)
    assert any(lv == "error" for lv, m in logs if "BLOQUEADO" in m)


def test_save_global_config_tek_never_persists_force_day_enabled() -> None:
    """UI/save não pode reativar ForceDay mesmo com BooleanVar True."""
    from src.pages.save_global_config_tek import save_global_config_tek

    app = MagicMock()
    cfg = AppConfig()
    cfg.force_day_on_start_enabled = True
    app.config_manager.config = cfg
    app.config_manager.save = MagicMock()

    def _fake_g(a, name, typ=None, strip=False):
        if name == "_cfg_force_day_var":
            return "42"
        if typ is not None:
            return False
        return ""

    with (
        patch("src.pages.save_global_config_tek._g", side_effect=_fake_g),
        patch("src.pages.save_global_config_tek._save_discord"),
        patch("src.pages.save_global_config_tek._save_backup"),
        patch("src.pages.save_global_config_tek._save_auto_update"),
        patch("src.pages.save_global_config_tek._save_shutdown"),
        patch("src.pages.save_global_config_tek._save_alert_messages"),
        patch("src.pages.save_global_config_tek._save_discord_bot"),
        patch("src.pages.save_global_config_tek._save_smtp"),
        patch("src.pages.save_global_config_tek._save_startup_registry"),
        patch("src.pages.save_global_config_tek.messagebox"),
    ):
        save_global_config_tek(app)

    assert cfg.force_day_on_start_enabled is False
    assert cfg.force_day_on_start == 42


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
