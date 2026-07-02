"""Testes do sistema de votações da comunidade."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app as _app_module
from app import app
from poll_service import (
    cast_vote,
    close_poll,
    create_poll,
    ensure_poll_schema,
    get_poll_detail,
    poll_meta,
    process_expired_polls,
)

ADMIN_STEAM = "76561198000000001"
USER_STEAM = "76561198000000002"
USER2_STEAM = "76561198000000003"


@pytest.fixture()
def poll_db(tmp_path):
    path = tmp_path / "polls.db"
    engine = create_engine(f"sqlite:///{path}", future=True)
    ensure_poll_schema(engine)
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS players ("
                "steam_id TEXT PRIMARY KEY, points INTEGER DEFAULT 0)"
            )
        )
        conn.commit()
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _admin_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_WEB_SECRET", "test-secret")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN_STEAM]), encoding="utf-8")
    yield


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _future_iso(hours: int = 24) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def test_poll_meta():
    meta = poll_meta()
    assert "statuses" in meta
    assert meta["min_options"] == 2


def test_create_vote_and_close(poll_db):
    poll = create_poll(
        poll_db,
        title="Mapa do mês",
        description="Escolha o próximo mapa",
        options=[{"label": "Alps"}, {"label": "Fjordur"}],
        ends_at=_future_iso(),
        reward_amber=50,
        min_votes_valid=2,
        allow_multiple=False,
        publish=True,
        created_by_steam_id=ADMIN_STEAM,
    )
    assert poll["status"] == "ACTIVE"
    assert len(poll["options"]) == 2

    voted = cast_vote(poll_db, poll["id"], USER_STEAM, [poll["options"][0]["id"]])
    assert voted["viewer_has_voted"] is True
    assert voted["options"][0]["votes"] == 1

    with pytest.raises(ValueError, match="já votou"):
        cast_vote(poll_db, poll["id"], USER_STEAM, [poll["options"][1]["id"]])

    pts = poll_db.execute(
        text("SELECT points FROM players WHERE steam_id = :sid"),
        {"sid": USER_STEAM},
    ).fetchone()
    assert int(pts[0]) == 50

    closed = close_poll(poll_db, poll["id"], auto=False)
    assert closed["status"] == "CLOSED"
    assert closed["result_valid"] is False
    assert closed["total_voters"] == 1


def test_close_with_quorum_and_winner(poll_db):
    poll = create_poll(
        poll_db,
        title="Evento",
        description="",
        options=[{"label": "A"}, {"label": "B"}],
        ends_at=_future_iso(),
        reward_amber=0,
        min_votes_valid=2,
        publish=True,
    )
    oid_a = poll["options"][0]["id"]
    oid_b = poll["options"][1]["id"]
    cast_vote(poll_db, poll["id"], USER_STEAM, [oid_a])
    cast_vote(poll_db, poll["id"], USER2_STEAM, [oid_a])
    closed = close_poll(poll_db, poll["id"])
    assert closed["result_valid"] is True
    assert closed["winner_option_id"] == oid_a


def test_process_expired_polls(poll_db):
    poll = create_poll(
        poll_db,
        title="Expirada",
        description="",
        options=[{"label": "X"}, {"label": "Y"}],
        ends_at=_future_iso(),
        publish=True,
    )
    poll_db.execute(
        text("UPDATE community_polls SET ends_at = :p WHERE id = :id"),
        {
            "p": (datetime.now(timezone.utc) - timedelta(hours=2)).replace(tzinfo=None),
            "id": poll["id"],
        },
    )
    poll_db.commit()
    n = process_expired_polls(poll_db)
    assert n == 1
    detail = get_poll_detail(poll_db, poll["id"])
    assert detail["status"] == "CLOSED"


def test_polls_meta_endpoint(client):
    r = client.get("/api/polls/meta")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_allow_multiple_options(poll_db):
    poll = create_poll(
        poll_db,
        title="Multi",
        description="",
        options=[{"label": "A"}, {"label": "B"}, {"label": "C"}],
        ends_at=_future_iso(),
        allow_multiple=True,
        publish=True,
    )
    ids = [o["id"] for o in poll["options"][:2]]
    voted = cast_vote(poll_db, poll["id"], USER_STEAM, ids)
    assert voted["viewer_has_voted"] is True
    assert sum(o["votes"] for o in voted["options"]) == 2
