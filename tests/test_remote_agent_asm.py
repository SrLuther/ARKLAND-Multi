import threading

from src.asm_engine.asm_server_config import AsmServerConfig
from src.asm_engine.asm_server_manager import AsmServerInstance, AsmServerManager
from src.remote_agent import RemoteAgent, RemoteClient


def _offline_asm_manager():
    manager = AsmServerManager.__new__(AsmServerManager)
    manager._lock = threading.RLock()
    config = AsmServerConfig(
        id="offline-ase-1",
        name="ARK Ragnarok",
        server_map="Ragnarok",
        server_port=7777,
        install_dir="C:/ARK/Ragnarok",
    )
    manager._instances = {config.id: AsmServerInstance(config)}
    return manager, config


def test_remote_agent_lists_configured_ase_server_even_when_stopped():
    manager, config = _offline_asm_manager()
    agent = RemoteAgent(manager, port=0, token="test-token", name="ASE Host")
    agent.start()
    try:
        port = agent._server.server_address[1]
        payload = RemoteClient("127.0.0.1", port, "test-token").get_servers()
        assert len(payload["servers"]) == 1
        server = payload["servers"][0]
        assert server["id"] == config.id
        assert server["name"] == "ARK Ragnarok"
        assert server["map"] == "Ragnarok"
        assert server["port"] == 7777
        assert server["status"] == "stopped"
        assert server["pid"] is None
    finally:
        agent.stop()


def test_asm_manager_remote_actions_target_the_selected_server():
    manager, config = _offline_asm_manager()
    calls = []
    manager.start = lambda cfg: calls.append(("start", cfg.id))
    manager.stop = lambda sid: calls.append(("stop", sid))
    manager.restart = lambda cfg: calls.append(("restart", cfg.id))

    assert manager.start_server(config.id) is True
    manager.get_instance(config.id).status = "running"
    assert manager.stop_server(config.id) is True
    assert manager.restart_server(config.id) is True
    assert calls == [
        ("start", config.id),
        ("stop", config.id),
        ("restart", config.id),
    ]


def test_asm_manager_does_not_start_a_server_that_is_already_running():
    manager, config = _offline_asm_manager()
    manager.get_instance(config.id).status = "running"
    called = []
    manager.start = lambda _cfg: called.append(True)

    assert manager.start_server(config.id) is False
    assert called == []


def test_identity_code_prefers_configured_public_host(monkeypatch):
    from types import SimpleNamespace
    from src.pages import refresh_identity_code as identity_page
    from src.remote_agent import parse_identity_code

    class _Value:
        value = ""

        def set(self, value):
            self.value = value

    code = _Value()
    status = _Value()
    app = SimpleNamespace(
        config_manager=SimpleNamespace(config=SimpleNamespace(
            remote_agent_name="Production", remote_agent_port=32440,
            remote_agent_token="secret-token", remote_agent_host="arkland.example.net",
        )),
        _remote_code_var=code,
        _remote_ip_var=status,
    )
    monkeypatch.setattr(identity_page, "local_ip", lambda: "192.168.15.51")

    identity_page.refresh_identity_code(app)

    assert parse_identity_code(code.value)["h"] == "arkland.example.net"
    assert "192.168.15.51" in status.value
