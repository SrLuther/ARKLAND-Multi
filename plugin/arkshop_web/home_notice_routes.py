"""Rotas HTTP — mural de avisos da home."""
from __future__ import annotations

from typing import Any, Callable

from flask import Flask, jsonify, request

from home_notice_service import get_home_notice, set_home_notice


def register_home_notice_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    admin_required: Callable,
    steam_id_from_session: Callable[[], str | None],
    limiter: Any | None = None,
) -> None:
    _limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))

    def _safe_get(db: Any) -> dict[str, Any]:
        try:
            return get_home_notice(db)
        except Exception:
            return {
                "title": "",
                "body": "",
                "updated_at": None,
                "updated_by_steam_id": None,
                "has_content": False,
            }

    @app.route("/api/public/home-notice", methods=["GET"])
    @_limit("120 per minute; 2000 per hour", override_defaults=True)
    def home_notice_public():
        if not db_ready():
            return jsonify({
                "ok": True,
                "notice": {
                    "title": "",
                    "body": "",
                    "updated_at": None,
                    "updated_by_steam_id": None,
                    "has_content": False,
                },
                "degraded": True,
            })
        db = session_factory()
        try:
            return jsonify({"ok": True, "notice": _safe_get(db)})
        finally:
            db.close()

    @app.route("/api/admin/home-notice", methods=["GET"])
    @admin_required
    def home_notice_admin_get():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            return jsonify({"ok": True, "notice": get_home_notice(db)})
        except Exception as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            db.close()

    @app.route("/api/admin/home-notice", methods=["PUT"])
    @admin_required
    @_limit("60 per hour")
    def home_notice_admin_put():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        db = session_factory()
        try:
            notice = set_home_notice(
                db,
                title=body.get("title"),
                body=body.get("body"),
                updated_by_steam_id=str(steam_id_from_session() or "") or None,
            )
            return jsonify({"ok": True, "notice": notice})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            db.close()
