"""Testes para classificação de status Steam/LAN (paridade ASM)."""
from __future__ import annotations

import unittest
import json
from types import SimpleNamespace
from unittest.mock import patch

from src.server_visibility import (
    STEAM_AVAILABLE,
    STEAM_LAN,
    STEAM_NEED_PUBLIC_IP,
    STEAM_UNAVAILABLE,
    STEAM_WAITING,
    classify_steam_status,
    format_status_badge,
    is_lan_match_config,
    _parse_a2s_info,
    check_steam_master_list,
    resolve_machine_public_ip,
)
import src.server_visibility as server_visibility


class TestClassifySteamStatus(unittest.TestCase):
    def test_stopped(self) -> None:
        mode, _ = classify_steam_status(
            process_running=False,
            lan_configured=False,
            local_query_ok=False,
            public_ip="1.2.3.4",
            public_query_ok=False,
            steam_master_ok=False,
        )
        self.assertEqual(mode, STEAM_UNAVAILABLE)

    def test_lan_mode(self) -> None:
        mode, _ = classify_steam_status(
            process_running=True,
            lan_configured=True,
            local_query_ok=True,
            public_ip="",
            public_query_ok=False,
            steam_master_ok=False,
        )
        self.assertEqual(mode, STEAM_LAN)

    def test_initializing(self) -> None:
        mode, _ = classify_steam_status(
            process_running=True,
            lan_configured=False,
            local_query_ok=False,
            public_ip="1.2.3.4",
            public_query_ok=False,
            steam_master_ok=False,
        )
        self.assertEqual(mode, STEAM_UNAVAILABLE)

    def test_need_public_ip(self) -> None:
        mode, _ = classify_steam_status(
            process_running=True,
            lan_configured=False,
            local_query_ok=True,
            public_ip="",
            public_query_ok=False,
            steam_master_ok=False,
        )
        self.assertEqual(mode, STEAM_NEED_PUBLIC_IP)

    def test_waiting(self) -> None:
        mode, _ = classify_steam_status(
            process_running=True,
            lan_configured=False,
            local_query_ok=True,
            public_ip="1.2.3.4",
            public_query_ok=False,
            steam_master_ok=False,
        )
        self.assertEqual(mode, STEAM_WAITING)

    def test_public_query_without_master_listing_waits(self) -> None:
        mode, _ = classify_steam_status(
            process_running=True,
            lan_configured=False,
            local_query_ok=True,
            public_ip="1.2.3.4",
            public_query_ok=True,
            steam_master_ok=False,
        )
        self.assertEqual(mode, STEAM_WAITING)

    def test_master_listing_without_public_query_waits(self) -> None:
        mode, _ = classify_steam_status(
            process_running=True,
            lan_configured=False,
            local_query_ok=True,
            public_ip="1.2.3.4",
            public_query_ok=False,
            steam_master_ok=True,
        )
        self.assertEqual(mode, STEAM_WAITING)

    def test_available_requires_public_query_and_master_listing(self) -> None:
        mode, _ = classify_steam_status(
            process_running=True,
            lan_configured=False,
            local_query_ok=True,
            public_ip="1.2.3.4",
            public_query_ok=True,
            steam_master_ok=True,
        )
        self.assertEqual(mode, STEAM_AVAILABLE)


class TestFormatBadge(unittest.TestCase):
    def test_running_steam(self) -> None:
        text, _ = format_status_badge("running", STEAM_AVAILABLE)
        self.assertIn("Steam", text)
        self.assertIn("ONLINE", text)

    def test_running_waiting(self) -> None:
        text, _ = format_status_badge("running", STEAM_WAITING)
        self.assertIn("Aguardando", text)

    def test_starting(self) -> None:
        text, _ = format_status_badge("starting", STEAM_UNAVAILABLE)
        self.assertEqual(text, "INICIANDO")


class TestLanConfig(unittest.TestCase):
    def test_lan_flag_in_args(self) -> None:
        cfg = SimpleNamespace(
            additional_args="?bIsLanMatch=True",
            server_map="TheIsland",
        )
        self.assertTrue(is_lan_match_config(cfg))


class TestResolvePublicIp(unittest.TestCase):
    def test_machine_public_ip_priority(self) -> None:
        cfg = SimpleNamespace(
            machine_public_ip="203.0.113.1",
            shop=SimpleNamespace(public_ip="198.51.100.1"),
        )
        self.assertEqual(resolve_machine_public_ip(cfg), "203.0.113.1")

    def test_shop_fallback(self) -> None:
        cfg = SimpleNamespace(
            machine_public_ip="",
            shop=SimpleNamespace(public_ip="198.51.100.1"),
        )
        self.assertEqual(resolve_machine_public_ip(cfg), "198.51.100.1")


class TestA2SInfoValidation(unittest.TestCase):
    @staticmethod
    def _payload(map_name: str, max_players: int) -> bytes:
        fields = ["[ARKLAND] Ragnarok", map_name, "ark_survival_evolved", "ARK: Survival Evolved"]
        payload = bytearray([17])
        for field in fields:
            payload.extend(field.encode("utf-8"))
            payload.append(0)
        payload.extend((0, 0))  # app id
        payload.extend((0, max_players, 0))  # players, max players, bots
        return bytes(payload)

    def test_accepts_complete_server_metadata(self) -> None:
        info = _parse_a2s_info(self._payload("Ragnarok", 35))
        self.assertEqual(info["map"], "Ragnarok")
        self.assertEqual(info["max_players"], 35)

    def test_rejects_empty_map(self) -> None:
        self.assertEqual(_parse_a2s_info(self._payload("", 35)), {})

    def test_rejects_zero_capacity(self) -> None:
        self.assertEqual(_parse_a2s_info(self._payload("Ragnarok", 0)), {})


class TestSteamMasterListCache(unittest.TestCase):
    def setUp(self) -> None:
        with server_visibility._steam_master_cache_lock:
            server_visibility._steam_master_cache.clear()

    @staticmethod
    def _response(payload: dict[str, object]):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(payload).encode("utf-8")

        return Response()

    def test_one_ip_query_confirms_multiple_map_query_ports(self) -> None:
        payload = {"response": {"success": True, "servers": [
            {"addr": "179.185.19.88:27015", "appid": 346110},
            {"addr": "179.185.19.88:27017", "appid": 346110},
            {"addr": "179.185.19.88:27020", "appid": 346110},
            {"addr": "179.185.19.88:27021", "appid": 730},
        ]}}
        with patch("src.server_visibility.urllib.request.urlopen", return_value=self._response(payload)) as get, \
             patch("src.server_visibility.time.monotonic", return_value=100.0):
            self.assertTrue(check_steam_master_list("179.185.19.88", 7777, 27015))
            self.assertTrue(check_steam_master_list("179.185.19.88", 7781, 27017))
            self.assertTrue(check_steam_master_list("179.185.19.88", 7787, 27020))
            self.assertFalse(check_steam_master_list("179.185.19.88", 7789, 27021))

        self.assertEqual(get.call_count, 1)
        self.assertTrue(get.call_args.args[0].full_url.endswith("addr=179.185.19.88"))

    def test_rate_limit_preserves_recent_positive_result(self) -> None:
        listed = self._response({"response": {"success": True, "servers": [
            {"addr": "179.185.19.88:27015", "appid": 346110},
        ]}})
        limited = self._response({"response": {
            "success": False, "message": "Please don't call this API more often than once per minute for a given IP.",
        }})
        with patch("src.server_visibility.urllib.request.urlopen", side_effect=[listed, limited]) as get, \
             patch("src.server_visibility.time.monotonic", side_effect=[100.0, 161.0, 162.0]):
            self.assertTrue(check_steam_master_list("179.185.19.88", 7777, 27015))
            self.assertTrue(check_steam_master_list("179.185.19.88", 7777, 27015))
            # A later same-minute poll reuses the previous positive listing
            # instead of dropping the confirmed map after a rate-limit reply.
            self.assertTrue(check_steam_master_list("179.185.19.88", 7777, 27015))

        self.assertEqual(get.call_count, 2)


class TestSteamStatusPollerMasterRetention(unittest.TestCase):
    def test_confirmed_master_result_survives_intermediate_ui_polls(self) -> None:
        poller = server_visibility.SteamStatusPoller()
        cfg = SimpleNamespace(
            additional_args="",
            server_map="Ragnarok",
            server_ip="",
            server_port=7781,
            query_port=27016,
        )
        inst = SimpleNamespace()
        reg = server_visibility._ServerRegistration(
            server_id="02_ragnarok",
            cfg=cfg,
            inst=inst,
            is_running=lambda: True,
        )
        poller.set_machine_public_ip("179.185.19.88")

        with patch("src.server_visibility.probe_a2s_info", return_value={"players": 0, "max_players": 35}), \
             patch("src.server_visibility.probe_a2s_query", return_value=True), \
             patch("src.server_visibility.check_steam_master_list", return_value=True) as check_master, \
             patch("src.server_visibility.time.monotonic", side_effect=[100.0, 105.0]):
            poller._poll_one(reg)
            self.assertEqual(inst.steam_status, STEAM_AVAILABLE)

            # The public/master probes are rate-limited to once per minute,
            # but status is refreshed every five seconds. A cached positive
            # master-list result must remain effective between those probes.
            poller._poll_one(reg)

        self.assertEqual(inst.steam_status, STEAM_AVAILABLE)
        self.assertEqual(check_master.call_count, 1)


if __name__ == "__main__":
    unittest.main()
