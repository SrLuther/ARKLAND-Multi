"""Testes do chat cluster."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from cross_chat_service import poll_messages, publish_message


@pytest.fixture()
def db_session(tmp_path):
    path = tmp_path / "chat.db"
    engine = create_engine(f"sqlite:///{path}", future=True)
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE TABLE cross_server_chat ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "channel TEXT, source_server TEXT, steam_id TEXT,"
            "player_name TEXT, message TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        ))
        conn.execute(text(
            "CREATE TABLE cross_server_chat_mutes ("
            "steam_id TEXT PRIMARY KEY, muted_until TEXT, reason TEXT)"
        ))
        conn.commit()
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


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
