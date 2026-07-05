"""Rotas HTTP — Mídias (vídeos YouTube)."""
from __future__ import annotations

from typing import Any, Callable

from flask import Flask, jsonify, request

from media_service import (
    create_media_video,
    delete_media_video,
    list_media_admin,
    list_media_public,
    media_meta,
    update_media_video,
)


def register_media_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    admin_required: Callable,
    steam_id_from_session: Callable[[], str | None],
    limiter: Any | None = None,
) -> None:
    _limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))

    @app.route("/api/public/media", methods=["GET"])
    def media_list_public():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        category = (request.args.get("category") or "").strip() or None
        db = session_factory()
        try:
            videos = list_media_public(db, category=category)
            return jsonify({"ok": True, "videos": videos, **media_meta()})
        finally:
            db.close()

    @app.route("/api/admin/media", methods=["GET"])
    @admin_required
    def media_admin_list():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            videos = list_media_admin(db)
            return jsonify({"ok": True, "videos": videos, **media_meta()})
        finally:
            db.close()

    @app.route("/api/admin/media", methods=["POST"])
    @admin_required
    @_limit("60 per hour")
    def media_admin_create():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        db = session_factory()
        try:
            video = create_media_video(
                db,
                youtube_url=body.get("youtube_url"),
                video_id=body.get("video_id"),
                title=str(body.get("title") or ""),
                description=body.get("description"),
                category=str(body.get("category") or "geral"),
                sort_order=int(body.get("sort_order") or 0),
                published=bool(body.get("published")),
                created_by_steam_id=str(steam_id_from_session() or "") or None,
            )
            return jsonify({"ok": True, "video": video}), 201
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/admin/media/<int:video_id>", methods=["PATCH"])
    @admin_required
    def media_admin_patch(video_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        db = session_factory()
        try:
            video = update_media_video(
                db,
                video_id,
                youtube_url=body.get("youtube_url"),
                video_id=body.get("video_id"),
                title=body.get("title"),
                description=body.get("description"),
                category=body.get("category"),
                sort_order=body.get("sort_order"),
                published=body.get("published"),
            )
            return jsonify({"ok": True, "video": video})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/admin/media/<int:video_id>", methods=["DELETE"])
    @admin_required
    def media_admin_delete(video_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            delete_media_video(db, video_id)
            return jsonify({"ok": True})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 404
        finally:
            db.close()
