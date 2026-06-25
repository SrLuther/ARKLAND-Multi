"""Testes para src/obobonic_bot.py — parser .env e sync ASM."""
from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.obobonic_bot import (  # noqa: E402
    ArkMapEntry,
    asm_servers_to_ark_maps,
    parse_ark_maps_from_env,
    sync_asm_servers_to_env,
    update_env_keys,
    validate_discord_token,
    write_ark_maps_to_env,
)


class TestObobonicEnvParser(unittest.TestCase):
    def test_parse_ark_maps_from_env(self) -> None:
        text = """
DISCORD_TOKEN=abc
ARK_MAP1_NAME=Brighamia
ARK_MAP1_PORT=32400
ARK_MAP1_QUERY_PORT=27100
ARK_MAP2_NAME=Alps
ARK_MAP2_PORT=32401
"""
        maps = parse_ark_maps_from_env(text)
        self.assertEqual(len(maps), 2)
        self.assertEqual(maps[0].name, "Brighamia")
        self.assertEqual(maps[0].port, "32400")
        self.assertEqual(maps[0].query_port, "27100")
        self.assertEqual(maps[1].port, "32401")

    def test_write_ark_maps_replaces_old_block(self) -> None:
        original = "DISCORD_TOKEN=x\nARK_MAP1_NAME=Old\nARK_MAP1_PORT=1\n"
        maps = [ArkMapEntry(index=1, name="New", port="32400", query_port="27100")]
        out = write_ark_maps_to_env(original, maps)
        self.assertIn("ARK_MAP1_NAME=New", out)
        self.assertNotIn("ARK_MAP1_NAME=Old", out)
        self.assertIn("DISCORD_TOKEN=x", out)

    def test_update_env_keys(self) -> None:
        text = "ARK_HOST=1.2.3.4\nFOO=bar\n"
        out = update_env_keys(text, {"ARK_HOST": "10.0.0.1", "ARK_RCON_PASSWORD": "secret"})
        self.assertIn("ARK_HOST=10.0.0.1", out)
        self.assertIn("ARK_RCON_PASSWORD=secret", out)
        self.assertIn("FOO=bar", out)

    def test_validate_discord_token(self) -> None:
        ok, _ = validate_discord_token("DISCORD_TOKEN=MTQ0MDgxMDYxNDUwNjI2MjcxMw.GYxOaf.abc123def456\n")
        self.assertTrue(ok)
        bad, msg = validate_discord_token("DISCORD_TOKEN=token_falso_para_dev\n")
        self.assertFalse(bad)
        self.assertIn("placeholder", msg.lower())


class TestAsmSync(unittest.TestCase):
    def _srv(self, **kwargs) -> SimpleNamespace:
        defaults = dict(
            name="Brighamia",
            session_name="[ARKLAND BR] - Brighamia",
            server_port=7790,
            query_port=27100,
            rcon_port=32400,
            admin_password="pass123",
            server_ip="179.185.19.88",
            max_players=30,
        )
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_asm_servers_to_ark_maps(self) -> None:
        servers = [
            self._srv(name="Alps", session_name="[ARKLAND BR] - Alps",
                      rcon_port=32401, query_port=27101, server_port=7792),
            self._srv(),
        ]
        maps, host, pwd, logs = asm_servers_to_ark_maps(servers)
        self.assertEqual(len(maps), 2)
        self.assertEqual(maps[0].port, "32400")  # sorted by rcon_port
        self.assertEqual(maps[0].query_port, "27100")
        self.assertEqual(host, "179.185.19.88")
        self.assertEqual(pwd, "pass123")
        self.assertTrue(any("2 servidor" in l for l in logs))

    def test_sync_asm_servers_to_env(self) -> None:
        env = "DISCORD_TOKEN=abc.def.ghi\nARK_HOST=old\n"
        servers = [self._srv()]
        new_env, maps, _ = sync_asm_servers_to_env(env, servers, default_host="127.0.0.1")
        self.assertEqual(len(maps), 1)
        self.assertIn("ARK_RCON_PASSWORD=pass123", new_env)
        self.assertIn("ARK_MAP1_PORT=32400", new_env)
        self.assertIn("ARK_MAP1_QUERY_PORT=27100", new_env)
        reparsed = parse_ark_maps_from_env(new_env)
        self.assertEqual(reparsed[0].name, "[ARKLAND BR] - Brighamia")


if __name__ == "__main__":
    unittest.main()
