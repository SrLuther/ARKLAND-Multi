"""Rotas HTTP do sistema de tickets (1.9.153)."""
from __future__ import annotations

from collections.abc import Callable
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_file

from ticket_service import (
    add_ticket_reply,
    attend_ticket,
    close_ticket,
    confirm_discord_link_code_for_discord_user,
    count_discord_link_admin_audit,
    count_discord_link_audit,
    create_ticket,
    generate_discord_link_code,
    get_attachment_for_download,
    get_discord_link,
    get_discord_link_verification_status,
    get_ticket_detail,
    get_ticket_history,
    list_discord_link_audit,
    list_discord_link_admin_audit,
    admin_unlink_discord,
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
    regulamento_guard: Callable[[str], Any] | None = None,
    uploads_dir: Path,
    limiter: Any | None = None,
    api_key_required: Callable[..., Any] | None = None,
    load_settings: Callable[[], dict[str, Any]] | None = None,
    save_settings: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    _limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))

    def _viewer_context() -> tuple[str | None, bool, bool]:
        sid = steam_id_from_session()
        admin = bool(sid and is_admin_steamid(sid))
        staff = bool(sid and can_manage_tickets(sid))
        return sid, admin, staff

    def _translation_build_info() -> dict[str, str]:
        release = app.config.get("ARKLAND_RELEASE") or {}
        return {
            "version": str(release.get("version") or "unknown"),
            "build_date": str(release.get("date") or "unknown"),
            "commit": str(os.environ.get("ARKLAND_GIT_COMMIT") or "unknown"),
        }

    @app.route("/api/translate", methods=["POST"])
    @login_required
    @_limit(
        "20 per minute",
        key_func=lambda: str(steam_id_from_session() or request.remote_addr or "unknown"),
        override_defaults=True,
    )
    def translate_player_text():
        """Translate user-requested text with free local Argos models."""
        body = request.get_json(silent=True) or {}
        text = str(body.get("text") or "").strip()
        target = str(body.get("target") or "").strip().lower()
        if not text:
            return jsonify({"ok": False, "error": "Informe o texto que deseja traduzir."}), 400
        if len(text) > 5000:
            return jsonify({"ok": False, "error": "O limite por tradução é de 5.000 caracteres."}), 413
        if target not in {"pt", "en", "es"}:
            return jsonify({"ok": False, "error": "Idioma de destino inválido."}), 400
        try:
            from translation_service import translate_offline

            translated = translate_offline(text, target)
            return jsonify({"ok": True, "translated": translated, "target": target})
        except Exception as exc:
            error_id = uuid.uuid4().hex[:12]
            code = getattr(exc, "code", "TRANSLATION_FAILED")
            stage = getattr(exc, "stage", "translation")
            pair = getattr(exc, "pair", None)
            logging.getLogger(__name__).exception(
                "Falha na tradução offline operation=translate stage=%s code=%s pair=%s reference_id=%s build=%s",
                stage, code, pair, error_id, _translation_build_info(),
            )
            return jsonify({
                "ok": False,
                "error_code": code,
                "stage": stage,
                "pair": "_to_".join(pair) if pair else None,
                "error": (
                    "Não foi possível preparar a tradução local. Confira a conexão para baixar os modelos gratuitos e tente novamente. "
                    f"ID: {error_id}"
                ),
                "reference": error_id,
                "reference_id": error_id,
            }), 503

    @app.route("/api/translate/models", methods=["POST"])
    @login_required
    @_limit(
        "6 per hour",
        key_func=lambda: str(steam_id_from_session() or request.remote_addr or "unknown"),
        override_defaults=True,
    )
    def manage_translation_models():
        """Let a signed-in player check, update or redownload the local free models."""
        body = request.get_json(silent=True) or {}
        force_redownload = bool(body.get("redownload"))
        try:
            from translation_service import refresh_translation_models

            # The explicit button promises a fresh check. Account-scoped limiting
            # prevents users behind a shared server IP from consuming each other's quota.
            result = refresh_translation_models(
                force_redownload=force_redownload,
                check_now=True,
            )
            return jsonify({"ok": True, **result})
        except Exception as exc:
            error_id = uuid.uuid4().hex[:12]
            code = getattr(exc, "code", "TRANSLATION_PREPARATION_FAILED")
            stage = getattr(exc, "stage", "preparation")
            pair = getattr(exc, "pair", None)
            logging.getLogger(__name__).exception(
                "Falha ao verificar modelos operation=models_check stage=%s code=%s pair=%s reference_id=%s build=%s",
                stage, code, pair, error_id, _translation_build_info(),
            )
            return jsonify({
                "ok": False,
                "error_code": code,
                "stage": stage,
                "pair": "_to_".join(pair) if pair else None,
                "error": (
                    "Não foi possível verificar os idiomas. Confira a conexão do servidor e tente novamente. "
                    f"ID: {error_id}"
                ),
                "reference": error_id,
                "reference_id": error_id,
            }), 503

    @app.route("/api/translate/models/upload", methods=["POST"])
    @login_required
    @_limit("10 per hour")
    def upload_translation_model():
        """Install a model file that the player downloaded manually."""
        file_obj = request.files.get("file")
        if not file_obj or not file_obj.filename:
            error_id = uuid.uuid4().hex[:12]
            logging.getLogger(__name__).warning(
                "Upload Argos operation=manual_upload stage=multipart_parse error_code=UPLOAD_FILE_MISSING "
                "reference_id=%s method=%s endpoint=%s content_type=%s content_length=%s "
                "form_fields=%s file_fields=%s build=%s",
                error_id,
                request.method,
                request.endpoint,
                request.mimetype,
                request.content_length,
                sorted(request.form.keys()),
                sorted(request.files.keys()),
                _translation_build_info(),
            )
            return jsonify({
                "ok": False,
                "error_code": "UPLOAD_FILE_MISSING",
                "stage": "multipart_parse",
                "reference": error_id,
                "reference_id": error_id,
                "error": "Selecione um arquivo .argosmodel.",
            }), 400
        if not file_obj.filename.lower().endswith(".argosmodel"):
            return jsonify({
                "ok": False, "error_code": "UPLOAD_INVALID_PACKAGE", "stage": "validation",
                "error": "O arquivo precisa ter a extensão .argosmodel.",
            }), 400
        # The largest official Argos package is about 273 MiB; leave room for
        # multipart framing while still keeping a bounded upload size.
        max_upload_bytes = 350 * 1024 * 1024
        if request.content_length and request.content_length > max_upload_bytes + 1024 * 1024:
            return jsonify({
                "ok": False, "error_code": "UPLOAD_TOO_LARGE", "stage": "receive",
                "error": "O envio excede o limite permitido de 350 MiB.",
            }), 413

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(prefix="argos-upload-", suffix=".argosmodel", delete=False) as temp:
                temp_path = Path(temp.name)
                total = 0
                while True:
                    chunk = file_obj.stream.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_upload_bytes:
                        return jsonify({
                            "ok": False, "error_code": "UPLOAD_TOO_LARGE", "stage": "receive",
                            "error": "O arquivo excede o limite de 350 MiB.",
                        }), 413
                    temp.write(chunk)

            from translation_service import install_translation_model

            pair = install_translation_model(temp_path)
            return jsonify({"ok": True, "installed": pair})
        except ValueError as exc:
            message = str(exc)
            code = "UNSUPPORTED_LANGUAGE_PAIR" if "idioma" in message.lower() or "idiomas" in message.lower() else "UPLOAD_INVALID_PACKAGE"
            error_id = uuid.uuid4().hex[:12]
            logging.getLogger(__name__).warning(
                "Upload Argos rejected operation=manual_upload stage=validation error_code=%s reference_id=%s build=%s",
                code, error_id, _translation_build_info(),
            )
            return jsonify({"ok": False, "error_code": code, "stage": "validation", "reference": error_id, "reference_id": error_id, "error": message}), 400
        except Exception as exc:
            error_id = uuid.uuid4().hex[:12]
            code = getattr(exc, "code", "MODEL_INSTALL_FAILED")
            stage = getattr(exc, "stage", "install")
            pair = getattr(exc, "pair", None)
            logging.getLogger(__name__).exception(
                "Falha ao instalar modelo operation=manual_upload stage=%s error_code=%s pair=%s reference_id=%s build=%s",
                stage, code, pair, error_id, _translation_build_info(),
            )
            return jsonify({
                "ok": False, "error_code": code, "stage": stage,
                "pair": "_to_".join(pair) if pair else None,
                "reference": error_id, "reference_id": error_id,
                "error": "Não foi possível instalar este modelo. Confira o arquivo e tente novamente.",
            }), 503
        finally:
            if temp_path:
                temp_path.unlink(missing_ok=True)

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
            verification = get_discord_link_verification_status(db, steam_id)
            try:
                audit_page = max(1, min(int(request.args.get("page", "1")), 100000))
            except (TypeError, ValueError):
                audit_page = 1
            audit_page_size = 5
            audit_total = count_discord_link_audit(db, steam_id)
            audit_pages = max(1, (audit_total + audit_page_size - 1) // audit_page_size)
            audit_page = min(audit_page, audit_pages)
            audit = list_discord_link_audit(
                db, steam_id, limit=audit_page_size,
                offset=(audit_page - 1) * audit_page_size,
            )
            return jsonify({
                "ok": True,
                "link": link,
                "verification": verification,
                "audit": audit,
                "audit_page": audit_page,
                "audit_page_size": audit_page_size,
                "audit_total": audit_total,
                "audit_pages": audit_pages,
                "instructions": {
                    "summary": "Envie somente o código no canal de validação Discord (sem texto adicional).",
                    "steps": [
                        "Clique em Gerar código de verificação.",
                        "Copie o código gerado na Minha Área.",
                        "Envie o código no canal de validação do Discord do servidor.",
                        "Clique em Revalidar para gerar outro código, se necessário.",
                    ],
                    "format": "ARKLAND-xxxXxxXXxX-0000000000-x0X0x0X0x0X0x-Discord",
                },
                "oauth_available": False,
            })
        finally:
            db.close()

    if api_key_required:
        @app.route("/api/internal/tickets/discord-link/confirm", methods=["POST"])
        @api_key_required(False)
        @_limit("120 per minute")
        def internal_tickets_discord_confirm_code():
            if not db_ready():
                return jsonify({"ok": False, "error": "Banco não configurado"}), 503
            body = request.get_json(force=True, silent=True) or {}
            code = str(body.get("code") or "").strip()
            discord_user_id = str(body.get("discord_user_id") or "").strip() or None
            discord_username = str(body.get("discord_username") or "").strip() or None

            if not code or not discord_user_id:
                return jsonify({
                    "ok": False,
                    "error": "code e discord_user_id são obrigatórios.",
                }), 400

            db = session_factory()
            try:
                out = confirm_discord_link_code_for_discord_user(
                    db,
                    code,
                    discord_user_id=discord_user_id,
                    discord_username=discord_username,
                )
                if not out.get("ok"):
                    reason = str(out.get("error") or out.get("message") or "").strip()
                    if not reason:
                        reason = "A Web Store recusou a vinculação sem informar o motivo. Consulte o log da Web Store."
                        app.logger.error("discord_link_confirmation_rejected_without_reason")
                    return jsonify({**out, "ok": False, "error": reason}), 400
                return jsonify({"ok": True, **out})
            finally:
                db.close()

    @app.route("/api/tickets/discord-link/code", methods=["POST"])
    @login_required
    @_limit("20 per minute")
    def tickets_discord_generate_code():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session())
        db = session_factory()
        try:
            out = generate_discord_link_code(
                db,
                steam_id=steam_id,
                expires_minutes=10,
                force_new=False,
            )
            if not out.get("ok"):
                return jsonify(out), 400
            return jsonify({"ok": True, **out})
        finally:
            db.close()

    @app.route("/api/tickets/discord-link/revalidate", methods=["POST"])
    @login_required
    @_limit("20 per minute")
    def tickets_discord_revalidate_code():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session())
        db = session_factory()
        try:
            out = generate_discord_link_code(
                db,
                steam_id=steam_id,
                expires_minutes=10,
                force_new=True,
            )
            if not out.get("ok"):
                return jsonify(out), 400
            return jsonify({"ok": True, **out})
        finally:
            db.close()

    @app.route("/api/tickets/discord-link/audit", methods=["GET"])
    @login_required
    def tickets_discord_audit():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session())
        db = session_factory()
        try:
            try:
                page = max(1, min(int(request.args.get("page", "1")), 100000))
            except (TypeError, ValueError):
                page = 1
            page_size = 5
            total = count_discord_link_audit(db, steam_id)
            pages = max(1, (total + page_size - 1) // page_size)
            page = min(page, pages)
            audit = list_discord_link_audit(db, steam_id, limit=page_size, offset=(page - 1) * page_size)
            return jsonify({"ok": True, "audit": audit, "page": page,
                            "page_size": page_size, "total": total, "pages": pages})
        finally:
            db.close()

    @app.route("/api/tickets/discord-link", methods=["POST"])
    @login_required
    @_limit("20 per minute")
    def tickets_discord_save():
        return jsonify({"ok": False, "error": "Manual link disabled; use Discord verification code."}), 410

    @app.route("/api/admin/discord-link/audit", methods=["GET"])
    @admin_required
    def admin_discord_link_audit():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        try:
            page = max(1, min(int(request.args.get("page", "1")), 100000))
            page_size = max(1, min(int(request.args.get("page_size", "50")), 100))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Paginação inválida"}), 400
        search = str(request.args.get("q") or "").strip()[:120]
        db = session_factory()
        try:
            query = str(request.args.get("q", "")).strip()[:128]
            total = count_discord_link_admin_audit(db, query=query)
            pages = max(1, (total + page_size - 1) // page_size)
            page = min(page, pages)
            events = list_discord_link_admin_audit(
                db, limit=page_size, offset=(page - 1) * page_size, query=query
            )
            return jsonify({"ok": True, "events": events, "total": total,
                            "page": page, "page_size": page_size, "pages": pages,
                            "search": search})
        finally:
            db.close()

    @app.route("/api/admin/discord-link/<steam_id>/unlink", methods=["POST"])
    @admin_required
    def admin_discord_link_unlink(steam_id: str):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        actor = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            result = admin_unlink_discord(db, steam_id=steam_id, actor_steam_id=actor,
                actor_name=resolve_player_name(db, actor) if actor else "",
                steam_name=resolve_player_name(db, steam_id))
            return jsonify(result), (200 if result.get("ok") else 404)
        finally:
            db.close()

    @app.route("/api/tickets", methods=["GET"])
    @login_required
    def tickets_list_player():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session())
        status = (request.args.get("tab") or request.args.get("status") or "").strip() or None
        limit = int(request.args.get("limit") or 10)
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
        steam_id = str(steam_id_from_session())
        if regulamento_guard and (reg_err := regulamento_guard(steam_id)) is not None:
            return reg_err
        body = request.get_json(force=True, silent=True) or {}
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
        steam_id, _is_admin, is_staff = _viewer_context()
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
        steam_id, _is_admin, is_staff = _viewer_context()
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
        steam_id, _is_admin, is_staff = _viewer_context()
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
        steam_id, _is_admin, is_staff = _viewer_context()
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
        limit = int(request.args.get("limit") or 10)
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
