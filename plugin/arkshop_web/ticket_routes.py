"""Rotas HTTP do sistema de tickets (MVP 1.9.149)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from flask import Flask, jsonify, request, send_file

from ticket_service import (
    add_ticket_reply,
    create_ticket,
    get_attachment_for_download,
    get_discord_link,
    get_ticket_detail,
    list_tickets_admin,
    list_tickets_for_player,
    resolve_player_name,
    save_discord_link,
    save_ticket_attachment,
    update_ticket_status,
)


def register_ticket_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    login_required: Callable,
    admin_required: Callable,
    steam_id_from_session: Callable[[], str | None],
    is_admin_steamid: Callable[[str], bool],
    resolve_display_name: Callable[[str], str] | None = None,
    uploads_dir: Path,
    limiter: Any | None = None,
) -> None:
    _limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))

    def _viewer_context() -> tuple[str | None, bool]:
        sid = steam_id_from_session()
        admin = bool(sid and is_admin_steamid(sid))
        return sid, admin

    @app.route("/api/tickets/discord-link", methods=["GET"])
    @login_required
    def tickets_discord_get():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session())
        db = session_factory()
        try:
            link = get_discord_link(db, steam_id)
            return jsonify({"ok": True, "link": link, "oauth_available": False})
        finally:
            db.close()

    @app.route("/api/tickets/discord-link", methods=["POST"])
    @login_required
    @_limit("20 per minute")
    def tickets_discord_save():
        """Vincula Discord manualmente (OAuth stub para versão futura)."""
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        if body.get("oauth"):
            return jsonify({
                "ok": False,
                "error": "OAuth Discord ainda não disponível — use vínculo manual.",
                "oauth_available": False,
            }), 501
        steam_id = str(steam_id_from_session())
        discord_user_id = str(body.get("discord_user_id") or "").strip() or None
        discord_username = str(body.get("discord_username") or "").strip() or None
        if not discord_user_id and not discord_username:
            return jsonify({"ok": False, "error": "Informe usuário ou ID do Discord"}), 400
        db = session_factory()
        try:
            link = save_discord_link(
                db,
                steam_id=steam_id,
                discord_user_id=discord_user_id,
                discord_username=discord_username,
                link_method="manual",
            )
            return jsonify({"ok": True, "link": link})
        finally:
            db.close()

    @app.route("/api/tickets", methods=["GET"])
    @login_required
    def tickets_list_player():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session())
        status = (request.args.get("status") or "").strip().lower() or None
        limit = int(request.args.get("limit") or 50)
        offset = int(request.args.get("offset") or 0)
        db = session_factory()
        try:
            items, total = list_tickets_for_player(
                db, steam_id, status=status, limit=limit, offset=offset
            )
            player_name = resolve_player_name(
                db, steam_id, resolve_display_name=resolve_display_name
            )
            link = get_discord_link(db, steam_id)
            return jsonify({
                "ok": True,
                "items": items,
                "total": total,
                "player_name": player_name,
                "discord_link": link,
            })
        finally:
            db.close()

    @app.route("/api/tickets", methods=["POST"])
    @login_required
    @_limit("10 per minute")
    def tickets_create():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        steam_id = str(steam_id_from_session())
        db = session_factory()
        try:
            player_name = resolve_player_name(
                db, steam_id, resolve_display_name=resolve_display_name
            )
            link = get_discord_link(db, steam_id)
            result = create_ticket(
                db,
                steam_id=steam_id,
                player_name=player_name,
                subject=str(body.get("subject") or ""),
                body=str(body.get("body") or ""),
                category=str(body.get("category") or "geral"),
                links=body.get("links"),
                discord_user_id=link.get("discord_user_id") if link else None,
                discord_username=link.get("discord_username") if link else None,
            )
            if not result.get("ok"):
                return jsonify(result), 400
            return jsonify(result), 201
        finally:
            db.close()

    @app.route("/api/tickets/<int:ticket_id>", methods=["GET"])
    @login_required
    def tickets_detail_player(ticket_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id, is_admin = _viewer_context()
        db = session_factory()
        try:
            detail = get_ticket_detail(
                db, ticket_id, viewer_steam_id=steam_id, is_admin=is_admin
            )
            if not detail:
                return jsonify({"ok": False, "error": "Ticket não encontrado"}), 404
            return jsonify({"ok": True, **detail})
        finally:
            db.close()

    @app.route("/api/tickets/<int:ticket_id>/reply", methods=["POST"])
    @login_required
    @_limit("30 per minute")
    def tickets_reply_player(ticket_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        steam_id, is_admin = _viewer_context()
        db = session_factory()
        try:
            player_name = resolve_player_name(
                db, str(steam_id), resolve_display_name=resolve_display_name
            )
            author_type = "admin" if is_admin else "player"
            result = add_ticket_reply(
                db,
                ticket_id,
                author_type=author_type,
                author_steam_id=steam_id,
                author_name=player_name if not is_admin else f"Admin ({player_name})",
                body=str(body.get("body") or ""),
                links=body.get("links"),
                viewer_steam_id=steam_id,
                is_admin=is_admin,
            )
            if not result.get("ok"):
                return jsonify(result), 400
            return jsonify(result)
        finally:
            db.close()

    @app.route("/api/tickets/<int:ticket_id>/attachments", methods=["POST"])
    @login_required
    @_limit("20 per minute")
    def tickets_upload_player(ticket_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id, is_admin = _viewer_context()
        file_obj = request.files.get("file")
        message_id_raw = request.form.get("message_id")
        message_id = int(message_id_raw) if message_id_raw else None
        db = session_factory()
        try:
            result = save_ticket_attachment(
                db,
                ticket_id=ticket_id,
                message_id=message_id,
                file_storage=file_obj,
                uploads_dir=uploads_dir,
                viewer_steam_id=str(steam_id),
                is_admin=is_admin,
            )
            if not result.get("ok"):
                return jsonify(result), 400
            return jsonify(result), 201
        finally:
            db.close()

    @app.route("/api/tickets/attachments/<int:attachment_id>", methods=["GET"])
    @login_required
    def tickets_download_attachment(attachment_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id, is_admin = _viewer_context()
        db = session_factory()
        try:
            meta = get_attachment_for_download(
                db,
                attachment_id,
                viewer_steam_id=steam_id,
                is_admin=is_admin,
                uploads_dir=uploads_dir,
            )
            if not meta:
                return jsonify({"ok": False, "error": "Anexo não encontrado"}), 404
            return send_file(
                meta["path"],
                mimetype=meta["mime_type"],
                as_attachment=True,
                download_name=meta["original_filename"],
            )
        finally:
            db.close()

    # ── Admin ─────────────────────────────────────────────────────────────────

    @app.route("/api/admin/tickets", methods=["GET"])
    @admin_required
    def admin_tickets_list():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        status = (request.args.get("status") or "").strip().lower() or None
        q = (request.args.get("q") or "").strip()
        limit = int(request.args.get("limit") or 50)
        offset = int(request.args.get("offset") or 0)
        db = session_factory()
        try:
            items, total = list_tickets_admin(
                db, status=status, q=q, limit=limit, offset=offset
            )
            open_count = sum(1 for t in items if t["status"] in ("OPEN", "IN_PROGRESS"))
            return jsonify({"ok": True, "items": items, "total": total, "open_hint": open_count})
        finally:
            db.close()

    @app.route("/api/admin/tickets/<int:ticket_id>", methods=["GET"])
    @admin_required
    def admin_tickets_detail(ticket_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            detail = get_ticket_detail(db, ticket_id, is_admin=True)
            if not detail:
                return jsonify({"ok": False, "error": "Ticket não encontrado"}), 404
            return jsonify({"ok": True, **detail})
        finally:
            db.close()

    @app.route("/api/admin/tickets/<int:ticket_id>/reply", methods=["POST"])
    @admin_required
    @_limit("60 per minute")
    def admin_tickets_reply(ticket_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        admin_sid = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            admin_name = resolve_player_name(
                db, admin_sid, resolve_display_name=resolve_display_name
            )
            result = add_ticket_reply(
                db,
                ticket_id,
                author_type="admin",
                author_steam_id=admin_sid,
                author_name=f"Suporte ({admin_name})",
                body=str(body.get("body") or ""),
                links=body.get("links"),
                viewer_steam_id=admin_sid,
                is_admin=True,
            )
            if not result.get("ok"):
                return jsonify(result), 400
            return jsonify(result)
        finally:
            db.close()

    @app.route("/api/admin/tickets/<int:ticket_id>/status", methods=["POST"])
    @admin_required
    def admin_tickets_status(ticket_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        status = str(body.get("status") or "").strip().upper()
        admin_sid = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            result = update_ticket_status(
                db, ticket_id, status=status, admin_steam_id=admin_sid
            )
            if not result.get("ok"):
                return jsonify(result), 400
            return jsonify(result)
        finally:
            db.close()

    @app.route("/api/admin/tickets/<int:ticket_id>/attachments", methods=["POST"])
    @admin_required
    @_limit("30 per minute")
    def admin_tickets_upload(ticket_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        file_obj = request.files.get("file")
        message_id_raw = request.form.get("message_id")
        message_id = int(message_id_raw) if message_id_raw else None
        admin_sid = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            result = save_ticket_attachment(
                db,
                ticket_id=ticket_id,
                message_id=message_id,
                file_storage=file_obj,
                uploads_dir=uploads_dir,
                viewer_steam_id=admin_sid,
                is_admin=True,
            )
            if not result.get("ok"):
                return jsonify(result), 400
            return jsonify(result), 201
        finally:
            db.close()

    @app.route("/api/admin/tickets/discord-oauth", methods=["GET"])
    @admin_required
    def admin_tickets_discord_oauth_stub():
        """Stub — OAuth Discord para staff em versão futura."""
        return jsonify({
            "ok": False,
            "error": "OAuth Discord para tickets ainda não implementado (1.9.149 MVP).",
            "oauth_available": False,
        }), 501
