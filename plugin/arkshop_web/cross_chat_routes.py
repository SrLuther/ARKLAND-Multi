"""Rotas HTTP do chat cluster entre mapas."""
from __future__ import annotations

from typing import Any, Callable

from flask import Flask, jsonify, request

from cross_chat_service import poll_messages, publish_message, purge_old_messages


def register_cross_chat_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    api_key_required: Callable,
    limiter: Any | None = None,
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
