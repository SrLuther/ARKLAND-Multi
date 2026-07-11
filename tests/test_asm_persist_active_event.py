"""Testes — ActiveEvent não deve ser apagado no restart quando o painel está fechado."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from src.asm_engine.asm_server_config import AsmServerConfig
from src.asm_ui.asm_server_panel import _sync_ui_to_cfg, is_asm_panel_active_for


def _mock_var(value: str) -> MagicMock:
    var = MagicMock()
    var.get.return_value = value
    return var


def test_is_asm_panel_active_for():
    app = MagicMock()
    app._asm_panel_active_server_id = "srv-a"
    assert is_asm_panel_active_for(app, "srv-a")
    assert not is_asm_panel_active_for(app, "srv-b")


def test_sync_ui_skips_when_panel_not_active():
    srv = AsmServerConfig(id="tek-1", name="Test", active_event="Easter")
    app = MagicMock()
    app._asm_panel_active_server_id = None
    app._asm_panel_vars = {
        "tek-1": {"active_event": _mock_var("(nenhum evento)")},
    }
    _sync_ui_to_cfg(app, srv)
    assert srv.active_event == "Easter"


def test_sync_ui_applies_when_panel_active():
    srv = AsmServerConfig(id="tek-1", name="Test", active_event="Easter")
    app = MagicMock()
    app._asm_panel_active_server_id = "tek-1"
    app._asm_panel_vars = {
        "tek-1": {"active_event": _mock_var("(nenhum evento)")},
    }
    _sync_ui_to_cfg(app, srv)
    assert srv.active_event == ""


def test_asm_persist_keeps_active_event_when_panel_closed(tmp_path):
    install = tmp_path / "srv"
    (install / "ShooterGame" / "Saved" / "Config" / "WindowsServer").mkdir(parents=True)

    srv = AsmServerConfig(
        id="tek-1",
        name="Test TEK",
        install_dir=str(install),
        active_event="Easter",
    )
    asm_cm = MagicMock()
    asm_cm.get_server.return_value = srv

    app = MagicMock()
    app.asm_config_manager = asm_cm
    app._asm_panel_active_server_id = None
    app._asm_panel_vars = {
        "tek-1": {"active_event": _mock_var("(nenhum evento)")},
    }

    from src.app_tek import ARKTEKApp

    persisted = ARKTEKApp._asm_persist_server(app, srv)

    assert persisted.active_event == "Easter"
    gus = install / "ShooterGame" / "Saved" / "Config" / "WindowsServer" / "GameUserSettings.ini"
    assert gus.is_file()
    text = gus.read_text(encoding="utf-16")
    assert "ActiveEvent=Easter" in text
