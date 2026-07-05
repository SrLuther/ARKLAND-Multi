"""Rotas HTTP — Sorteio de Doações ARKLAND."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Callable

from flask import Flask, jsonify, request
from sqlalchemy.exc import IntegrityError, OperationalError

from lottery_service import (
    LOTTERY_REGULAMENTO_VERSION,
    accept_regulamento,
    buy_random_number,
    cancel_campaign,
    create_campaign_draft,
    get_campaign_results,
    get_history,
    get_number_grid,
    get_participants_public,
    get_player_me,
    get_public_current,
    list_campaigns_admin,
    lottery_meta,
    publish_campaign,
    regulamento_status,
    reserve_number,
    update_campaign,
)

log = logging.getLogger("arkshop_web.lottery_routes")


def _lottery_purchase_error_response(code: str, *, number: int | None = None) -> tuple[Any, int]:
    status = 409 if code in ("pool_exhausted", "number_unavailable", "random_limit_reached") else 400
    if code == "insufficient_balance":
        status = 402
    msgs = {
        "lottery_disabled": "Sorteio desabilitado.",
        "no_active_campaign": "Nenhuma campanha ativa.",
        "random_limit_reached": "Limite de compras aleatórias atingido.",
        "insufficient_balance": "Saldo insuficiente.",
        "pool_exhausted": "Não há números disponíveis nesta campanha.",
        "number_unavailable": (
            f"O número {number} já está reservado nesta campanha." if number is not None
            else "Este número já está reservado nesta campanha."
        ),
        "invalid_number": "Número deve estar entre 100 e 999.",
        "lottery_not_configured": "Sorteio não configurado no servidor.",
    }
    return jsonify({"ok": False, "error": code, "message": msgs.get(code, code)}), status


def _lottery_bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def lottery_regulamento_html() -> str:
    ver = LOTTERY_REGULAMENTO_VERSION.replace(".", "_")
    path = _lottery_bundle_dir() / "static" / f"lottery_regulamento_v{ver}.html"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return "<p>Regulamento do sorteio indisponível.</p>"


def register_lottery_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    login_required: Callable,
    admin_required: Callable,
    steam_id_from_session: Callable[[], str | None],
    limiter: Any | None = None,
) -> None:
    _limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))

    @app.route("/api/public/lottery/current", methods=["GET"])
    @app.route("/api/public/lottery/active", methods=["GET"])
    def lottery_public_current():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            return jsonify(get_public_current(db))
        finally:
            db.close()

    @app.route("/api/public/lottery/history", methods=["GET"])
    def lottery_public_history():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        page = int(request.args.get("page") or 1)
        db = session_factory()
        try:
            return jsonify(get_history(db, page=page))
        finally:
            db.close()

    @app.route("/api/public/lottery/campaign/<campaign_ref>", methods=["GET"])
    def lottery_public_campaign(campaign_ref: str):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            from lottery_service import _fetch_campaign_row, get_active_campaign, _campaign_public_dict

            if campaign_ref == "current":
                row = get_active_campaign(db)
            else:
                row = _fetch_campaign_row(db, int(campaign_ref))
            if not row:
                return jsonify({"ok": False, "error": "Campanha não encontrada"}), 404
            return jsonify({"ok": True, "campaign": _campaign_public_dict(row, db=db)})
        finally:
            db.close()

    @app.route("/api/public/lottery/campaign/<int:campaign_id>/participants", methods=["GET"])
    @_limit("60 per minute")
    def lottery_public_participants(campaign_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        page = int(request.args.get("page") or 1)
        page_size = int(request.args.get("page_size") or 50)
        search = request.args.get("search_number")
        search_num = int(search) if search and str(search).isdigit() else None
        db = session_factory()
        try:
            return jsonify(
                get_participants_public(
                    db, campaign_id, page=page, page_size=page_size, search_number=search_num,
                )
            )
        finally:
            db.close()

    @app.route("/api/public/lottery/campaign/<int:campaign_id>/number-grid", methods=["GET"])
    def lottery_public_grid(campaign_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        viewer = steam_id_from_session()
        db = session_factory()
        try:
            return jsonify(get_number_grid(db, campaign_id, viewer_steam_id=viewer))
        finally:
            db.close()

    @app.route("/api/public/lottery/campaign/<int:campaign_id>/results", methods=["GET"])
    def lottery_public_results(campaign_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            return jsonify(get_campaign_results(db, campaign_id))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404
        finally:
            db.close()

    @app.route("/api/public/lottery/regulamento", methods=["GET"])
    def lottery_public_regulamento():
        return jsonify({
            "ok": True,
            "version": LOTTERY_REGULAMENTO_VERSION,
            "title": "Regulamento do Sorteio de Doações ARKLAND",
            "updated_at": "2026-07-05",
            "html": lottery_regulamento_html(),
        })

    @app.route("/api/player/lottery/me", methods=["GET"])
    @login_required
    def lottery_player_me():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session())
        db = session_factory()
        try:
            return jsonify(get_player_me(db, steam_id))
        finally:
            db.close()

    @app.route("/api/player/lottery/buy-random", methods=["POST"])
    @app.route("/api/lottery/buy-random", methods=["POST"])
    @login_required
    @_limit("30 per minute")
    def lottery_buy_random():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session())
        db = session_factory()
        try:
            result = buy_random_number(db, steam_id)
            db.commit()
            return jsonify({"ok": True, **result})
        except ValueError as exc:
            db.rollback()
            return _lottery_purchase_error_response(str(exc))
        except IntegrityError:
            db.rollback()
            return _lottery_purchase_error_response("number_unavailable")
        except OperationalError as exc:
            db.rollback()
            log.exception("lottery buy-random db error: %s", exc)
            return jsonify({"ok": False, "error": "database_error", "message": "Erro de banco ao comprar número."}), 503
        except RuntimeError as exc:
            db.rollback()
            if str(exc) == "lottery_not_configured":
                return _lottery_purchase_error_response("lottery_not_configured")
            raise
        finally:
            db.close()

    @app.route("/api/player/lottery/reserve/<int:number>", methods=["POST"])
    @app.route("/api/lottery/reserve/<int:number>", methods=["POST"])
    @login_required
    @_limit("30 per minute")
    def lottery_reserve(number: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session())
        db = session_factory()
        try:
            result = reserve_number(db, steam_id, number)
            db.commit()
            return jsonify({"ok": True, **result})
        except ValueError as exc:
            db.rollback()
            return _lottery_purchase_error_response(str(exc), number=number)
        except IntegrityError:
            db.rollback()
            return _lottery_purchase_error_response("number_unavailable", number=number)
        except OperationalError as exc:
            db.rollback()
            log.exception("lottery reserve db error steam=%s num=%s: %s", steam_id, number, exc)
            return jsonify({"ok": False, "error": "database_error", "message": "Erro de banco ao reservar número."}), 503
        except RuntimeError as exc:
            db.rollback()
            if str(exc) == "lottery_not_configured":
                return _lottery_purchase_error_response("lottery_not_configured", number=number)
            raise
        finally:
            db.close()

    @app.route("/api/player/lottery/regulamento/status", methods=["GET"])
    @login_required
    def lottery_regulamento_status_route():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session())
        db = session_factory()
        try:
            return jsonify({"ok": True, **regulamento_status(db, steam_id)})
        finally:
            db.close()

    @app.route("/api/player/lottery/regulamento/accept", methods=["POST"])
    @login_required
    def lottery_regulamento_accept():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session())
        db = session_factory()
        try:
            result = accept_regulamento(db, steam_id)
            db.commit()
            return jsonify({"ok": True, **result})
        finally:
            db.close()

    @app.route("/api/admin/lottery/campaigns", methods=["GET"])
    @admin_required
    def lottery_admin_list():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            items = list_campaigns_admin(db)
            return jsonify({"ok": True, "campaigns": items, **lottery_meta()})
        finally:
            db.close()

    @app.route("/api/admin/lottery/campaigns", methods=["POST"])
    @admin_required
    def lottery_admin_create():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        db = session_factory()
        try:
            camp = create_campaign_draft(
                db, data=body, admin_steam_id=str(steam_id_from_session() or ""),
            )
            db.commit()
            return jsonify({"ok": True, "campaign": camp})
        finally:
            db.close()

    @app.route("/api/admin/lottery/campaigns/<int:campaign_id>", methods=["PATCH"])
    @admin_required
    def lottery_admin_patch(campaign_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        db = session_factory()
        try:
            camp = update_campaign(db, campaign_id, body)
            db.commit()
            return jsonify({"ok": True, "campaign": camp})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/admin/lottery/campaigns/<int:campaign_id>/publish", methods=["POST"])
    @admin_required
    def lottery_admin_publish(campaign_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            camp = publish_campaign(db, campaign_id)
            db.commit()
            return jsonify({"ok": True, "campaign": camp})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/admin/lottery/campaigns/<int:campaign_id>/cancel", methods=["POST"])
    @admin_required
    def lottery_admin_cancel(campaign_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        db = session_factory()
        try:
            camp = cancel_campaign(db, campaign_id, reason=str(body.get("reason") or ""))
            db.commit()
            return jsonify({"ok": True, "campaign": camp})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/admin/lottery/campaigns/<int:campaign_id>/participants", methods=["GET"])
    @admin_required
    def lottery_admin_participants(campaign_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        from sqlalchemy import text

        db = session_factory()
        try:
            rows = db.execute(
                text(
                    "SELECT steam_id, number_value, source, payment_id, amber_cost, assigned_at "
                    "FROM lottery_numbers WHERE campaign_id = :cid AND status = 'ACTIVE' "
                    "ORDER BY assigned_at DESC"
                ),
                {"cid": campaign_id},
            ).fetchall()
            items = [
                {
                    "steam_id": str(r.steam_id),
                    "number_value": int(r.number_value),
                    "source": str(r.source),
                    "payment_id": r.payment_id,
                    "amber_cost": int(r.amber_cost or 0),
                    "assigned_at": str(r.assigned_at),
                }
                for r in rows
            ]
            return jsonify({"ok": True, "participants": items})
        finally:
            db.close()

    @app.route("/api/admin/lottery/meta", methods=["GET"])
    @admin_required
    def lottery_admin_meta():
        return jsonify({"ok": True, **lottery_meta()})
