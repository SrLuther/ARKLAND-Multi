"""Rotas HTTP — Sugestões da comunidade."""
from __future__ import annotations

from typing import Any, Callable

from flask import Flask, jsonify, request

from suggestion_service import (
    create_suggestion,
    list_suggestions_admin,
    list_suggestions_for_player,
    public_suggestion_stats,
    suggestion_meta,
    update_suggestion_admin,
)


def register_suggestion_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    login_required: Callable,
    admin_required: Callable,
    steam_id_from_session: Callable[[], str | None],
    regulamento_guard: Callable[[str], Any] | None = None,
    limiter: Any | None = None,
) -> None:
    _limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))

    @app.route("/api/suggestions/meta", methods=["GET"])
    def suggestions_meta():
        return jsonify({"ok": True, **suggestion_meta()})

    @app.route("/api/suggestions/mine", methods=["GET"])
    @login_required
    def suggestions_mine():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session())
        limit = int(request.args.get("limit") or 10)
        offset = int(request.args.get("offset") or 0)
        db = session_factory()
        try:
            items, total = list_suggestions_for_player(
                db, steam_id, limit=limit, offset=offset,
            )
            remaining = max(0, 3 - _count_today(db, steam_id))
            return jsonify({
                "ok": True,
                "items": items,
                "total": total,
                "remaining_today": remaining,
                **suggestion_meta(),
            })
        finally:
            db.close()

    @app.route("/api/suggestions", methods=["POST"])
    @login_required
    @_limit("3 per day")
    def suggestions_create():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session())
        if regulamento_guard:
            if (reg_err := regulamento_guard(steam_id)) is not None:
                return reg_err
        body = request.get_json(force=True, silent=True) or {}
        db = session_factory()
        try:
            result = create_suggestion(
                db,
                steam_id=steam_id,
                category=str(body.get("category") or "outro"),
                title=str(body.get("title") or ""),
                description=str(body.get("description") or ""),
                details={
                    "species_name": body.get("species_name"),
                    "item_name": body.get("item_name"),
                    "reason": body.get("reason"),
                },
            )
            if not result.get("ok"):
                return jsonify(result), 400
            return jsonify(result), 201
        finally:
            db.close()

    @app.route("/api/public/suggestions/stats", methods=["GET"])
    def suggestions_public_stats():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            stats = public_suggestion_stats(db)
            return jsonify({"ok": True, "stats": stats})
        finally:
            db.close()

    @app.route("/api/admin/suggestions", methods=["GET"])
    @admin_required
    def suggestions_admin_list():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        status = (request.args.get("status") or "").strip() or None
        q = (request.args.get("q") or "").strip()
        limit = int(request.args.get("limit") or 10)
        offset = int(request.args.get("offset") or 0)
        db = session_factory()
        try:
            items, total = list_suggestions_admin(
                db, status=status, q=q, limit=limit, offset=offset,
            )
            return jsonify({
                "ok": True,
                "items": items,
                "total": total,
                **suggestion_meta(),
            })
        finally:
            db.close()

    @app.route("/api/admin/suggestions/<int:suggestion_id>", methods=["PATCH"])
    @admin_required
    def suggestions_admin_patch(suggestion_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        admin_sid = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            result = update_suggestion_admin(
                db,
                suggestion_id,
                status=body.get("status"),
                admin_note=body.get("admin_note"),
                admin_steam_id=admin_sid or None,
            )
            if not result.get("ok"):
                return jsonify(result), 400
            return jsonify(result)
        finally:
            db.close()


def _count_today(db: Any, steam_id: str) -> int:
    from suggestion_service import _count_recent_for_player

    return _count_recent_for_player(db, steam_id)
