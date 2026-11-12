from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flask import Flask
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from player_monitoring_routes import register_player_monitoring_routes


STEAM_ID = "76561198000000001"


def _client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'players.db'}", future=True)
    Session = sessionmaker(bind=engine)
    app = Flask("player-monitoring-test")
    app.secret_key = "test-secret"
    register_player_monitoring_routes(
        app,
        db_ready=lambda: True,
        session_factory=Session,
        api_key_required=lambda **_kwargs: (lambda fn: fn),
        ticket_staff_required=lambda fn: fn,
    )
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE store_users (steam_id TEXT PRIMARY KEY)"))
    return app.test_client(), Session


def _start_session(client):
    response = client.post("/api/moderation/player-session", json={
        "event": "connect",
        "server_id": "map_a",
        "steam_id": STEAM_ID,
        "session_id": "session-a",
        "player_name": "Ciano",
    })
    assert response.status_code == 200
    assert response.get_json()["ok"] is True


def test_player_list_includes_live_elapsed_time_before_next_heartbeat(tmp_path):
    client, Session = _client(tmp_path)
    _start_session(client)
    now = datetime.now(UTC).replace(tzinfo=None)
    db = Session()
    try:
        db.execute(text(
            "UPDATE game_player_sessions SET connected_at=:connected, last_seen_at=:seen, duration_seconds=0 "
            "WHERE session_id='session-a'"
        ), {"connected": now - timedelta(hours=2), "seen": now})
        db.commit()
    finally:
        db.close()

    response = client.get("/api/staff/moderation/players?linked=unlinked")
    assert response.status_code == 200
    player = response.get_json()["players"][0]
    assert player["active_sessions"] is True
    assert player["total_play_seconds"] >= 2 * 60 * 60 - 2


def test_stale_open_session_counts_only_until_last_confirmed_heartbeat(tmp_path):
    client, Session = _client(tmp_path)
    _start_session(client)
    now = datetime.now(UTC).replace(tzinfo=None)
    connected = now - timedelta(hours=3)
    last_seen = now - timedelta(hours=2)
    db = Session()
    try:
        db.execute(text(
            "UPDATE game_player_sessions SET connected_at=:connected, last_seen_at=:seen, duration_seconds=0 "
            "WHERE session_id='session-a'"
        ), {"connected": connected, "seen": last_seen})
        db.commit()
    finally:
        db.close()

    response = client.get("/api/staff/moderation/players?linked=unlinked")
    assert response.status_code == 200
    player = response.get_json()["players"][0]
    assert player["active_sessions"] is False
    assert 60 * 60 - 2 <= player["total_play_seconds"] <= 60 * 60 + 2


def test_session_details_freeze_elapsed_time_when_stale_session_is_closed(tmp_path):
    client, Session = _client(tmp_path)
    _start_session(client)
    now = datetime.now(UTC).replace(tzinfo=None)
    db = Session()
    try:
        db.execute(text(
            "UPDATE game_player_sessions SET connected_at=:connected, last_seen_at=:seen, duration_seconds=0 "
            "WHERE session_id='session-a'"
        ), {"connected": now - timedelta(hours=2), "seen": now - timedelta(hours=1)})
        db.commit()
    finally:
        db.close()

    response = client.get(f"/api/staff/moderation/players/{STEAM_ID}/sessions")
    assert response.status_code == 200
    session = response.get_json()["sessions"][0]
    assert session["disconnected_at"] is not None
    assert 60 * 60 - 2 <= session["duration_seconds"] <= 60 * 60 + 2


def test_duplicate_connect_closes_previous_session_with_elapsed_duration(tmp_path):
    client, Session = _client(tmp_path)
    _start_session(client)
    now = datetime.now(UTC).replace(tzinfo=None)
    db = Session()
    try:
        db.execute(text(
            "UPDATE game_player_sessions SET connected_at=:connected, last_seen_at=:seen, duration_seconds=0 "
            "WHERE session_id='session-a'"
        ), {"connected": now - timedelta(hours=2), "seen": now - timedelta(hours=1)})
        db.commit()
    finally:
        db.close()
    response = client.post("/api/moderation/player-session", json={
        "event": "connect", "server_id": "map_a", "steam_id": STEAM_ID,
        "session_id": "session-b", "player_name": "Ciano",
    })
    assert response.status_code == 200

    sessions = client.get(f"/api/staff/moderation/players/{STEAM_ID}/sessions").get_json()["sessions"]
    previous = next(item for item in sessions if item["session_id"] == "session-a")
    assert previous["disconnected_at"] is not None
    assert 60 * 60 - 2 <= previous["duration_seconds"] <= 60 * 60 + 2


def test_player_list_recovers_legacy_zero_duration_from_session_timestamps(tmp_path):
    client, Session = _client(tmp_path)
    _start_session(client)
    now = datetime.now(UTC).replace(tzinfo=None)
    db = Session()
    try:
        db.execute(text(
            "UPDATE game_player_sessions SET connected_at=:connected, last_seen_at=:disconnected, "
            "disconnected_at=:disconnected, duration_seconds=0 WHERE session_id='session-a'"
        ), {
            "connected": now - timedelta(hours=3),
            "disconnected": now - timedelta(hours=1),
        })
        db.commit()
    finally:
        db.close()

    response = client.get("/api/staff/moderation/players?linked=unlinked")
    assert response.status_code == 200
    player = response.get_json()["players"][0]
    assert player["total_play_seconds"] >= 2 * 60 * 60 - 2


def test_session_details_recover_legacy_zero_duration_without_rewriting_it(tmp_path):
    client, Session = _client(tmp_path)
    _start_session(client)
    now = datetime.now(UTC).replace(tzinfo=None)
    db = Session()
    try:
        db.execute(text(
            "UPDATE game_player_sessions SET connected_at=:connected, last_seen_at=:disconnected, "
            "disconnected_at=:disconnected, duration_seconds=0 WHERE session_id='session-a'"
        ), {
            "connected": now - timedelta(hours=3),
            "disconnected": now - timedelta(hours=1),
        })
        db.commit()
    finally:
        db.close()
    response = client.get(f"/api/staff/moderation/players/{STEAM_ID}/sessions")
    assert response.status_code == 200
    session = response.get_json()["sessions"][0]
    assert session["duration_seconds"] >= 2 * 60 * 60 - 2
    db = Session()
    try:
        stored = db.execute(text(
            "SELECT duration_seconds FROM game_player_sessions WHERE session_id='session-a'"
        )).scalar_one()
        assert stored == 0
    finally:
        db.close()


def test_completed_recent_session_does_not_gain_time_after_disconnect(tmp_path):
    client, Session = _client(tmp_path)
    _start_session(client)
    now = datetime.now(UTC).replace(tzinfo=None)
    connected = now - timedelta(seconds=70)
    disconnected = now - timedelta(seconds=20)
    db = Session()
    try:
        db.execute(text(
            "UPDATE game_player_sessions SET connected_at=:connected, last_seen_at=:disconnected, "
            "disconnected_at=:disconnected, duration_seconds=0 WHERE session_id='session-a'"
        ), {"connected": connected, "disconnected": disconnected})
        db.commit()
    finally:
        db.close()

    session = client.get(f"/api/staff/moderation/players/{STEAM_ID}/sessions").get_json()["sessions"][0]
    assert 49 <= session["duration_seconds"] <= 51
