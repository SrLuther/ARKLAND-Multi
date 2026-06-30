"""Testes de notificações Discord para tickets."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from ticket_discord import (
    format_ticket_discord_message,
    load_ticket_discord_config,
    notify_ticket_discord,
    send_discord_channel_message,
    ticket_discord_status,
)


def test_load_ticket_discord_config_from_settings(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps({
            "ticket_discord_enabled": True,
            "ticket_discord_channel_id": "999888777",
            "cross_chat_discord_token": "shared-token",
        }),
        encoding="utf-8",
    )

    def load():
        return json.loads(settings_file.read_text(encoding="utf-8"))

    cfg = load_ticket_discord_config(load)
    assert cfg["enabled"] is True
    assert cfg["channel_id"] == 999888777
    assert cfg["token_set"] is True
    assert cfg["token_source"] == "cross_chat"


def test_format_ticket_discord_message():
    ticket = {
        "id": 7,
        "subject": "Problema no resgate",
        "player_name": "Nick",
        "steam_id": "76561198000000002",
        "category_label": "Resgate / entrega",
        "priority_label": "Urgente",
        "status_label": "Em análise",
    }
    msg = format_ticket_discord_message(
        ticket,
        "reply_admin",
        actor_name="Suporte",
        note="Verificando seu pedido.",
    )
    assert "Ticket **#7**" in msg
    assert "Nick" in msg
    assert "Suporte" in msg
    assert "Verificando" in msg


@patch("ticket_discord.send_discord_channel_message", return_value=True)
def test_notify_ticket_discord_when_enabled(mock_send, tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps({
            "ticket_discord_enabled": True,
            "ticket_discord_channel_id": "12345",
            "ticket_discord_token": "bot-token",
        }),
        encoding="utf-8",
    )

    def load():
        return json.loads(settings_file.read_text(encoding="utf-8"))

    ticket = {"id": 1, "subject": "Teste", "player_name": "A", "status": "ABERTO", "status_label": "Aberto"}
    ok = notify_ticket_discord(load, ticket, "created", actor_name="Nick")
    assert ok is True
    mock_send.assert_called_once()
    args = mock_send.call_args[0]
    assert args[0] == "bot-token"
    assert args[1] == 12345


def test_ticket_discord_status_message(tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps({"ticket_discord_enabled": False}),
        encoding="utf-8",
    )

    def load():
        return json.loads(settings_file.read_text(encoding="utf-8"))

    st = ticket_discord_status(load)
    assert st["requested_enabled"] is False
    assert st["status_message"] == "Desativado"


@patch("ticket_discord.urllib.request.urlopen")
def test_send_discord_channel_message_http(mock_urlopen):
    mock_urlopen.return_value.__enter__.return_value.status = 200
    ok = send_discord_channel_message("tok", 123, "Olá Discord")
    assert ok is True
