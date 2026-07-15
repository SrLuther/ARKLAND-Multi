"""Rotas HTTP — Dino Lab (entrega admin de dinos customizados)."""
from __future__ import annotations

import logging
from typing import Any, Callable

from flask import Flask, jsonify, request

from custom_dino_service import (
    ITEM_TYPE,
    STAT_MAX,
    claim_custom_dino_orders,
    create_custom_dino_order,
    get_custom_dino_level_max,
    get_stale_entregando_minutes,
    get_custom_dino_order,
    is_custom_dino_enabled,
    list_custom_dino_orders_admin,
    list_species_admin,
    mark_custom_dino_delivered,
    mark_custom_dino_failed,
    release_custom_dino_orders,
    simulate_purchase,
    validate_payload,
)

log = logging.getLogger("arkshop_web.custom_dino_routes")


def _custom_dino_admin_required(admin_required: Callable, settings_fn: Callable[[], dict[str, Any]]):
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        wrapped = admin_required(fn)

        def _inner(*args: Any, **kwargs: Any):
            if not bool(settings_fn().get("custom_dino_enabled", False)):
                return jsonify({"ok": False, "error": "custom_dino_disabled", "message": "Dino Lab desabilitado."}), 503
            return wrapped(*args, **kwargs)

        _inner.__name__ = getattr(fn, "__name__", "custom_dino_route")
        return _inner

    return decorator


def register_custom_dino_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    admin_required: Callable,
    login_required: Callable,
    api_key_required: Callable,
    steam_id_from_session: Callable[[], str | None],
    load_settings: Callable[[], dict[str, Any]],
    is_valid_steamid64: Callable[[str], bool],
    audit_event: Callable[..., None],
    get_server_id: Callable[[], str],
    limiter: Any | None = None,
) -> None:
    _limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))
    _gate = _custom_dino_admin_required(admin_required, load_settings)

    @app.route("/api/admin/custom-dino/species", methods=["GET"])
    @_gate
    def custom_dino_admin_species():
        vanilla_only = request.args.get("vanilla_only", "").lower() in ("1", "true", "yes")
        return jsonify({
            "ok": True,
            "species": list_species_admin(vanilla_only=vanilla_only),
            "item_type": ITEM_TYPE,
        })

    @app.route("/api/admin/custom-dino/validate", methods=["POST"])
    @_gate
    def custom_dino_admin_validate():
        body = request.get_json(force=True, silent=True) or {}
        dry_run = bool(body.get("dry_run")) or str(request.args.get("dry_run") or "").lower() in (
            "1", "true", "yes",
        )
        if dry_run:
            if not db_ready():
                return jsonify({"ok": False, "error": "Banco não configurado"}), 503
            db = session_factory()
            try:
                result, err = simulate_purchase(body, db=db)
                if err:
                    return jsonify({"ok": False, "error": err}), 400
                return jsonify(result)
            finally:
                db.close()
        payload, err = validate_payload(body)
        if err:
            return jsonify({"ok": False, "error": err}), 400
        return jsonify({"ok": True, "payload": payload})

    @app.route("/api/admin/custom-dino/simulate", methods=["POST"])
    @_gate
    def custom_dino_admin_simulate():
        """Simula preço de encomenda (sem débito) a partir do formulário Dino Lab."""
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        db = session_factory()
        try:
            result, err = simulate_purchase(body, db=db)
            if err:
                return jsonify({"ok": False, "error": err}), 400
            return jsonify(result)
        finally:
            db.close()

    @app.route("/api/admin/custom-dino/deliver", methods=["POST"])
    @_gate
    @_limit("60 per minute")
    def custom_dino_admin_deliver():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        steam_id = str(body.get("steam_id") or "").strip()
        if not steam_id or not is_valid_steamid64(steam_id):
            return jsonify({"ok": False, "error": "steam_id inválido"}), 400
        payload, err = validate_payload(body)
        if err:
            return jsonify({"ok": False, "error": err}), 400
        admin_steam_id = str(steam_id_from_session() or "")
        db = session_factory()
        try:
            result = create_custom_dino_order(
                db,
                steam_id=steam_id,
                payload=payload or {},
                admin_steam_id=admin_steam_id,
                server_id=get_server_id(),
            )
            db.commit()
            audit_event(
                "custom_dino_deliver",
                severity="info",
                source="web",
                actor_type="admin",
                actor_steam_id=admin_steam_id,
                target_steam_id=steam_id,
                order_id=result["order_id"],
                item_type=ITEM_TYPE,
                status_after="PENDENTE",
                message="Pedido Dino Lab enfileirado",
                species_key=payload.get("species_key") if payload else None,
                colors=payload.get("colors") if payload else None,
                level=payload.get("level") if payload else None,
                ticket_id=payload.get("ticket_id") if payload else None,
                delivered_as=payload.get("deliver_as") if payload else None,
            )
            return jsonify({"ok": True, **result, "queued": True})
        except ValueError as exc:
            db.rollback()
            code = str(exc)
            msgs = {
                "custom_dino_disabled": "Dino Lab desabilitado.",
                "rate_limit_exceeded": "Limite de entregas por hora atingido.",
            }
            status = 429 if code == "rate_limit_exceeded" else 400
            return jsonify({"ok": False, "error": code, "message": msgs.get(code, code)}), status
        except Exception as exc:
            db.rollback()
            log.exception("custom_dino deliver: %s", exc)
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            db.close()

    @app.route("/api/admin/custom-dino/orders", methods=["GET"])
    @_gate
    def custom_dino_admin_orders():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        page = int(request.args.get("page") or 1)
        page_size = int(request.args.get("page_size") or 25)
        status = request.args.get("status")
        steam_id = request.args.get("steam_id")
        # Histórico unificado: inclui encomendas por padrão (badge origem).
        include_raw = (request.args.get("include_encomenda") or "1").strip().lower()
        exclude_player = include_raw in ("0", "false", "no", "off")
        db = session_factory()
        try:
            data = list_custom_dino_orders_admin(
                db,
                page=page,
                page_size=page_size,
                status=status,
                steam_id=steam_id,
                exclude_player_orders=exclude_player,
            )
            return jsonify({"ok": True, **data})
        finally:
            db.close()

    @app.route("/api/admin/custom-dino/orders/<order_id>", methods=["GET"])
    @_gate
    def custom_dino_admin_order_detail(order_id: str):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            row = get_custom_dino_order(db, order_id)
            if not row:
                return jsonify({"ok": False, "error": "Pedido não encontrado"}), 404
            return jsonify({"ok": True, "order": row})
        finally:
            db.close()

    @app.route("/api/pending/custom-dino/claim", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    @_limit("60 per minute")
    def custom_dino_pending_claim():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        if not is_custom_dino_enabled():
            return jsonify({"ok": True, "items": [], "orders": []})
        body = request.get_json(force=True, silent=True) or {}
        steam_id = str(body.get("steam_id") or "").strip()
        raw_ids = body.get("order_ids") or []
        if not steam_id or not is_valid_steamid64(steam_id):
            return jsonify({"ok": False, "error": "steam_id inválido"}), 400
        order_ids = [str(x).strip() for x in raw_ids if str(x).strip()] if isinstance(raw_ids, list) and raw_ids else None
        db = session_factory()
        try:
            claimed = claim_custom_dino_orders(db, steam_id, order_ids=order_ids)
            db.commit()
            return jsonify({"ok": True, "items": claimed, "orders": claimed})
        except Exception as exc:
            db.rollback()
            log.exception("custom_dino claim: %s", exc)
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            db.close()

    @app.route("/api/pending/custom-dino/release", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    @_limit("60 per minute")
    def custom_dino_pending_release():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        steam_id = str(body.get("steam_id") or "").strip()
        raw_ids = body.get("order_ids") or []
        if not steam_id or not isinstance(raw_ids, list) or not raw_ids:
            return jsonify({"ok": False, "error": "steam_id e order_ids são obrigatórios"}), 400
        db = session_factory()
        try:
            released = release_custom_dino_orders(db, steam_id, [str(x) for x in raw_ids])
            db.commit()
            return jsonify({"ok": True, "released": released})
        except Exception as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            db.close()

    @app.route("/api/pending/custom-dino/delivered", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    @_limit("30 per minute")
    def custom_dino_pending_delivered():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        steam_id = str(body.get("steam_id") or "").strip()
        raw_ids = body.get("order_ids") or []
        failures = body.get("failures") or []
        dino_records = body.get("dino_records") or []
        if not steam_id or not isinstance(raw_ids, list):
            return jsonify({"ok": False, "error": "steam_id e order_ids são obrigatórios"}), 400
        if not raw_ids and (not isinstance(failures, list) or not failures):
            return jsonify({"ok": False, "error": "steam_id e order_ids são obrigatórios"}), 400
        db = session_factory()
        delivered: list[str] = []
        try:
            from dino_lab_block_service import (
                audit_dino_lab_block_event,
                is_dino_lab_block_debug,
                new_trace_id,
                register_blocked_dino_ids,
            )

            debug = is_dino_lab_block_debug(load_settings())
            trace_id = new_trace_id() if debug else None

            records_by_order: dict[str, dict] = {}
            if isinstance(dino_records, list):
                for rec in dino_records:
                    if not isinstance(rec, dict):
                        continue
                    oid = str(rec.get("order_id") or "").strip()
                    if oid:
                        records_by_order[oid] = rec

            pending_ids = [str(x).strip() for x in raw_ids if str(x).strip()]
            for oid in pending_ids:
                rec = records_by_order.get(oid)
                if rec:
                    inserted = register_blocked_dino_ids(db, oid, steam_id, rec)
                    audit_dino_lab_block_event(
                        audit_event,
                        "dino_lab_id_registered",
                        source="plugin",
                        target_steam_id=steam_id,
                        order_id=oid,
                        trace_id=trace_id,
                        inserted=inserted,
                        dino_id1=rec.get("dino_id1"),
                        dino_id2=rec.get("dino_id2"),
                        ancestor_count=len(rec.get("ancestors") or []),
                    )

            delivered = mark_custom_dino_delivered(db, steam_id, pending_ids)
            for oid in delivered:
                rec = records_by_order.get(oid)
                id1 = int(rec.get("dino_id1", 0) or 0) if rec else 0
                id2 = int(rec.get("dino_id2", 0) or 0) if rec else 0
                if not rec or (id1 == 0 and id2 == 0):
                    audit_dino_lab_block_event(
                        audit_event,
                        "dino_lab_identity_capture_failed",
                        severity="error",
                        source="plugin",
                        target_steam_id=steam_id,
                        order_id=oid,
                        trace_id=trace_id,
                        message="ENTREGUE sem dino_records validos",
                    )
            if isinstance(failures, list):
                for f in failures:
                    if not isinstance(f, dict):
                        continue
                    oid = str(f.get("order_id") or "").strip()
                    err = str(f.get("error") or "delivery_failed")
                    if oid:
                        mark_custom_dino_failed(db, steam_id, oid, error=err)
                        audit_event(
                            "custom_dino_deliver_failed",
                            source="plugin",
                            actor_type="plugin",
                            target_steam_id=steam_id,
                            order_id=oid,
                            message=err,
                        )
            db.commit()
            for oid in delivered:
                audit_event(
                    "custom_dino_deliver",
                    source="plugin",
                    actor_type="plugin",
                    target_steam_id=steam_id,
                    order_id=oid,
                    status_after="ENTREGUE",
                    message="CustomDinoDeliver confirmou entrega",
                )
            return jsonify({"ok": True, "delivered": delivered})
        except Exception as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            db.close()

    @app.route("/api/admin/custom-dino/meta", methods=["GET"])
    @_gate
    def custom_dino_admin_meta():
        s = load_settings()
        return jsonify({
            "ok": True,
            "enabled": is_custom_dino_enabled(),
            "item_type": ITEM_TYPE,
            "color_regions": 6,
            "stat_max": STAT_MAX,
            "level_max": get_custom_dino_level_max(),
            "flags": {
                "custom_dino_enabled": bool(s.get("custom_dino_enabled")),
                "custom_dino_require_ticket": bool(s.get("custom_dino_require_ticket")),
                "custom_dino_ground_fallback": bool(s.get("custom_dino_ground_fallback", True)),
                "custom_dino_spawn_exact": bool(s.get("custom_dino_spawn_exact")),
                "custom_dino_level_max": get_custom_dino_level_max(),
                "custom_dino_stale_entregando_minutes": get_stale_entregando_minutes(),
                "dino_lab_block_debug": bool(s.get("dino_lab_block_debug")),
            },
        })

    @app.route("/api/admin/dino-lab-block/list", methods=["GET"])
    @_gate
    def dino_lab_block_admin_list():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        page = int(request.args.get("page") or 1)
        per_page = int(request.args.get("per_page") or 50)
        db = session_factory()
        try:
            from dino_lab_block_service import search_blocked_ids

            data = search_blocked_ids(
                db,
                q=request.args.get("q"),
                steam_id=request.args.get("steam_id"),
                order_id=request.args.get("order_id"),
                source=request.args.get("source"),
                role=request.args.get("role"),
                date_from=request.args.get("date_from"),
                date_to=request.args.get("date_to"),
                page=page,
                per_page=per_page,
            )
            return jsonify({"ok": True, **data})
        finally:
            db.close()

    @app.route("/api/admin/dino-lab-block/stats", methods=["GET"])
    @_gate
    def dino_lab_block_admin_stats():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            from dino_lab_block_service import get_dino_lab_block_stats_api

            stats = get_dino_lab_block_stats_api(db)
            return jsonify({"ok": True, "stats": stats})
        finally:
            db.close()

    @app.route("/api/admin/dino-lab-block/debug", methods=["GET"])
    @_gate
    def dino_lab_block_admin_debug():
        from dino_lab_block_service import get_dino_lab_block_debug_snapshot, is_dino_lab_block_debug

        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        limit = request.args.get("limit", 50, type=int)
        db = session_factory()
        try:
            snapshot = get_dino_lab_block_debug_snapshot(db, limit=limit)
            return jsonify({
                "ok": True,
                "debug_enabled": is_dino_lab_block_debug(load_settings()),
                **snapshot,
            })
        finally:
            db.close()

    @app.route("/api/dino-lab-block/check", methods=["POST"])
    @login_required
    @_limit("60 per minute")
    def dino_lab_block_player_check():
        """Verifica se um ID de criatura está bloqueado (match exato, sem ancestralidade)."""
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(silent=True) or {}
        db = session_factory()
        try:
            from dino_lab_block_service import check_dino_id_from_body

            result = check_dino_id_from_body(db, body)
            status = 400 if not result.get("ok") else 200
            return jsonify(result), status
        finally:
            db.close()
