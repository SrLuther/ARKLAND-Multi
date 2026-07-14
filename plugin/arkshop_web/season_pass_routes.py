"""Rotas HTTP — Season Pass (config persistente + claim queue stub)."""
from __future__ import annotations

from typing import Any, Callable

from flask import Flask, jsonify, request

import season_pass_config as spcfg


def _fmt_amber(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _season_id(cfg: dict[str, Any]) -> str:
    return f"season-{str(cfg.get('current_tier') or 'delta').lower()}"


def _season_block(cfg: dict[str, Any]) -> dict[str, Any]:
    tier = str(cfg.get("current_tier") or "Delta")
    dur = int(cfg.get("duration_days") or 30)
    price = spcfg.premium_price(cfg, tier)
    return {
        "id": _season_id(cfg),
        "tier": tier,
        "name": f"Season Pass — {tier}",
        "title": f"Season Pass — {tier}",
        "status": "active",
        "status_label": "Ativa",
        "duration_days": dur,
        "days_remaining": dur,
        "starts_at": None,
        "ends_at": None,
        "tier_sequence": list(cfg.get("tier_sequence") or []),
        "premium_price_amber": price,
        "note": (
            f"Season Pass — {tier}: {dur} dias fixos; fim automático. "
            "Próxima season só quando admin iniciar. Meta coletiva ≠ XP do passe."
        ),
    }


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
) -> list[dict[str, Any]]:
    levels = (
        list(cfg.get("free_levels") or spcfg._FREE_LEVELS)
        if kind == "free"
        else list(range(1, 31))
    )
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
        # Claim manual: nível atingido + track unlock + ainda não na queue.
        # Entrega in-game = False (só enfileira intenção).
        claimable = bool(unlocked and reachable and not is_claimed)
        out.append({
            "level": lv,
            "track": kind,
            "label": label,
            "reward_hint": label,
            "grants": annotated,
            "delivery": summary,
            "locked": not unlocked,
            "reachable": reachable,
            "claimable": claimable,
            "claimed": is_claimed,
            "claimed_status": "queued_not_delivered" if is_claimed else None,
            "in_game_delivered": False,
            "state": "claimed" if is_claimed else state,
        })
    return out


def _player_payload(
    *,
    steam_id: str | None,
    premium: bool = False,
    xp: int = 0,
) -> dict[str, Any]:
    cfg = spcfg.load_config()
    progress = spcfg.level_from_xp(xp, list(cfg.get("xp_thresholds") or []))
    level = int(progress["level"])
    season = _season_block(cfg)
    price = spcfg.premium_price(cfg, season["tier"])
    sid = str(steam_id or "")
    claimed: set[tuple[str, int]] = set()
    if sid:
        claimed = spcfg.player_claimed_set(sid, season["id"])
    return {
        "ok": True,
        "placeholder": True,
        "economy_live": False,
        "xp_live": False,
        "grant_engine_live": False,
        "season": season,
        "player": {
            "steam_id": steam_id,
            "premium": bool(premium),
            **progress,
        },
        "premium": {
            "owned": bool(premium),
            "price_amber": price,
            "price_tbd": False,
            "price_table": dict(cfg.get("premium_price_by_tier") or {}),
            "cta_label": f"Comprar Premium ({_fmt_amber(price)} Â)",
            "purchase_enabled": False,
            "purchase_ui": "season_pass",
            "entitlement_scope": "current_season",
            "vault_note": (
                f"100% de {_fmt_amber(price)} Â vai para o cofre ARKBANK. "
                "Compra só com Âmbar (sem PIX/cartão). Válido só nesta season (30 dias)."
            ),
            "claim_note": (
                "Resgate manual: nenhuma recompensa é entregue automaticamente ao subir de nível. "
                "Claim actualmente só regista a intenção (queue) — entrega in-game ainda não."
            ),
        },
        "tracks": {
            "free": _track_nodes(cfg, "free", level, unlocked=True, claimed=claimed),
            "premium": _track_nodes(
                cfg, "premium", level, unlocked=bool(premium), claimed=claimed
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
                "in_game_delivery": False,
            },
        },
        "notes": {
            "xp_source": (
                "XP do passe = Âmbar dos ticks TimedPoints (previsto) — "
                "hook ainda NÃO ligado; progresso = 0 até existir."
            ),
            "vault_vs_pass": (
                "Meta coletiva do cofre ARKBANK ≠ XP individual. "
                "Ao completar a meta, a admin agenda a data do evento (não dispara sozinha)."
            ),
            "duration": (
                f"Cada season dura exactamente {int(cfg.get('duration_days') or 30)} dias "
                "(fim automático). A seguinte só começa com start manual da administração."
            ),
            "claim": (
                "Resgate manual (click). Enfileira grants da config; "
                "NÃO entrega Â/kits/dinos/licenças no jogo ainda. "
                "sku_pending = falta id/SKU na config admin."
            ),
            "premium_scope": "Premium só em Âmbar, só em SeasonLand, só a season actual.",
            "regulamento": "Ver Regulamento Season Pass (unclaimed, calendário, licença 30 dias).",
            "grant_engine": "grant_engine_live=false — admin config + claim queue apenas.",
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
    limiter: Any | None = None,
) -> None:
    _limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))

    @app.route("/api/season-pass/meta", methods=["GET"])
    def season_pass_meta():
        cfg = spcfg.load_config()
        season = _season_block(cfg)
        price = spcfg.premium_price(cfg, season["tier"])
        return jsonify({
            "ok": True,
            "placeholder": True,
            "enabled": True,
            "economy_live": False,
            "xp_live": False,
            "grant_engine_live": False,
            "season_name": season["name"],
            "tier": season["tier"],
            "status": season["status"],
            "duration_days": int(cfg.get("duration_days") or 30),
            "premium_price_amber": price,
            "premium_price_by_tier": dict(cfg.get("premium_price_by_tier") or {}),
            "xp_thresholds": list(cfg.get("xp_thresholds") or []),
            "free_levels": list(cfg.get("free_levels") or []),
            "tier_sequence": list(cfg.get("tier_sequence") or []),
            "notes": {
                "xp_source": "XP TimedPoints previsto — hook ainda não ligado.",
                "vault_vs_pass": "Meta coletiva ≠ XP do passe; admin agenda o evento.",
                "duration": (
                    f"Season = {int(cfg.get('duration_days') or 30)} dias (fim automático); "
                    "próxima = start manual admin."
                ),
                "claim": (
                    "Claim manual enfileira grants da config; "
                    "entrega in-game ainda não."
                ),
                "premium_scope": "Entitlement = season actual; compra só em Âmbar.",
                "regulamento": "Regulamento Season Pass (static/regulamento_season_pass.html).",
            },
        })

    @app.route("/api/season-pass/preview", methods=["GET"])
    def season_pass_preview():
        return jsonify(_player_payload(steam_id=None, premium=False, xp=0))

    @app.route("/api/season-pass/me", methods=["GET"])
    @login_required
    def season_pass_me():
        _ = db_ready
        steam_id = str(steam_id_from_session() or "")
        return jsonify(_player_payload(steam_id=steam_id or None, premium=False, xp=0))

    @app.route("/api/season-pass/premium", methods=["POST"])
    @login_required
    @_limit("10 per hour")
    def season_pass_buy_premium():
        price = spcfg.premium_price()
        return jsonify({
            "ok": False,
            "placeholder": True,
            "error": "Compra do Season Pass Premium ainda não está disponível.",
            "price_amber": price,
            "purchase_ui": "season_pass",
            "entitlement_scope": "current_season",
        }), 501

    @app.route("/api/season-pass/claim", methods=["POST"])
    @login_required
    @_limit("60 per hour")
    def season_pass_claim():
        """
        Claim manual stub: valida nível/track contra config, enfileira grants pretendidos.
        NÃO entrega Âmbar / kits / dinos / licenças in-game.
        """
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

        cfg = spcfg.load_config()
        # XP ainda não live — aceita force_preview_level só para admin? Não: stub player level=0.
        # Para o stub ser útil em testes de queue, permitir claim se body.preview_xp (admin only via separate).
        # Jogador: level 0 → só claimable depois do hook XP. Ainda assim gravamos se reachable.
        progress = spcfg.level_from_xp(0, list(cfg.get("xp_thresholds") or []))
        player_level = int(progress["level"])
        # Stub: premium entitlement não existe → premium claims bloqueados.
        premium_owned = False
        if track == "premium" and not premium_owned:
            return jsonify({
                "ok": False,
                "error": "Track Premium bloqueada (sem entitlement / compra ainda stub).",
                "grant_engine_live": False,
            }), 403
        if track == "free" and level not in (cfg.get("free_levels") or list(spcfg._FREE_LEVELS)):
            return jsonify({"ok": False, "error": f"Nível Free {level} não existe (só ×4)."}), 400
        if player_level < level:
            return jsonify({
                "ok": False,
                "error": (
                    f"Nível {level} ainda não atingido "
                    f"(XP live=false; progresso actual={player_level})."
                ),
                "xp_live": False,
                "player_level": player_level,
            }), 400

        grants = spcfg.rewards_for(cfg, track, level)
        if not grants:
            return jsonify({
                "ok": False,
                "error": "Sem rewards na config para este nó — edita no painel admin.",
            }), 400

        season = _season_block(cfg)
        try:
            result = spcfg.enqueue_claim(
                steam_id=steam_id,
                season_id=season["id"],
                tier=season["tier"],
                track=track,
                level=level,
                grants=grants,
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

        claim = result["claim"]
        delivery = result["delivery"]
        return jsonify({
            "ok": True,
            "queued": True,
            "already_queued": result["already_queued"],
            "in_game_delivered": False,
            "grant_engine_live": False,
            "message": (
                "Claim registado na queue. "
                "Nada foi entregue in-game (Â/kits/dinos/licenças). "
                "Grants com delivery=sku_pending precisam de id na config admin."
            ),
            "claim": claim,
            "intended_grants": claim.get("grants") or [],
            "delivery": delivery,
            "not_yet_delivered": {
                "amber": True,
                "dino": True,
                "item": True,
                "kit": True,
                "license": True,
                "reason": "grant_engine_not_implemented",
            },
        })

    @app.route("/api/admin/season-pass/config", methods=["GET"])
    @admin_required
    def admin_season_pass_config_get():
        cfg = spcfg.load_config()
        return jsonify({
            "ok": True,
            "config": cfg,
            "grant_types": sorted(spcfg._GRANT_TYPES),
            "free_levels": list(spcfg._FREE_LEVELS),
            "premium_levels": list(spcfg._PREMIUM_LEVELS),
            "grant_engine_live": False,
            "note": (
                "Edita preço Premium e grants tipados (amber|dino|item|kit|license). "
                "ids vazios = sku_pending — claim queue regista intenção sem entrega."
            ),
        })

    @app.route("/api/admin/season-pass/config", methods=["PUT"])
    @admin_required
    @_limit("60 per hour")
    def admin_season_pass_config_put():
        body = request.get_json(force=True, silent=True) or {}
        raw = body.get("config") if isinstance(body.get("config"), dict) else body
        try:
            cfg = spcfg.save_config(
                raw,
                updated_by_steam_id=str(steam_id_from_session() or "") or None,
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
        return jsonify({"ok": True, "config": cfg})
