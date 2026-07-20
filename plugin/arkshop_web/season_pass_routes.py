"""Rotas HTTP — Season Pass (calendário, XP, Premium, claims)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from flask import Flask, jsonify, request

import season_pass_config as spcfg
import season_pass_service as sps


def _fmt_amber(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _node_state(player_level: int, lv: int, *, unlocked: bool) -> str:
    if not unlocked:
        return "locked"
    if player_level >= lv:
        return "ready"
    return "pending"


def _track_nodes(
    cfg: dict[str, Any],
    kind: str,
    player_level: int,
    *,
    unlocked: bool,
    claimed: set[tuple[str, int]],
    claims_open: bool,
    entitlements: list[dict[str, Any]] | None = None,
    season_id: str | None = None,
    orders_by_idem: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    levels = (
        list(cfg.get("free_levels") or spcfg._FREE_LEVELS)
        if kind == "free"
        else list(range(1, 31))
    )
    ents = entitlements or []
    sid = str(season_id or cfg.get("season_id") or "")
    orders = orders_by_idem or {}
    out: list[dict[str, Any]] = []
    for lv in levels:
        lv = int(lv)
        grants = spcfg.rewards_for(cfg, kind, lv)
        annotated = spcfg.annotate_grants(grants)
        summary = spcfg.delivery_summary(annotated)
        label = spcfg.grants_label(annotated) if annotated else f"Recompensa {kind} L{lv}"
        state = _node_state(player_level, lv, unlocked=unlocked)
        is_claimed = (kind, lv) in claimed
        reachable = player_level >= lv
        grants_ok = bool(summary.get("in_game_delivery"))
        choice_info = sps.license_choice_needed(ents, annotated) if annotated else None
        needs_choice = bool(choice_info)
        claimable = bool(
            claims_open
            and unlocked
            and reachable
            and not is_claimed
            and annotated
            and grants_ok
        )
        block_reason = None
        if is_claimed:
            block_reason = None
        elif not claims_open:
            block_reason = "Janela de resgate fechada (season seguinte já iniciada ou ainda sem start)."
        elif not unlocked:
            block_reason = "Compra o Premium nesta season para desbloquear (catch-up 1…N)."
        elif not reachable:
            block_reason = f"Atinge o nível {lv} para resgatar."
        elif not annotated:
            block_reason = "Sem recompensa configurada."
        elif not grants_ok:
            block_reason = summary.get("note") or "SKU pendente — IDs em falta."

        delivery_state = None
        claimed_status = None
        in_game_delivered = False
        queued_for_shop = False
        grant_rows = annotated
        if is_claimed and sid:
            grant_rows, delivery_state = sps.annotate_claimed_grants(
                grants,
                season_id=sid,
                track=kind,
                level=lv,
                orders_by_idem=orders,
            )
            claimed_status = delivery_state
            in_game_delivered = delivery_state == "delivered"
            queued_for_shop = delivery_state in ("queued", "partial", "delivering", "failed")
        elif is_claimed:
            # Sem season/orders: não mentir — claimed ≠ entregue in-game.
            claimed_status = "claimed"
            in_game_delivered = False
            delivery_state = "unknown"

        out.append({
            "level": lv,
            "track": kind,
            "label": label,
            "reward_hint": label,
            "grants": grant_rows,
            "delivery": summary,
            "locked": not unlocked,
            "reachable": reachable,
            "claimable": claimable,
            "claimed": is_claimed,
            "claimed_status": claimed_status,
            "delivery_state": delivery_state,
            # Deprecated: prefer delivery_state / queued_for_shop.
            "in_game_delivered": in_game_delivered,
            "queued_for_shop": queued_for_shop,
            "license_choice_may_apply": needs_choice,
            "license_amber_alternative": (
                int(choice_info["amber_alternative"]) if choice_info else None
            ),
            "block_reason": block_reason,
            "state": "claimed" if is_claimed else state,
        })
    return out


def _player_payload(
    *,
    steam_id: str | None,
    db: Any | None = None,
) -> dict[str, Any]:
    cfg = spcfg.load_config()
    season = sps.season_public(cfg)
    st = season["status"]
    claims_open = st in ("active", "claim_window")
    purchase_ok = st == "active"
    price = spcfg.premium_price(cfg, season["tier"])
    collective = sps.collective_meta_public(cfg, db, latch=bool(db is not None))

    xp = 0
    premium = False
    claimed: set[tuple[str, int]] = set()
    entitlements: list[dict[str, Any]] = []
    orders_by_idem: dict[str, dict[str, Any]] = {}
    season_id = str(season.get("id") or "")
    if steam_id and season_id and db is not None:
        try:
            sps.ensure_season_pass_schema(db.get_bind())
            prog = sps.get_progress(db, steam_id, season_id)
            xp = int(prog["xp"])
            premium = bool(prog["premium"])
            claimed = sps.player_claimed_pairs(prog)
            get_ents = sps._cbs.get("get_entitlements")
            if get_ents:
                entitlements = list(get_ents(steam_id, db) or [])
            orders_by_idem = sps.load_sp_catalog_orders(
                db, steam_id, season_id=season_id
            )
        except Exception:
            pass
    elif steam_id and season_id:
        # Fallback audit file se DB offline
        claimed = spcfg.player_claimed_set(steam_id, season_id)

    progress = spcfg.level_from_xp(xp, list(cfg.get("xp_thresholds") or []))
    level = int(progress["level"])
    live = st != "inactive"

    return {
        "ok": True,
        "placeholder": False,
        "economy_live": live,
        "xp_live": live,
        "grant_engine_live": True,
        "season": season,
        "collective_meta": collective,
        "player": {
            "steam_id": steam_id,
            "premium": premium,
            **progress,
            "xp_cap": sps.MAX_XP,
            "xp_frozen": xp >= sps.MAX_XP,
        },
        "premium": {
            "owned": premium,
            "price_amber": price,
            "price_tbd": False,
            "price_table": dict(cfg.get("premium_price_by_tier") or {}),
            "cta_label": f"Comprar Premium ({_fmt_amber(price)} Â)",
            "purchase_enabled": purchase_ok and not premium,
            "purchase_ui": "season_pass",
            "entitlement_scope": "current_season",
            "vault_note": (
                f"100% de {_fmt_amber(price)} Â vai para o cofre ARKBANK. "
                "Compra só com Âmbar (sem PIX/cartão). Válido só nesta season."
            ),
            "claim_note": (
                "Resgate manual. Âmbar na hora; kits/itens/dinos → fila PENDENTE "
                "(/shop online força a entrega agora); licenças → entitlement. "
                "Catch-up: ao comprar Premium no nível N podes resgatar Premium 1…N."
            ),
        },
        "tracks": {
            "free": _track_nodes(
                cfg,
                "free",
                level,
                unlocked=True,
                claimed=claimed,
                claims_open=claims_open,
                entitlements=entitlements,
                season_id=season_id,
                orders_by_idem=orders_by_idem,
            ),
            "premium": _track_nodes(
                cfg,
                "premium",
                level,
                unlocked=premium,
                claimed=claimed,
                claims_open=claims_open,
                entitlements=entitlements,
                season_id=season_id,
                orders_by_idem=orders_by_idem,
            ),
            "rules": {
                "free_levels": list(cfg.get("free_levels") or []),
                "premium_levels": "1-30",
                "premium_gets_both": True,
                "claim_mode": "manual",
                "retroactive_premium_catchup": True,
                "unclaimed_until_next_season_start": True,
                "xp_freeze_at_max": True,
                "premium_currency": "amber_only",
                "in_game_delivery": True,
                "license_or_amber_on_higher_tier": True,
            },
        },
        "notes": {
            "xp_source": (
                "XP do passe = Âmbar dos ticks TimedPoints (todos os mapas). "
                f"Congela no nível 30 ({_fmt_amber(sps.MAX_XP)} XP)."
                if live
                else "Season não iniciada — XP ainda não conta."
            ),
            "vault_vs_pass": (
                "Meta coletiva do cofre ARKBANK ≠ XP individual. "
                "Progresso = inflows do cofre nesta season (não o saldo total). "
                "Ao completar a meta, a admin agenda a data do evento."
            ),
            "duration": (
                f"Cada season dura exactamente {int(cfg.get('duration_days') or 30)} dias "
                "(fim automático). A seguinte só começa com start manual da administração."
            ),
            "claim": (
                "Resgate manual. Após o fim dos 30 dias ainda podes resgatar "
                "até o admin iniciar a próxima season; depois o que ficar é perdido. "
                "SKU pendente some quando o ID de catálogo for preenchido. "
                "/shop no servidor força a entrega da fila agora."
            ),
            "premium_scope": "Premium só em Âmbar, só em SeasonLand, só a season actual.",
            "regulamento": "Ver Regulamento Season Pass (unclaimed, calendário, licença 30 dias).",
            "grant_engine": "Entrega live: Â / fila loja / entitlements (sku_pending bloqueia).",
        },
        "config_meta": {
            "updated_at": cfg.get("updated_at"),
            "updated_by_steam_id": cfg.get("updated_by_steam_id"),
            "current_tier": cfg.get("current_tier"),
        },
    }


def register_season_pass_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    login_required: Callable,
    admin_required: Callable,
    steam_id_from_session: Callable[[], str | None],
    session_factory: Callable[[], Any] | None = None,
    release_session: Callable[[Any], None] | None = None,
    limiter: Any | None = None,
) -> None:
    _limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))

    def _db():
        if not session_factory or not db_ready():
            return None
        return session_factory()

    def _close(db: Any) -> None:
        if db is None:
            return
        if release_session:
            release_session(db)
        else:
            try:
                db.close()
            except Exception:
                pass

    @app.route("/api/season-pass/meta", methods=["GET"])
    def season_pass_meta():
        cfg = spcfg.load_config()
        season = sps.season_public(cfg)
        price = spcfg.premium_price(cfg, season["tier"])
        live = season["status"] != "inactive"
        db = _db()
        try:
            collective = sps.collective_meta_public(cfg, db, latch=bool(db is not None))
        finally:
            _close(db)
        return jsonify({
            "ok": True,
            "placeholder": False,
            "enabled": True,
            "economy_live": live,
            "xp_live": live,
            "grant_engine_live": True,
            "season_name": season["name"],
            "tier": season["tier"],
            "status": season["status"],
            "status_label": season["status_label"],
            "starts_at": season["starts_at"],
            "ends_at": season["ends_at"],
            "days_remaining": season["days_remaining"],
            "duration_days": int(cfg.get("duration_days") or 30),
            "premium_price_amber": price,
            "premium_price_by_tier": dict(cfg.get("premium_price_by_tier") or {}),
            "xp_thresholds": list(cfg.get("xp_thresholds") or []),
            "free_levels": list(cfg.get("free_levels") or []),
            "tier_sequence": list(cfg.get("tier_sequence") or []),
            "collective_meta": collective,
            "notes": {
                "xp_source": f"XP = Â TimedPoints (multi-mapa), cap {_fmt_amber(sps.MAX_XP)} (curva +25%/nível).",
                "vault_vs_pass": (
                    "Meta coletiva ≠ XP do passe; progresso = inflows da season "
                    "(≠ saldo do cofre); admin agenda o evento."
                ),
                "duration": (
                    f"Season = {int(cfg.get('duration_days') or 30)} dias (fim automático); "
                    "próxima = start manual admin."
                ),
                "claim": "Claim manual com entrega (Â / fila / licença).",
                "premium_scope": "Entitlement = season actual; compra só em Âmbar.",
                "regulamento": "Regulamento Season Pass (static/regulamento_season_pass.html).",
            },
        })

    @app.route("/api/season-pass/preview", methods=["GET"])
    def season_pass_preview():
        db = _db()
        try:
            return jsonify(_player_payload(steam_id=None, db=db))
        finally:
            _close(db)

    @app.route("/api/season-pass/me", methods=["GET"])
    @login_required
    def season_pass_me():
        steam_id = str(steam_id_from_session() or "")
        db = _db()
        try:
            return jsonify(_player_payload(steam_id=steam_id or None, db=db))
        finally:
            _close(db)

    @app.route("/api/season-pass/premium", methods=["POST"])
    @login_required
    @_limit("10 per hour")
    def season_pass_buy_premium():
        if not db_ready() or not session_factory:
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session() or "")
        if not steam_id:
            return jsonify({"ok": False, "error": "Não autenticado"}), 401
        db = session_factory()
        try:
            result = sps.buy_premium(db, steam_id)
            if result.get("already_owned"):
                msg = "Já tinhas Premium nesta season."
            else:
                msg = result.get("catchup_note") or "Season Pass Premium adquirido."
            return jsonify({**result, "message": msg})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            _close(db)

    @app.route("/api/season-pass/claim", methods=["POST"])
    @login_required
    @_limit("60 per hour")
    def season_pass_claim():
        if not db_ready() or not session_factory:
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session() or "")
        if not steam_id:
            return jsonify({"ok": False, "error": "Não autenticado"}), 401
        body = request.get_json(force=True, silent=True) or {}
        track = str(body.get("track") or "").strip().lower()
        try:
            level = int(body.get("level"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "level inválido"}), 400
        if track not in ("free", "premium"):
            return jsonify({"ok": False, "error": "track deve ser free|premium"}), 400
        license_choice = body.get("license_choice")
        if license_choice is not None:
            license_choice = str(license_choice).strip().lower()

        db = session_factory()
        try:
            result = sps.claim_reward(
                db,
                steam_id=steam_id,
                track=track,
                level=level,
                license_choice=license_choice,
            )
            return jsonify(result)
        except ValueError as exc:
            db.rollback()
            msg = str(exc)
            code = 400
            if "Premium" in msg and "bloqueada" in msg:
                code = 403
            elif msg.startswith("sku_pending") or msg.startswith("sku_missing"):
                code = 409
            payload: dict[str, Any] = {
                "ok": False,
                "error": msg,
                "grant_engine_live": True,
            }
            if "license_choice" in msg:
                payload["license_choice_required"] = True
            return jsonify(payload), code
        except Exception as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            _close(db)

    @app.route("/api/admin/season-pass/start", methods=["POST"])
    @admin_required
    @_limit("20 per hour")
    def admin_season_pass_start():
        body = request.get_json(force=True, silent=True) or {}
        advance = bool(body.get("next") or body.get("advance_tier"))
        try:
            cfg = sps.start_season(
                advance_tier=advance,
                updated_by_steam_id=str(steam_id_from_session() or "") or None,
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        season = sps.season_public(cfg)
        return jsonify({
            "ok": True,
            "config": cfg,
            "season": season,
            "message": (
                f"Próxima season iniciada: {season['title']}"
                if advance
                else f"Season iniciada: {season['title']}"
            ),
        })

    @app.route("/api/admin/season-pass/config", methods=["GET"])
    @admin_required
    def admin_season_pass_config_get():
        cfg = spcfg.load_config()
        season = sps.season_public(cfg)
        db = _db()
        try:
            collective = sps.collective_meta_public(cfg, db, latch=bool(db is not None))
        finally:
            _close(db)
        return jsonify({
            "ok": True,
            "config": cfg,
            "season": season,
            "collective_meta": collective,
            "grant_types": sorted(spcfg._GRANT_TYPES),
            "free_levels": list(spcfg._FREE_LEVELS),
            "premium_levels": list(spcfg._PREMIUM_LEVELS),
            "grant_engine_live": True,
            "note": (
                "Calendário: «Iniciar season» / «Iniciar próxima». "
                "Meta colectiva: target Â (inflows da season) + agenda do evento (não auto-fire). "
                f"XP: curva +25%/nível (B={spcfg.XP_BASE}), cap L30={_fmt_amber(sps.MAX_XP)}. "
                "IDs vazios em kit/item/dino = claim bloqueado (sku_pending)."
            ),
            "xp_cap": sps.MAX_XP,
            "xp_curve": {
                "base": spcfg.XP_BASE,
                "growth": spcfg.XP_GROWTH,
                "max_level": spcfg.MAX_LEVEL,
                "formula": "delta(n)=max(1,round(B*1.25**(n-1))); XP(L)=sum(delta(1..L))",
            },
        })

    @app.route("/api/admin/season-pass/resend", methods=["POST"])
    @admin_required
    @_limit("30 per hour")
    def admin_season_pass_resend():
        """Reenvia Â e/ou fila kit/item/dino de um nó já claimed (ops / Felipe-like).

        Body: steam_id, track, level, season_id? (default=actual),
        parts=["amber"|"catalog"|ambos] ou flags amber/catalog,
        confirm=true obrigatório se amber (re-grant).
        """
        if not db_ready() or not session_factory:
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        steam_id = str(body.get("steam_id") or "").strip()
        track = str(body.get("track") or "").strip().lower()
        season_id = body.get("season_id")
        if season_id is not None:
            season_id = str(season_id).strip() or None
        reason = str(body.get("reason") or "").strip() or None
        confirm = bool(body.get("confirm"))
        try:
            level = int(body.get("level"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "level inválido"}), 400
        try:
            parts = sps.parse_resend_parts(
                parts=body.get("parts"),
                amber=body.get("amber"),
                catalog=body.get("catalog"),
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        if not steam_id:
            return jsonify({"ok": False, "error": "steam_id obrigatório"}), 400

        db = session_factory()
        try:
            result = sps.admin_resend_reward(
                db,
                steam_id=steam_id,
                track=track,
                level=level,
                parts=parts,
                season_id=season_id,
                confirm=confirm,
                reason=reason,
                admin_steam_id=str(steam_id_from_session() or "") or None,
                missing_only=bool(body.get("missing_only")),
            )
            return jsonify(result)
        except ValueError as exc:
            db.rollback()
            msg = str(exc)
            code = 400
            if msg.startswith("confirm_required"):
                code = 409
            elif msg.startswith("sku_pending"):
                code = 409
            return jsonify({"ok": False, "error": msg}), code
        except Exception as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            _close(db)

    @app.route("/api/admin/season-pass/sku-health", methods=["GET"])
    @admin_required
    @_limit("60 per hour")
    def admin_season_pass_sku_health():
        """Staff: SKUs SeasonLand vs catálogo shop (sku_pending / sku_missing)."""
        cfg = spcfg.load_config()
        result = sps.check_season_pass_sku_sync(cfg)
        return jsonify({"ok": True, **result})

    @app.route("/api/admin/season-pass/orders", methods=["GET"])
    @admin_required
    @_limit("120 per hour")
    def admin_season_pass_orders():
        """Ops: fila de entrega SeasonLand (sp:% / skip-kit|sp:%)."""
        if not db_ready() or not session_factory:
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        status = str(request.args.get("status", "")).strip() or None
        steam_id = str(request.args.get("steam_id", "") or request.args.get("q", "")).strip() or None
        track = str(request.args.get("track", "")).strip().lower() or None
        level_raw = str(request.args.get("level", "")).strip()
        level: int | None = None
        if level_raw:
            try:
                level = int(level_raw)
            except ValueError:
                return jsonify({"ok": False, "error": "level inválido"}), 400
        date_from = None
        date_to = None
        df = str(request.args.get("date_from", "")).strip()
        dt = str(request.args.get("date_to", "")).strip()
        if df:
            try:
                date_from = datetime.fromisoformat(df.replace("Z", "+00:00"))
                if date_from.tzinfo is not None:
                    date_from = date_from.replace(tzinfo=None)
            except ValueError:
                return jsonify({"ok": False, "error": "date_from inválido"}), 400
        if dt:
            try:
                date_to = datetime.fromisoformat(dt.replace("Z", "+00:00"))
                if date_to.tzinfo is not None:
                    date_to = date_to.replace(tzinfo=None)
                if len(dt) <= 10:
                    date_to = date_to.replace(
                        hour=23, minute=59, second=59, microsecond=999999
                    )
            except ValueError:
                return jsonify({"ok": False, "error": "date_to inválido"}), 400
        try:
            limit = max(1, min(200, int(request.args.get("limit", 10))))
            offset = max(0, int(request.args.get("offset", 0)))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "limit/offset inválidos"}), 400
        db = session_factory()
        try:
            return jsonify(
                sps.list_season_pass_orders(
                    db,
                    status=status,
                    steam_id=steam_id,
                    track=track,
                    level=level,
                    date_from=date_from,
                    date_to=date_to,
                    limit=limit,
                    offset=offset,
                )
            )
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            _close(db)

    @app.route("/api/admin/season-pass/delivery-metrics", methods=["GET"])
    @admin_required
    @_limit("60 per hour")
    def admin_season_pass_delivery_metrics():
        """Ops: fila SeasonLand (sp:%) — contagens/idade + top fail reasons."""
        if not db_ready() or not session_factory:
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        db = session_factory()
        try:
            return jsonify(sps.season_pass_delivery_metrics(db))
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
        finally:
            _close(db)

    @app.route("/api/admin/season-pass/config", methods=["PUT"])
    @admin_required
    @_limit("60 per hour")
    def admin_season_pass_config_put():
        body = request.get_json(force=True, silent=True) or {}
        raw = body.get("config") if isinstance(body.get("config"), dict) else body
        if isinstance(raw, dict) and "meta_target_amber" in raw:
            try:
                new_target = int(raw.get("meta_target_amber") or 0)
            except (TypeError, ValueError):
                new_target = -1
            if new_target >= 0:
                existing = spcfg.load_config()
                db = _db()
                try:
                    if db is not None and existing.get("starts_at"):
                        cur = sps.collective_meta_public(existing, db, latch=False)
                        prog = int(cur.get("progress_amber") or 0)
                        if new_target > prog:
                            raw = {
                                **raw,
                                "meta_reached": False,
                                "meta_reached_at": None,
                            }
                finally:
                    _close(db)
        try:
            cfg = spcfg.save_config(
                raw,
                updated_by_steam_id=str(steam_id_from_session() or "") or None,
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
        db = _db()
        try:
            collective = sps.collective_meta_public(cfg, db, latch=bool(db is not None))
        finally:
            _close(db)
        return jsonify({
            "ok": True,
            "config": cfg,
            "season": sps.season_public(cfg),
            "collective_meta": collective,
        })
