"""Rotas HTTP do sistema de tickets (1.9.153)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from flask import Flask, jsonify, request, send_file

from ticket_service import (
    add_ticket_reply,
    attend_ticket,
    close_ticket,
    create_ticket,
    get_attachment_for_download,
    get_discord_link,
    get_ticket_detail,
    get_ticket_history,
    list_tickets_admin,
    list_tickets_for_player,
    request_player_close,
    resolve_player_name,
    save_discord_link,
    save_ticket_attachment,
    ticket_meta,
    update_ticket_priority,
    update_ticket_status,
)


def register_ticket_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    login_required: Callable,
    admin_required: Callable,
    ticket_staff_required: Callable,
    steam_id_from_session: Callable[[], str | None],
    is_admin_steamid: Callable[[str], bool],
    can_manage_tickets: Callable[[str], bool],
    resolve_display_name: Callable[[str], str] | None = None,
    uploads_dir: Path,
    limiter: Any | None = None,
    load_settings: Callable[[], dict[str, Any]] | None = None,
    save_settings: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    _limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))

    def _viewer_context() -> tuple[str | None, bool, bool]:
        sid = steam_id_from_session()
        admin = bool(sid and is_admin_steamid(sid))
        staff = bool(sid and can_manage_tickets(sid))
        return sid, admin, staff

    @app.route("/api/tickets/meta", methods=["GET"])
    def tickets_meta():
        return jsonify({"ok": True, **ticket_meta()})

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
        status = (request.args.get("tab") or request.args.get("status") or "").strip() or None
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
                **ticket_meta(),
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
            order_id_raw = body.get("order_id")
            order_id = str(order_id_raw).strip() if order_id_raw else None
            listing_id_raw = body.get("listing_id")
            listing_id = int(listing_id_raw) if listing_id_raw else None
            claim_id_raw = body.get("claim_id")
            claim_id = int(claim_id_raw) if claim_id_raw else None
            market_trace_id = str(body.get("market_trace_id") or "").strip() or None
            result = create_ticket(
                db,
                steam_id=steam_id,
                player_name=player_name,
                subject=str(body.get("subject") or ""),
                body=str(body.get("body") or ""),
                category=str(body.get("category") or "geral"),
                priority=str(body.get("priority") or "normal"),
                order_id=order_id,
                listing_id=listing_id,
                claim_id=claim_id,
                market_trace_id=market_trace_id,
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
        steam_id, is_admin, is_staff = _viewer_context()
        db = session_factory()
        try:
            detail = get_ticket_detail(
                db,
                ticket_id,
                viewer_steam_id=steam_id,
                is_admin=is_staff,
                include_order=True,
            )
            if not detail:
                return jsonify({"ok": False, "error": "Ticket não encontrado"}), 404
            return jsonify({"ok": True, **detail})
        finally:
            db.close()

    @app.route("/api/tickets/<int:ticket_id>/history", methods=["GET"])
    @login_required
    def tickets_history_player(ticket_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id, is_admin, is_staff = _viewer_context()
        db = session_factory()
        try:
            data = get_ticket_history(
                db, ticket_id, viewer_steam_id=steam_id, is_admin=is_staff
            )
            if not data:
                return jsonify({"ok": False, "error": "Ticket não encontrado"}), 404
            return jsonify({"ok": True, **data})
        finally:
            db.close()

    @app.route("/api/tickets/<int:ticket_id>/reply", methods=["POST"])
    @login_required
    @_limit("30 per minute")
    def tickets_reply_player(ticket_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        steam_id, is_admin, is_staff = _viewer_context()
        db = session_factory()
        try:
            player_name = resolve_player_name(
                db, str(steam_id), resolve_display_name=resolve_display_name
            )
            author_type = "admin" if is_staff else "player"
            if is_admin:
                author_label = f"Admin ({player_name})"
            elif is_staff:
                author_label = f"Suporte ({player_name})"
            else:
                author_label = player_name
            result = add_ticket_reply(
                db,
                ticket_id,
                author_type=author_type,
                author_steam_id=steam_id,
                author_name=author_label,
                body=str(body.get("body") or ""),
                links=body.get("links"),
                viewer_steam_id=steam_id,
                is_admin=is_staff,
            )
            if not result.get("ok"):
                return jsonify(result), 400
            return jsonify(result)
        finally:
            db.close()

    @app.route("/api/tickets/<int:ticket_id>/request-close", methods=["POST"])
    @login_required
    @_limit("10 per minute")
    def tickets_request_close_player(ticket_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        steam_id = str(steam_id_from_session())
        db = session_factory()
        try:
            player_name = resolve_player_name(
                db, steam_id, resolve_display_name=resolve_display_name
            )
            result = request_player_close(
                db,
                ticket_id,
                steam_id=steam_id,
                player_name=player_name,
                note=str(body.get("note") or "").strip() or None,
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
        steam_id, is_admin, is_staff = _viewer_context()
        file_obj = request.files.get("file")
        message_id_raw = request.form.get("message_id")
        message_id = int(message_id_raw) if message_id_raw else None
        db = session_factory()
        try:
            player_name = resolve_player_name(
                db, str(steam_id), resolve_display_name=resolve_display_name
            )
            result = save_ticket_attachment(
                db,
                ticket_id=ticket_id,
                message_id=message_id,
                file_storage=file_obj,
                uploads_dir=uploads_dir,
                viewer_steam_id=str(steam_id),
                is_admin=is_staff,
                actor_name=player_name,
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
        steam_id, is_admin, is_staff = _viewer_context()
        db = session_factory()
        try:
            meta = get_attachment_for_download(
                db,
                attachment_id,
                viewer_steam_id=steam_id,
                is_admin=is_staff,
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
    @ticket_staff_required
    def admin_tickets_list():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        status = (request.args.get("status") or "").strip() or None
        category = (request.args.get("category") or "").strip().lower() or None
        priority = (request.args.get("priority") or "").strip().lower() or None
        q = (request.args.get("q") or "").strip()
        limit = int(request.args.get("limit") or 50)
        offset = int(request.args.get("offset") or 0)
        db = session_factory()
        try:
            items, total = list_tickets_admin(
                db,
                status=status,
                category=category,
                priority=priority,
                q=q,
                limit=limit,
                offset=offset,
            )
            open_count = sum(
                1 for t in items if t["status"] in (
                    "AGUARDANDO_SUPORTE", "AGUARDANDO_JOGADOR",
                    "ABERTO", "EM_ANALISE",
                )
            )
            return jsonify({
                "ok": True,
                "items": items,
                "total": total,
                "open_hint": open_count,
                **ticket_meta(),
            })
        finally:
            db.close()

    @app.route("/api/admin/tickets/<int:ticket_id>", methods=["GET"])
    @ticket_staff_required
    def admin_tickets_detail(ticket_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            detail = get_ticket_detail(db, ticket_id, is_admin=True, include_order=True)
            if not detail:
                return jsonify({"ok": False, "error": "Ticket não encontrado"}), 404
            return jsonify({"ok": True, **detail})
        finally:
            db.close()

    @app.route("/api/admin/tickets/<int:ticket_id>/history", methods=["GET"])
    @ticket_staff_required
    def admin_tickets_history(ticket_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            data = get_ticket_history(db, ticket_id, is_admin=True)
            if not data:
                return jsonify({"ok": False, "error": "Ticket não encontrado"}), 404
            return jsonify({"ok": True, **data})
        finally:
            db.close()

    @app.route("/api/admin/tickets/<int:ticket_id>/reply", methods=["POST"])
    @ticket_staff_required
    @_limit("60 per minute")
    def admin_tickets_reply(ticket_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        staff_sid = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            staff_name = resolve_player_name(
                db, staff_sid, resolve_display_name=resolve_display_name
            )
            label = "Admin" if is_admin_steamid(staff_sid) else "Suporte"
            result = add_ticket_reply(
                db,
                ticket_id,
                author_type="admin",
                author_steam_id=staff_sid,
                author_name=f"{label} ({staff_name})",
                body=str(body.get("body") or ""),
                links=body.get("links"),
                viewer_steam_id=staff_sid,
                is_admin=True,
            )
            if not result.get("ok"):
                return jsonify(result), 400
            return jsonify(result)
        finally:
            db.close()

    @app.route("/api/admin/tickets/<int:ticket_id>/attend", methods=["POST"])
    @ticket_staff_required
    def admin_tickets_attend(ticket_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        staff_sid = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            staff_name = resolve_player_name(
                db, staff_sid, resolve_display_name=resolve_display_name
            )
            result = attend_ticket(
                db,
                ticket_id,
                admin_steam_id=staff_sid,
                admin_name=staff_name,
            )
            if not result.get("ok"):
                return jsonify(result), 400
            return jsonify(result)
        finally:
            db.close()

    @app.route("/api/admin/tickets/<int:ticket_id>/close", methods=["POST"])
    @ticket_staff_required
    def admin_tickets_close(ticket_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        staff_sid = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            staff_name = resolve_player_name(
                db, staff_sid, resolve_display_name=resolve_display_name
            )
            result = close_ticket(
                db,
                ticket_id,
                admin_steam_id=staff_sid,
                admin_name=staff_name,
                note=str(body.get("note") or "").strip() or None,
            )
            if not result.get("ok"):
                return jsonify(result), 400
            return jsonify(result)
        finally:
            db.close()

    @app.route("/api/admin/tickets/<int:ticket_id>/status", methods=["POST"])
    @ticket_staff_required
    def admin_tickets_status(ticket_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        status = str(body.get("status") or "").strip()
        staff_sid = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            staff_name = resolve_player_name(
                db, staff_sid, resolve_display_name=resolve_display_name
            )
            result = update_ticket_status(
                db,
                ticket_id,
                status=status,
                admin_steam_id=staff_sid,
                admin_name=staff_name,
            )
            if not result.get("ok"):
                return jsonify(result), 400
            return jsonify(result)
        finally:
            db.close()

    @app.route("/api/admin/tickets/<int:ticket_id>/priority", methods=["POST"])
    @ticket_staff_required
    def admin_tickets_priority(ticket_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        priority = str(body.get("priority") or "").strip().lower()
        staff_sid = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            staff_name = resolve_player_name(
                db, staff_sid, resolve_display_name=resolve_display_name
            )
            result = update_ticket_priority(
                db,
                ticket_id,
                priority=priority,
                admin_steam_id=staff_sid,
                admin_name=staff_name,
            )
            if not result.get("ok"):
                return jsonify(result), 400
            return jsonify(result)
        finally:
            db.close()

    @app.route("/api/admin/tickets/<int:ticket_id>/attachments", methods=["POST"])
    @ticket_staff_required
    @_limit("30 per minute")
    def admin_tickets_upload(ticket_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        file_obj = request.files.get("file")
        message_id_raw = request.form.get("message_id")
        message_id = int(message_id_raw) if message_id_raw else None
        staff_sid = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            staff_name = resolve_player_name(
                db, staff_sid, resolve_display_name=resolve_display_name
            )
            result = save_ticket_attachment(
                db,
                ticket_id=ticket_id,
                message_id=message_id,
                file_storage=file_obj,
                uploads_dir=uploads_dir,
                viewer_steam_id=staff_sid,
                is_admin=True,
                actor_name=staff_name,
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
            "error": "OAuth Discord para tickets ainda não implementado (1.9.149).",
            "oauth_available": False,
        }), 501

    @app.route("/api/admin/tickets/discord", methods=["GET"])
    @admin_required
    def admin_tickets_discord_status():
        if not load_settings:
            return jsonify({"ok": False, "error": "settings indisponível"}), 503
        from ticket_discord import ticket_discord_status

        return jsonify({"ok": True, **ticket_discord_status(load_settings)})

    @app.route("/api/admin/tickets/discord", methods=["POST"])
    @admin_required
    def admin_tickets_discord_save():
        if not load_settings or not save_settings:
            return jsonify({"ok": False, "error": "settings indisponível"}), 503
        from ticket_discord import ticket_discord_status

        body = request.get_json(force=True, silent=True) or {}
        s = load_settings()
        if "ticket_discord_enabled" in body:
            s["ticket_discord_enabled"] = bool(body["ticket_discord_enabled"])
        if "ticket_discord_channel_id" in body:
            s["ticket_discord_channel_id"] = str(
                body.get("ticket_discord_channel_id") or ""
            ).strip()
        token = str(body.get("ticket_discord_token") or "").strip()
        if token:
            s["ticket_discord_token"] = token
        save_settings(s)
        return jsonify({"ok": True, **ticket_discord_status(load_settings)})
