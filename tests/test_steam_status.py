"""Testes para classificação de status Steam/LAN (paridade ASM)."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

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
    resolve_machine_public_ip,
)


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

    def test_available_public_query(self) -> None:
        mode, _ = classify_steam_status(
            process_running=True,
            lan_configured=False,
            local_query_ok=True,
            public_ip="1.2.3.4",
            public_query_ok=True,
            steam_master_ok=False,
        )
        self.assertEqual(mode, STEAM_AVAILABLE)

    def test_available_steam_master(self) -> None:
        mode, _ = classify_steam_status(
            process_running=True,
            lan_configured=False,
            local_query_ok=True,
            public_ip="1.2.3.4",
            public_query_ok=False,
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


if __name__ == "__main__":
    unittest.main()
