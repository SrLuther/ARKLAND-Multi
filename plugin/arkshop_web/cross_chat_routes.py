"""Rotas HTTP do chat cluster entre mapas."""
from __future__ import annotations

from typing import Any, Callable

from flask import Flask, jsonify, request

from cross_chat_service import (
    chat_stats,
    list_messages,
    list_mutes,
    mute_player,
    poll_messages,
    publish_message,
    purge_old_messages,
    unmute_player,
)


def register_cross_chat_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    api_key_required: Callable,
    admin_required: Callable | None = None,
    limiter: Any | None = None,
    load_settings: Callable[[], Any] | None = None,
    save_settings: Callable[[Any], None] | None = None,
) -> None:
    _limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))

    @app.route("/api/chat/publish", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    @_limit("120 per minute")
    def chat_publish():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco nao configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        db = session_factory()
        try:
            result = publish_message(
                db,
                source_server=str(body.get("source_server", "")).strip(),
                steam_id=str(body.get("steam_id", "")).strip(),
                player_name=str(body.get("player_name", "")).strip(),
                tribe_name=str(body.get("tribe_name", "")).strip(),
                message=str(body.get("message", "")).strip(),
                channel=str(body.get("channel", "cluster")).strip(),
            )
            if not result.get("ok"):
                return jsonify(result), 400
            return jsonify(result)
        finally:
            db.close()

    @app.route("/api/chat/poll", methods=["GET"])
    @api_key_required(allow_admin_session=False)
    @_limit("300 per minute")
    def chat_poll():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco nao configurado"}), 503
        server_id = (request.args.get("server") or "").strip()
        since = int(request.args.get("since") or 0)
        db = session_factory()
        try:
            messages = poll_messages(db, server_id=server_id, since_id=since)
            return jsonify({"ok": True, "messages": messages})
        finally:
            db.close()

    @app.route("/api/chat/purge", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    @_limit("10 per hour")
    def chat_purge():
        """Manutenção — remove mensagens antigas."""
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco nao configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        days = int(body.get("days") or 7)
        db = session_factory()
        try:
            deleted = purge_old_messages(db, days=days)
            return jsonify({"ok": True, "deleted": deleted})
        finally:
            db.close()

    if not admin_required:
        return

    @app.route("/api/admin/chat/stats", methods=["GET"])
    @admin_required
    def admin_chat_stats():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco nao configurado"}), 503
        db = session_factory()
        try:
            return jsonify({"ok": True, **chat_stats(db)})
        finally:
            db.close()

    @app.route("/api/admin/chat/messages", methods=["GET"])
    @admin_required
    def admin_chat_messages():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco nao configurado"}), 503
        limit = int(request.args.get("limit") or 50)
        offset = int(request.args.get("offset") or 0)
        steam_id = (request.args.get("steam_id") or "").strip()
        source_server = (request.args.get("source_server") or "").strip()
        q = (request.args.get("q") or "").strip()
        db = session_factory()
        try:
            items, total = list_messages(
                db,
                limit=limit,
                offset=offset,
                steam_id=steam_id,
                source_server=source_server,
                q=q,
            )
            return jsonify({"ok": True, "items": items, "total": total})
        finally:
            db.close()

    @app.route("/api/admin/chat/mutes", methods=["GET"])
    @admin_required
    def admin_chat_mutes():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco nao configurado"}), 503
        db = session_factory()
        try:
            return jsonify({"ok": True, "items": list_mutes(db)})
        finally:
            db.close()

    @app.route("/api/admin/chat/mute", methods=["POST"])
    @admin_required
    def admin_chat_mute():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco nao configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        hours_raw = body.get("hours")
        hours = int(hours_raw) if hours_raw not in (None, "") else None
        db = session_factory()
        try:
            result = mute_player(
                db,
                steam_id=str(body.get("steam_id", "")).strip(),
                hours=hours,
                reason=str(body.get("reason", "")).strip(),
            )
            if not result.get("ok"):
                return jsonify(result), 400
            return jsonify(result)
        finally:
            db.close()

    @app.route("/api/admin/chat/mute/<steam_id>", methods=["DELETE"])
    @admin_required
    def admin_chat_unmute(steam_id: str):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco nao configurado"}), 503
        db = session_factory()
        try:
            result = unmute_player(db, steam_id=steam_id)
            if not result.get("ok"):
                return jsonify(result), 400
            return jsonify(result)
        finally:
            db.close()

    @app.route("/api/admin/chat/discord", methods=["GET"])
    @admin_required
    def admin_chat_discord_status():
        if not load_settings:
            return jsonify({"ok": False, "error": "settings indisponivel"}), 503
        from cross_chat_discord import discord_bridge_status, load_discord_config

        return jsonify({
            "ok": True,
            **discord_bridge_status(load_settings, db_ready),
        })

    @app.route("/api/admin/chat/discord", methods=["POST"])
    @admin_required
    def admin_chat_discord_save():
        if not load_settings or not save_settings:
            return jsonify({"ok": False, "error": "settings indisponivel"}), 503
        from cross_chat_discord import stop_discord_bridge, start_discord_bridge

        body = request.get_json(force=True, silent=True) or {}
        s = load_settings()
        if "cross_chat_discord_enabled" in body:
            s["cross_chat_discord_enabled"] = bool(body["cross_chat_discord_enabled"])
        if "cross_chat_discord_channel_id" in body:
            s["cross_chat_discord_channel_id"] = str(
                body.get("cross_chat_discord_channel_id") or ""
            ).strip()
        token = str(body.get("cross_chat_discord_token") or "").strip()
        if token:
            s["cross_chat_discord_token"] = token
        save_settings(s)

        stop_discord_bridge()
        start_discord_bridge(
            session_factory=session_factory,
            load_settings=load_settings,
            save_settings=save_settings,
            db_ready=db_ready,
        )
        from cross_chat_discord import discord_bridge_status

        return jsonify({
            "ok": True,
            **discord_bridge_status(load_settings, db_ready),
        })
