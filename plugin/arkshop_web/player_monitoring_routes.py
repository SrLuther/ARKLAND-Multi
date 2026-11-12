"""Read-only staff view and authenticated ingestion for ARK server player sessions."""
from __future__ import annotations

import re
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import Flask, jsonify, request
from sqlalchemy import text

_SCHEMA_LOCK = threading.Lock()
_SCHEMA_READY: set[str] = set()
_STEAM_ID_RE = re.compile(r"^\d{17}$")
_SERVER_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def _ensure_schema(engine: Any) -> None:
    identity = str(engine.url)
    if identity in _SCHEMA_READY:
        return
    with _SCHEMA_LOCK:
        if identity in _SCHEMA_READY:
            return
        mysql = "mysql" in identity.lower()
        with engine.begin() as conn:
            if mysql:
                conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS game_players ("
                    "steam_id VARCHAR(32) NOT NULL PRIMARY KEY, "
                    "player_name VARCHAR(128) NOT NULL DEFAULT '', "
                    "character_id VARCHAR(32) NOT NULL DEFAULT '', "
                    "tribe_id VARCHAR(32) NOT NULL DEFAULT '', "
                    "tribe_name VARCHAR(128) NOT NULL DEFAULT '', "
                    "server_id VARCHAR(80) NOT NULL DEFAULT '', "
                    "first_seen_at DATETIME NOT NULL, last_seen_at DATETIME NOT NULL)"
                ))
                conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS game_player_sessions ("
                    "session_id VARCHAR(64) NOT NULL PRIMARY KEY, "
                    "server_id VARCHAR(80) NOT NULL, steam_id VARCHAR(32) NOT NULL, "
                    "connected_at DATETIME NOT NULL, last_seen_at DATETIME NOT NULL, "
                    "disconnected_at DATETIME NULL, duration_seconds INT NOT NULL DEFAULT 0)"
                ))
                for name, ddl in (
                    ("ix_game_players_last_seen", "CREATE INDEX ix_game_players_last_seen ON game_players (last_seen_at)"),
                    ("ix_game_player_sessions_steam", "CREATE INDEX ix_game_player_sessions_steam ON game_player_sessions (steam_id, connected_at)"),
                    ("ix_game_player_sessions_server", "CREATE INDEX ix_game_player_sessions_server ON game_player_sessions (server_id, steam_id, disconnected_at)"),
                ):
                    try:
                        conn.execute(text(ddl))
                    except Exception:
                        # MySQL has no portable CREATE INDEX IF NOT EXISTS.
                        pass
            else:
                conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS game_players ("
                    "steam_id VARCHAR(32) PRIMARY KEY, player_name VARCHAR(128) NOT NULL DEFAULT '', "
                    "character_id VARCHAR(32) NOT NULL DEFAULT '', tribe_id VARCHAR(32) NOT NULL DEFAULT '', "
                    "tribe_name VARCHAR(128) NOT NULL DEFAULT '', server_id VARCHAR(80) NOT NULL DEFAULT '', "
                    "first_seen_at DATETIME NOT NULL, last_seen_at DATETIME NOT NULL)"
                ))
                conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS game_player_sessions ("
                    "session_id VARCHAR(64) PRIMARY KEY, server_id VARCHAR(80) NOT NULL, "
                    "steam_id VARCHAR(32) NOT NULL, connected_at DATETIME NOT NULL, "
                    "last_seen_at DATETIME NOT NULL, disconnected_at DATETIME NULL, "
                    "duration_seconds INTEGER NOT NULL DEFAULT 0)"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_game_players_last_seen ON game_players (last_seen_at)"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_game_player_sessions_steam "
                    "ON game_player_sessions (steam_id, connected_at)"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_game_player_sessions_server "
                    "ON game_player_sessions (server_id, steam_id, disconnected_at)"
                ))
        _SCHEMA_READY.add(identity)


def _clean(value: Any, limit: int) -> str:
    return str(value or "").replace("\x00", "").strip()[:limit]


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()
    return str(value) if value else None


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
        except ValueError:
            return None
    return None


def _session_duration(connected_at: Any, last_seen_at: Any, persisted_seconds: Any, now: datetime) -> int:
    persisted = max(0, int(persisted_seconds or 0))
    connected = _as_datetime(connected_at)
    last_seen = _as_datetime(last_seen_at)
    if connected is None or last_seen is None:
        return persisted
    cutoff = now - timedelta(minutes=5)
    endpoint = now if last_seen >= cutoff else last_seen
    elapsed = max(0, int((endpoint - connected).total_seconds()))
    return max(persisted, elapsed)


def _completed_session_duration(connected_at: Any, ended_at: Any, persisted_seconds: Any) -> int:
    persisted = max(0, int(persisted_seconds or 0))
    connected = _as_datetime(connected_at)
    ended = _as_datetime(ended_at)
    if connected is None or ended is None:
        return persisted
    return max(persisted, 0, int((ended - connected).total_seconds()))


def _upsert_profile(db: Any, now: datetime, payload: dict[str, Any]) -> None:
    steam_id = payload["steam_id"]
    existing = db.execute(
        text("SELECT first_seen_at FROM game_players WHERE steam_id=:steam_id"),
        {"steam_id": steam_id},
    ).first()
    values = {
        "steam_id": steam_id,
        "player_name": payload["player_name"],
        "character_id": payload["character_id"],
        "tribe_id": payload["tribe_id"],
        "tribe_name": payload["tribe_name"],
        "server_id": payload["server_id"],
        "now": now,
    }
    if existing:
        db.execute(text(
            "UPDATE game_players SET "
            "player_name=CASE WHEN :player_name<>'' THEN :player_name ELSE player_name END, "
            "character_id=CASE WHEN :character_id<>'' THEN :character_id ELSE character_id END, "
            "tribe_id=CASE WHEN :tribe_id<>'' THEN :tribe_id ELSE tribe_id END, "
            "tribe_name=CASE WHEN :tribe_name<>'' THEN :tribe_name ELSE tribe_name END, "
            "server_id=:server_id, last_seen_at=:now WHERE steam_id=:steam_id"
        ), values)
    else:
        db.execute(text(
            "INSERT INTO game_players "
            "(steam_id, player_name, character_id, tribe_id, tribe_name, server_id, first_seen_at, last_seen_at) "
            "VALUES (:steam_id, :player_name, :character_id, :tribe_id, :tribe_name, :server_id, :now, :now)"
        ), values)


def register_player_monitoring_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    api_key_required: Callable[..., Any],
    ticket_staff_required: Callable,
    limiter: Any | None = None,
) -> None:
    limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))

    @app.route("/api/moderation/player-session", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    @limit("600 per minute")
    def moderation_ingest_player_session():
        if not db_ready():
            return jsonify({"ok": False, "error": "database_unavailable"}), 503
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"ok": False, "error": "invalid_json"}), 400
        event = _clean(body.get("event"), 16).lower()
        server_id = _clean(body.get("server_id"), 80)
        steam_id = _clean(body.get("steam_id"), 32)
        session_id = _clean(body.get("session_id"), 64)
        if event not in {"connect", "heartbeat", "disconnect"}:
            return jsonify({"ok": False, "error": "invalid_event"}), 400
        if not _SERVER_ID_RE.fullmatch(server_id) or not _STEAM_ID_RE.fullmatch(steam_id) or not session_id:
            return jsonify({"ok": False, "error": "invalid_identity"}), 400

        now = datetime.now(UTC).replace(tzinfo=None)
        payload = {
            "steam_id": steam_id,
            "server_id": server_id,
            "session_id": session_id,
            "player_name": _clean(body.get("player_name"), 128),
            "character_id": _clean(body.get("character_id"), 32),
            "tribe_id": _clean(body.get("tribe_id"), 32),
            "tribe_name": _clean(body.get("tribe_name"), 128),
        }
        db = session_factory()
        try:
            _ensure_schema(db.get_bind())
            _upsert_profile(db, now, payload)
            row = db.execute(text(
                "SELECT connected_at, duration_seconds, disconnected_at FROM game_player_sessions "
                "WHERE session_id=:session_id AND steam_id=:steam_id AND server_id=:server_id"
            ), payload).first()
            if event == "connect":
                # A duplicate connection on the same server closes the old session at its last heartbeat.
                old_sessions = db.execute(text(
                    "SELECT session_id, connected_at, last_seen_at, duration_seconds "
                    "FROM game_player_sessions "
                    "WHERE server_id=:server_id AND steam_id=:steam_id "
                    "AND disconnected_at IS NULL AND session_id<>:session_id"
                ), payload).mappings().all()
                for old in old_sessions:
                    db.execute(text(
                        "UPDATE game_player_sessions SET disconnected_at=:ended, duration_seconds=:duration "
                        "WHERE session_id=:session_id AND disconnected_at IS NULL"
                    ), {
                        "ended": old["last_seen_at"],
                        "duration": _completed_session_duration(old["connected_at"], old["last_seen_at"], old["duration_seconds"]),
                        "session_id": old["session_id"],
                    })
                if row is None:
                    db.execute(text(
                        "INSERT INTO game_player_sessions "
                        "(session_id, server_id, steam_id, connected_at, last_seen_at, duration_seconds) "
                        "VALUES (:session_id, :server_id, :steam_id, :now, :now, 0)"
                    ), {**payload, "now": now})
                elif row[2] is not None:
                    # Replays are expected when the plugin retries after a lost response.
                    db.commit()
                    return jsonify({"ok": True, "duplicate": True})
                else:
                    db.execute(text(
                        "UPDATE game_player_sessions SET last_seen_at=:now "
                        "WHERE session_id=:session_id"
                    ), {"now": now, "session_id": session_id})
            elif row is not None and row[2] is None:
                connected = row[0]
                if isinstance(connected, str):
                    connected = datetime.fromisoformat(connected)
                elapsed = max(0, int((now - connected).total_seconds()))
                duration = max(int(row[1] or 0), elapsed)
                ended = now if event == "disconnect" else None
                db.execute(text(
                    "UPDATE game_player_sessions SET last_seen_at=:now, duration_seconds=:duration, "
                    "disconnected_at=:ended WHERE session_id=:session_id"
                ), {"now": now, "duration": duration, "ended": ended, "session_id": session_id})
            elif row is None and event == "heartbeat":
                # A heartbeat after a plugin/server restart recovers a missed connect event.
                db.execute(text(
                    "INSERT INTO game_player_sessions "
                    "(session_id, server_id, steam_id, connected_at, last_seen_at, duration_seconds) "
                    "VALUES (:session_id, :server_id, :steam_id, :now, :now, 0)"
                ), {**payload, "now": now})
            elif row is None:
                db.rollback()
                return jsonify({"ok": False, "error": "session_not_found"}), 404
            db.commit()
            return jsonify({"ok": True})
        except Exception:
            db.rollback()
            app.logger.exception("player_monitoring_ingest_failed")
            return jsonify({"ok": False, "error": "storage_error"}), 503
        finally:
            db.close()

    @app.route("/api/staff/moderation/players", methods=["GET"])
    @ticket_staff_required
    @limit("60 per minute")
    def moderation_list_players():
        if not db_ready():
            return jsonify({"ok": False, "error": "database_unavailable"}), 503
        query = _clean(request.args.get("q"), 128)
        linked_filter = _clean(request.args.get("linked"), 12).lower()
        server_id = _clean(request.args.get("server_id"), 80)
        try:
            limit_n = min(100, max(1, int(request.args.get("limit", "50"))))
            offset = max(0, int(request.args.get("offset", "0")))
        except ValueError:
            return jsonify({"ok": False, "error": "invalid_pagination"}), 400
        where = ["1=1"]
        params: dict[str, Any] = {"limit": limit_n, "offset": offset}
        if query:
            where.append("(gp.steam_id LIKE :q OR gp.player_name LIKE :q OR gp.tribe_name LIKE :q)")
            params["q"] = f"%{query}%"
        if server_id:
            where.append("gp.server_id=:server_id")
            params["server_id"] = server_id
        if linked_filter == "linked":
            where.append("su.steam_id IS NOT NULL")
        elif linked_filter == "unlinked":
            where.append("su.steam_id IS NULL")
        clause = " AND ".join(where)
        db = session_factory()
        try:
            _ensure_schema(db.get_bind())
            total = int(db.execute(text(
                f"SELECT COUNT(*) FROM game_players gp LEFT JOIN store_users su ON su.steam_id=gp.steam_id WHERE {clause}"
            ), params).scalar() or 0)
            rows = db.execute(text(
                "SELECT gp.steam_id, gp.player_name, gp.character_id, gp.tribe_id, gp.tribe_name, "
                "gp.server_id, gp.first_seen_at, gp.last_seen_at, su.steam_id IS NOT NULL AS site_linked, "
                "(SELECT COUNT(*) FROM game_player_sessions s WHERE s.steam_id=gp.steam_id) AS session_count, "
                "(SELECT COALESCE(SUM(s.duration_seconds),0) FROM game_player_sessions s WHERE s.steam_id=gp.steam_id) AS total_play_seconds, "
                "(SELECT MAX(s.connected_at) FROM game_player_sessions s WHERE s.steam_id=gp.steam_id) AS last_game_login, "
                "(SELECT COUNT(*) FROM game_player_sessions s WHERE s.steam_id=gp.steam_id AND s.disconnected_at IS NULL "
                "AND s.last_seen_at>=:online_since) AS active_sessions "
                "FROM game_players gp LEFT JOIN store_users su ON su.steam_id=gp.steam_id "
                f"WHERE {clause} ORDER BY gp.last_seen_at DESC, gp.steam_id LIMIT :limit OFFSET :offset"
            ), {**params, "online_since": datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)}).mappings().all()
            # Older sessions may have timestamps but a zero duration due to the previous
            # tracking behavior. Also include the elapsed portion of open sessions between
            # heartbeats. Both are read-only calculations; existing rows are not rewritten.
            player_ids = [str(row["steam_id"]) for row in rows]
            recovered_seconds: dict[str, int] = {}
            if player_ids:
                placeholders = ", ".join(f":sid_{index}" for index in range(len(player_ids)))
                open_sessions = db.execute(text(
                    "SELECT steam_id, connected_at, last_seen_at, disconnected_at, duration_seconds "
                    "FROM game_player_sessions "
                    f"WHERE steam_id IN ({placeholders}) "
                    "AND (duration_seconds=0 OR disconnected_at IS NULL)"
                ), {f"sid_{index}": steam_id for index, steam_id in enumerate(player_ids)}).mappings().all()
                now = datetime.now(UTC).replace(tzinfo=None)
                online_since = now - timedelta(minutes=5)
                for session_row in open_sessions:
                    steam_id = str(session_row["steam_id"])
                    connected_at = _as_datetime(session_row["connected_at"])
                    last_seen_at = _as_datetime(session_row["last_seen_at"])
                    disconnected_at = _as_datetime(session_row["disconnected_at"])
                    if connected_at is None:
                        continue
                    if disconnected_at is not None:
                        endpoint = disconnected_at
                    elif last_seen_at is not None and last_seen_at >= online_since:
                        # A fresh heartbeat means the player is still online, so count to now.
                        endpoint = now
                    else:
                        # Stop stale sessions at their last confirmed heartbeat.
                        endpoint = last_seen_at
                    if endpoint is None:
                        continue
                    effective = max(0, int((endpoint - connected_at).total_seconds()))
                    persisted = max(0, int(session_row["duration_seconds"] or 0))
                    recovered_seconds[steam_id] = recovered_seconds.get(steam_id, 0) + max(effective, persisted) - persisted
            return jsonify({"ok": True, "total": total, "limit": limit_n, "offset": offset, "players": [
                {**dict(row), "first_seen_at": _iso(row["first_seen_at"]),
                 "last_seen_at": _iso(row["last_seen_at"]), "last_game_login": _iso(row["last_game_login"]),
                 "site_linked": bool(row["site_linked"]), "active_sessions": int(row["active_sessions"] or 0) > 0,
                 "total_play_seconds": int(row["total_play_seconds"] or 0) + recovered_seconds.get(str(row["steam_id"]), 0)}
                for row in rows
            ]})
        except Exception:
            app.logger.exception("player_monitoring_list_failed")
            return jsonify({"ok": False, "error": "storage_error"}), 503
        finally:
            db.close()

    @app.route("/api/staff/moderation/players/<steam_id>/sessions", methods=["GET"])
    @ticket_staff_required
    @limit("60 per minute")
    def moderation_player_sessions(steam_id: str):
        if not _STEAM_ID_RE.fullmatch(steam_id or ""):
            return jsonify({"ok": False, "error": "invalid_steam_id"}), 400
        if not db_ready():
            return jsonify({"ok": False, "error": "database_unavailable"}), 503
        db = session_factory()
        try:
            _ensure_schema(db.get_bind())
            cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)
            stale_sessions = db.execute(text(
                "SELECT session_id, connected_at, last_seen_at, duration_seconds "
                "FROM game_player_sessions "
                "WHERE steam_id=:steam_id AND disconnected_at IS NULL AND last_seen_at<:cutoff"
            ), {"steam_id": steam_id, "cutoff": cutoff}).mappings().all()
            now = datetime.now(UTC).replace(tzinfo=None)
            for stale in stale_sessions:
                db.execute(text(
                    "UPDATE game_player_sessions SET disconnected_at=:ended, duration_seconds=:duration "
                    "WHERE session_id=:session_id AND disconnected_at IS NULL"
                ), {
                    "ended": stale["last_seen_at"],
                    "duration": _completed_session_duration(stale["connected_at"], stale["last_seen_at"], stale["duration_seconds"]),
                    "session_id": stale["session_id"],
                })
            db.commit()
            rows = db.execute(text(
                "SELECT session_id, server_id, connected_at, last_seen_at, disconnected_at, duration_seconds "
                "FROM game_player_sessions WHERE steam_id=:steam_id ORDER BY connected_at DESC LIMIT 100"
            ), {"steam_id": steam_id}).mappings().all()
            return jsonify({"ok": True, "sessions": [
                {**dict(row), "connected_at": _iso(row["connected_at"]), "last_seen_at": _iso(row["last_seen_at"]),
                 "disconnected_at": _iso(row["disconnected_at"]), "duration_seconds": (
                     _completed_session_duration(
                         row["connected_at"], row["disconnected_at"], row["duration_seconds"]
                     ) if row["disconnected_at"] is not None else
                     _session_duration(row["connected_at"], row["last_seen_at"], row["duration_seconds"], now)
                 )}
                for row in rows
            ]})
        except Exception:
            app.logger.exception("player_monitoring_sessions_failed")
            return jsonify({"ok": False, "error": "storage_error"}), 503
        finally:
            db.close()
