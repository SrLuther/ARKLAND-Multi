"""Presence and activity rewards from the embedded Discord bot.

The bot sends identifiers and counters only; message bodies are never accepted
or persisted. Rewarding defaults to disabled until an administrator configures
positive amounts and daily caps in the Discord-link admin page.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from flask import Flask, jsonify, request
from sqlalchemy import text

SCAN_SECONDS = 60
_SCHEMA_ENGINES: set[int] = set()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _int_setting(settings: dict[str, Any], key: str, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(settings.get(key, default))))
    except (TypeError, ValueError):
        return default


def _schema(db: Any) -> None:
    bind = db.get_bind()
    eid = id(bind)
    if eid in _SCHEMA_ENGINES:
        return
    mysql = "mysql" in str(bind.url).lower()
    if mysql:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS discord_engagement_presence (
              guild_id VARCHAR(32) NOT NULL, discord_user_id VARCHAR(32) NOT NULL,
              username VARCHAR(128) NOT NULL DEFAULT '', steam_id VARCHAR(32) NULL,
              channel_id VARCHAR(32) NOT NULL, channel_name VARCHAR(128) NOT NULL DEFAULT '',
              eligible TINYINT NOT NULL DEFAULT 0,
              connected_since DATETIME(3) NOT NULL, last_seen_at DATETIME(3) NOT NULL,
              PRIMARY KEY (guild_id, discord_user_id), KEY idx_discord_presence_seen (last_seen_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS discord_engagement_daily (
              discord_user_id VARCHAR(32) NOT NULL, activity_date CHAR(10) NOT NULL,
              kind VARCHAR(16) NOT NULL, steam_id VARCHAR(32) NOT NULL,
              seconds BIGINT NOT NULL DEFAULT 0, amount BIGINT NOT NULL DEFAULT 0,
              events INT NOT NULL DEFAULT 0, last_seen_at DATETIME(3) NULL,
              eligible_last TINYINT NOT NULL DEFAULT 0,
              connected_since DATETIME(3) NULL,
              PRIMARY KEY (discord_user_id, activity_date, kind),
              KEY idx_discord_engagement_steam (steam_id, activity_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS discord_engagement_status (
              guild_id VARCHAR(32) NOT NULL PRIMARY KEY, last_scan_at DATETIME(3) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))
    else:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS discord_engagement_presence (
              guild_id VARCHAR(32) NOT NULL, discord_user_id VARCHAR(32) NOT NULL,
              username VARCHAR(128) NOT NULL DEFAULT '', steam_id VARCHAR(32) NULL,
              channel_id VARCHAR(32) NOT NULL, channel_name VARCHAR(128) NOT NULL DEFAULT '',
              eligible INTEGER NOT NULL DEFAULT 0,
              connected_since DATETIME NOT NULL, last_seen_at DATETIME NOT NULL,
              PRIMARY KEY (guild_id, discord_user_id)
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS discord_engagement_daily (
              discord_user_id VARCHAR(32) NOT NULL, activity_date CHAR(10) NOT NULL,
              kind VARCHAR(16) NOT NULL, steam_id VARCHAR(32) NOT NULL,
              seconds BIGINT NOT NULL DEFAULT 0, amount BIGINT NOT NULL DEFAULT 0,
              events INT NOT NULL DEFAULT 0, last_seen_at DATETIME NULL,
              eligible_last INTEGER NOT NULL DEFAULT 0,
              connected_since DATETIME NULL,
              PRIMARY KEY (discord_user_id, activity_date, kind)
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS discord_engagement_status (
              guild_id VARCHAR(32) NOT NULL PRIMARY KEY, last_scan_at DATETIME NOT NULL
            )
        """))
    db.commit()
    _SCHEMA_ENGINES.add(eid)


def _linked_steam(db: Any, discord_id: str) -> str | None:
    row = db.execute(text(
        "SELECT steam_id FROM support_ticket_discord_links "
        "WHERE discord_user_id = :did LIMIT 1"
    ), {"did": discord_id}).fetchone()
    return str(row[0]) if row and row[0] else None


def _ensure_daily(db: Any, discord_id: str, day: str, kind: str, steam_id: str) -> Any:
    mysql = "mysql" in str(db.get_bind().url).lower()
    if mysql:
        db.execute(text("""
            INSERT IGNORE INTO discord_engagement_daily
              (discord_user_id, activity_date, kind, steam_id)
            VALUES (:did, :day, :kind, :sid)
        """), {"did": discord_id, "day": day, "kind": kind, "sid": steam_id})
    else:
        db.execute(text("""
            INSERT OR IGNORE INTO discord_engagement_daily
              (discord_user_id, activity_date, kind, steam_id)
            VALUES (:did, :day, :kind, :sid)
        """), {"did": discord_id, "day": day, "kind": kind, "sid": steam_id})
    lock = " FOR UPDATE" if mysql else ""
    return db.execute(text("""
        SELECT seconds, amount, events, last_seen_at, connected_since, eligible_last
        FROM discord_engagement_daily
        WHERE discord_user_id=:did AND activity_date=:day AND kind=:kind
    """ + lock), {"did": discord_id, "day": day, "kind": kind}).fetchone()


def register_discord_engagement_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    api_key_required: Callable[..., Any],
    admin_required: Callable,
    load_settings: Callable[[], dict[str, Any]],
    add_points_tx: Callable[[Any, str, int], int],
    limiter: Any | None = None,
) -> None:
    limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))

    @app.route("/api/internal/discord-engagement/voice-snapshot", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    @limit("120 per minute")
    def discord_engagement_voice_snapshot():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco indisponível"}), 503
        body = request.get_json(silent=True) or {}
        guild_id = str(body.get("guild_id") or "").strip()
        members = body.get("members") if isinstance(body.get("members"), list) else []
        cfg = load_settings()
        expected_guild = str(cfg.get("discord_engagement_guild_id") or "").strip()
        if not guild_id or (expected_guild and guild_id != expected_guild):
            return jsonify({"ok": False, "error": "Servidor Discord não autorizado"}), 403
        now = _now()
        day = now.date().isoformat()
        interval_minutes = _int_setting(cfg, "discord_engagement_voice_interval_minutes", 30, 5, 1440)
        reward = _int_setting(cfg, "discord_engagement_voice_reward", 0, 0, 1000000)
        daily_cap = _int_setting(cfg, "discord_engagement_voice_daily_cap", 0, 0, 100000000)
        db = session_factory()
        credits = 0
        try:
            _schema(db)
            previous_presence = {
                str(r[0]): r[1]
                for r in db.execute(text("""
                    SELECT discord_user_id, connected_since FROM discord_engagement_presence
                    WHERE guild_id=:gid
                """), {"gid": guild_id}).fetchall()
            }
            db.execute(text("DELETE FROM discord_engagement_presence WHERE guild_id=:gid"), {"gid": guild_id})
            for member in members[:1000]:
                if not isinstance(member, dict):
                    continue
                did = str(member.get("discord_user_id") or "").strip()
                channel_id = str(member.get("channel_id") or "").strip()
                if not did or not channel_id:
                    continue
                username = str(member.get("username") or "")[:128]
                channel_name = str(member.get("channel_name") or "")[:128]
                steam_id = _linked_steam(db, did)
                eligible = bool(member.get("eligible")) and bool(steam_id)
                connected_since = now
                previous_since = previous_presence.get(did)
                if previous_since:
                    connected_since = previous_since
                db.execute(text("""
                    INSERT INTO discord_engagement_presence
                      (guild_id,discord_user_id,username,steam_id,channel_id,channel_name,eligible,connected_since,last_seen_at)
                    VALUES (:gid,:did,:username,:sid,:cid,:cname,:eligible,:since,:now)
                """), {"gid": guild_id, "did": did, "username": username, "sid": steam_id,
                       "cid": channel_id, "cname": channel_name, "eligible": int(eligible),
                       "since": connected_since, "now": now})
                if not steam_id:
                    continue
                row = _ensure_daily(db, did, day, "voice", steam_id)
                old_seconds, old_amount = int(row[0] or 0), int(row[1] or 0)
                last_seen = row[3]
                delta = 0
                if eligible and bool(row[5]) and last_seen:
                    if isinstance(last_seen, str):
                        try:
                            last_seen = datetime.fromisoformat(last_seen)
                        except ValueError:
                            last_seen = None
                    if last_seen:
                        delta = max(0, min(SCAN_SECONDS, int((now - last_seen).total_seconds())))
                seconds = old_seconds + delta
                interval_seconds = interval_minutes * 60
                due_amount = (seconds // interval_seconds) * reward if eligible else old_amount
                payout = min(max(0, due_amount - old_amount), max(0, daily_cap - old_amount)) if eligible and reward > 0 and daily_cap > 0 else 0
                db.execute(text("""
                    UPDATE discord_engagement_daily SET seconds=:seconds, amount=:amount,
                      last_seen_at=:now, connected_since=COALESCE(connected_since,:now),
                      eligible_last=:eligible
                    WHERE discord_user_id=:did AND activity_date=:day AND kind='voice'
                """), {"seconds": seconds, "amount": old_amount + payout,
                       "eligible": int(eligible),
                       "now": now, "did": did, "day": day})
                if payout > 0:
                    from amber_ledger import record_movement
                    key = f"discord:voice:{did}:{day}:{old_amount + payout}"
                    if record_movement(db, channel="discord_link", event_type="discord_voice_reward",
                                       signed_delta=payout, idempotency_key=key, steam_id=steam_id,
                                       source_table="discord_engagement_daily", source_id=f"{did}:{day}:voice",
                                       metadata={"minutes": interval_minutes}):
                        add_points_tx(db, steam_id, payout)
                        credits += payout
            # The DELETE above intentionally refreshes only this guild's live roster.
            db.execute(text("""
                INSERT INTO discord_engagement_status (guild_id,last_scan_at) VALUES (:gid,:now)
                ON CONFLICT(guild_id) DO UPDATE SET last_scan_at=excluded.last_scan_at
            """) if "sqlite" in str(db.get_bind().url).lower() else text("""
                INSERT INTO discord_engagement_status (guild_id,last_scan_at) VALUES (:gid,:now)
                ON DUPLICATE KEY UPDATE last_scan_at=VALUES(last_scan_at)
            """), {"gid": guild_id, "now": now})
            db.commit()
            return jsonify({"ok": True, "scanned": len(members), "credits": credits,
                            "scanned_at": now.isoformat() + "Z", "scan_seconds": SCAN_SECONDS})
        except Exception as exc:
            db.rollback()
            app.logger.exception("Discord voice snapshot failed")
            return jsonify({"ok": False, "error": f"Falha ao processar presença: {type(exc).__name__}"}), 500
        finally:
            db.close()

    @app.route("/api/internal/discord-engagement/config", methods=["GET"])
    @api_key_required(allow_admin_session=False)
    def internal_discord_engagement_config():
        cfg = load_settings()
        channels = sorted({x.strip() for x in str(cfg.get("discord_engagement_text_channel_ids") or "").split(",") if x.strip().isdigit()})
        return jsonify({"ok": True, "guild_id": str(cfg.get("discord_engagement_guild_id") or "").strip(),
                        "text_channel_ids": channels, "scan_seconds": SCAN_SECONDS})

    @app.route("/api/internal/discord-engagement/text-event", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    @limit("300 per minute")
    def discord_engagement_text_event():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco indisponível"}), 503
        body = request.get_json(silent=True) or {}
        cfg = load_settings()
        channels = {x.strip() for x in str(cfg.get("discord_engagement_text_channel_ids") or "").split(",") if x.strip().isdigit()}
        channel_id = str(body.get("channel_id") or "").strip()
        discord_id = str(body.get("discord_user_id") or "").strip()
        message_id = str(body.get("message_id") or "").strip()
        guild_id = str(body.get("guild_id") or "").strip()
        expected_guild = str(cfg.get("discord_engagement_guild_id") or "").strip()
        if not guild_id or (expected_guild and guild_id != expected_guild) or not channels or channel_id not in channels:
            return jsonify({"ok": True, "eligible": False, "reason": "channel_not_configured"})
        if not discord_id or not message_id or bool(body.get("is_command")):
            return jsonify({"ok": True, "eligible": False, "reason": "invalid_or_command"})
        min_chars = _int_setting(cfg, "discord_engagement_text_min_chars", 20, 1, 5000)
        chars = _int_setting(body, "content_length", 0, 0, 100000)
        attachments = _int_setting(body, "attachment_count", 0, 0, 20)
        if chars < min_chars and attachments <= 0:
            return jsonify({"ok": True, "eligible": False, "reason": "message_too_short"})
        reward = _int_setting(cfg, "discord_engagement_text_reward", 0, 0, 1000000)
        daily_cap = _int_setting(cfg, "discord_engagement_text_daily_cap", 0, 0, 100000000)
        cooldown_minutes = _int_setting(cfg, "discord_engagement_text_cooldown_minutes", 5, 1, 1440)
        if reward <= 0 or daily_cap <= 0:
            return jsonify({"ok": True, "eligible": False, "reason": "rewards_disabled"})
        db = session_factory()
        try:
            _schema(db)
            steam_id = _linked_steam(db, discord_id)
            if not steam_id:
                return jsonify({"ok": True, "eligible": False, "reason": "not_linked"})
            now = _now()
            day = now.date().isoformat()
            row = _ensure_daily(db, discord_id, day, "text", steam_id)
            old_amount = int(row[1] or 0)
            last_seen = row[3]
            if isinstance(last_seen, str):
                try:
                    last_seen = datetime.fromisoformat(last_seen)
                except ValueError:
                    last_seen = None
            if last_seen and (now - last_seen).total_seconds() < cooldown_minutes * 60:
                db.rollback()
                return jsonify({"ok": True, "eligible": False, "reason": "cooldown"})
            payout = min(reward, max(0, daily_cap - old_amount))
            if payout <= 0:
                db.rollback()
                return jsonify({"ok": True, "eligible": False, "reason": "daily_cap"})
            from amber_ledger import record_movement
            if not record_movement(db, channel="discord_link", event_type="discord_text_reward",
                                   signed_delta=payout, idempotency_key=f"discord:text:{message_id}",
                                   steam_id=steam_id, source_table="discord_messages",
                                   source_id=message_id,
                                   metadata={"channel_id": channel_id, "attachments": attachments}):
                db.rollback()
                return jsonify({"ok": True, "eligible": False, "reason": "duplicate"})
            add_points_tx(db, steam_id, payout)
            db.execute(text("""
                UPDATE discord_engagement_daily SET amount=amount+:payout, events=events+1,
                  last_seen_at=:now
                WHERE discord_user_id=:did AND activity_date=:day AND kind='text'
            """), {"payout": payout, "now": now, "did": discord_id, "day": day})
            db.commit()
            return jsonify({"ok": True, "eligible": True, "credited": payout})
        except Exception as exc:
            db.rollback()
            app.logger.exception("Discord text event failed")
            return jsonify({"ok": False, "error": f"Falha ao processar atividade: {type(exc).__name__}"}), 500
        finally:
            db.close()

    @app.route("/api/admin/discord-link/engagement", methods=["GET"])
    @admin_required
    def admin_discord_engagement():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco indisponível"}), 503
        cfg = load_settings()
        db = session_factory()
        try:
            _schema(db)
            guild_id = str(cfg.get("discord_engagement_guild_id") or "").strip()
            if not guild_id:
                latest = db.execute(text("SELECT guild_id FROM discord_engagement_status ORDER BY last_scan_at DESC LIMIT 1")).fetchone()
                guild_id = str(latest[0]) if latest else ""
            roster = db.execute(text("""
                SELECT p.discord_user_id,p.username,p.steam_id,p.channel_id,p.channel_name,p.eligible,
                       p.connected_since,p.last_seen_at,
                       COALESCE(v.seconds,0) AS seconds,COALESCE(v.amount,0) AS amount
                FROM discord_engagement_presence p
                LEFT JOIN discord_engagement_daily v ON v.discord_user_id=p.discord_user_id
                  AND v.activity_date=:day AND v.kind='voice'
                WHERE p.guild_id=:gid ORDER BY p.channel_name,p.username
            """), {"day": _now().date().isoformat(), "gid": guild_id}).fetchall() if guild_id else []
            status = db.execute(text("SELECT last_scan_at FROM discord_engagement_status WHERE guild_id=:gid"),
                                {"gid": guild_id}).fetchone() if guild_id else None
            last_scan = status[0] if status else None
            if isinstance(last_scan, datetime):
                last_scan = last_scan.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
            elif last_scan:
                last_scan = str(last_scan).replace(" ", "T") + "Z"
            return jsonify({"ok": True, "scan_seconds": SCAN_SECONDS,
                            "last_scan_at": last_scan,
                            "members": [{"discord_user_id": str(r[0]), "username": str(r[1] or ""),
                                         "steam_id": str(r[2] or ""), "channel_id": str(r[3]),
                                         "channel_name": str(r[4] or ""),
                                         "eligible": bool(r[5]), "connected_since": str(r[6]), "last_seen_at": str(r[7]),
                                         "eligible_seconds_today": int(r[8] or 0),
                                         "earned_today": int(r[9] or 0), "linked": bool(r[2])}
                                        for r in roster],
                            "config": {"guild_configured": bool(guild_id),
                                       "voice_reward": _int_setting(cfg, "discord_engagement_voice_reward", 0, 0, 1000000),
                                       "voice_interval_minutes": _int_setting(cfg, "discord_engagement_voice_interval_minutes", 30, 5, 1440),
                                       "voice_daily_cap": _int_setting(cfg, "discord_engagement_voice_daily_cap", 0, 0, 100000000),
                                       "text_reward": _int_setting(cfg, "discord_engagement_text_reward", 0, 0, 1000000),
                                       "text_daily_cap": _int_setting(cfg, "discord_engagement_text_daily_cap", 0, 0, 100000000)}})
        finally:
            db.close()
