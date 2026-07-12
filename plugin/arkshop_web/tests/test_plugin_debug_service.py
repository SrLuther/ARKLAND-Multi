"""Testes mínimos do serviço plugin_debug."""
from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from plugin_debug_service import ensure_plugin_debug_schema, ingest_event, list_events


def test_plugin_debug_ingest_and_list(tmp_path):
    db = tmp_path / "pd.sqlite"
    # MySQL DDL usa DATETIME/JSON — usar MySQL se disponível; senão skip-style com sqlite adaptado
    # Aqui usamos SQLite com DDL simplificado embutido no teste.
    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE arkland_plugin_debug (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  created_at TEXT,
                  plugin TEXT NOT NULL,
                  plugin_version TEXT DEFAULT '',
                  level TEXT NOT NULL,
                  category TEXT NOT NULL,
                  server_id TEXT,
                  steam_id TEXT,
                  order_id TEXT,
                  correlation_id TEXT,
                  message TEXT NOT NULL,
                  fields_json TEXT
                )
                """
            )
        )
    Session = sessionmaker(bind=engine)
    session = Session()
    eid = ingest_event(
        session,
        {
            "plugin": "CustomShop",
            "version": "1.10.14",
            "level": "WARN",
            "category": "TribeSync",
            "steam_id": "76561198000000000",
            "message": "presence fail",
            "fields": {"db_ok": False},
        },
    )
    session.commit()
    assert eid is not None
    rows = list_events(session, plugin="CustomShop", category="TribeSync", limit=10)
    session.close()
    assert len(rows) == 1
    assert rows[0]["message"] == "presence fail"
    assert rows[0]["level"] == "WARN"
