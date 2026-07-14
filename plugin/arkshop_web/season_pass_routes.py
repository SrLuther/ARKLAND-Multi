"""Rotas HTTP — Season Pass (MVP stub; economia real ainda não implementada)."""
from __future__ import annotations

from typing import Any, Callable

from flask import Flask, jsonify

# Thresholds cumulativos §15.5 (ARKBANK_SPEC) — XP(L)=round(L*162.5); L30=4875 sob orçamento 6000.
_XP_THRESHOLDS = [
    163, 325, 488, 650, 813, 975, 1138, 1300, 1463, 1625,
    1788, 1950, 2113, 2275, 2438, 2600, 2763, 2925, 3088, 3250,
    3413, 3575, 3738, 3900, 4063, 4225, 4388, 4550, 4713, 4875,
]

# Nomes de season = tiers de licença (ordem de progressão).
_SEASON_TIERS = ("Delta", "Gamma", "Beta", "Alfa", "Omega", "Transcendente")
_CURRENT_SEASON_TIER = "Delta"
_SEASON_DURATION_DAYS = 30

# Free: só múltiplos de 4 (4…28). Premium: todos 1–30. (§15.6)
_FREE_LEVELS = tuple(n for n in range(4, 29, 4))  # 4,8,12,16,20,24,28
_PREMIUM_LEVELS = tuple(range(1, 31))

# Labels exemplo Season Pass — Delta (§15.6.1–15.6.2). Grant engine fora de escopo.
_FREE_REWARDS: dict[int, str] = {
    4: "500 Â",
    8: "Kit consumíveis / stock (~1–2k Â)",
    12: "1.500 Â",
    16: "Cryo + 1 dino L1 comum (não apex)",
    20: "3.000 Â",
    24: "Kit selas vanilla / item utilitário (alta quality)",
    28: "5.000 Â",
}

_PREMIUM_REWARDS: dict[int, str] = {
    1: "250 Â",
    2: "500 Â",
    3: "750 Â",
    4: "400 Â + tag / cosmetic menor",
    5: "1.000 Â",
    6: "Cosmetic menor (placeholder)",
    7: "1.000 Â",
    8: "500 Â + consumível leve",
    9: "2.000 Â",
    10: "Kit L1 comum (pack pequeno)",
    11: "2.000 Â",
    12: "750 Â + item utilitário leve",
    13: "Dino L1 mid",
    14: "2.500 Â",
    15: "Boost curto (ou 2.500 Â)",
    16: "1.000 Â + consumível / item leve",
    17: "3.000 Â",
    18: "Item ItensAlfa Delta (ou 3.500 Â)",
    19: "4.000 Â",
    20: "1.200 Â + cosmetic / title leve",
    21: "Pack10 comum barato (ou 5.000 Â)",
    22: "5.500 Â",
    23: "Pack10 / kit gear barato (ou 6.000 Â)",
    24: "1.500 Â + sela vanilla leve",
    25: "Kit selas / gear",
    26: "Renovação parcial licença Delta (ou 7.500 Â)",
    27: "Kit gear / utilitário mid (ou 8.000 Â)",
    28: "2.000 Â + item distintivo pequeno",
    29: "Licença Delta 30 dias (ou Â catálogo se já tiveres tier superior)",
    30: "20.000 Â",
}

# Preços Premium locked §15.2.2 — 100% → cofre ARKBANK.
_PREMIUM_PRICE_BY_TIER: dict[str, int] = {
    "Delta": 15_000,
    "Gamma": 18_000,
    "Beta": 22_000,
    "Alfa": 28_000,
    "Omega": 35_000,
    "Transcendente": 45_000,
}


def _premium_price(tier: str | None = None) -> int:
    t = tier or _CURRENT_SEASON_TIER
    return int(_PREMIUM_PRICE_BY_TIER.get(t, _PREMIUM_PRICE_BY_TIER["Delta"]))


def _fmt_amber(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _level_from_xp(xp: int) -> dict[str, Any]:
    xp = max(0, int(xp))
    level = 0
    for i, thr in enumerate(_XP_THRESHOLDS, start=1):
        if xp >= thr:
            level = i
        else:
            prev = _XP_THRESHOLDS[i - 2] if i > 1 else 0
            return {
                "level": level,
                "next_level": i,
                "xp": xp,
                "xp_into_level": xp - prev,
                "xp_for_next": thr - prev,
                "xp_to_next": thr - xp,
                "next_threshold": thr,
                "max_level": len(_XP_THRESHOLDS),
            }
    return {
        "level": level,
        "next_level": None,
        "xp": xp,
        "xp_into_level": 0,
        "xp_for_next": 0,
        "xp_to_next": 0,
        "next_threshold": _XP_THRESHOLDS[-1],
        "max_level": len(_XP_THRESHOLDS),
    }


def _node_state(player_level: int, lv: int, *, unlocked: bool) -> str:
    if not unlocked:
        return "locked"
    if player_level >= lv:
        return "ready"
    return "pending"


def _reward_label(kind: str, lv: int) -> str:
    table = _FREE_REWARDS if kind == "free" else _PREMIUM_REWARDS
    return table.get(lv, f"Recompensa {kind} L{lv}")


def _placeholder_track(kind: str, player_level: int, *, unlocked: bool) -> list[dict[str, Any]]:
    """
    Stub: claim engine ainda não existe.
    Na implementação real: claimable=True quando nível atingido, track
    desbloqueada, e ainda não claimed — claim é SEMPRE manual (sem auto-grant).
    Buy Premium mid-season → Premium 1..N + Free já unlocked passam a claimable
    (catch-up retroactivo §15.2 #11).
    """
    levels = _FREE_LEVELS if kind == "free" else _PREMIUM_LEVELS
    out: list[dict[str, Any]] = []
    for lv in levels:
        state = _node_state(player_level, lv, unlocked=unlocked)
        label = _reward_label(kind, lv)
        # Stub: claimable fica False até existir motor de claim; flag documenta a regra.
        out.append({
            "level": lv,
            "track": kind,
            "label": label,
            "reward_hint": label,
            "locked": not unlocked,
            "reachable": player_level >= lv,
            "claimable": False,  # futuro: unlocked & reachable & not claimed (manual claim)
            "claimed": False,
            "state": state,
        })
    return out


def _season_block() -> dict[str, Any]:
    tier = _CURRENT_SEASON_TIER
    return {
        "id": f"season-{tier.lower()}",
        "tier": tier,
        "name": f"Season Pass — {tier}",
        "title": f"Season Pass — {tier}",
        "status": "active",
        "status_label": "Ativa (placeholder)",
        "duration_days": _SEASON_DURATION_DAYS,
        "days_remaining": _SEASON_DURATION_DAYS,
        "starts_at": None,
        "ends_at": None,
        "tier_sequence": list(_SEASON_TIERS),
        "premium_price_amber": _premium_price(tier),
        "note": (
            f"Season Pass — {tier}: {_SEASON_DURATION_DAYS} dias fixos; fim automático. "
            "Próxima season só quando admin iniciar. Meta coletiva ≠ XP do passe."
        ),
    }


def _placeholder_payload(*, steam_id: str | None, premium: bool = False, xp: int = 0) -> dict[str, Any]:
    progress = _level_from_xp(xp)
    level = int(progress["level"])
    season = _season_block()
    price = _premium_price(season["tier"])
    return {
        "ok": True,
        "placeholder": True,
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
            "price_table": dict(_PREMIUM_PRICE_BY_TIER),
            "cta_label": f"Comprar Premium ({_fmt_amber(price)} Â)",
            "purchase_enabled": False,
            "purchase_ui": "season_pass",  # compra só nesta área UI
            "entitlement_scope": "current_season",
            "vault_note": (
                f"100% de {_fmt_amber(price)} Â vai para o cofre ARKBANK. "
                "Compra só com Âmbar (sem PIX/cartão). Válido só nesta season (30 dias)."
            ),
            "claim_note": (
                "Resgate manual: nenhuma recompensa é entregue automaticamente ao subir de nível. "
                "Comprar Premium a meio desbloqueia catch-up 1..N. "
                "Após o dia 30 podes ainda resgatar até o admin abrir a próxima season; depois disso, não-resgatadas são perdidas."
            ),
        },
        "tracks": {
            "free": _placeholder_track("free", level, unlocked=True),
            "premium": _placeholder_track("premium", level, unlocked=bool(premium)),
            "rules": {
                "free_levels": list(_FREE_LEVELS),
                "premium_levels": "1-30",
                "premium_gets_both": True,
                "claim_mode": "manual",
                "retroactive_premium_catchup": True,
                "unclaimed_until_next_season_start": True,
                "xp_freeze_at_max": True,
                "premium_currency": "amber_only",
            },
        },
        "notes": {
            "xp_source": (
                "XP do passe = Âmbar dos ticks TimedPoints em todos os mapas. "
                "No L30 o Â continua; o XP do passe congela."
            ),
            "vault_vs_pass": (
                "Meta coletiva do cofre ARKBANK ≠ XP individual. "
                "Ao completar a meta, a admin agenda a data do evento (não dispara sozinha)."
            ),
            "duration": (
                f"Cada season dura exactamente {_SEASON_DURATION_DAYS} dias (fim automático). "
                "A seguinte só começa com start manual da administração."
            ),
            "claim": (
                "Resgate manual (click). Sem auto-grant. Catch-up Premium mid-season OK. "
                "Não-resgatadas: claimáveis até o start da próxima season; depois perdidas."
            ),
            "premium_scope": "Premium só em Âmbar, só nesta área, só a season actual.",
            "regulamento": "Ver Regulamento Season Pass (unclaimed, calendário, licença 30 dias).",
        },
    }


def register_season_pass_routes(
    app: Flask,
    *,
    db_ready: Callable[[], bool],
    login_required: Callable,
    steam_id_from_session: Callable[[], str | None],
    limiter: Any | None = None,
) -> None:
    _limit = limiter.limit if limiter else (lambda *a, **k: (lambda f: f))

    @app.route("/api/season-pass/meta", methods=["GET"])
    def season_pass_meta():
        """Metadados públicos (sem progresso do jogador)."""
        season = _season_block()
        price = _premium_price(season["tier"])
        return jsonify({
            "ok": True,
            "placeholder": True,
            "enabled": True,
            "season_name": season["name"],
            "tier": season["tier"],
            "status": season["status"],
            "duration_days": _SEASON_DURATION_DAYS,
            "premium_price_amber": price,
            "premium_price_by_tier": dict(_PREMIUM_PRICE_BY_TIER),
            "xp_thresholds": list(_XP_THRESHOLDS),
            "free_levels": list(_FREE_LEVELS),
            "tier_sequence": list(_SEASON_TIERS),
            "notes": {
                "xp_source": (
                    "XP do passe = Âmbar dos ticks TimedPoints em todos os mapas; "
                    "congela no L30 (Â do tick continua)."
                ),
                "vault_vs_pass": "Meta coletiva ≠ XP do passe; admin agenda o evento.",
                "duration": (
                    f"Season = {_SEASON_DURATION_DAYS} dias (fim automático); "
                    "próxima = start manual admin."
                ),
                "claim": (
                    "Claim manual; catch-up Premium OK; "
                    "unclaimed até next season start — depois perdido."
                ),
                "premium_scope": "Entitlement = season actual; compra só em Âmbar.",
                "regulamento": "Regulamento Season Pass (static/regulamento_season_pass.html).",
            },
        })


    @app.route("/api/season-pass/preview", methods=["GET"])
    def season_pass_preview():
        """Preview público (stub) — sem login; progresso zerado."""
        return jsonify(_placeholder_payload(steam_id=None, premium=False, xp=0))

    @app.route("/api/season-pass/me", methods=["GET"])
    @login_required
    def season_pass_me():
        """Progresso do jogador logado — stub seguro (sem DB ainda)."""
        _ = db_ready
        steam_id = str(steam_id_from_session() or "")
        return jsonify(_placeholder_payload(steam_id=steam_id or None, premium=False, xp=0))

    @app.route("/api/season-pass/premium", methods=["POST"])
    @login_required
    @_limit("10 per hour")
    def season_pass_buy_premium():
        """Compra Premium — stub (sem débito de Âmbar). Canal: só UI SEASON PASS."""
        price = _premium_price()
        return jsonify({
            "ok": False,
            "placeholder": True,
            "error": "Compra do Season Pass Premium ainda não está disponível.",
            "price_amber": price,
            "purchase_ui": "season_pass",
            "entitlement_scope": "current_season",
        }), 501
