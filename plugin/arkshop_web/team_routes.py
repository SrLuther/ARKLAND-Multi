"""Rotas do Modo Equipe ARKLAND.

Registrar via register_team_routes(app, ...) no app.py.

Player (login_required):
  GET  /api/teams/status
  GET  /api/teams/public
  GET  /api/teams/my
  POST /api/teams/create
  POST /api/teams/rename
  POST /api/teams/invite
  POST /api/teams/invite/accept
  POST /api/teams/invite/decline
  POST /api/teams/join/request
  POST /api/teams/join/approve
  POST /api/teams/join/reject
  POST /api/teams/leave
  POST /api/teams/kick
  GET  /api/teams/members
  POST /api/teams/roles/assign
  POST /api/teams/roles/remove
  POST /api/teams/transfer
  POST /api/teams/recruitment
  POST /api/teams/settings
  POST /api/teams/mural
  POST /api/teams/bank/donate
  GET  /api/teams/bank
  GET  /api/teams/bank/ledger
  POST /api/teams/bank/commit-resource   (Owner/Tesoureiro: armazém → marco)
  GET  /api/teams/milestone
  POST /api/teams/milestone/complete
  GET  /api/teams/split
  POST /api/teams/split
  POST /api/teams/split/optin
  POST /api/teams/split/optout
  POST /api/teams/split/disable
  POST /api/teams/lottery/confirm
  GET  /api/teams/lottery
  GET  /api/teams/rankings/teams
  GET  /api/teams/rankings/players
  GET  /api/teams/<id>

Admin:
  GET  /api/admin/teams
  POST /api/admin/teams/kick
  POST /api/admin/teams/transfer
  POST /api/admin/teams/suspend
  POST /api/admin/teams/max-members
  GET  /api/admin/teams/warehouse-catalog
  GET  /api/admin/teams/milestones
  POST /api/admin/teams/milestones
  POST /api/admin/teams/milestones/publish
  DELETE /api/admin/teams/milestones/<index>

Plugin (api_key):
  POST /api/teams/bank/deposit-resource   (/marco bridge → armazém; só catálogo)
  GET  /api/teams/plugin/membership/<sid> (/marco membership check; api_key)
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from flask import Flask, jsonify, request

log = logging.getLogger("arkshop_web.team_routes")


def register_team_routes(
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
    if app.view_functions.get("teams_my") is not None:
        log.info("team_routes: already registered — skip")
        return

    from team_service import (
        accept_invite,
        approve_join,
        assign_role,
        commit_warehouse_to_milestone,
        create_or_update_team_split,
        create_team,
        decline_invite,
        default_milestone_resource_suggestions,
        delete_milestone,
        deposit_resource,
        disable_team_split,
        donate_amber,
        get_bank,
        get_bank_ledger,
        get_current_milestone_for_team,
        get_team,
        invite_member,
        kick_member,
        leave_team,
        list_members,
        list_milestones,
        list_public_teams,
        confirm_team_lottery,
        get_team_lottery_status,
        milestone_progress_view,
        my_player_rank,
        my_team_or_invites,
        publish_milestone,
        ranking_players,
        ranking_teams,
        reject_join,
        remove_role,
        rename_team,
        request_join,
        set_recruitment_open,
        staff_list_teams,
        staff_set_team_max_members,
        suspend_team,
        team_public_view,
        team_split_optin,
        team_split_optout,
        teams_enabled,
        transfer_ownership,
        try_complete_milestone,
        update_mural,
        update_team_settings,
        upsert_milestone,
        warehouse_catalog,
        get_active_team_split,
        get_active_membership,
    )

    def _db():
        return session_factory()

    def _fail(msg: str, code: int = 400):
        return jsonify({"ok": False, "error": msg}), code

    def _ok(data: Any = None, **kw):
        payload: dict[str, Any] = {"ok": True}
        if data is not None:
            payload["data"] = data
        payload.update(kw)
        return jsonify(payload)

    def _sid() -> str | None:
        return steam_id_from_session()

    def _gate_enabled():
        if not teams_enabled():
            return _fail("Modo Equipe desativado. Ative teams_enabled nas configurações.", 403)
        return None

    # ── Public / status ──────────────────────────────────────

    @app.route("/api/teams/status", methods=["GET"])
    def teams_status():
        from team_service import (
            DEFAULT_AMBER_BONUS_CAP,
            DEFAULT_AMBER_BONUS_PP,
            FOUNDING_FEE_AMBER,
            LOTTERY_SHORTFALL_REFUND_AMBER,
            MAX_SPECIAL_ROLES,
            default_max_members,
            founding_fee_amber,
        )
        return _ok({
            "enabled": teams_enabled(),
            "max_members_default": default_max_members(),
            "founding_fee": founding_fee_amber(),
            "founding_fee_default": FOUNDING_FEE_AMBER,
            "founding_first_free": True,
            "max_special_roles": MAX_SPECIAL_ROLES,
            "amber_bonus_mode": "additive",  # Q7: stacks additively; unlocked via marcos
            "amber_bonus_pp_default": DEFAULT_AMBER_BONUS_PP,
            "amber_bonus_cap_default": DEFAULT_AMBER_BONUS_CAP,
            "lottery_shortfall_refund_default": LOTTERY_SHORTFALL_REFUND_AMBER,
            "roles": {
                "OWNER": "Proprietário",
                "GUARDIAN": "Guardião",
                "HERALD": "Arauto",
                "TREASURER": "Guardião do Cofre",
                "ENGINEER": "Engenheiro de Marcos",
                "AMBASSADOR": "Embaixador",
                "ARCHIVIST": "Arquivista",
            },
            "warehouse_catalog": warehouse_catalog(),
        })

    @app.route("/api/teams/public", methods=["GET"])
    def teams_public_list():
        """Global directory of ACTIVE teams (authenticated or public)."""
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            q = (request.args.get("q") or "").strip()
            limit = int(request.args.get("limit") or 100)
            offset = int(request.args.get("offset") or 0)
            data = list_public_teams(db, q=q, limit=limit, offset=offset)
            sid = _sid()
            viewer_has_team = False
            if sid:
                viewer_has_team = get_active_membership(db, sid) is not None
            data["viewer_has_team"] = viewer_has_team
            data["viewer_steam_id"] = sid
            return _ok(data)
        except Exception as exc:
            log.warning("teams/public: %s", exc)
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/teams/rankings/teams", methods=["GET"])
    def teams_ranking_teams():
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            limit = int(request.args.get("limit") or 50)
            return _ok(ranking_teams(db, limit=limit))
        except Exception as exc:
            log.warning("teams ranking: %s", exc)
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/teams/rankings/players", methods=["GET"])
    def teams_ranking_players():
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            limit = int(request.args.get("limit") or 50)
            return _ok(ranking_players(db, limit=limit))
        except Exception as exc:
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/teams/<int:team_id>", methods=["GET"])
    def teams_public_get(team_id: int):
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            sid = _sid()
            return _ok(team_public_view(db, team_id, viewer_steam_id=sid))
        except ValueError as exc:
            return _fail(str(exc), 404)
        except Exception as exc:
            return _fail(str(exc), 500)
        finally:
            db.close()

    # ── Player ───────────────────────────────────────────────

    @app.route("/api/teams/my", methods=["GET"])
    @login_required
    def teams_my():
        blocked = _gate_enabled()
        if blocked:
            # Still return status so UI can show disabled state
            return _ok({"team": None, "enabled": False, "pending": []})
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        if not sid:
            return _fail("Não autenticado", 401)
        db = _db()
        try:
            return _ok(my_team_or_invites(db, sid))
        except Exception as exc:
            log.warning("teams/my: %s", exc)
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/teams/create", methods=["POST"])
    @login_required
    def teams_create():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        if not sid:
            return _fail("Não autenticado", 401)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            data = create_team(
                db,
                steam_id=sid,
                name=str(body.get("name") or ""),
                tag=str(body.get("tag") or ""),
                display_name=str(body.get("display_name") or ""),
                represents_tribe=bool(body.get("represents_tribe")),
            )
            return _ok(data)
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        except Exception as exc:
            log.warning("teams/create: %s", exc)
            return _fail(str(exc), 500)
        finally:
            db.close()

    def _team_id_from_body_or_membership(db, sid: str, body: dict) -> int:
        if body.get("team_id") is not None:
            return int(body["team_id"])
        mem = get_active_membership(db, sid)
        if not mem:
            raise ValueError("Não está em nenhuma equipe.")
        return int(mem["team_id"])

    @app.route("/api/teams/rename", methods=["POST"])
    @login_required
    def teams_rename():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            tid = _team_id_from_body_or_membership(db, sid, body)
            return _ok(rename_team(db, team_id=tid, actor_steam_id=sid, name=str(body.get("name") or "")))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/invite", methods=["POST"])
    @login_required
    def teams_invite():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            tid = _team_id_from_body_or_membership(db, sid, body)
            return _ok(invite_member(
                db,
                team_id=tid,
                actor_steam_id=sid,
                target_steam_id=str(body.get("steam_id") or ""),
                display_name=str(body.get("display_name") or ""),
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/invite/accept", methods=["POST"])
    @login_required
    def teams_invite_accept():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            tid = body.get("team_id")
            return _ok(accept_invite(
                db,
                steam_id=sid,
                invite_code=body.get("invite_code"),
                team_id=int(tid) if tid is not None else None,
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/invite/decline", methods=["POST"])
    @login_required
    def teams_invite_decline():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            return _ok(decline_invite(db, steam_id=sid, team_id=int(body.get("team_id"))))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/join/request", methods=["POST"])
    @login_required
    def teams_join_request():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            return _ok(request_join(
                db,
                team_id=int(body.get("team_id")),
                steam_id=sid,
                display_name=str(body.get("display_name") or ""),
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/join/approve", methods=["POST"])
    @login_required
    def teams_join_approve():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            tid = _team_id_from_body_or_membership(db, sid, body)
            return _ok(approve_join(
                db, team_id=tid, actor_steam_id=sid,
                target_steam_id=str(body.get("steam_id") or ""),
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/join/reject", methods=["POST"])
    @login_required
    def teams_join_reject():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            tid = _team_id_from_body_or_membership(db, sid, body)
            return _ok(reject_join(
                db, team_id=tid, actor_steam_id=sid,
                target_steam_id=str(body.get("steam_id") or ""),
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/leave", methods=["POST"])
    @login_required
    def teams_leave():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        db = _db()
        try:
            return _ok(leave_team(db, steam_id=sid))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/kick", methods=["POST"])
    @login_required
    def teams_kick():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            tid = _team_id_from_body_or_membership(db, sid, body)
            return _ok(kick_member(
                db, team_id=tid, actor_steam_id=sid,
                target_steam_id=str(body.get("steam_id") or ""),
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/members", methods=["GET"])
    @login_required
    def teams_members():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        db = _db()
        try:
            mem = get_active_membership(db, sid)
            if not mem:
                return _fail("Não está em nenhuma equipe.")
            return _ok(list_members(db, int(mem["team_id"])))
        finally:
            db.close()

    @app.route("/api/teams/roles/assign", methods=["POST"])
    @login_required
    def teams_roles_assign():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            tid = _team_id_from_body_or_membership(db, sid, body)
            return _ok(assign_role(
                db, team_id=tid, actor_steam_id=sid,
                target_steam_id=str(body.get("steam_id") or ""),
                role_key=str(body.get("role") or body.get("role_key") or ""),
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/roles/remove", methods=["POST"])
    @login_required
    def teams_roles_remove():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            tid = _team_id_from_body_or_membership(db, sid, body)
            return _ok(remove_role(
                db, team_id=tid, actor_steam_id=sid,
                target_steam_id=str(body.get("steam_id") or ""),
                role_key=str(body.get("role") or body.get("role_key") or ""),
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/transfer", methods=["POST"])
    @login_required
    def teams_transfer():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            tid = _team_id_from_body_or_membership(db, sid, body)
            return _ok(transfer_ownership(
                db, team_id=tid, actor_steam_id=sid,
                new_owner_steam_id=str(body.get("steam_id") or body.get("new_owner") or ""),
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/recruitment", methods=["POST"])
    @login_required
    def teams_recruitment():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            tid = _team_id_from_body_or_membership(db, sid, body)
            open_ = body.get("open")
            if open_ is None:
                open_ = body.get("recruitment_open")
            return _ok(set_recruitment_open(
                db, team_id=tid, actor_steam_id=sid, open_=bool(open_),
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/settings", methods=["POST"])
    @login_required
    def teams_settings():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            tid = _team_id_from_body_or_membership(db, sid, body)
            hours = body.get("auto_kick_inactive_hours")
            return _ok(update_team_settings(
                db,
                team_id=tid,
                actor_steam_id=sid,
                auto_kick_inactive=body.get("auto_kick_inactive"),
                auto_kick_inactive_hours=int(hours) if hours is not None else None,
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/mural", methods=["POST"])
    @login_required
    def teams_mural():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            tid = _team_id_from_body_or_membership(db, sid, body)
            return _ok(update_mural(
                db,
                team_id=tid,
                actor_steam_id=sid,
                mural_text=str(body.get("mural_text") or body.get("regulamento") or ""),
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/bank", methods=["GET"])
    @login_required
    def teams_bank_get():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        db = _db()
        try:
            mem = get_active_membership(db, sid)
            if not mem:
                return _fail("Não está em nenhuma equipe.")
            return _ok(get_bank(db, int(mem["team_id"])))
        finally:
            db.close()

    @app.route("/api/teams/bank/ledger", methods=["GET"])
    @login_required
    def teams_bank_ledger():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        db = _db()
        try:
            mem = get_active_membership(db, sid)
            if not mem:
                return _fail("Não está em nenhuma equipe.")
            # Soft check: members can view if bank_mode transparency; MVP allows all ACTIVE
            return _ok(get_bank_ledger(db, int(mem["team_id"])))
        finally:
            db.close()

    @app.route("/api/teams/bank/donate", methods=["POST"])
    @login_required
    def teams_bank_donate():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            mem = get_active_membership(db, sid)
            if not mem:
                return _fail("Não está em nenhuma equipe.")
            return _ok(donate_amber(
                db,
                team_id=int(mem["team_id"]),
                steam_id=sid,
                amount=int(body.get("amount") or 0),
                idempotency_key=body.get("idempotency_key"),
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        except Exception as exc:
            if "insufficient" in str(exc).lower():
                return _fail("Saldo de Âmbares insuficiente.")
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/teams/bank/deposit-resource", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    def teams_bank_deposit_resource():
        """Plugin bridge for /marco→/confirmar — credits WAREHOUSE (catalog only).

        C++: scan on /marco (preview + no-refund warning, TTL 60s), consume+POST
        only after /confirmar. See docs/PROJETO_MODO_EQUIPE.md §5.5 and ShopTeams.
        """
        if not teams_enabled():
            return _fail("teams_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            sid = str(body.get("steam_id") or "")
            mem = get_active_membership(db, sid)
            if not mem:
                return _fail("Jogador sem equipe ACTIVE")
            return _ok(deposit_resource(
                db,
                team_id=int(body.get("team_id") or mem["team_id"]),
                steam_id=sid,
                resource_key=str(body.get("resource_key") or body.get("blueprint") or ""),
                amount=int(body.get("amount") or 0),
                idempotency_key=body.get("idempotency_key"),
                note=str(body.get("note") or "/marco"),
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        except Exception as exc:
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/teams/plugin/membership/<steam_id>", methods=["GET"])
    @api_key_required(allow_admin_session=False)
    def teams_plugin_membership(steam_id: str):
        """Plugin bridge: ACTIVE team membership check for /marco."""
        if not teams_enabled():
            return _fail("teams_enabled=false", 403)
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            sid = str(steam_id or "").strip()
            mem = get_active_membership(db, sid) if sid else None
            if not mem:
                return _ok({"active": False, "steam_id": sid, "team_id": None})
            return _ok({
                "active": True,
                "steam_id": sid,
                "team_id": int(mem["team_id"]),
                "role": mem.get("role"),
            })
        except Exception as exc:
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/teams/bank/commit-resource", methods=["POST"])
    @login_required
    def teams_bank_commit_resource():
        """Owner/Treasurer: apply warehouse stock toward current milestone."""
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            mem = get_active_membership(db, sid)
            if not mem:
                return _fail("Não está em nenhuma equipe.")
            return _ok(commit_warehouse_to_milestone(
                db,
                team_id=int(mem["team_id"]),
                actor_steam_id=sid,
                resource_key=str(body.get("resource_key") or body.get("key") or ""),
                amount=int(body.get("amount") or 0),
                idempotency_key=body.get("idempotency_key"),
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        except Exception as exc:
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/teams/milestone", methods=["GET"])
    @login_required
    def teams_milestone_get():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        db = _db()
        try:
            mem = get_active_membership(db, sid)
            if not mem:
                return _fail("Não está em nenhuma equipe.")
            team = get_team(db, int(mem["team_id"]))
            ms = get_current_milestone_for_team(db, team) if team else None
            if not ms:
                return _ok({"milestone": None, "waiting_staff": True})
            return _ok(milestone_progress_view(db, team, ms))
        finally:
            db.close()

    @app.route("/api/teams/milestone/complete", methods=["POST"])
    @login_required
    def teams_milestone_complete():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        db = _db()
        try:
            mem = get_active_membership(db, sid)
            if not mem:
                return _fail("Não está em nenhuma equipe.")
            return _ok(try_complete_milestone(db, team_id=int(mem["team_id"]), actor_steam_id=sid))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/split", methods=["GET"])
    @login_required
    def teams_split_get():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        db = _db()
        try:
            mem = get_active_membership(db, sid)
            if not mem:
                return _fail("Não está em nenhuma equipe.")
            return _ok(get_active_team_split(db, int(mem["team_id"])))
        finally:
            db.close()

    @app.route("/api/teams/split", methods=["POST"])
    @login_required
    def teams_split_post():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            mem = get_active_membership(db, sid)
            if not mem:
                return _fail("Não está em nenhuma equipe.")
            return _ok(create_or_update_team_split(
                db,
                team_id=int(mem["team_id"]),
                actor_steam_id=sid,
                sender_pct=int(body.get("sender_pct") or 60),
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/split/optin", methods=["POST"])
    @login_required
    def teams_split_optin():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        db = _db()
        try:
            mem = get_active_membership(db, sid)
            if not mem:
                return _fail("Não está em nenhuma equipe.")
            return _ok(team_split_optin(db, team_id=int(mem["team_id"]), steam_id=sid))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/split/optout", methods=["POST"])
    @login_required
    def teams_split_optout():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        db = _db()
        try:
            mem = get_active_membership(db, sid)
            if not mem:
                return _fail("Não está em nenhuma equipe.")
            return _ok(team_split_optout(db, team_id=int(mem["team_id"]), steam_id=sid))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/split/disable", methods=["POST"])
    @login_required
    def teams_split_disable():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        db = _db()
        try:
            mem = get_active_membership(db, sid)
            if not mem:
                return _fail("Não está em nenhuma equipe.")
            return _ok(disable_team_split(db, team_id=int(mem["team_id"]), actor_steam_id=sid))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/lottery/confirm", methods=["POST"])
    @login_required
    def teams_lottery_confirm():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            mem = get_active_membership(db, sid)
            if not mem:
                return _fail("Não está em nenhuma equipe.")
            raw_cid = body.get("campaign_id")
            campaign_id = int(raw_cid) if raw_cid not in (None, "", 0, "0") else None
            return _ok(confirm_team_lottery(
                db,
                team_id=int(mem["team_id"]),
                actor_steam_id=sid,
                campaign_id=campaign_id,
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/lottery", methods=["GET"])
    @login_required
    def teams_lottery_status():
        blocked = _gate_enabled()
        if blocked:
            return blocked
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        db = _db()
        try:
            mem = get_active_membership(db, sid)
            if not mem:
                return _fail("Não está em nenhuma equipe.")
            return _ok(get_team_lottery_status(db, int(mem["team_id"])))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/teams/me/xp", methods=["GET"])
    @login_required
    def teams_me_xp():
        if not db_ready():
            return _fail("DB não disponível", 503)
        sid = _sid()
        db = _db()
        try:
            return _ok(my_player_rank(db, sid))
        finally:
            db.close()

    # ── Admin ────────────────────────────────────────────────

    @app.route("/api/admin/teams", methods=["GET"])
    @admin_required
    def admin_teams_list():
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            return _ok(staff_list_teams(
                db,
                q=str(request.args.get("q") or ""),
                limit=int(request.args.get("limit") or 100),
            ))
        finally:
            db.close()

    @app.route("/api/admin/teams/kick", methods=["POST"])
    @admin_required
    def admin_teams_kick():
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        sid = _sid() or "admin"
        db = _db()
        try:
            return _ok(kick_member(
                db,
                team_id=int(body.get("team_id")),
                actor_steam_id=sid,
                target_steam_id=str(body.get("steam_id") or ""),
                staff=True,
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/admin/teams/transfer", methods=["POST"])
    @admin_required
    def admin_teams_transfer():
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        sid = _sid() or "admin"
        db = _db()
        try:
            return _ok(transfer_ownership(
                db,
                team_id=int(body.get("team_id")),
                actor_steam_id=sid,
                new_owner_steam_id=str(body.get("steam_id") or body.get("new_owner") or ""),
                staff=True,
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/admin/teams/suspend", methods=["POST"])
    @admin_required
    def admin_teams_suspend():
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            return _ok(suspend_team(
                db,
                team_id=int(body.get("team_id")),
                suspend=bool(body.get("suspend", True)),
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/admin/teams/max-members", methods=["POST"])
    @admin_required
    def admin_teams_max_members():
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            return _ok(staff_set_team_max_members(
                db,
                team_id=int(body.get("team_id")),
                max_members=int(body.get("max_members") or 10),
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/admin/teams/warehouse-catalog", methods=["GET"])
    @admin_required
    def admin_teams_warehouse_catalog():
        return _ok({
            "catalog": warehouse_catalog(),
            "defaults": default_milestone_resource_suggestions(),
        })

    @app.route("/api/admin/teams/milestones", methods=["GET"])
    @admin_required
    def admin_teams_milestones_list():
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            return _ok({
                "milestones": list_milestones(db, include_draft=True),
                "warehouse_catalog": warehouse_catalog(),
                "defaults": default_milestone_resource_suggestions(),
            })
        finally:
            db.close()

    @app.route("/api/admin/teams/milestones", methods=["POST"])
    @admin_required
    def admin_teams_milestones_upsert():
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            return _ok(upsert_milestone(
                db,
                milestone_index=int(body.get("milestone_index") or body.get("index") or 0),
                title=str(body.get("title") or ""),
                description=str(body.get("description") or ""),
                amber_required=int(body.get("amber_required") or 0),
                xp_required=int(body.get("xp_required") or 0),
                resources=body.get("resources") or [],
                max_members_unlock=body.get("max_members_unlock"),
                amber_bonus_pp=(
                    int(body["amber_bonus_pp"])
                    if body.get("amber_bonus_pp") is not None and body.get("amber_bonus_pp") != ""
                    else None
                ),
                status=str(body.get("status") or "DRAFT"),
            ))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/admin/teams/milestones/publish", methods=["POST"])
    @admin_required
    def admin_teams_milestones_publish():
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            idx = int(body.get("milestone_index") or body.get("index") or 0)
            return _ok(publish_milestone(db, idx))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/admin/teams/milestones/<int:milestone_index>", methods=["DELETE"])
    @admin_required
    def admin_teams_milestones_delete(milestone_index: int):
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            return _ok(delete_milestone(db, milestone_index))
        except (ValueError, PermissionError) as exc:
            return _fail(str(exc))
        finally:
            db.close()

    log.info("team_routes: registered")
