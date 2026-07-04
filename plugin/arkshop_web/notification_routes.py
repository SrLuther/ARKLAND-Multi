"""Rotas HTTP de notificações in-app."""
from __future__ import annotations

from typing import Any, Callable

from flask import Flask, jsonify, request

from notification_service import list_notifications, mark_all_read, mark_read, unread_count


def register_notification_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    login_required: Callable,
    steam_id_from_session: Callable[[], str | None],
    limiter: Any | None = None,
) -> None:
    _limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))

    @app.route("/api/notifications", methods=["GET"])
    @login_required
    @_limit("30 per minute; 300 per hour", override_defaults=True)
    def notifications_list():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session())
        unread_only = (request.args.get("unread_only") or "").strip().lower() in (
            "1", "true", "yes",
        )
        limit = int(request.args.get("limit") or 50)
        offset = int(request.args.get("offset") or 0)
        db = session_factory()
        try:
            items, total = list_notifications(
                db, steam_id, unread_only=unread_only, limit=limit, offset=offset
            )
            count = unread_count(db, steam_id)
            return jsonify({
                "ok": True,
                "items": items,
                "total": total,
                "unread_count": count,
            })
        finally:
            db.close()

    @app.route("/api/notifications/unread-count", methods=["GET"])
    @login_required
    @_limit("60 per minute; 600 per hour", override_defaults=True)
    def notifications_unread_count():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session())
        db = session_factory()
        try:
            return jsonify({"ok": True, "unread_count": unread_count(db, steam_id)})
        finally:
            db.close()

    @app.route("/api/notifications/<int:notification_id>/read", methods=["POST"])
    @login_required
    @_limit("60 per minute")
    def notifications_mark_read(notification_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session())
        db = session_factory()
        try:
            result = mark_read(db, notification_id, steam_id=steam_id)
            if not result.get("ok"):
                return jsonify(result), 404
            return jsonify(result)
        finally:
            db.close()

    @app.route("/api/notifications/read-all", methods=["POST"])
    @login_required
    @_limit("20 per minute")
    def notifications_mark_all_read():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session())
        db = session_factory()
        try:
            return jsonify(mark_all_read(db, steam_id=steam_id))
        finally:
            db.close()
