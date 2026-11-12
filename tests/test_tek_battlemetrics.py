from __future__ import annotations

import threading
from types import SimpleNamespace

from src.battlemetrics_client import BattleMetricsData
from src.server_manager import ServerManager


class _Poller:
    def __init__(self):
        self.mapping = {}
        self.data = {}

    def set_servers(self, mapping):
        self.mapping = dict(mapping)

    def get(self, server_id):
        return self.data.get(server_id)


def test_shared_battlemetrics_poller_maps_classic_and_tek_profiles():
    manager = object.__new__(ServerManager)
    manager._lock = threading.Lock()
    manager._instances = {
        "classic": SimpleNamespace(config=SimpleNamespace(battlemetrics_id="111")),
    }
    manager._external_bm_mapping = {}
    manager._bm_poller = _Poller()
    manager._on_bm_update_cb = lambda _sid: None

    manager.set_external_battlemetrics_servers({"tek": "222", "empty": ""})

    assert manager._bm_poller.mapping == {"classic": "111", "tek": "222"}


def test_battlemetrics_callback_reaches_tek_profile_without_classic_instance():
    manager = object.__new__(ServerManager)
    manager._lock = threading.Lock()
    manager._instances = {}
    manager._external_bm_mapping = {"tek": "222"}
    manager._bm_poller = _Poller()
    manager._on_bm_update_cb_calls = []
    manager._on_bm_update_cb = manager._on_bm_update_cb_calls.append
    data = BattleMetricsData(True, 7, 70, "TEK server")
    manager._bm_poller.data["tek"] = data

    manager._on_bm_update("tek", data)

    assert manager._on_bm_update_cb_calls == ["tek"]
    assert manager.get_battlemetrics_data("tek") is data
