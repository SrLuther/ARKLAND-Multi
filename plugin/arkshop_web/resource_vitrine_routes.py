"""Rotas HTTP da Vitrine de Recursos (contrato: docs/VITRINE_RECURSOS_SPEC.md)."""
from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from flask import Flask, jsonify, request

import resource_vitrine_service as svc

log = logging.getLogger("arkshop.resource_vitrine.routes")

PREFIX = "/api/market/resources"


def register_resource_vitrine_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    admin_required: Callable,
    login_required: Callable,
    api_key_required: Callable,
    steam_id_from_session: Callable[[], str | None],
    audit_event: Callable[..., None] | None = None,
    limiter: Any | None = None,
) -> None:
    _limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))

    def _body() -> dict[str, Any]:
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}

    def _json_error(exc: svc.RVError):
        payload = {"ok": False, "error": exc.message, "code": exc.code}
        payload.update(exc.extra)
        return jsonify(payload), exc.status

    def _handler(fn: Callable[..., Any]) -> Callable[..., Any]:
        """Banco pronto + sessão por request + RVError→JSON; nunca vaza traceback."""

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            if not db_ready():
                return jsonify({"ok": False, "error": "Banco não configurado", "code": "db_unavailable"}), 503
            db = session_factory()
            try:
                return fn(db, *args, **kwargs)
            except svc.RVError as exc:
                try:
                    db.rollback()
                except Exception:
                    pass
                return _json_error(exc)
            except Exception as exc:
                try:
                    db.rollback()
                except Exception:
                    pass
                log.exception("vitrine recursos: erro inesperado em %s: %s", fn.__name__, type(exc).__name__)
                return jsonify({"ok": False, "error": "Erro interno", "code": "internal"}), 500
            finally:
                db.close()

        return wrapper

    def _me() -> str:
        return str(steam_id_from_session() or "")

    # ── Público / jogador ────────────────────────────────────────────────────

    @app.route(f"{PREFIX}/catalog", methods=["GET"])
    @_handler
    def rv_public_catalog(db):
        return jsonify(
            {
                "ok": True,
                "resources": svc.list_catalog(db),
                "max_types_per_player": svc.get_max_types(db),
            }
        )

    @app.route(f"{PREFIX}/listings", methods=["GET"])
    @_handler
    def rv_public_listings(db):
        limit = svc.as_int(request.args.get("limit") or 25, "limit", minimum=1, maximum=100)
        offset = svc.as_int(request.args.get("offset") or 0, "offset", minimum=0)
        rid_raw = request.args.get("resource_id")
        rid = svc.as_int(rid_raw, "resource_id", minimum=1) if rid_raw else None
        seller = (request.args.get("seller_steam_id") or "").strip() or None
        if seller:
            seller = svc.clean_steam_id(seller)
        items = svc.list_public_listings(
            db,
            seller_steam_id=seller,
            resource_id=rid,
            query=(request.args.get("q") or "").strip() or None,
            limit=limit,
            offset=offset,
        )
        return jsonify({"ok": True, "listings": items, "limit": limit, "offset": offset, "has_more": len(items) >= limit})

    @app.route(f"{PREFIX}/my", methods=["GET"])
    @login_required
    @_handler
    def rv_my(db):
        return jsonify({"ok": True, **svc.my_overview(db, _me())})

    @app.route(f"{PREFIX}/my/stock/<int:resource_id>/listing", methods=["PUT"])
    @login_required
    @_limit("60 per minute")
    @_handler
    def rv_my_set_listing(db, resource_id: int):
        item = svc.set_listing(db, _me(), resource_id, _body())
        return jsonify({"ok": True, "stock": item})

    @app.route(f"{PREFIX}/my/withdraw", methods=["POST"])
    @login_required
    @_limit("20 per minute")
    @_handler
    def rv_my_withdraw(db):
        body = _body()
        result = svc.withdraw_stock(
            db,
            _me(),
            resource_id=body.get("resource_id"),
            quantity=body.get("quantity"),
            request_id=body.get("request_id"),
        )
        return jsonify({"ok": True, **result})

    @app.route(f"{PREFIX}/listings/<int:stock_id>/purchase", methods=["POST"])
    @login_required
    @_limit("10 per minute; 60 per hour")
    @_handler
    def rv_purchase(db, stock_id: int):
        body = _body()
        result = svc.purchase_lots(
            db,
            stock_id,
            _me(),
            body.get("lots"),
            request_id=body.get("request_id"),
            expected_price=body.get("expected_price"),
        )
        return jsonify({"ok": True, **result})

    # ── Admin ────────────────────────────────────────────────────────────────

    @app.route(f"{PREFIX}/admin/catalog", methods=["GET"])
    @admin_required
    @_handler
    def rv_admin_catalog(db):
        return jsonify({"ok": True, **svc.admin_overview(db)})

    @app.route(f"{PREFIX}/admin/catalog", methods=["PUT"])
    @admin_required
    @_handler
    def rv_admin_catalog_upsert(db):
        item = svc.upsert_catalog_resource(db, _body(), admin_steam_id=_me())
        return jsonify({"ok": True, "resource": item})

    @app.route(f"{PREFIX}/admin/catalog/<int:resource_id>", methods=["DELETE"])
    @admin_required
    @_handler
    def rv_admin_catalog_disable(db, resource_id: int):
        return jsonify({"ok": True, **svc.disable_catalog_resource(db, resource_id, admin_steam_id=_me())})

    @app.route(f"{PREFIX}/admin/settings", methods=["PUT"])
    @admin_required
    @_handler
    def rv_admin_settings(db):
        value = svc.set_max_types(db, _body().get("max_types_per_player"))
        svc._audit(
            db,
            "MARKET_RESOURCE_ADMIN_SETTINGS",
            source="web",
            steam_id=_me(),
            metadata={"max_types_per_player": value},
        )
        return jsonify({"ok": True, "max_types_per_player": value})

    @app.route(f"{PREFIX}/admin/claims/expire-stale", methods=["POST"])
    @admin_required
    @_handler
    def rv_admin_expire(db):
        batch = svc.as_int(_body().get("batch_size") or 50, "batch_size", minimum=1, maximum=200)
        result = svc.expire_resource_claims(db, batch_size=batch)
        if audit_event:
            try:
                audit_event(
                    "MARKET_RESOURCE_CLAIMS_EXPIRE_MANUAL",
                    actor_type="admin",
                    actor_steam_id=_me(),
                    processed=result.get("processed"),
                )
            except Exception:
                pass
        return jsonify({"ok": True, **result})

    # ── Plugin (X-API-Key) ───────────────────────────────────────────────────

    @app.route(f"{PREFIX}/plugin/config", methods=["GET"])
    @api_key_required(allow_admin_session=False)
    @_limit("120 per minute")
    @_handler
    def rv_plugin_config(db):
        return jsonify({"ok": True, **svc.plugin_config(db)})

    @app.route(f"{PREFIX}/plugin/stock/<steam_id>", methods=["GET"])
    @api_key_required(allow_admin_session=False)
    @_limit("120 per minute")
    @_handler
    def rv_plugin_stock(db, steam_id: str):
        return jsonify({"ok": True, **svc.plugin_stock_summary(db, steam_id)})

    @app.route(f"{PREFIX}/plugin/upload", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    @_limit("60 per minute")
    @_handler
    def rv_plugin_upload(db):
        return jsonify({"ok": True, **svc.process_upload(db, _body())})

    @app.route(f"{PREFIX}/plugin/upload/<upload_id>", methods=["GET"])
    @api_key_required(allow_admin_session=False)
    @_limit("120 per minute")
    @_handler
    def rv_plugin_upload_status(db, upload_id: str):
        return jsonify({"ok": True, **svc.get_upload_status(db, upload_id)})

    @app.route(f"{PREFIX}/plugin/upload/cancel", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    @_limit("60 per minute")
    @_handler
    def rv_plugin_upload_cancel(db):
        return jsonify({"ok": True, **svc.cancel_upload(db, _body())})

    @app.route(f"{PREFIX}/plugin/pending/<steam_id>", methods=["GET"])
    @api_key_required(allow_admin_session=False)
    @_limit("120 per minute")
    @_handler
    def rv_plugin_pending(db, steam_id: str):
        return jsonify({"ok": True, "claims": svc.get_pending_claims(db, steam_id)})

    @app.route(f"{PREFIX}/plugin/claims/claim", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    @_limit("120 per minute")
    @_handler
    def rv_plugin_claim(db):
        body = _body()
        return jsonify({"ok": True, "claimed": svc.claim_deliveries(db, body.get("steam_id"), body.get("claim_ids"))})

    @app.route(f"{PREFIX}/plugin/claims/release", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    @_limit("120 per minute")
    @_handler
    def rv_plugin_release(db):
        body = _body()
        return jsonify({"ok": True, "released": svc.release_claims(db, body.get("steam_id"), body.get("claim_ids"))})

    @app.route(f"{PREFIX}/plugin/claims/delivered", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    @_limit("120 per minute")
    @_handler
    def rv_plugin_delivered(db):
        body = _body()
        return jsonify({"ok": True, **svc.mark_claim_delivered(db, body.get("claim_id"), body.get("steam_id"))})
