"""Testes do chat cluster."""
from __future__ import annotations

from cross_chat_service import (
    chat_stats,
    list_messages,
    list_mutes,
    mute_player,
    poll_messages,
    publish_message,
    unmute_player,
)


def test_publish_and_poll(db_session):
    r1 = publish_message(
        db_session,
        source_server="Brighamia",
        steam_id="76561198000000001",
        player_name="Luther",
        message="ola cluster",
    )
    assert r1["ok"] is True

    msgs = poll_messages(db_session, server_id="Ragnarok", since_id=0)
    assert len(msgs) == 1
    assert msgs[0]["source_server"] == "Brighamia"
    assert msgs[0]["message"] == "ola cluster"

    own = poll_messages(db_session, server_id="Brighamia", since_id=0)
    assert len(own) == 0


def test_list_messages_and_mute(db_session):
    publish_message(
        db_session,
        source_server="Island",
        steam_id="76561198000000002",
        player_name="PlayerA",
        message="help",
    )
    items, total = list_messages(db_session, limit=10, offset=0)
    assert total == 1
    assert items[0]["steam_id"] == "76561198000000002"

    muted = mute_player(db_session, steam_id="76561198000000002", hours=1, reason="spam")
    assert muted["ok"] is True
    assert len(list_mutes(db_session)) == 1

    blocked = publish_message(
        db_session,
        source_server="Island",
        steam_id="76561198000000002",
        player_name="PlayerA",
        message="again",
    )
    assert blocked["ok"] is False

    unmute_player(db_session, steam_id="76561198000000002")
    assert len(list_mutes(db_session)) == 0


def test_chat_stats(db_session):
    publish_message(
        db_session,
        source_server="Fjordur",
        steam_id="76561198000000003",
        player_name="Viking",
        message="hej",
    )
    stats = chat_stats(db_session)
    assert stats["messages_24h"] >= 1
    assert "Fjordur" in stats["servers"]


def test_publish_and_poll_with_tribe(db_session):
    r1 = publish_message(
        db_session,
        source_server="Brighamia",
        steam_id="76561198000000010",
        player_name="Luther",
        tribe_name="ARKLAND",
        message="ola tribo",
    )
    assert r1["ok"] is True

    msgs = poll_messages(db_session, server_id="Ragnarok", since_id=0)
    assert len(msgs) == 1
    assert msgs[0]["tribe_name"] == "ARKLAND"
    assert msgs[0]["message"] == "ola tribo"


def test_publish_discord_channel(db_session):
    from cross_chat_service import publish_message as pub

    r = pub(
        db_session,
        source_server="Discord",
        steam_id="discord:112233445566",
        player_name="Bob",
        message="oi do discord",
        channel="discord",
    )
    assert r["ok"] is True

    msgs = poll_messages(db_session, server_id="Island", since_id=0)
    assert len(msgs) == 1
    assert msgs[0]["message"] == "oi do discord"
