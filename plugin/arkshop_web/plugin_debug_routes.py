"""Rotas Admin + ingest de debug dos plugins ARKLAND.

  POST /api/plugin-debug/ingest     — api_key (CustomDinoDeliver sem MySQL)
  GET  /api/admin/plugin-debug/events — admin_required
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from flask import Flask, jsonify, request

log = logging.getLogger("arkshop_web.plugin_debug_routes")


def register_plugin_debug_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    admin_required: Callable,
    api_key_required: Callable,
) -> None:
    from plugin_debug_service import ensure_plugin_debug_schema, ingest_event, list_events

    def _ok(data=None, **kw):
        return jsonify({"ok": True, "data": data, **kw})

    def _fail(msg: str, code: int = 400):
        return jsonify({"ok": False, "error": msg}), code

    @app.route("/api/plugin-debug/ingest", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    def plugin_debug_ingest():
        if not db_ready():
            return _fail("database_unavailable", 503)
        body = request.get_json(silent=True)
        if isinstance(body, list):
            if not body or len(body) > 100 or any(not isinstance(item, dict) for item in body):
                return _fail("invalid_batch")
            events = body
        elif isinstance(body, dict):
            events = [body]
        else:
            return _fail("invalid_json")
        session = session_factory()
        try:
            ensure_plugin_debug_schema(session.get_bind())
            ids = [ingest_event(session, item) for item in events]
            if any(eid is None for eid in ids):
                session.rollback()
                return _fail("invalid_plugin_or_message")
            session.commit()
            return _ok({"id": ids[0], "ids": ids, "count": len(ids)})
        except Exception as exc:
            session.rollback()
            log.warning("plugin_debug_ingest failed: %s", exc)
            return _fail("ingest_failed", 500)
        finally:
            session.close()

    @app.route("/api/admin/plugin-debug/events", methods=["GET"])
    @admin_required
    def admin_plugin_debug_events():
        if not db_ready():
            return _fail("database_unavailable", 503)
        session = session_factory()
        try:
            ensure_plugin_debug_schema(session.get_bind())
            events = list_events(
                session,
                plugin=request.args.get("plugin") or None,
                category=request.args.get("category") or None,
                level=request.args.get("level") or None,
                min_level=request.args.get("min_level") or None,
                steam_id=request.args.get("steam_id") or None,
                q=request.args.get("q") or None,
                limit=int(request.args.get("limit") or 50),
                offset=int(request.args.get("offset") or 0),
                since_id=(
                    int(request.args["since_id"])
                    if request.args.get("since_id")
                    else None
                ),
            )
            return _ok({"events": events, "count": len(events)})
        except Exception as exc:
            log.warning("admin_plugin_debug_events failed: %s", exc)
            return _fail("query_failed", 500)
        finally:
            session.close()
