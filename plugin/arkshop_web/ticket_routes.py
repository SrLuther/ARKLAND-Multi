"""Rotas HTTP do sistema de tickets (1.9.153)."""
from __future__ import annotations

from collections.abc import Callable
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_file
from sqlalchemy import bindparam, inspect, text

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
    admin_credit_discord_link_bonus,
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

    def _translation_usage_store():
        if not db_ready():
            raise RuntimeError("central database unavailable")
        db = session_factory()
        try:
            from translation_usage import TranslationUsage
            return TranslationUsage(db.get_bind())
        finally:
            db.close()

    def _translation_limits() -> tuple[int, list[int]]:
        settings = load_settings() if load_settings else {}
        limit_override = settings.get("azure_translator_monthly_character_limit")
        thresholds_override = settings.get("azure_translator_alert_thresholds")
        from translation_service import alert_thresholds, monthly_character_limit
        return (monthly_character_limit(limit_override),
                alert_thresholds(thresholds_override))

    def _translation_config() -> dict[str, str]:
        settings = load_settings() if load_settings else {}
        return {
            "key": str(settings.get("azure_translator_key") or "").strip(),
            "region": str(settings.get("azure_translator_region") or "").strip(),
            "endpoint": str(settings.get("azure_translator_endpoint") or "").strip(),
        }

    def _translate_text(text: str, target: str, source: str | None = None):
        from translation_service import TranslationServiceError, translate
        usage = _translation_usage_store()
        limit, thresholds = _translation_limits()
        periods: list[str] = []

        def before_attempt(characters: int) -> bool:
            allowed, _alerts, _used, period = usage.reserve(characters, limit, thresholds)
            if allowed:
                periods.append(period)
            return allowed

        def after_attempt(event: dict) -> None:
            period = periods.pop(0) if periods else None
            usage.finish(event, period)

        try:
            result = translate(
                text, target, source, before_attempt=before_attempt,
                after_attempt=after_attempt, config_override=_translation_config(),
            )
        except TranslationServiceError:
            raise
        return result

    def _translation_error(exc: Exception, *, operation: str, text_length: int,
                           target: str, source: str | None = None):
        reference_id = uuid.uuid4().hex[:12]
        code = getattr(exc, "code", "TRANSLATION_FAILED")
        stage = getattr(exc, "stage", "translation")
        status = getattr(exc, "http_status", None)
        azure_request_id = getattr(exc, "request_id", None)
        source_language = getattr(exc, "source_language", None) or source or "auto"
        target_language = getattr(exc, "target_language", None) or target
        logging.getLogger(__name__).error(
            "[Translation] provider=azure operation=%s source=%s target=%s characters=%d "
            "duration_ms=0 success=false error=%s stage=%s http_status=%s "
            "azure_request_id=%s reference_id=%s build=%s",
            operation, source_language, target_language, text_length, code, stage,
            status, azure_request_id, reference_id, _translation_build_info(),
        )
        response_status = 429 if code in {
            "AZURE_TRANSLATOR_RATE_LIMITED", "AZURE_TRANSLATOR_MONTHLY_LIMIT"
        } else 503
        return jsonify({
            "ok": False,
            "error_code": code,
            "stage": stage,
            "http_status": status,
            "reference_id": reference_id,
            "error": "Tradução temporariamente indisponível. A mensagem original continua disponível.",
        }), response_status

    @app.route("/api/translate", methods=["POST"])
    @login_required
    @_limit(
        "20 per minute",
        key_func=lambda: str(steam_id_from_session() or request.remote_addr or "unknown"),
        override_defaults=True,
    )
    def translate_player_text():
        """Translate on demand; failure never affects ticket creation or replies."""
        body = request.get_json(silent=True) or {}
        source_text = str(body.get("text") or "").strip()
        target = str(body.get("target") or "").strip().lower()
        source = str(body.get("source") or "").strip().lower() or None
        if not source_text:
            return jsonify({"ok": False, "error": "Informe o texto que deseja traduzir."}), 400
        if len(source_text) > 5000:
            return jsonify({"ok": False, "error": "O limite por tradução é de 5.000 caracteres."}), 413
        if target not in {"pt", "en", "es"}:
            return jsonify({"ok": False, "error": "Idioma de destino inválido."}), 400
        try:
            result = _translate_text(source_text, target, source)
            logging.getLogger(__name__).info(
                "[Translation] provider=%s source=%s target=%s characters=%d duration_ms=%d "
                "success=true http_status=%s azure_request_id=%s",
                result.provider, result.source_language or "unknown", result.target_language,
                len(source_text), result.duration_ms, result.http_status, result.request_id,
            )
            return jsonify({
                "ok": True,
                "original": source_text,
                "translated": result.translated_text,
                "source_language": result.source_language,
                "target_language": result.target_language,
                "provider": result.provider,
                "confidence": result.confidence,
                "duration_ms": result.duration_ms,
            })
        except Exception as exc:
            return _translation_error(exc, operation="translate", text_length=len(source_text),
                                      target=target, source=source)

    @app.route("/api/admin/translation/status", methods=["GET"])
    @admin_required
    def admin_translation_status():
        from translation_service import translator_status
        try:
            limit, thresholds = _translation_limits()
            usage = _translation_usage_store().snapshot(limit)
        except Exception:
            logging.getLogger(__name__).exception(
                "[Translation] provider=azure operation=admin_status error=USAGE_STORE_UNAVAILABLE build=%s",
                _translation_build_info(),
            )
            return jsonify({"ok": False, "error_code": "TRANSLATION_METRICS_UNAVAILABLE"}), 503
        return jsonify({"ok": True, "config": translator_status(
            limit_override=limit, thresholds_override=thresholds,
            config_override=_translation_config(),
        ), "usage": usage})

    @app.route("/api/admin/translation/settings", methods=["POST"])
    @admin_required
    @_limit("20 per hour", key_func=lambda: str(steam_id_from_session() or "admin"), override_defaults=True)
    def admin_translation_settings():
        from translation_service import translator_status
        if not load_settings or not save_settings:
            return jsonify({"ok": False, "error_code": "TRANSLATION_SETTINGS_UNAVAILABLE"}), 503
        body = request.get_json(silent=True) or {}
        try:
            raw_limit = body.get("monthly_character_limit")
            if isinstance(raw_limit, bool):
                raise ValueError
            limit = int(raw_limit)
            if limit < 0 or limit > 10**12:
                raise ValueError
            raw_thresholds = body.get("alert_thresholds")
            if not isinstance(raw_thresholds, list) or len(raw_thresholds) > 10:
                raise ValueError
            thresholds = sorted(set(int(value) for value in raw_thresholds))
            if any(value < 1 or value > 100 for value in thresholds):
                raise ValueError
            key = body.get("translator_key", "")
            region = body.get("region", "")
            endpoint = body.get("endpoint", "")
            clear_key = body.get("clear_key", False)
            if (not isinstance(key, str) or len(key.strip()) > 512
                    or not isinstance(region, str) or len(region.strip()) > 128
                    or not isinstance(endpoint, str) or len(endpoint.strip()) > 512
                    or not isinstance(clear_key, bool)):
                raise ValueError
            endpoint = endpoint.strip().rstrip("/")
            if endpoint:
                from urllib.parse import urlsplit
                parsed_endpoint = urlsplit(endpoint)
                if (parsed_endpoint.scheme != "https" or not parsed_endpoint.hostname
                        or parsed_endpoint.username or parsed_endpoint.password
                        or parsed_endpoint.query or parsed_endpoint.fragment):
                    raise ValueError
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error_code": "TRANSLATION_SETTINGS_INVALID",
                            "error": "Informe um limite mensal não negativo e alertas entre 1% e 100%."}), 400
        settings = load_settings()
        settings["azure_translator_monthly_character_limit"] = limit
        settings["azure_translator_alert_thresholds"] = thresholds
        settings["azure_translator_region"] = region.strip()
        settings["azure_translator_endpoint"] = endpoint
        if key.strip():
            settings["azure_translator_key"] = key.strip()
        elif clear_key:
            settings["azure_translator_key"] = ""
        try:
            save_settings(settings)
            usage = _translation_usage_store().snapshot(limit)
        except Exception:
            logging.getLogger(__name__).exception(
                "[Translation] provider=azure operation=admin_settings error=SAVE_FAILED build=%s",
                _translation_build_info(),
            )
            return jsonify({"ok": False, "error_code": "TRANSLATION_SETTINGS_SAVE_FAILED"}), 503
        return jsonify({"ok": True, "config": translator_status(
            limit_override=limit, thresholds_override=thresholds,
            config_override=_translation_config(),
        ), "usage": usage})

    @app.route("/api/admin/translation/test", methods=["POST"])
    @admin_required
    @_limit("10 per hour", key_func=lambda: str(steam_id_from_session() or "admin"), override_defaults=True)
    def admin_translation_test():
        text_to_test = "Hello, I need help with my server."
        try:
            result = _translate_text(text_to_test, "pt")
            logging.getLogger(__name__).info(
                "[Translation] provider=%s operation=admin_test source=%s target=pt characters=%d "
                "duration_ms=%d success=true http_status=%s azure_request_id=%s",
                result.provider, result.source_language or "unknown", len(text_to_test),
                result.duration_ms, result.http_status, result.request_id,
            )
            return jsonify({
                "ok": True, "message": "Azure Translator funcionando.",
                "source_language": result.source_language,
                "target_language": result.target_language,
                "translated": result.translated_text,
                "confidence": result.confidence,
                "duration_ms": result.duration_ms,
            })
        except Exception as exc:
            return _translation_error(exc, operation="admin_test", text_length=len(text_to_test), target="pt")
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
        @app.route("/api/internal/discord/nickname-sync", methods=["GET"])
        @api_key_required(False)
        @_limit("30 per minute")
        def internal_discord_nickname_sync():
            """Fornece ao bot a identidade do jogo das contas Discord vinculadas."""
            if not db_ready():
                return jsonify({"ok": False, "error": "Banco não configurado"}), 503
            db = session_factory()
            try:
                links = db.execute(text("""
                    SELECT steam_id, discord_user_id
                    FROM support_ticket_discord_links
                    WHERE discord_user_id IS NOT NULL AND TRIM(discord_user_id) <> ''
                    ORDER BY steam_id
                    LIMIT 1000
                """)).fetchall()
                linked_by_steam: dict[str, str] = {}
                for link in links:
                    steam_id = str(link[0] or "").strip()
                    discord_user_id = str(link[1] or "").strip()
                    if not steam_id or not discord_user_id:
                        continue
                    linked_by_steam[steam_id] = discord_user_id
                if not linked_by_steam:
                    return jsonify({
                        "ok": True, "users": [],
                        "diagnostics": {"active_source": "available", "online": 0, "fallback": 0},
                    })
                users = []
                seen_steam: set[str] = set()
                has_game_players = inspect(db.get_bind()).has_table("game_players")
                has_game_sessions = inspect(db.get_bind()).has_table("game_player_sessions")
                active_lookup_error: str | None = None
                online_count = 0

                # A sessão ativa é a fonte de verdade para o mapa atual. O plugin
                # envia heartbeat a cada 90 segundos; 4 minutos toleram uma perda
                # de heartbeat sem manter online uma sessão abandonada após crash.
                if has_game_players and has_game_sessions:
                    try:
                        online_query = text("""
                            SELECT gp.steam_id, gp.player_name, gp.tribe_name, s.last_seen_at
                            FROM game_player_sessions s
                            JOIN game_players gp
                              ON gp.steam_id = s.steam_id AND gp.server_id = s.server_id
                            WHERE s.steam_id IN :online_steam_ids
                              AND s.disconnected_at IS NULL
                              AND s.last_seen_at >= :online_since
                              AND gp.player_name IS NOT NULL AND TRIM(gp.player_name) <> ''
                            ORDER BY s.last_seen_at DESC
                        """).bindparams(bindparam("online_steam_ids", expanding=True))
                        online_since = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=4)
                        online_rows = db.execute(online_query, {
                            "online_steam_ids": list(linked_by_steam),
                            "online_since": online_since,
                        }).fetchall()
                        for online in online_rows:
                            steam_id = str(online[0] or "").strip()
                            if not steam_id or steam_id in seen_steam:
                                continue
                            seen_steam.add(steam_id)
                            online_count += 1
                            last_seen = online[3].isoformat() if hasattr(online[3], "isoformat") else str(online[3] or "")
                            users.append({
                                "discord_user_id": linked_by_steam[steam_id],
                                "character_name": str(online[1] or "").strip(),
                                "tribe_name": str(online[2] or "").strip(),
                                "identity_source": "active_session",
                                "identity_last_seen_at": last_seen,
                            })
                    except Exception as exc:
                        db.rollback()
                        active_lookup_error = f"{type(exc).__name__}: {exc}"
                        app.logger.exception(
                            "discord_nickname_active_lookup_failed; falling back to last-known identity"
                        )
                else:
                    active_lookup_error = "Tabelas de sessões online ainda não estão disponíveis."
                    app.logger.warning(
                        "discord_nickname_active_lookup_unavailable; falling back to last-known identity"
                    )

                unresolved_steam = [sid for sid in linked_by_steam if sid not in seen_steam]
                # If the player is offline, retain a useful fallback identity.
                # TribeSync can persist offline members under ``pdid:<id>``; for
                # those accounts game_players is the stable Steam-ID keyed source.
                identity_sql = """
                    SELECT steam_id, character_name, tribe_name, last_seen_at
                    FROM tribe_members
                    WHERE steam_id IN :tribe_steam_ids
                      AND character_name IS NOT NULL AND TRIM(character_name) <> ''
                """
                identities = []
                if unresolved_steam:
                    bind_params = [bindparam("tribe_steam_ids", expanding=True)]
                    identity_params: dict[str, Any] = {"tribe_steam_ids": unresolved_steam}
                    if has_game_players:
                        identity_sql += """
                            UNION ALL
                            SELECT steam_id, player_name AS character_name, tribe_name, last_seen_at
                            FROM game_players
                            WHERE steam_id IN :player_steam_ids
                              AND player_name IS NOT NULL AND TRIM(player_name) <> ''
                        """
                        bind_params.append(bindparam("player_steam_ids", expanding=True))
                        identity_params["player_steam_ids"] = unresolved_steam
                    identity_query = text(
                        f"SELECT steam_id, character_name, tribe_name, last_seen_at FROM ({identity_sql}) AS identities "
                        "ORDER BY last_seen_at DESC"
                    ).bindparams(*bind_params)
                    identities = db.execute(identity_query, identity_params).fetchall()
                for identity in identities:
                    steam_id = str(identity[0] or "").strip()
                    if not steam_id or steam_id in seen_steam:
                        continue
                    seen_steam.add(steam_id)
                    last_seen = identity[3].isoformat() if hasattr(identity[3], "isoformat") else str(identity[3] or "")
                    users.append({
                        "discord_user_id": linked_by_steam[steam_id],
                        "character_name": str(identity[1] or "").strip(),
                        "tribe_name": str(identity[2] or "").strip(),
                        "identity_source": "last_known",
                        "identity_last_seen_at": last_seen,
                    })

                return jsonify({
                    "ok": True,
                    "users": users,
                    "diagnostics": {
                        "active_source": "available" if not active_lookup_error else "fallback",
                        "active_error": active_lookup_error,
                        "online": online_count,
                        "fallback": sum(1 for user in users if user.get("identity_source") == "last_known"),
                    },
                })
            except Exception:
                db.rollback()
                app.logger.exception("discord_nickname_sync_snapshot_failed")
                return jsonify({"ok": False, "error": "Falha ao consultar identidades vinculadas"}), 503
            finally:
                db.close()

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
            except Exception:
                db.rollback()
                app.logger.exception("discord_link_confirmation_failed")
                return jsonify({
                    "ok": False,
                    "error": "Falha temporaria ao concluir o vinculo e creditar o bonus. Tente novamente.",
                }), 503
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

    @app.route("/api/admin/discord-link/<steam_id>/credit-bonus", methods=["POST"])
    @admin_required
    def admin_discord_link_credit_bonus(steam_id: str):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        actor = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            result = admin_credit_discord_link_bonus(db, steam_id=steam_id,
                actor_steam_id=actor,
                actor_name=resolve_player_name(db, actor) if actor else "")
            return jsonify(result), (200 if result.get("ok") else int(result.get("status", 409)))
        except Exception:
            db.rollback()
            logging.exception("Falha no crédito administrativo do bônus de vínculo Discord")
            return jsonify({"ok": False, "error": "Falha ao creditar o bônus. Nenhum saldo foi alterado."}), 503
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
