"""Rotas HTTP — mural de avisos / carrossel de cards da home."""
from __future__ import annotations

from typing import Any, Callable

from flask import Flask, jsonify, request, send_from_directory

from home_notice_service import (
    create_home_card,
    delete_home_card,
    get_home_notice,
    home_cards_meta,
    list_home_cards,
    reorder_home_cards,
    resolve_home_card_image_path,
    save_home_card_image,
    set_home_notice,
    update_home_card,
)

_CARD_ERRORS = {
    "card_empty": "Informe título, texto ou imagem.",
    "card_not_found": "Card não encontrado.",
    "invalid_url": "URL inválida (use http(s):// ou caminho /…).",
    "file_required": "Selecione um arquivo de imagem.",
    "invalid_image_type": "Tipo de imagem inválido (JPEG, PNG, WebP ou GIF).",
    "empty_file": "Arquivo vazio.",
    "file_too_large": "Imagem muito grande (máx. 5 MB).",
    "home_cards_uploads_not_configured": "Upload de cards não configurado.",
}


def register_home_notice_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    admin_required: Callable,
    steam_id_from_session: Callable[[], str | None],
    limiter: Any | None = None,
    invalidate_home_cache: Callable[[], None] | None = None,
) -> None:
    _limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))

    def _bump_home_cache() -> None:
        if invalidate_home_cache is not None:
            try:
                invalidate_home_cache()
            except Exception:
                pass

    def _safe_get_notice(db: Any) -> dict[str, Any]:
        try:
            return get_home_notice(db)
        except Exception:
            return {
                "title": "",
                "body": "",
                "updated_at": None,
                "updated_by_steam_id": None,
                "has_content": False,
            }

    def _safe_list_cards(db: Any, *, active_only: bool) -> list[dict[str, Any]]:
        try:
            return list_home_cards(db, active_only=active_only)
        except Exception:
            return []

    @app.route("/api/public/home-notice", methods=["GET"])
    @_limit("120 per minute; 2000 per hour", override_defaults=True)
    def home_notice_public():
        if not db_ready():
            return jsonify({
                "ok": True,
                "notice": {
                    "title": "",
                    "body": "",
                    "updated_at": None,
                    "updated_by_steam_id": None,
                    "has_content": False,
                },
                "degraded": True,
            })
        db = session_factory()
        try:
            return jsonify({"ok": True, "notice": _safe_get_notice(db)})
        finally:
            db.close()

    @app.route("/api/public/home-cards", methods=["GET"])
    @_limit("120 per minute; 2000 per hour", override_defaults=True)
    def home_cards_public():
        meta = home_cards_meta()
        if not db_ready():
            return jsonify({"ok": True, "cards": [], "degraded": True, **meta})
        db = session_factory()
        try:
            return jsonify({
                "ok": True,
                "cards": _safe_list_cards(db, active_only=True),
                **meta,
            })
        finally:
            db.close()

    @app.route("/api/public/home-card-images/<path:filename>", methods=["GET"])
    @_limit("240 per minute; 4000 per hour", override_defaults=True)
    def home_card_image(filename: str):
        path = resolve_home_card_image_path(filename)
        if path is None:
            return jsonify({"ok": False, "error": "not_found"}), 404
        return send_from_directory(path.parent, path.name)

    @app.route("/api/admin/home-notice", methods=["GET"])
    @admin_required
    def home_notice_admin_get():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            return jsonify({"ok": True, "notice": get_home_notice(db)})
        except Exception as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            db.close()

    @app.route("/api/admin/home-notice", methods=["PUT"])
    @admin_required
    @_limit("60 per hour")
    def home_notice_admin_put():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        db = session_factory()
        try:
            notice = set_home_notice(
                db,
                title=body.get("title"),
                body=body.get("body"),
                updated_by_steam_id=str(steam_id_from_session() or "") or None,
            )
            _bump_home_cache()
            return jsonify({"ok": True, "notice": notice})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            db.close()

    @app.route("/api/admin/home-cards", methods=["GET"])
    @admin_required
    def home_cards_admin_list():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            return jsonify({
                "ok": True,
                "cards": list_home_cards(db, active_only=False),
                **home_cards_meta(),
            })
        except Exception as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            db.close()

    @app.route("/api/admin/home-cards", methods=["POST"])
    @admin_required
    @_limit("60 per hour")
    def home_cards_admin_create():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        db = session_factory()
        try:
            card = create_home_card(
                db,
                title=body.get("title"),
                body=body.get("body") if body.get("body") is not None else body.get("text"),
                image_url=body.get("image_url") or body.get("image_path"),
                link_url=body.get("link_url"),
                active=body.get("active", True),
                sort_order=body.get("order") if body.get("order") is not None else body.get("sort_order"),
                updated_by_steam_id=str(steam_id_from_session() or "") or None,
            )
            _bump_home_cache()
            return jsonify({"ok": True, "card": card}), 201
        except ValueError as exc:
            db.rollback()
            code = str(exc)
            return jsonify({
                "ok": False,
                "error": code,
                "message": _CARD_ERRORS.get(code, code),
            }), 400
        except Exception as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            db.close()

    @app.route("/api/admin/home-cards/<int:card_id>", methods=["PATCH", "PUT"])
    @admin_required
    @_limit("120 per hour")
    def home_cards_admin_update(card_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        kwargs: dict[str, Any] = {
            "updated_by_steam_id": str(steam_id_from_session() or "") or None,
        }
        if "title" in body:
            kwargs["title"] = body.get("title")
        if "body" in body or "text" in body:
            kwargs["body"] = body.get("body") if "body" in body else body.get("text")
        if "image_url" in body or "image_path" in body:
            kwargs["image_url"] = body.get("image_url") if "image_url" in body else body.get("image_path")
        if "link_url" in body:
            kwargs["link_url"] = body.get("link_url")
        if "active" in body:
            kwargs["active"] = body.get("active")
        if "order" in body or "sort_order" in body:
            kwargs["sort_order"] = body.get("order") if "order" in body else body.get("sort_order")
        db = session_factory()
        try:
            card = update_home_card(db, card_id, **kwargs)
            _bump_home_cache()
            return jsonify({"ok": True, "card": card})
        except ValueError as exc:
            db.rollback()
            code = str(exc)
            return jsonify({
                "ok": False,
                "error": code,
                "message": _CARD_ERRORS.get(code, code),
            }), 400
        except Exception as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            db.close()

    @app.route("/api/admin/home-cards/<int:card_id>", methods=["DELETE"])
    @admin_required
    @_limit("60 per hour")
    def home_cards_admin_delete(card_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            card = delete_home_card(db, card_id)
            _bump_home_cache()
            return jsonify({"ok": True, "card": card})
        except ValueError as exc:
            db.rollback()
            code = str(exc)
            return jsonify({
                "ok": False,
                "error": code,
                "message": _CARD_ERRORS.get(code, code),
            }), 400
        except Exception as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            db.close()

    @app.route("/api/admin/home-cards/reorder", methods=["PUT"])
    @admin_required
    @_limit("60 per hour")
    def home_cards_admin_reorder():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        ids = body.get("ids") or body.get("ordered_ids") or []
        try:
            ordered = [int(x) for x in ids]
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "ids_invalid"}), 400
        db = session_factory()
        try:
            cards = reorder_home_cards(
                db,
                ordered,
                updated_by_steam_id=str(steam_id_from_session() or "") or None,
            )
            _bump_home_cache()
            return jsonify({"ok": True, "cards": cards})
        except Exception as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            db.close()

    @app.route("/api/admin/home-cards/upload", methods=["POST"])
    @admin_required
    @_limit("30 per hour")
    def home_cards_admin_upload():
        file_obj = request.files.get("file")
        try:
            result = save_home_card_image(file_obj)
            return jsonify({"ok": True, **result, **home_cards_meta()}), 201
        except ValueError as exc:
            code = str(exc)
            return jsonify({
                "ok": False,
                "error": code,
                "message": _CARD_ERRORS.get(code, code),
            }), 400
