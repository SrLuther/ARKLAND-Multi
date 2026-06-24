"""Testes do scheduler e configuração de broadcasts TEK."""
from src.config_manager import BroadcastTekConfig
from src.pages.broadcast_tek_settings import (
    pick_next_message,
    resolve_rotation_messages,
    resolve_target_server_ids,
    seconds_until_next,
)


class _Srv:
    def __init__(self, sid: str, name: str):
        self.id = sid
        self.name = name


class _FakeCM:
    def __init__(self, settings: BroadcastTekConfig, library: list):
        class C:
            broadcast_tek = settings
            broadcast_library = library
        self.config = C()


class _FakeAsm:
    def __init__(self, servers):
        self.servers = servers


class _FakeApp:
    def __init__(self, servers, settings=None, library=None):
        self.asm_config_manager = _FakeAsm(servers)
        self.config_manager = _FakeCM(settings or BroadcastTekConfig(), library or [])


def test_resolve_target_all_when_empty():
    app = _FakeApp([_Srv("a", "A"), _Srv("b", "B")])
    assert resolve_target_server_ids(app) == ["a", "b"]


def test_resolve_target_subset():
    app = _FakeApp([_Srv("a", "A"), _Srv("b", "B")])
    app.config_manager.config.broadcast_tek.target_server_ids = ["b"]
    assert resolve_target_server_ids(app) == ["b"]


def test_rotation_sequential():
    lib = [
        {"id": "1", "label": "A", "message": "a"},
        {"id": "2", "label": "B", "message": "b"},
    ]
    settings = BroadcastTekConfig(random_order=False, rotation_index=0)
    app = _FakeApp([], settings, lib)
    e1, idx1 = pick_next_message(app)
    assert e1["id"] == "1"
    assert idx1 == 1
    settings.rotation_index = 1
    e2, idx2 = pick_next_message(app)
    assert e2["id"] == "2"
    assert idx2 == 0


def test_rotation_random_stays_index():
    lib = [{"id": "1", "label": "A", "message": "a"}]
    settings = BroadcastTekConfig(random_order=True, rotation_index=3)
    app = _FakeApp([], settings, lib)
    entry, idx = pick_next_message(app)
    assert entry["id"] == "1"
    assert idx == 3


def test_seconds_until_next():
    import time
    s = BroadcastTekConfig(scheduler_enabled=True, interval_minutes=30, last_sent_at=time.time())
    assert seconds_until_next(s) <= 1800
