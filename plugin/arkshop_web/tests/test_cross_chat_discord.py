"""Testes da ponte Discord do chat cluster."""
from __future__ import annotations

from cross_chat_discord import (
    DISCORD_SOURCE,
    discord_bridge_status,
    format_discord_outbound,
    is_discord_steam_id,
    load_discord_config,
)
from cross_chat_service import publish_message, poll_messages


def test_format_discord_outbound():
    line = format_discord_outbound("Ragnarok", "Luther", "ola cluster")
    assert line == "[Ragnarok] Luther: ola cluster"


def test_is_discord_steam_id():
    assert is_discord_steam_id("discord:123456789")
    assert not is_discord_steam_id("76561198000000001")


def test_publish_discord_message(db_session):
    r = publish_message(
        db_session,
        source_server=DISCORD_SOURCE,
        steam_id="discord:998877665544",
        player_name="AdminDiscord",
        message="mensagem do discord",
        channel="discord",
    )
    assert r["ok"] is True

    msgs = poll_messages(db_session, server_id="Island", since_id=0)
    assert len(msgs) == 1
    assert msgs[0]["source_server"] == DISCORD_SOURCE
    assert msgs[0]["player_name"] == "AdminDiscord"


def test_load_discord_config_env(monkeypatch, tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text('{"cross_chat_discord_enabled": false}', encoding="utf-8")

    def _load():
        import json
        return json.loads(settings_file.read_text(encoding="utf-8"))

    monkeypatch.setenv("ARKSHOP_CROSS_CHAT_DISCORD_ENABLED", "true")
    monkeypatch.setenv("ARKSHOP_CROSS_CHAT_DISCORD_TOKEN", "tok")
    monkeypatch.setenv("ARKSHOP_CROSS_CHAT_DISCORD_CHANNEL_ID", "12345")

    cfg = load_discord_config(_load)
    assert cfg["enabled"] is True
    assert cfg["channel_id"] == 12345
    assert cfg["token_set"] is True


def test_discord_bridge_status_disabled():
    def _load():
        return {"cross_chat_discord_enabled": False}

    st = discord_bridge_status(_load, lambda: True)
    assert st["connected"] is False
    assert st["status_message"] == "Desativado"
    assert "phase" in st
    assert "discord_py_available" in st
