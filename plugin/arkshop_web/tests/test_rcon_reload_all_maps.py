"""Testes de Shop.Reload multi-mapas na Web Store."""
from __future__ import annotations

import json

import app as _app_module


def test_rcon_hosts_to_try_prefers_localhost():
    hosts = _app_module._rcon_hosts_to_try(
        {"rcon_host": "192.168.1.50"},
        {"rcon_host": "10.0.0.1"},
    )
    assert hosts[0] == "127.0.0.1"
    assert "192.168.1.50" in hosts


def test_discover_local_rcon_servers_from_asm(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "ARKLAND-ServerManager"
    cfg_dir.mkdir()
    (cfg_dir / "config.json").write_text(
        json.dumps({"machine_public_ip": "203.0.113.40", "shop": {"public_ip": ""}}),
        encoding="utf-8",
    )
    asm = [
        {
            "id": "uuid-1",
            "name": "Ragnarok",
            "install_dir": "C:/ARK/Ragnarok",
            "server_port": 7779,
            "rcon_enabled": True,
            "rcon_port": 27025,
            "admin_password": "secret",
            "shop_server_id": "ragnarok",
        }
    ]
    (cfg_dir / "asm_servers.json").write_text(json.dumps(asm), encoding="utf-8")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(_app_module, "_load_settings", lambda: {})

    found = _app_module._discover_local_rcon_servers()
    assert len(found) == 1
    assert found[0]["server_id"] == "ragnarok"
    assert found[0]["rcon_port"] == 27025
    assert found[0]["game_host"] == "203.0.113.40"
    assert found[0]["game_port"] == 7779


def test_resolve_rcon_reload_targets_merges_discovery(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "ARKLAND-ServerManager"
    cfg_dir.mkdir()
    (cfg_dir / "asm_servers.json").write_text(json.dumps([{
        "id": "uuid-2",
        "name": "Island",
        "install_dir": "C:/ARK/Island",
        "rcon_enabled": True,
        "rcon_port": 27030,
        "admin_password": "pwd123",
        "shop_server_id": "island",
    }]), encoding="utf-8")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(_app_module, "_load_servers", lambda: [{
        "server_id": "island",
        "label": "Island",
        "rcon_host": "192.168.0.10",
        "rcon_port": 27030,
    }])

    targets = _app_module._resolve_rcon_reload_targets({})
    assert len(targets) == 1
    assert targets[0]["rcon_password"] == "pwd123"


def test_rcon_reload_one_server_tries_hosts(monkeypatch):
    calls: list[tuple] = []

    def fake_rcon(host, port, password, command, **kwargs):
        calls.append((host, port, command))
        if host == "127.0.0.1":
            raise RuntimeError("offline")
        return "ok"

    monkeypatch.setattr(_app_module, "_rcon_command", fake_rcon)
    srv = {
        "server_id": "test",
        "label": "Test",
        "rcon_host": "192.168.1.5",
        "rcon_port": 27020,
        "rcon_password": "pass",
    }
    res = _app_module._rcon_reload_one_server(srv, {})
    assert res["ok"] is True
    assert calls[0][0] == "127.0.0.1"
    assert any(c[0] == "192.168.1.5" for c in calls)
