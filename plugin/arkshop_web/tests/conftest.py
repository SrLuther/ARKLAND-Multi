"""Fixtures compartilhadas dos testes arkshop_web."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


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
