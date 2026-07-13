"""Rotas da Área de Tribo ARKLAND.

Registrar via register_tribe_routes(app, ...) no app.py.

Endpoints públicos (player, login_required):
  GET  /api/tribe/my           — visão agregada das tribos do jogador
  POST /api/tribe/register     — ativar painel de tribo
  GET  /api/tribe/members      — membros por mapa
  POST /api/tribe/members/add  — owner adiciona membro por SteamID (MVP)
  GET  /api/tribe/log/<server> — log por mapa (espelho TribeLog)
  POST /api/tribe/log/ingest   — ingestão de linhas (api_key / plugin / poller)
  GET  /api/tribe/split        — configuração de split
  POST /api/tribe/split        — criar/atualizar split
  POST /api/tribe/split/optout — sair do pool (100% nas vendas próprias)
  POST /api/tribe/split/optin  — aceitar ganho partilhado
  POST /api/tribe/split/disable — desativar split
  GET  /api/tribe/regulation   — regulamento interno
  POST /api/tribe/regulation   — salvar regulamento (owner)
  POST /api/tribe/fob/link     — vincular fob (owner principal)

Endpoints de plugin (api_key_required):
  POST /api/tribe/presence              — snapshot de presença do plugin C++
  POST /api/tribe/sync-request/claim    — plugin puxa pedidos «Verificar de novo»
  POST /api/tribe/sync-request/done     — plugin confirma execução do pedido

Endpoints públicos (player, login_required) — sync:
  POST /api/tribe/sync         — cria pedido pull + backfill (RCON opcional)
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
    trigger_tribe_sync_rcon: Callable[[], list[dict[str, Any]]] | None = None,
) -> None:
    from tribe_service import (
        SPLIT_MIN_SALE_AMBER,
        activate_pending_splits,
        claim_tribe_sync_requests,
        complete_tribe_sync_request,
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
        get_tribe_log,
        ingest_tribe_log_lines,
        is_tribe_member,
        link_fob,
        manual_add_member,
        member_optout,
        record_presence,
        request_tribe_sync,
        resolve_is_owner,
        save_regulation,
        sync_owner_maps,
        update_owner_profile,
        upsert_map_link,
        member_optin,
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
                is_owner=resolve_is_owner(
                    is_owner=body.get("is_owner"),
                    member_rank=body.get("member_rank"),
                ),
                member_rank=body.get("member_rank"),
                source=str(body.get("source") or "login_hook"),
                members=body.get("members"),
            )
            return _ok()
        except Exception as exc:
            log.warning("tribe_presence error: %s", exc)
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/tribe/sync", methods=["POST"])
    @login_required
    def tribe_sync():
        """Verificar de novo: pedido pull na MySQL + backfill (RCON só acelerador).

        Body opcional:
          refresh_only=true — só backfill (sem novo pedido / sem RCON); usado no poll da UI.
          skip_rcon=true — cria/renova pedido mas não tenta RCON.
        """
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session()
        body = request.get_json(silent=True) or {}
        refresh_only = bool(body.get("refresh_only"))
        skip_rcon = bool(body.get("skip_rcon")) or refresh_only

        db = _db()
        sync_req: dict[str, Any] | None = None
        if not refresh_only:
            try:
                sync_req = request_tribe_sync(db, steam_id)
            except Exception as exc:
                log.warning("tribe_sync request_tribe_sync failed steam=%s: %s", steam_id, exc)
                db.close()
                return _fail(f"Falha ao registar pedido de sync: {exc}", 500)

        rcon_results: list[dict[str, Any]] = []
        if not skip_rcon and trigger_tribe_sync_rcon is not None:
            try:
                rcon_results = list(trigger_tribe_sync_rcon() or [])
                if any(r.get("ok") for r in rcon_results):
                    import time
                    time.sleep(2.5)
            except Exception as exc:
                log.warning("tribe_sync RCON trigger failed steam=%s: %s", steam_id, exc)
                rcon_results.append({"ok": False, "error": f"RCON indisponível: {exc}"})

        try:
            data = sync_owner_maps(db, steam_id)
            if sync_req is not None:
                data["sync_request"] = sync_req
            data["sync_requested"] = not refresh_only
            data["rcon"] = rcon_results
            rcon_ok = sum(1 for r in rcon_results if r.get("ok"))
            data["rcon_ok"] = rcon_ok
            data["rcon_total"] = len(rcon_results)
            data["rcon_optional"] = True

            if data.get("maps"):
                return _ok(data)

            # Sem mapas: mensagem honesta — RCON não é o caminho principal.
            base = data.get("hint") or ""
            if rcon_results and rcon_ok == 0:
                extra = (
                    "RCON falhou (atalho opcional). O pedido ficou na fila MySQL: "
                    "o CustomShop puxa em ~15s e grava presença sem RCON."
                )
                data["hint"] = f"{base} {extra}".strip() if base else extra
            elif rcon_ok > 0 and not (data.get("presences") or []):
                data["hint"] = (
                    "Pedido na fila (+ atalho RCON), mas ainda sem presença. "
                    "Aguarde ~15s (poll MySQL do plugin) ou confirme "
                    "«TribeSync: presence OK» / presence MySQL OK no log."
                )
            elif not data.get("hint"):
                data["hint"] = (
                    "Pedido de sync registado na DB. Aguarde o plugin (~15s) e "
                    "clique de novo — RCON não é obrigatório."
                )
            return _ok(data)
        except Exception as exc:
            log.warning("tribe_sync error steam=%s: %s", steam_id, exc)
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/tribe/sync-request/claim", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    def tribe_sync_request_claim():
        """Plugin puxa pedidos pending para jogadores online neste mapa."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        server_id = str(body.get("server_id") or "").strip()
        raw_ids = body.get("steam_ids") or []
        if not isinstance(raw_ids, list):
            return _fail("steam_ids deve ser lista")
        if not server_id:
            return _fail("server_id obrigatório")

        db = _db()
        try:
            items = claim_tribe_sync_requests(
                db,
                [str(x) for x in raw_ids],
                server_id=server_id,
            )
            return _ok({"items": items, "count": len(items)})
        except Exception as exc:
            log.warning("tribe_sync_request_claim error: %s", exc)
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/tribe/sync-request/done", methods=["POST"])
    @api_key_required(allow_admin_session=False)
    def tribe_sync_request_done():
        """Plugin confirma que executou o pedido (presence enviada ou falha)."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        try:
            request_id = int(body.get("request_id") or 0)
        except (TypeError, ValueError):
            return _fail("request_id inválido")
        if request_id <= 0:
            return _fail("request_id obrigatório")
        ok = bool(body.get("ok", True))
        error = body.get("error")
        error_s = str(error) if error is not None else None

        db = _db()
        try:
            row = complete_tribe_sync_request(
                db, request_id, ok=ok, error=error_s,
            )
            if not row:
                return _fail("pedido não encontrado", 404)
            return _ok(row)
        except Exception as exc:
            log.warning("tribe_sync_request_done error: %s", exc)
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

    @app.route("/api/tribe/log/ingest", methods=["POST"])
    @api_key_required(allow_admin_session=True)
    def tribe_log_ingest():
        """Ingestão de linhas do TribeLog (plugin, poller ou admin)."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        server_id = str(body.get("server_id") or "").strip()
        lines = body.get("lines")
        if not server_id:
            return _fail("server_id obrigatório")
        if not isinstance(lines, list) or not lines:
            return _fail("lines obrigatório (lista não vazia)")
        db = _db()
        try:
            result = ingest_tribe_log_lines(
                db,
                server_id=server_id,
                lines=lines,
                tribe_id=body.get("tribe_id"),
                tribe_name=body.get("tribe_name"),
                steam_id=body.get("steam_id"),
                source=str(body.get("source") or "api"),
            )
            return _ok(result)
        except ValueError as exc:
            return _fail(str(exc))
        except Exception as exc:
            log.warning("tribe_log_ingest error: %s", exc)
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/tribe/log/<server_id>", methods=["GET"])
    @login_required
    def tribe_log(server_id: str):
        """Log de tribo por mapa (espelho em tribe_logs)."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session()
        if not steam_id:
            return _fail("Não autenticado", 401)
        db = _db()
        try:
            admin = bool(is_admin_steamid(steam_id))
            data = get_tribe_log(
                db,
                steam_id=steam_id,
                server_id=server_id,
                limit=int(request.args.get("limit", 200)),
                event_type=request.args.get("type") or request.args.get("event_type"),
                tribe_id=request.args.get("tribe_id"),
                is_admin=admin,
            )
            return _ok(data)
        except PermissionError as exc:
            return _fail(str(exc), 403)
        except ValueError as exc:
            return _fail(str(exc))
        except Exception as exc:
            log.warning("tribe_log error server=%s: %s", server_id, exc)
            return _fail(str(exc), 500)
        finally:
            db.close()

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
        """Membro sai do pool (opt-out) — vendas próprias ficam a 100%."""
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

    @app.route("/api/tribe/split/optin", methods=["POST"])
    @login_required
    def tribe_split_optin():
        """Aceita ganho partilhado (opt-in). Reentrada: 45h + aprovação do owner."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session()
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            split_id = int(body.get("split_id") or 0)
            target_steam_id = str(body.get("steam_id") or steam_id)
            owner_approved = bool(body.get("owner_approved"))

            # Owner pode aprovar reentrada de outro membro
            if target_steam_id != steam_id:
                owner = get_owner(db, steam_id)
                if not owner and not is_admin_steamid(steam_id):
                    return _fail("Só o proprietário pode aprovar reentrada de outro membro", 403)
                if owner:
                    split = get_active_split(db, owner["id"])
                    if not split or int(split["id"]) != split_id:
                        return _fail("Split não pertence à sua tribo", 403)
                owner_approved = True

            result = member_optin(
                db,
                split_id=split_id,
                steam_id=target_steam_id,
                actor_steam_id=steam_id,
                owner_approved=owner_approved,
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

    # ── Convite /tribe.CODE + Principal/Fob + admin ───────────

    def _invite():
        from tribe_invite_service import (
            create_join_request,
            generate_invite_code,
            get_active_invite_code,
            get_group_for_owner,
            get_or_stub_construction_limits,
            handle_ownership_transfer,
            list_admin_alerts,
            list_admin_tribes,
            list_confirmed_members,
            list_join_requests,
            resolve_join_request,
            revoke_membership_on_map,
            save_construction_limits,
            set_principal_map,
        )
        return {
            "generate_invite_code": generate_invite_code,
            "get_active_invite_code": get_active_invite_code,
            "get_group_for_owner": get_group_for_owner,
            "create_join_request": create_join_request,
            "list_join_requests": list_join_requests,
            "resolve_join_request": resolve_join_request,
            "list_confirmed_members": list_confirmed_members,
            "set_principal_map": set_principal_map,
            "revoke_membership_on_map": revoke_membership_on_map,
            "handle_ownership_transfer": handle_ownership_transfer,
            "list_admin_tribes": list_admin_tribes,
            "list_admin_alerts": list_admin_alerts,
            "get_or_stub_construction_limits": get_or_stub_construction_limits,
            "save_construction_limits": save_construction_limits,
        }

    @app.route("/api/tribe/invite", methods=["GET"])
    @login_required
    def tribe_invite_get():
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session()
        if not steam_id:
            return _fail("Não autenticado", 401)
        db = _db()
        try:
            inv = _invite()
            group = inv["get_group_for_owner"](db, steam_id)
            if not group:
                return _ok({"invite": None, "cluster_group": None, "requests": [], "confirmed": []})
            code = inv["get_active_invite_code"](db, group["id"])
            return _ok({
                "invite": code,
                "cluster_group": group,
                "requests": inv["list_join_requests"](db, owner_steam_id=steam_id, status="PENDING"),
                "confirmed": inv["list_confirmed_members"](db, group["id"]),
                "construction_limits": inv["get_or_stub_construction_limits"](db, group["id"]),
            })
        except Exception as exc:
            log.warning("tribe_invite_get: %s", exc)
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/tribe/invite", methods=["POST"])
    @login_required
    def tribe_invite_generate():
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session()
        if not steam_id:
            return _fail("Não autenticado", 401)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            result = _invite()["generate_invite_code"](
                db,
                owner_steam_id=steam_id,
                regenerate=bool(body.get("regenerate")),
            )
            return _ok(result)
        except ValueError as exc:
            return _fail(str(exc))
        except Exception as exc:
            log.warning("tribe_invite_generate: %s", exc)
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/tribe/invite/requests", methods=["GET"])
    @login_required
    def tribe_invite_requests():
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session()
        if not steam_id:
            return _fail("Não autenticado", 401)
        status = str(request.args.get("status") or "PENDING")
        db = _db()
        try:
            rows = _invite()["list_join_requests"](
                db, owner_steam_id=steam_id, status=status,
            )
            return _ok({"requests": rows})
        finally:
            db.close()

    @app.route("/api/tribe/invite/requests/<int:req_id>", methods=["POST"])
    @login_required
    def tribe_invite_resolve(req_id: int):
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session()
        if not steam_id:
            return _fail("Não autenticado", 401)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            result = _invite()["resolve_join_request"](
                db,
                owner_steam_id=steam_id,
                request_id=req_id,
                action=str(body.get("action") or ""),
                regenerate_code_on_deny=bool(body.get("regenerate_code")),
            )
            return _ok(result)
        except ValueError as exc:
            return _fail(str(exc))
        except Exception as exc:
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/tribe/invite/join", methods=["POST"])
    @api_key_required
    def tribe_invite_join():
        """Plugin: /tribe.CODE → cria pedido PENDING."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            result = _invite()["create_join_request"](
                db,
                code=str(body.get("code") or ""),
                steam_id=str(body.get("steam_id") or ""),
                server_id=str(body.get("server_id") or ""),
                tribe_id=int(body.get("tribe_id") or 0),
                character_name=str(body.get("character_name") or ""),
            )
            return _ok(result)
        except ValueError as exc:
            return _fail(str(exc))
        except Exception as exc:
            log.warning("tribe_invite_join: %s", exc)
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/tribe/principal", methods=["POST"])
    @login_required
    def tribe_set_principal():
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session()
        if not steam_id:
            return _fail("Não autenticado", 401)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            result = _invite()["set_principal_map"](
                db,
                owner_steam_id=steam_id,
                server_id=str(body.get("server_id") or ""),
            )
            return _ok(result)
        except ValueError as exc:
            return _fail(str(exc))
        except Exception as exc:
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/tribe/leave", methods=["POST"])
    @api_key_required
    def tribe_leave_revoke():
        """Plugin: tribe_id=0 / leave → revoga membership neste mapa."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            result = _invite()["revoke_membership_on_map"](
                db,
                steam_id=str(body.get("steam_id") or ""),
                server_id=str(body.get("server_id") or ""),
                tribe_id=int(body.get("tribe_id") or 0) or None,
                reason=str(body.get("reason") or "plugin_leave"),
            )
            return _ok(result)
        except Exception as exc:
            return _fail(str(exc), 500)
        finally:
            db.close()

    @app.route("/api/tribe/ownership-transfer", methods=["POST"])
    @api_key_required
    def tribe_ownership_transfer():
        if not db_ready():
            return _fail("DB não disponível", 503)
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            result = _invite()["handle_ownership_transfer"](
                db,
                server_id=str(body.get("server_id") or ""),
                tribe_id=int(body.get("tribe_id") or 0),
                new_owner_steam_id=str(body.get("new_owner_steam_id") or ""),
                old_owner_steam_id=str(body.get("old_owner_steam_id") or "") or None,
                tribe_name=str(body.get("tribe_name") or ""),
            )
            return _ok(result)
        except ValueError as exc:
            return _fail(str(exc))
        except Exception as exc:
            return _fail(str(exc), 500)
        finally:
            db.close()

    # Painel Tribos / códigos: somente admins (@admin_required).
    # Papel support NÃO entra (lista separada de admin_steamids).
    @app.route("/api/tribe/admin/list", methods=["GET"])
    @admin_required
    def tribe_admin_list():
        if not db_ready():
            return _fail("DB não disponível", 503)
        db = _db()
        try:
            inv = _invite()
            return _ok({
                "tribes": inv["list_admin_tribes"](db),
                "alerts": inv["list_admin_alerts"](db),
                "construction_limits": inv["get_or_stub_construction_limits"](db),
            })
        finally:
            db.close()

    @app.route("/api/tribe/admin/construction-limits", methods=["POST"])
    @admin_required
    def tribe_admin_construction_limits():
        """Notas admin apenas — sem enforcement (decisão Jul/2026 §20.8)."""
        if not db_ready():
            return _fail("DB não disponível", 503)
        steam_id = steam_id_from_session() or ""
        body = request.get_json(silent=True) or {}
        db = _db()
        try:
            result = _invite()["save_construction_limits"](
                db,
                admin_steam_id=steam_id,
                principal_max=0,
                fob_max=0,
                notes=str(body.get("notes") or ""),
                cluster_group_id=int(body["cluster_group_id"]) if body.get("cluster_group_id") else None,
            )
            return _ok(result)
        except Exception as exc:
            return _fail(str(exc), 500)
        finally:
            db.close()

    log.info("tribe_routes: rotas registradas")
