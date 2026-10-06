"""Busca de blueprints — só admin.

  POST   /api/admin/blueprint-index/refresh
  GET    /api/admin/blueprint-index
  POST   /api/admin/blueprint-index
  PATCH  /api/admin/blueprint-index
  DELETE /api/admin/blueprint-index
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from flask import Flask, jsonify, request

log = logging.getLogger("arkshop.blueprint_index.routes")


def register_blueprint_index_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    admin_required: Callable,
) -> None:
    from blueprint_index_service import (
        BlueprintIndexError,
        add_manual_blueprint,
        delete_manual_blueprint,
        ensure_blueprint_index_schema,
        list_blueprint_index,
        sync_blueprint_index,
        update_manual_blueprint,
    )

    def _ok(data: Any = None, **extra: Any):
        return jsonify({"ok": True, "data": data, **extra})

    def _fail(msg: str, code: int = 400):
        return jsonify({"ok": False, "error": msg}), code

    def _as_int(raw: Any, default: int) -> int:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    @app.route("/api/admin/blueprint-index/refresh", methods=["POST"])
    @admin_required
    def blueprint_index_refresh():
        if not db_ready():
            return _fail("database_unavailable", 503)
        session = session_factory()
        try:
            result = sync_blueprint_index(session.get_bind(), force=True)
            return _ok(result)
        except Exception as exc:
            log.warning("blueprint_index_refresh failed: %s", exc)
            return _fail("refresh_failed", 500)
        finally:
            session.close()

    @app.route("/api/admin/blueprint-index", methods=["POST"])
    @admin_required
    def blueprint_index_create():
        if not db_ready():
            return _fail("database_unavailable", 503)
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return _fail("Informe o caminho ou a classe.")
        session = session_factory()
        try:
            row = add_manual_blueprint(
                session.get_bind(),
                identifier=str(body.get("identifier") or ""),
                kind=str(body.get("kind") or ""),
                display_name=str(body.get("display_name") or ""),
                mod_name=str(body.get("mod_name") or ""),
                note=str(body.get("note") or ""),
            )
            return _ok(row)
        except BlueprintIndexError as exc:
            return _fail(exc.message, 400)
        except Exception as exc:
            log.warning("blueprint_index_create failed: %s", exc)
            return _fail("create_failed", 500)
        finally:
            session.close()

    @app.route("/api/admin/blueprint-index", methods=["PATCH"])
    @admin_required
    def blueprint_index_update():
        if not db_ready():
            return _fail("database_unavailable", 503)
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return _fail("Cadastro não encontrado.")
        session = session_factory()
        try:
            row = update_manual_blueprint(
                session.get_bind(),
                ident_norm=str(body.get("ident_norm") or ""),
                identifier=str(body.get("identifier") or ""),
                kind=str(body.get("kind") or ""),
                display_name=str(body.get("display_name") or ""),
                mod_name=str(body.get("mod_name") or ""),
                note=str(body.get("note") or ""),
            )
            return _ok(row)
        except BlueprintIndexError as exc:
            return _fail(exc.message, 400)
        except Exception as exc:
            log.warning("blueprint_index_update failed: %s", exc)
            return _fail("update_failed", 500)
        finally:
            session.close()

    @app.route("/api/admin/blueprint-index", methods=["DELETE"])
    @admin_required
    def blueprint_index_delete():
        if not db_ready():
            return _fail("database_unavailable", 503)
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            body = {}
        ident = str(body.get("ident_norm") or request.args.get("ident_norm") or "")
        session = session_factory()
        try:
            row = delete_manual_blueprint(session.get_bind(), ident_norm=ident)
            return _ok(row)
        except BlueprintIndexError as exc:
            return _fail(exc.message, 400)
        except Exception as exc:
            log.warning("blueprint_index_delete failed: %s", exc)
            return _fail("delete_failed", 500)
        finally:
            session.close()

    @app.route("/api/admin/blueprint-index", methods=["GET"])
    @admin_required
    def blueprint_index_list():
        if not db_ready():
            return _fail("database_unavailable", 503)
        session = session_factory()
        try:
            engine = session.get_bind()
            ensure_blueprint_index_schema(engine)
            payload = list_blueprint_index(
                engine,
                q=request.args.get("q") or "",
                kind=request.args.get("kind") or "",
                source=request.args.get("source") or "",
                limit=_as_int(request.args.get("limit"), 50),
                offset=_as_int(request.args.get("offset"), 0),
            )
            return _ok(payload)
        except Exception as exc:
            log.warning("blueprint_index_list failed: %s", exc)
            return _fail("query_failed", 500)
        finally:
            session.close()
