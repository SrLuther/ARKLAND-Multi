"""Fixtures compartilhadas dos testes arkshop_web."""
from __future__ import annotations

import os

# Migração síncrona em testes — evita race com threads de boot do app.
os.environ.setdefault("ARKSHOP_SYNC_DB_MIGRATE", "1")
os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from db_diagnostics import record_circuit_success


@pytest.fixture(autouse=True)
def _isolate_steam_api_from_env(monkeypatch):
    """Evita chamadas reais à Steam Web API quando STEAM_API_KEY vem do .env local."""
    monkeypatch.delenv("STEAM_API_KEY", raising=False)
    record_circuit_success()


@pytest.fixture()
def db_session(tmp_path):
    path = tmp_path / "chat.db"
    engine = create_engine(f"sqlite:///{path}", future=True)
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE TABLE cross_server_chat ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "channel TEXT, source_server TEXT, steam_id TEXT,"
            "player_name TEXT, tribe_name TEXT DEFAULT '', message TEXT, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
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
