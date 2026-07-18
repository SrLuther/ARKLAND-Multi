"""Rotas HTTP — Votações da comunidade."""
from __future__ import annotations

from typing import Any, Callable

from flask import Flask, jsonify, request

from poll_service import (
    cancel_poll,
    cast_vote,
    close_poll,
    create_poll,
    get_poll_detail,
    list_polls_admin,
    list_polls_public,
    poll_meta,
    publish_poll,
    update_poll,
)


def register_poll_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    login_required: Callable,
    admin_required: Callable,
    steam_id_from_session: Callable[[], str | None],
    limiter: Any | None = None,
    create_notification: Callable[..., Any] | None = None,
) -> None:
    _limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))

    @app.route("/api/polls/meta", methods=["GET"])
    def polls_meta():
        return jsonify({"ok": True, **poll_meta()})

    @app.route("/api/polls", methods=["GET"])
    def polls_list_public():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        include_closed = request.args.get("include_closed", "1") not in ("0", "false")
        sid = steam_id_from_session()
        db = session_factory()
        try:
            polls = list_polls_public(
                db, viewer_steam_id=sid, include_closed=include_closed,
            )
            return jsonify({"ok": True, "polls": polls})
        except Exception as exc:
            db.rollback()
            return jsonify({"ok": False, "error": "Falha ao carregar votações"}), 503
        finally:
            db.close()

    @app.route("/api/polls/<int:poll_id>", methods=["GET"])
    def polls_detail_public(poll_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        sid = steam_id_from_session()
        db = session_factory()
        try:
            poll = get_poll_detail(db, poll_id, viewer_steam_id=sid)
            return jsonify({"ok": True, "poll": poll})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404
        finally:
            db.close()

    @app.route("/api/polls/<int:poll_id>/vote", methods=["POST"])
    @login_required
    @_limit("30 per hour")
    def polls_vote(poll_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        raw_ids = body.get("option_ids") or body.get("option_id")
        if raw_ids is None:
            return jsonify({"ok": False, "error": "Selecione ao menos uma opção"}), 400
        if isinstance(raw_ids, (int, str)):
            option_ids = [int(raw_ids)]
        else:
            option_ids = [int(x) for x in raw_ids]
        steam_id = str(steam_id_from_session())
        db = session_factory()
        try:
            notify = None
            if create_notification:
                def notify(db_, **kwargs):
                    create_notification(db_, **kwargs)

            poll = cast_vote(
                db, poll_id, steam_id, option_ids, notify_fn=notify,
            )
            return jsonify({"ok": True, "poll": poll})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            db.close()

    @app.route("/api/admin/polls", methods=["GET"])
    @admin_required
    def polls_admin_list():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            polls = list_polls_admin(db)
            return jsonify({"ok": True, "polls": polls})
        except Exception:
            db.rollback()
            return jsonify({"ok": False, "error": "Falha ao carregar votações"}), 503
        finally:
            db.close()

    @app.route("/api/admin/polls", methods=["POST"])
    @admin_required
    @_limit("30 per hour")
    def polls_admin_create():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        options = body.get("options") or []
        if not isinstance(options, list):
            return jsonify({"ok": False, "error": "Opções inválidas"}), 400
        db = session_factory()
        try:
            poll = create_poll(
                db,
                title=str(body.get("title") or ""),
                description=str(body.get("description") or ""),
                options=options,
                ends_at=body.get("ends_at"),
                reward_amber=int(body.get("reward_amber") or 0),
                allow_multiple=bool(body.get("allow_multiple")),
                min_votes_valid=body.get("min_votes_valid"),
                publish=bool(body.get("publish", True)),
                created_by_steam_id=str(steam_id_from_session() or ""),
            )
            return jsonify({"ok": True, "poll": poll})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/admin/polls/<int:poll_id>", methods=["PUT"])
    @admin_required
    def polls_admin_update(poll_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        db = session_factory()
        try:
            poll = update_poll(
                db,
                poll_id,
                title=body.get("title"),
                description=body.get("description"),
                ends_at=body.get("ends_at"),
                reward_amber=body.get("reward_amber"),
                allow_multiple=body.get("allow_multiple"),
                min_votes_valid=body.get("min_votes_valid"),
                options=body.get("options"),
            )
            return jsonify({"ok": True, "poll": poll})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/admin/polls/<int:poll_id>/publish", methods=["POST"])
    @admin_required
    def polls_admin_publish(poll_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            poll = publish_poll(db, poll_id)
            return jsonify({"ok": True, "poll": poll})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/admin/polls/<int:poll_id>/close", methods=["POST"])
    @admin_required
    def polls_admin_close(poll_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            poll = close_poll(db, poll_id, auto=False)
            return jsonify({"ok": True, "poll": poll})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()

    @app.route("/api/admin/polls/<int:poll_id>/cancel", methods=["POST"])
    @admin_required
    def polls_admin_cancel(poll_id: int):
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            poll = cancel_poll(db, poll_id)
            return jsonify({"ok": True, "poll": poll})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400
        finally:
            db.close()
