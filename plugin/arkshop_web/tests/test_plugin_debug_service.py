"""Testes mínimos do serviço plugin_debug."""
from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from plugin_debug_service import (
    enrich_event_row,
    ingest_event,
    list_events,
)


def _make_session(tmp_path):
    db = tmp_path / "pd.sqlite"
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
    return sessionmaker(bind=engine)()


def test_plugin_debug_ingest_and_list(tmp_path):
    session = _make_session(tmp_path)
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
    assert rows[0]["fields_json"]["db_ok"] is False


def test_ingest_extracts_steam_order_from_fields(tmp_path):
    session = _make_session(tmp_path)
    eid = ingest_event(
        session,
        {
            "plugin": "CustomShop",
            "level": "WARN",
            "category": "Http",
            "message": "POST HTTP 503 /api/pending/claim",
            "fields": {
                "method": "POST",
                "path": "/api/pending/claim",
                "host": "127.0.0.1",
                "http_status": 503,
                "duration_ms": 42,
                "steam_id": "76561198171186412",
                "order_id": "ord-abc",
            },
        },
    )
    session.commit()
    assert eid is not None
    rows = list_events(session, category="Http", limit=5)
    session.close()
    assert len(rows) == 1
    assert rows[0]["steam_id"] == "76561198171186412"
    assert rows[0]["order_id"] == "ord-abc"
    assert rows[0]["fields_json"]["http_status"] == 503
    assert rows[0]["fields_json"]["path"] == "/api/pending/claim"


def test_list_min_level_and_q_search(tmp_path):
    session = _make_session(tmp_path)
    ingest_event(
        session,
        {
            "plugin": "CustomShop",
            "level": "INFO",
            "category": "TribeSync",
            "message": "presence OK",
        },
    )
    ingest_event(
        session,
        {
            "plugin": "CustomShop",
            "level": "WARN",
            "category": "Http",
            "message": "GET WinHttpSendRequest failed / timeout",
            "fields": {
                "method": "GET",
                "path": "/api/health",
                "host": "shop.local",
                "winhttp_error": 12002,
                "duration_ms": 8001,
            },
        },
    )
    ingest_event(
        session,
        {
            "plugin": "CustomDinoDeliver",
            "level": "ERROR",
            "category": "Http",
            "message": "POST HTTP 503 /api/dino/claim",
            "fields": {"http_status": 503, "path": "/api/dino/claim"},
        },
    )
    session.commit()

    warn_plus = list_events(session, min_level="WARN", limit=20)
    assert {r["level"] for r in warn_plus} == {"WARN", "ERROR"}

    by_q = list_events(session, q="12002", limit=20)
    assert len(by_q) == 1
    assert by_q[0]["fields_json"]["winhttp_error"] == 12002

    by_path = list_events(session, q="/api/dino/claim", category="Http", limit=20)
    assert len(by_path) == 1
    assert by_path[0]["plugin"] == "CustomDinoDeliver"
    session.close()


def test_enrich_event_row_fills_from_fields_json():
    row = enrich_event_row(
        {
            "steam_id": None,
            "order_id": None,
            "fields_json": '{"steam_id":"76561198000000001","order_id":"o1","path":"/x"}',
        }
    )
    assert row["steam_id"] == "76561198000000001"
    assert row["order_id"] == "o1"
    assert row["fields_json"]["path"] == "/x"
