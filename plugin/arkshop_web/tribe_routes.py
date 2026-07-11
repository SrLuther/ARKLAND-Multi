"""Rotas da Área de Tribo ARKLAND.

Registrar via register_tribe_routes(app, ...) no app.py.

Endpoints públicos (player, login_required):
  GET  /api/tribe/my           — visão agregada das tribos do jogador
  POST /api/tribe/register     — ativar painel de tribo
  GET  /api/tribe/members      — membros por mapa
  POST /api/tribe/members/add  — owner adiciona membro por SteamID (MVP)
  GET  /api/tribe/log/<server> — log por mapa (stub MVP)
  GET  /api/tribe/split        — configuração de split
  POST /api/tribe/split        — criar/atualizar split
  POST /api/tribe/split/optout — opt-out de membro
  POST /api/tribe/split/disable — desativar split
  GET  /api/tribe/regulation   — regulamento interno
  POST /api/tribe/regulation   — salvar regulamento (owner)
  POST /api/tribe/fob/link     — vincular fob (owner principal)

Endpoints de plugin (api_key_required):
  POST /api/tribe/presence     — snapshot de presença do plugin C++
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from flask import Flask, jsonify, request

log = logging.getLogger("arkshop_web.tribe_routes")


def register_tribe_routes(
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
    from tribe_service import (
        SPLIT_MIN_SALE_AMBER,
        activate_pending_splits,
        create_cluster_group,
        create_or_update_split,
        disable_split,
        get_active_split,
        get_members_by_map,
        get_my_tribes,
        backfill_owner_links_from_presence,
        get_or_create_owner,
        get_owner,
        get_regulation,
        get_tribe_log_stub,
        is_tribe_member,
        link_fob,
        manual_add_member,
        member_optout,
        record_presence,
        save_regulation,
        update_owner_profile,
        upsert_map_link,
    )

    # ── Utilitários ──────────────────────────────────────────

    def _db():
        return session_factory()

    def _ip():
        try:
            from flask_limiter.util import get_remote_address
            return get_remote_address()
        except Exception:
            return request.remote_addr

    def _fail(msg: str, code: int = 400):
        return jsonify({"ok": False, "error": msg}), code

    def _ok(data: Any = None, **kw):
        payload = {"ok": True}
        if data is not None:
            payload["data"] = data
        payload.update(kw)
        return jsonify(payload)

    # ── Presence (plugin C++ → web) ──────────────────────────

    @app.route("/api/tribe/presence", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    def tribe_presence():
        """Plugin envia snapshot de presença de um jogador."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        steam_id = str(body.get("steam_id") or "")
        server_id = str(body.get("server_id") or "")
        if not steam_id or not server_id:
            return _fail("steam_id e server_id obrigatórios")

        db = _db()
        try:
            record_presence(
                db,
                steam_id=steam_id,
                server_id=server_id,
                map_name=str(body.get("map_name") or server_id),
                tribe_id=body.get("tribe_id"),
                tribe_name=body.get("tribe_name"),
                is_owner=bool(body.get("is_owner")),
                member_rank=body.get("member_rank"),
                source="login_hook",
                members=body.get("members"),
            )
            return _ok()
        except Exception as exc:
            log.warning("tribe_presence error: %s", exc)
            return _fail(str(exc), 500)
        finally:
            db.close()

    # ── Minha Área — Minha Tribo ──────────────────────────────

    @app.route("/api/tribe/my", methods=["GET"])
    @login_required
    def tribe_my():
        """Retorna todas as tribos do jogador logado por mapa."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session()
        db = _db()
        try:
            data = get_my_tribes(db, steam_id)
            return _ok(data)
        except Exception as exc:
            log.warning("tribe_my error steam=%s: %s", steam_id, exc)
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/tribe/register", methods=["POST"])
    @login_required
    def tribe_register():
        """Ativa o painel de tribo para o jogador (primeira vez)."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session()
        body = request.get_json(silent=True) or {}
        display_name = str(body.get("display_name") or steam_id)[:128]

        db = _db()
        try:
            owner = get_or_create_owner(db, steam_id, display_name)
            linked = backfill_owner_links_from_presence(db, steam_id)
            data = dict(owner)
            data["maps_linked"] = linked
            return _ok(data)
        except Exception as exc:
            log.warning("tribe_register error: %s", exc)
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/tribe/profile", methods=["PATCH"])
    @login_required
    def tribe_profile_update():
        """Atualiza perfil do owner (display_name, description, log_visibility)."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            owner = update_owner_profile(
                db, steam_id,
                display_name=body.get("display_name"),
                description=body.get("description"),
                log_visibility=body.get("log_visibility"),
            )
            return _ok(owner)
        except Exception as exc:
            return _fail(str(exc))
        finally:
            db.close()

    @app.route("/api/tribe/members", methods=["GET"])
    @login_required
    def tribe_members():
        """Lista membros de uma tribo por mapa."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        server_id = request.args.get("server_id") or ""
        tribe_id_raw = request.args.get("tribe_id")
        if not server_id or not tribe_id_raw:
            return _fail("server_id e tribe_id obrigatórios")
        try:
            tribe_id = int(tribe_id_raw)
        except ValueError:
            return _fail("tribe_id inválido")

        steam_id = steam_id_from_session()
        db = _db()
        try:
            # Verifica acesso: membro, owner do painel, ou admin
            owner = get_owner(db, steam_id)
            is_panel_owner = bool(owner)
            if (
                not is_admin_steamid(steam_id)
                and not is_tribe_member(db, steam_id, server_id, tribe_id)
                and not is_panel_owner
            ):
                return _fail("Acesso negado — apenas membros da tribo", 403)
            members = get_members_by_map(db, server_id=server_id, tribe_id=tribe_id)
            return _ok(members)
        except Exception as exc:
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/tribe/members/add", methods=["POST"])
    @login_required
    def tribe_members_add():
        """Owner adiciona membro manualmente por SteamID64 (MVP)."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            result = manual_add_member(
                db,
                owner_steam_id=steam_id,
                server_id=str(body.get("server_id") or ""),
                tribe_id=int(body.get("tribe_id") or 0),
                member_steam_id=str(body.get("steam_id") or ""),
                character_name=str(body.get("character_name") or ""),
            )
            return _ok(result)
        except ValueError as exc:
            return _fail(str(exc))
        except Exception as exc:
            log.warning("tribe_members_add error: %s", exc)
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/tribe/log/<server_id>", methods=["GET"])
    @login_required
    def tribe_log(server_id: str):
        """Log de tribo por mapa (stub MVP — ver TODO em tribe_service.get_tribe_log_stub)."""
        return _ok(get_tribe_log_stub(server_id, limit=int(request.args.get("limit", 200))))

    # ── Fob linking ──────────────────────────────────────────

    @app.route("/api/tribe/fob/link", methods=["POST"])
    @login_required
    def tribe_fob_link():
        """Owner principal vincula uma fob ao cluster group."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            owner = get_or_create_owner(db, steam_id)
            cluster_group_id = body.get("cluster_group_id")
            if not cluster_group_id:
                # Cria grupo automático se não existir
                grp = create_cluster_group(
                    db,
                    group_name=body.get("group_name") or "Cluster",
                    anchor_server_id=body.get("anchor_server_id") or "",
                    anchor_tribe_id=int(body.get("anchor_tribe_id") or 0),
                    created_by_steam_id=steam_id,
                )
                cluster_group_id = grp["id"]

            result = link_fob(
                db,
                cluster_group_id=cluster_group_id,
                tribe_owner_id=owner["id"],
                server_id=str(body.get("server_id") or ""),
                tribe_id=int(body.get("tribe_id") or 0),
                tribe_name=str(body.get("tribe_name") or ""),
                fob_owner_steam_id=str(body.get("fob_owner_steam_id") or steam_id),
            )
            return _ok(result)
        except (ValueError, TypeError) as exc:
            return _fail(str(exc))
        except Exception as exc:
            log.warning("tribe_fob_link error: %s", exc)
            return _fail(str(exc), 500)
        finally:
            db.close()

    # ── Split ─────────────────────────────────────────────────

    @app.route("/api/tribe/split", methods=["GET"])
    @login_required
    def tribe_split_get():
        """Retorna configuração de split ativa."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session()
        db = _db()
        try:
            owner = get_owner(db, steam_id)
            if not owner:
                return _ok(None)
            split = get_active_split(db, owner["id"])
            # Ativa splits pendentes com cooldown concluído
            activate_pending_splits(db)
            return _ok(split)
        except Exception as exc:
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/tribe/split", methods=["POST"])
    @login_required
    def tribe_split_save():
        """Cria ou atualiza configuração de split (owner only). Aplica cooldown 48h."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            owner = get_or_create_owner(db, steam_id)
            members = body.get("members")
            if not isinstance(members, list):
                return _fail("Campo 'members' obrigatório (lista)")

            result = create_or_update_split(
                db,
                tribe_owner_id=owner["id"],
                tribe_id=int(body.get("tribe_id") or 0),
                server_id=str(body.get("server_id") or ""),
                tribe_name=str(body.get("tribe_name") or ""),
                members=members,
                actor_steam_id=steam_id,
                ip_address=_ip(),
            )
            return _ok(result)
        except ValueError as exc:
            return _fail(str(exc))
        except Exception as exc:
            log.warning("tribe_split_save error: %s", exc)
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/tribe/split/optout", methods=["POST"])
    @login_required
    def tribe_split_optout():
        """Membro faz opt-out imediato do split."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            split_id = int(body.get("split_id") or 0)
            target_steam_id = str(body.get("steam_id") or steam_id)
            if target_steam_id != steam_id and not is_admin_steamid(steam_id):
                return _fail("Só pode fazer opt-out da sua própria participação", 403)

            result = member_optout(
                db,
                split_id=split_id,
                steam_id=target_steam_id,
                actor_steam_id=steam_id,
                ip_address=_ip(),
            )
            return _ok(result)
        except ValueError as exc:
            return _fail(str(exc))
        except Exception as exc:
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/tribe/split/disable", methods=["POST"])
    @login_required
    def tribe_split_disable():
        """Owner desativa o split imediatamente (sem cooldown)."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session()
        db = _db()
        try:
            owner = get_owner(db, steam_id)
            if not owner:
                return _fail("Nenhum painel de tribo registrado", 404)
            disable_split(db, tribe_owner_id=owner["id"], actor_steam_id=steam_id, ip_address=_ip())
            return _ok({"message": "Split desativado com sucesso."})
        except Exception as exc:
            return _fail(str(exc), 500)
        finally:
            db.close()

    # ── Regulamento ──────────────────────────────────────────

    @app.route("/api/tribe/regulation", methods=["GET"])
    @login_required
    def tribe_regulation_get():
        """Retorna regulamento da tribo (somente membros)."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session()
        tribe_owner_id_raw = request.args.get("tribe_owner_id")
        db = _db()
        try:
            if tribe_owner_id_raw:
                tribe_owner_id = int(tribe_owner_id_raw)
            else:
                owner = get_owner(db, steam_id)
                if not owner:
                    return _ok(None)
                tribe_owner_id = owner["id"]
            reg = get_regulation(db, tribe_owner_id)
            if reg and reg.get("is_hidden") and not is_admin_steamid(steam_id):
                return _fail("Regulamento oculto por moderação.", 403)
            return _ok(reg)
        except Exception as exc:
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/tribe/regulation", methods=["POST"])
    @login_required
    def tribe_regulation_save():
        """Salva regulamento (owner only). Cria versão nova."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            owner = get_owner(db, steam_id)
            if not owner:
                return _fail("Registro de proprietário não encontrado. Use /api/tribe/register primeiro.", 404)

            content = str(body.get("content_text") or "")
            visibility = str(body.get("visibility") or "private")
            checklist = body.get("checklist_json")

            reg = save_regulation(
                db,
                tribe_owner_id=owner["id"],
                content_text=content,
                actor_steam_id=steam_id,
                visibility=visibility,
                checklist_json=checklist,
            )
            return _ok(reg)
        except ValueError as exc:
            return _fail(str(exc))
        except Exception as exc:
            log.warning("tribe_regulation_save error: %s", exc)
            return _fail(str(exc), 500)
        finally:
            db.close()

    # ── Admin: link de mapa manual ───────────────────────────

    @app.route("/api/tribe/admin/link", methods=["POST"])
    @admin_required
    def tribe_admin_link():
        """Admin vincula manualmente uma tribo a um owner por mapa."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            owner = get_or_create_owner(db, str(body.get("steam_id") or ""))
            result = upsert_map_link(
                db,
                tribe_owner_id=owner["id"],
                server_id=str(body.get("server_id") or ""),
                tribe_id=int(body.get("tribe_id") or 0),
                tribe_name_local=str(body.get("tribe_name") or ""),
                tribe_type=str(body.get("tribe_type") or "principal"),
            )
            return _ok(result)
        except ValueError as exc:
            return _fail(str(exc))
        except Exception as exc:
            return _fail(str(exc), 500)
        finally:
            db.close()

    log.info("tribe_routes: rotas registradas")
