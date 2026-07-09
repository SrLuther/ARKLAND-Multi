"""Testes — aplicação global de ActiveEvent."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from src.asm_engine.asm_server_config import AsmServerConfig
from src.buff_server_bridge import BuffServerEntry
from src.pages.global_active_event import (
    apply_active_event_to_server,
    apply_active_event_to_servers,
    event_id_from_combo_label,
)
from src.server_config import ServerConfig


def test_event_id_from_combo_label_easter():
    label = "Easter — Páscoa / Eggcellent Adventure 🐣"
    assert event_id_from_combo_label(label) == "Easter"


def test_event_id_from_combo_label_none():
    assert event_id_from_combo_label("(nenhum evento)") == ""


def test_apply_active_event_tek_writes_ini(tmp_path):
    install = tmp_path / "srv"
    (install / "ShooterGame" / "Saved" / "Config" / "WindowsServer").mkdir(parents=True)

    srv = AsmServerConfig(
        id="tek-1",
        name="Test TEK",
        install_dir=str(install),
        active_event="",
    )
    asm_cm = MagicMock()
    asm_cm.get_server.return_value = srv

    app = MagicMock()
    app.asm_config_manager = asm_cm

    entry = BuffServerEntry(id="tek-1", name="Test TEK", kind="tek", label="Test TEK (TEK)")
    result = apply_active_event_to_server(app, entry, "Easter")

    assert result.ok
    gus = install / "ShooterGame" / "Saved" / "Config" / "WindowsServer" / "GameUserSettings.ini"
    assert gus.is_file()
    text = gus.read_text(encoding="utf-16")
    assert "ActiveEvent=Easter" in text
    assert srv.active_event == "Easter"
    asm_cm.update_server.assert_called_once_with(srv)
    asm_cm.save.assert_called_once()


def test_apply_active_event_primitive_writes_ini(tmp_path):
    install = tmp_path / "leg"
    (install / "ShooterGame" / "Saved" / "Config" / "WindowsServer").mkdir(parents=True)

    srv = ServerConfig(
        id="leg-1",
        name="Test Leg",
        install_dir=str(install),
        active_event="",
    )
    app = MagicMock()
    app.asm_config_manager = None
    app.config_manager.get_server.return_value = srv

    entry = BuffServerEntry(id="leg-1", name="Test Leg", kind="primitive", label="Test Leg (legado)")
    result = apply_active_event_to_server(app, entry, "FearEvolved")

    assert result.ok
    gus = install / "ShooterGame" / "Saved" / "Config" / "WindowsServer" / "GameUserSettings.ini"
    assert gus.is_file()
    text = gus.read_text(encoding="utf-8")
    assert "ActiveEvent=FearEvolved" in text or "ActiveEvent = FearEvolved" in text
    assert srv.active_event == "FearEvolved"
    app.config_manager.update_server.assert_called_once_with(srv)
    app.config_manager.save.assert_called_once()


def test_apply_active_event_to_multiple_servers(tmp_path):
    install_a = tmp_path / "a"
    install_b = tmp_path / "b"
    for p in (install_a, install_b):
        (p / "ShooterGame" / "Saved" / "Config" / "WindowsServer").mkdir(parents=True)

    srv_a = AsmServerConfig(id="a", name="A", install_dir=str(install_a))
    srv_b = AsmServerConfig(id="b", name="B", install_dir=str(install_b))

    asm_cm = MagicMock()

    def _get(sid):
        return {"a": srv_a, "b": srv_b}.get(sid)

    asm_cm.get_server.side_effect = _get

    app = MagicMock()
    app.asm_config_manager = asm_cm
    app.config_manager.servers = []

    from src.buff_server_bridge import list_buff_servers

    app.asm_config_manager.servers = [srv_a, srv_b]

    results = apply_active_event_to_servers(app, ["a", "b"], "Easter")
    assert len(results) == 2
    assert all(r.ok for r in results)
