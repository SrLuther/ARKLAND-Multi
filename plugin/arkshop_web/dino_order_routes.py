"""Rotas HTTP — Encomenda de Dino (jogador + admin)."""
from __future__ import annotations

import logging
from typing import Any, Callable

from flask import Flask, jsonify, request

from dino_order_service import (
    approve_order,
    checkout,
    get_pricing_config,
    is_dino_order_enabled,
    list_admin_queue,
    list_gallery_species,
    list_player_orders,
    quote,
    reject_order,
)

log = logging.getLogger("arkshop_web.dino_order_routes")


def register_dino_order_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    login_required: Callable,
    admin_required: Callable,
    steam_id_from_session: Callable[[], str | None],
    guard_player_commerce: Callable[[str], Any],
    audit_event: Callable[..., None],
    get_server_id: Callable[[], str],
    limiter: Any | None = None,
) -> None:
    _limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))

    def _require_db():
        if not db_ready():
            return jsonify({"ok": False, "error": "db_not_configured"}), 503
        return None

    def _disabled():
        return jsonify({
            "ok": False,
            "error": "dino_order_disabled",
            "message": "Encomenda de Dino desabilitada.",
        }), 503

    @app.route("/api/player/dino-order/species", methods=["GET"])
    @login_required
    def dino_order_species():
        if not is_dino_order_enabled():
            return _disabled()
        err = _require_db()
        if err:
            return err
        db = session_factory()
        try:
            species = list_gallery_species(db)
            return jsonify({
                "ok": True,
                "species": species,
                "pricing": get_pricing_config(),
            })
        except Exception as exc:
            log.exception("dino_order species: %s", exc)
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            db.close()

    @app.route("/api/player/dino-order/quote", methods=["POST"])
    @login_required
    @_limit("30 per minute")
    def dino_order_quote():
        if not is_dino_order_enabled():
            return _disabled()
        err = _require_db()
        if err:
            return err
        body = request.get_json(force=True, silent=True) or {}
        db = session_factory()
        try:
            result = quote(body, db=db)
            return jsonify({"ok": True, **result})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            log.exception("dino_order quote: %s", exc)
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            db.close()

    @app.route("/api/player/dino-order/checkout", methods=["POST"])
    @login_required
    @_limit("5 per minute; 10 per hour")
    def dino_order_checkout():
        if not is_dino_order_enabled():
            return _disabled()
        steam_id = steam_id_from_session()
        if not steam_id:
            return jsonify({"ok": False, "error": "not_authenticated"}), 401
        if (guard_err := guard_player_commerce(str(steam_id))) is not None:
            return guard_err
        err = _require_db()
        if err:
            return err
        body = request.get_json(force=True, silent=True) or {}
        db = session_factory()
        try:
            result = checkout(db, str(steam_id), body, server_id=get_server_id())
            db.commit()
            audit_event(
                "dino_encomenda_created",
                actor_type="player",
                actor_steam_id=str(steam_id),
                target_steam_id=str(steam_id),
                order_id=result["order_id"],
                status_after=result["status"],
                amount=result["points_spent"],
                message=f"Encomenda de dino — {result['points_spent']} Âmbar",
            )
            return jsonify({"ok": True, **result})
        except ValueError as exc:
            db.rollback()
            code = str(exc)
            status = 402 if code == "insufficient_balance" else 400
            if code == "rate_limit_exceeded":
                status = 429
            msgs = {
                "dino_order_disabled": "Encomenda desabilitada.",
                "custom_dino_disabled": "Entrega custom desabilitada (custom_dino_enabled).",
                "insufficient_balance": "Saldo insuficiente.",
                "rate_limit_exceeded": f"Limite de {3} encomendas por 7 dias atingido.",
                "species_not_available": "Espécie indisponível para encomenda.",
                "species_not_vanilla": "Apenas espécies vanilla no MVP.",
            }
            return jsonify({
                "ok": False,
                "error": code,
                "message": msgs.get(code, code),
            }), status
        except Exception as exc:
            db.rollback()
            log.exception("dino_order checkout: %s", exc)
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            db.close()

    @app.route("/api/player/dino-order/orders", methods=["GET"])
    @login_required
    def dino_order_player_orders():
        steam_id = steam_id_from_session()
        if not steam_id:
            return jsonify({"ok": False, "error": "not_authenticated"}), 401
        err = _require_db()
        if err:
            return err
        page = int(request.args.get("page", 1) or 1)
        page_size = int(request.args.get("page_size", 20) or 20)
        db = session_factory()
        try:
            data = list_player_orders(db, str(steam_id), page=page, page_size=page_size)
            return jsonify({"ok": True, **data})
        finally:
            db.close()

    @app.route("/api/admin/dino-order/queue", methods=["GET"])
    @admin_required
    def dino_order_admin_queue():
        if not is_dino_order_enabled():
            return _disabled()
        err = _require_db()
        if err:
            return err
        page = int(request.args.get("page", 1) or 1)
        page_size = int(request.args.get("page_size", 25) or 25)
        status = request.args.get("status")
        db = session_factory()
        try:
            data = list_admin_queue(db, page=page, page_size=page_size, status=status)
            return jsonify({"ok": True, **data, "pricing": get_pricing_config()})
        finally:
            db.close()

    @app.route("/api/admin/dino-order/<order_id>/approve", methods=["POST"])
    @admin_required
    def dino_order_admin_approve(order_id: str):
        if not is_dino_order_enabled():
            return _disabled()
        err = _require_db()
        if err:
            return err
        admin_id = steam_id_from_session() or ""
        db = session_factory()
        try:
            result = approve_order(db, order_id, admin_steam_id=admin_id)
            db.commit()
            audit_event(
                "dino_encomenda_approved",
                actor_type="admin",
                actor_steam_id=admin_id,
                order_id=order_id,
                status_after="PENDENTE",
            )
            return jsonify({"ok": True, **result})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/admin/dino-order/<order_id>/reject", methods=["POST"])
    @admin_required
    def dino_order_admin_reject(order_id: str):
        if not is_dino_order_enabled():
            return _disabled()
        err = _require_db()
        if err:
            return err
        body = request.get_json(force=True, silent=True) or {}
        reason = str(body.get("reason") or "").strip()
        admin_id = steam_id_from_session() or ""
        db = session_factory()
        try:
            result = reject_order(db, order_id, admin_steam_id=admin_id, reason=reason)
            db.commit()
            audit_event(
                "dino_encomenda_rejected",
                actor_type="admin",
                actor_steam_id=admin_id,
                target_steam_id=result.get("order_id"),
                order_id=order_id,
                status_after="REJEITADO",
                amount=result.get("refunded"),
                message=reason or "Encomenda rejeitada",
            )
            return jsonify({"ok": True, **result})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()
