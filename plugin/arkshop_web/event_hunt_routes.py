"""Rotas ArkEventHunt (Mode A + Mode B).

Registrar via register_event_hunt_routes(app, ...) no app.py.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from flask import Flask, jsonify, request

log = logging.getLogger("arkshop_web.event_hunt_routes")


def register_event_hunt_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    login_required: Callable,
    admin_required: Callable,
    api_key_required: Callable,
    steam_id_from_session: Callable[[], str | None],
    is_admin_steamid: Callable[[str], bool],
    limiter: Any | None = None,
) -> None:
    if app.view_functions.get("event_hunt_a_me_summary") is not None:
        log.info("event_hunt_routes: already registered — skip")
        return

    from event_hunt_service import (
        admin_create_challenge,
        admin_create_public_dino,
        admin_create_session,
        admin_create_weapon_preset,
        admin_delete_weapon_preset,
        admin_disable_challenge,
        admin_grant_reward,
        admin_grant_reward_instance,
        admin_list_audit,
        admin_list_claims,
        admin_list_inscriptions,
        admin_list_instances,
        admin_list_public_dinos,
        admin_list_sessions,
        admin_transition_session,
        admin_update_challenge,
        admin_update_public_dino,
        admin_update_session,
        admin_update_weapon_preset,
        admin_void_claim,
        admin_void_instance,
        cancel_claim,
        event_hunt_enabled,
        get_challenge,
        list_challenges,
        list_team_claims,
        list_weapon_presets,
        me_summary,
        mode_b_current_session,
        mode_b_inscribe,
        mode_b_leaderboard,
        mode_b_team_summary,
        mode_b_withdraw,
        plugin_b_by_code,
        plugin_b_expire,
        plugin_b_mark_spawned,
        plugin_b_report_kill,
        plugin_claim_by_code,
        plugin_complete,
        plugin_fail,
        plugin_mark_spawned,
        select_challenge,
        team_summary,
    )

    def _db():
        return session_factory()

    def _ok(data: Any = None, **extra):
        payload = {"ok": True}
        if data is not None:
            payload["data"] = data
        payload.update(extra)
        return jsonify(payload)

    def _fail(msg: str, code: int = 400):
        return jsonify({"ok": False, "error": msg}), code

    def _handle(exc: Exception):
        if isinstance(exc, PermissionError):
            return _fail(str(exc) or "Sem permissão", 403)
        if isinstance(exc, LookupError):
            return _fail(str(exc) or "Não encontrado", 404)
        if isinstance(exc, ValueError):
            msg = str(exc)
            code = 409 if "Já" in msg or "já" in msg or "override" in msg.lower() else 400
            return _fail(msg, code)
        log.exception("event_hunt error: %s", exc)
        return _fail(str(exc) or "Erro interno", 500)

    # ── Player UI ────────────────────────────────────────────────────────────

    @app.route("/api/event-hunt/a/challenges", methods=["GET"])
    @login_required
    def event_hunt_a_challenges():
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = steam_id_from_session()
        if not sid:
            return _fail("Login necessário", 401)
        available = request.args.get("available_for_me", "0") in ("1", "true", "yes")
        enabled_only = request.args.get("enabled", "1") not in ("0", "false")
        db = _db()
        try:
            items = list_challenges(
                db,
                enabled_only=enabled_only and not request.args.get("all"),
                steam_id=sid,
                available_for_me=available,
            )
            return _ok({"items": items})
        except Exception as exc:
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/event-hunt/a/claims", methods=["POST"])
    @login_required
    def event_hunt_a_claims_create():
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = steam_id_from_session()
        if not sid:
            return _fail("Login necessário", 401)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            result = select_challenge(
                db, steam_id=sid, challenge_id=int(body.get("challenge_id") or 0)
            )
            return _ok(result)
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/event-hunt/a/me/summary", methods=["GET"])
    @login_required
    def event_hunt_a_me_summary():
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = steam_id_from_session()
        if not sid:
            return _fail("Login necessário", 401)
        db = _db()
        try:
            return _ok(me_summary(db, sid))
        except Exception as exc:
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/event-hunt/a/team/summary", methods=["GET"])
    @login_required
    def event_hunt_a_team_summary():
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = steam_id_from_session()
        if not sid:
            return _fail("Login necessário", 401)
        db = _db()
        try:
            return _ok(team_summary(db, sid))
        except Exception as exc:
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/event-hunt/a/team/claims", methods=["GET"])
    @login_required
    def event_hunt_a_team_claims():
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = steam_id_from_session()
        if not sid:
            return _fail("Login necessário", 401)
        db = _db()
        try:
            return _ok(list_team_claims(
                db,
                sid,
                page=int(request.args.get("page") or 1),
                page_size=int(request.args.get("page_size") or 50),
                mine_only=False,
            ))
        except Exception as exc:
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/event-hunt/a/me/claims", methods=["GET"])
    @login_required
    def event_hunt_a_me_claims():
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = steam_id_from_session()
        if not sid:
            return _fail("Login necessário", 401)
        db = _db()
        try:
            return _ok(list_team_claims(
                db,
                sid,
                page=int(request.args.get("page") or 1),
                page_size=int(request.args.get("page_size") or 50),
                mine_only=True,
            ))
        except Exception as exc:
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/event-hunt/a/claims/<int:claim_id>/cancel", methods=["POST"])
    @login_required
    def event_hunt_a_claim_cancel(claim_id: int):
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = steam_id_from_session()
        if not sid:
            return _fail("Login necessário", 401)
        db = _db()
        try:
            return _ok(cancel_claim(db, steam_id=sid, claim_id=int(claim_id)))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    # ── Plugin ───────────────────────────────────────────────────────────────

    @app.route("/api/event-hunt/a/claims/by-code/<code>", methods=["GET"])
    @api_key_required(allow_admin_session=False)
    def event_hunt_a_by_code(code: str):
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            return jsonify(plugin_claim_by_code(db, code))
        except Exception as exc:
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/event-hunt/a/claims/<int:claim_id>/spawned", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    def event_hunt_a_spawned(claim_id: int):
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            result = plugin_mark_spawned(
                db,
                int(claim_id),
                steam_id=str(body.get("steam_id") or ""),
                dino_id1=body.get("dino_id1"),
                dino_id2=body.get("dino_id2"),
                server_id=body.get("server_id"),
                map_name=body.get("map_name"),
            )
            return _ok(result)
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/event-hunt/a/claims/<int:claim_id>/complete", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    def event_hunt_a_complete(claim_id: int):
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            result = plugin_complete(
                db,
                int(claim_id),
                killer_steam_id=str(body.get("killer_steam_id") or body.get("steam_id") or ""),
                killer_team_id=body.get("killer_team_id"),
                idempotency_key=body.get("idempotency_key"),
            )
            return _ok(result)
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/event-hunt/a/claims/<int:claim_id>/fail", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    def event_hunt_a_fail(claim_id: int):
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            result = plugin_fail(
                db,
                int(claim_id),
                reason=str(body.get("reason") or "unknown"),
                actor_steam_id=body.get("steam_id") or body.get("actor_steam_id"),
                idempotency_key=body.get("idempotency_key"),
            )
            return _ok(result)
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    # ── Admin ────────────────────────────────────────────────────────────────

    @app.route("/api/admin/event-hunt/a/challenges", methods=["GET"])
    @admin_required
    def admin_event_hunt_a_challenges_list():
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            items = list_challenges(db, enabled_only=False)
            return _ok({"items": items})
        except Exception as exc:
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/admin/event-hunt/a/challenges", methods=["POST"])
    @admin_required
    def admin_event_hunt_a_challenges_create():
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            return _ok(admin_create_challenge(db, body))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/admin/event-hunt/a/challenges/<int:challenge_id>", methods=["PUT"])
    @admin_required
    def admin_event_hunt_a_challenges_update(challenge_id: int):
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            return _ok(admin_update_challenge(db, int(challenge_id), body))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/admin/event-hunt/a/challenges/<int:challenge_id>", methods=["DELETE"])
    @admin_required
    def admin_event_hunt_a_challenges_delete(challenge_id: int):
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            return _ok(admin_disable_challenge(db, int(challenge_id)))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/admin/event-hunt/a/weapon-presets", methods=["GET"])
    @admin_required
    def admin_event_hunt_weapon_presets_list():
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            return _ok({"items": list_weapon_presets(db)})
        except Exception as exc:
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/admin/event-hunt/a/weapon-presets", methods=["POST"])
    @admin_required
    def admin_event_hunt_weapon_presets_create():
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            return _ok(admin_create_weapon_preset(db, body))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route(
        "/api/admin/event-hunt/a/weapon-presets/<int:preset_id>", methods=["PUT"]
    )
    @admin_required
    def admin_event_hunt_weapon_presets_update(preset_id: int):
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            return _ok(admin_update_weapon_preset(db, int(preset_id), body))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route(
        "/api/admin/event-hunt/a/weapon-presets/<int:preset_id>", methods=["DELETE"]
    )
    @admin_required
    def admin_event_hunt_weapon_presets_delete(preset_id: int):
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            return _ok(admin_delete_weapon_preset(db, int(preset_id)))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/admin/event-hunt/a/claims", methods=["GET"])
    @admin_required
    def admin_event_hunt_a_claims():
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            tid = request.args.get("team_id")
            return _ok(admin_list_claims(
                db,
                team_id=int(tid) if tid else None,
                steam_id=request.args.get("steam_id") or None,
                status=request.args.get("status") or None,
                event_code=request.args.get("event_code") or None,
                page=int(request.args.get("page") or 1),
                page_size=int(request.args.get("page_size") or 50),
            ))
        except Exception as exc:
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/admin/event-hunt/a/claims/<int:claim_id>/void", methods=["POST"])
    @admin_required
    def admin_event_hunt_a_void(claim_id: int):
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = steam_id_from_session() or ""
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            return _ok(admin_void_claim(
                db,
                int(claim_id),
                admin_steam_id=sid,
                note=str(body.get("note") or ""),
            ))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/admin/event-hunt/audit", methods=["GET"])
    @admin_required
    def admin_event_hunt_audit():
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            tid = request.args.get("team_id")
            cid = request.args.get("challenge_id")
            pdid = request.args.get("public_dino_id")
            pmin = request.args.get("points_awarded_min")
            pmax = request.args.get("points_awarded_max")
            amin = request.args.get("amber_awarded_min")
            amax = request.args.get("amber_awarded_max")
            return _ok(admin_list_audit(
                db,
                team_id=int(tid) if tid else None,
                member_steam_id=request.args.get("member_steam_id") or None,
                challenge_id=int(cid) if cid else None,
                public_dino_id=int(pdid) if pdid else None,
                mode=request.args.get("mode") or None,
                event_type=request.args.get("event_type") or None,
                status=request.args.get("status") or None,
                reward_status=request.args.get("reward_status") or None,
                from_ts=request.args.get("from") or None,
                to_ts=request.args.get("to") or None,
                points_awarded_min=int(pmin) if pmin not in (None, "") else None,
                points_awarded_max=int(pmax) if pmax not in (None, "") else None,
                amber_awarded_min=int(amin) if amin not in (None, "") else None,
                amber_awarded_max=int(amax) if amax not in (None, "") else None,
                unpaid_only=request.args.get("unpaid_only") in ("1", "true", "yes"),
                page=int(request.args.get("page") or 1),
                page_size=int(request.args.get("page_size") or 50),
            ))
        except Exception as exc:
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/admin/event-hunt/claims/<int:claim_id>/grant-reward", methods=["POST"])
    @admin_required
    def admin_event_hunt_grant_claim(claim_id: int):
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = steam_id_from_session() or ""
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            return jsonify(admin_grant_reward(
                db,
                claim_id=int(claim_id),
                admin_steam_id=sid or str(body.get("admin_steam_id") or ""),
                reason=str(body.get("reason") or ""),
                grant_points=bool(body.get("grant_points", True)),
                grant_amber=bool(body.get("grant_amber", True)),
                points_amount=body.get("points_amount"),
                amber_amount=body.get("amber_amount"),
                override_double_pay=bool(body.get("override_double_pay")),
                idempotency_key=body.get("idempotency_key"),
            ))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/admin/event-hunt/instances/<int:instance_id>/grant-reward", methods=["POST"])
    @admin_required
    def admin_event_hunt_grant_instance(instance_id: int):
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = steam_id_from_session() or ""
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            return jsonify(admin_grant_reward_instance(
                db,
                instance_id=int(instance_id),
                admin_steam_id=sid or str(body.get("admin_steam_id") or ""),
                reason=str(body.get("reason") or ""),
                grant_points=bool(body.get("grant_points", True)),
                grant_amber=bool(body.get("grant_amber", True)),
                points_amount=body.get("points_amount"),
                amber_amount=body.get("amber_amount"),
                override_double_pay=bool(body.get("override_double_pay")),
                idempotency_key=body.get("idempotency_key"),
            ))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    # ── Mode B — player UI ───────────────────────────────────────────────────

    @app.route("/api/event-hunt/b/sessions/current", methods=["GET"])
    @login_required
    def event_hunt_b_current():
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = steam_id_from_session()
        db = _db()
        try:
            return _ok(mode_b_current_session(db, sid))
        except Exception as exc:
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/event-hunt/b/sessions/<int:session_id>/inscribe", methods=["POST"])
    @login_required
    def event_hunt_b_inscribe(session_id: int):
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = steam_id_from_session()
        if not sid:
            return _fail("Login necessário", 401)
        db = _db()
        try:
            return _ok(mode_b_inscribe(db, sid, int(session_id)))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/event-hunt/b/sessions/<int:session_id>/withdraw", methods=["POST"])
    @login_required
    def event_hunt_b_withdraw(session_id: int):
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = steam_id_from_session()
        if not sid:
            return _fail("Login necessário", 401)
        db = _db()
        try:
            return _ok(mode_b_withdraw(db, sid, int(session_id)))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/event-hunt/b/sessions/<int:session_id>/leaderboard", methods=["GET"])
    @login_required
    def event_hunt_b_leaderboard(session_id: int):
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            limit = int(request.args.get("limit") or 20)
            return _ok(mode_b_leaderboard(db, int(session_id), limit=limit))
        except Exception as exc:
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/event-hunt/b/team/summary", methods=["GET"])
    @login_required
    def event_hunt_b_team_summary():
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = steam_id_from_session()
        if not sid:
            return _fail("Login necessário", 401)
        db = _db()
        try:
            return _ok(mode_b_team_summary(db, sid))
        except Exception as exc:
            return _handle(exc)
        finally:
            db.close()

    # ── Mode B — plugin bridge ───────────────────────────────────────────────

    @app.route("/api/event-hunt/b/codes/<code>", methods=["GET"])
    @api_key_required(allow_admin_session=False)
    def event_hunt_b_plugin_code(code: str):
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            return jsonify(plugin_b_by_code(db, code))
        except Exception as exc:
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/event-hunt/b/instances/spawned", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    def event_hunt_b_plugin_spawned():
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            pdid = body.get("public_dino_id")
            return _ok(plugin_b_mark_spawned(
                db,
                public_dino_id=int(pdid) if pdid is not None else None,
                event_code=body.get("event_code"),
                admin_steam_id=str(body.get("admin_steam_id") or body.get("steam_id") or ""),
                dino_id1=body.get("dino_id1"),
                dino_id2=body.get("dino_id2"),
                server_id=body.get("server_id"),
                map_name=body.get("map_name"),
            ))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/event-hunt/b/instances/<int:instance_id>/kill", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    def event_hunt_b_plugin_kill(instance_id: int):
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            ktid = body.get("killer_team_id")
            return _ok(plugin_b_report_kill(
                db,
                int(instance_id),
                killer_steam_id=str(body.get("killer_steam_id") or ""),
                killer_team_id=int(ktid) if ktid is not None else None,
                valid=bool(body.get("valid", True)),
                fail_reason=body.get("fail_reason"),
                idempotency_key=body.get("idempotency_key"),
            ))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/event-hunt/b/instances/<int:instance_id>/expire", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    def event_hunt_b_plugin_expire(instance_id: int):
        if not event_hunt_enabled():
            return _fail("event_hunt_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            return _ok(plugin_b_expire(
                db,
                int(instance_id),
                warned_1min=bool(body.get("warned_1min")),
                actor_steam_id=body.get("actor_steam_id") or body.get("admin_steam_id"),
            ))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    # ── Mode B — admin UI ────────────────────────────────────────────────────

    @app.route("/api/admin/event-hunt/b/sessions", methods=["GET"])
    @admin_required
    def admin_event_hunt_b_sessions():
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            return _ok({"items": admin_list_sessions(db)})
        except Exception as exc:
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/admin/event-hunt/b/sessions", methods=["POST"])
    @admin_required
    def admin_event_hunt_b_sessions_create():
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            return _ok(admin_create_session(db, body))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/admin/event-hunt/b/sessions/<int:session_id>", methods=["PUT"])
    @admin_required
    def admin_event_hunt_b_sessions_update(session_id: int):
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            return _ok(admin_update_session(db, int(session_id), body))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/admin/event-hunt/b/sessions/<int:session_id>/transition", methods=["POST"])
    @admin_required
    def admin_event_hunt_b_sessions_transition(session_id: int):
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = steam_id_from_session() or ""
        body = request.get_json(silent=True) or {}
        target = body.get("status") or body.get("target_status") or ""
        db = _db()
        try:
            return _ok(admin_transition_session(
                db,
                int(session_id),
                target_status=str(target),
                admin_steam_id=sid,
            ))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/admin/event-hunt/b/sessions/<int:session_id>/dinos", methods=["GET"])
    @admin_required
    def admin_event_hunt_b_dinos_list(session_id: int):
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            return _ok({"items": admin_list_public_dinos(db, int(session_id))})
        except Exception as exc:
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/admin/event-hunt/b/sessions/<int:session_id>/dinos", methods=["POST"])
    @admin_required
    def admin_event_hunt_b_dinos_create(session_id: int):
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            return _ok(admin_create_public_dino(db, int(session_id), body))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/admin/event-hunt/b/dinos/<int:public_dino_id>", methods=["PUT"])
    @admin_required
    def admin_event_hunt_b_dinos_update(public_dino_id: int):
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            return _ok(admin_update_public_dino(db, int(public_dino_id), body))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/admin/event-hunt/b/sessions/<int:session_id>/inscriptions", methods=["GET"])
    @admin_required
    def admin_event_hunt_b_inscriptions(session_id: int):
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            return _ok({"items": admin_list_inscriptions(db, int(session_id))})
        except Exception as exc:
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/admin/event-hunt/b/instances", methods=["GET"])
    @admin_required
    def admin_event_hunt_b_instances():
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            sid = request.args.get("event_session_id") or request.args.get("session_id")
            return _ok(admin_list_instances(
                db,
                event_session_id=int(sid) if sid else None,
                status=request.args.get("status") or None,
                page=int(request.args.get("page") or 1),
                page_size=int(request.args.get("page_size") or 50),
            ))
        except Exception as exc:
            return _handle(exc)
        finally:
            db.close()

    @app.route("/api/admin/event-hunt/b/instances/<int:instance_id>/void", methods=["POST"])
    @admin_required
    def admin_event_hunt_b_void(instance_id: int):
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = steam_id_from_session() or ""
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            return _ok(admin_void_instance(
                db,
                int(instance_id),
                admin_steam_id=sid,
                note=str(body.get("note") or ""),
            ))
        except Exception as exc:
            db.rollback()
            return _handle(exc)
        finally:
            db.close()

    # silence unused imports for linters
    _ = (get_challenge, is_admin_steamid, limiter)

    log.info("event_hunt_routes: registered")
