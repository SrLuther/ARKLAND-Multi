"""Modelo de níveis do jogador ARK — nível base + bônus fixos (+100)."""
from __future__ import annotations

import json
from typing import Any

ARK_DEFAULT_BASE_LEVEL = 105

# Bônus fixos após o nível base (farmável só com XP).
# 75 na rampa INI (5 mapas × α +15) + 25 de conquistas (notas, runas, chibi).
ARK_BOSS_ASCENSION_LEVELS = 75
ARK_CONQUEST_LEVELS = 25  # notas +10, runas +10, chibi +5
ARK_TOTAL_BONUS_LEVELS = ARK_BOSS_ASCENSION_LEVELS + ARK_CONQUEST_LEVELS  # 100

# Mapas com ascensão α (+15 cada) — entram nos 75 slots da rampa.
ASCENSION_BOSSES: tuple[tuple[str, str, str], ...] = (
    ("island", "The Island", "Overseer"),
    ("scorched", "Scorched Earth", "Manticore"),
    ("aberration", "Aberration", "Rockwell"),
    ("genesis1", "Genesis Pt.1", "Corrupted Master Controller"),
    ("genesis2", "Genesis Pt.2", "Rockwell Prime"),
)

# Conquistas fora dos 75 slots da rampa (+25 total).
CONQUEST_BONUSES: tuple[tuple[str, str, int], ...] = (
    ("explorer_notes", "Notas de Explorador (todas)", 10),
    ("fjordur_runes", "Runas de Fjordur", 10),
    ("chibi", "Chibi nível 6", 5),
)

# Legado — mantido para parse de configs antigas.
EXTRA_BONUSES = CONQUEST_BONUSES
TIER_BONUSES = (0, 5, 10, 15)
TIER_LABELS = ("—", "γ +5", "β +10", "α +15")


def calc_max_total_level(base_level: int) -> int:
    """Teto absoluto do servidor: base + 100 (bosses + conquistas)."""
    base = max(1, int(base_level or 0)) or ARK_DEFAULT_BASE_LEVEL
    return base + ARK_TOTAL_BONUS_LEVELS


def calc_ascension_bonus(_boss_tiers: dict[str, int] | None = None) -> int:
    """Bônus de boss na rampa — fixo +75 no modelo ARKLAND."""
    return ARK_BOSS_ASCENSION_LEVELS


def calc_extra_bonus(_extras: dict[str, bool] | None = None) -> int:
    """Bônus de conquistas — fixo +25 no modelo ARKLAND."""
    return ARK_CONQUEST_LEVELS


def calc_total_player_level(
    base_level: int,
    _boss_tiers: dict[str, int] | None = None,
    _extras: dict[str, bool] | None = None,
) -> int:
    return calc_max_total_level(base_level)


def level_to_xp(level: int) -> int:
    from .ark_ini import _level_to_xp

    return _level_to_xp(max(0, int(level)))


def xp_to_level(xp: int) -> int:
    """Converte XP acumulado (curva vanilla) em nível-teto aproximado."""
    target = max(0, int(xp or 0))
    if target <= 0:
        return 0
    lo, hi = 1, 500
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if level_to_xp(mid) <= target:
            lo = mid
        else:
            hi = mid - 1
    return lo


def default_ascension_state() -> dict[str, Any]:
    """Estado canônico: servidor habilita o caminho completo (+100)."""
    return {
        "bosses": {bid: 3 for bid, _, _ in ASCENSION_BOSSES},
        "extras": {eid: True for eid, _, _ in CONQUEST_BONUSES},
    }


def empty_ascension_state() -> dict[str, Any]:
    return default_ascension_state()


def parse_ascension_state(raw: str | None) -> dict[str, Any]:
    """Aceita JSON legado; retorna sempre o modelo canônico (+100)."""
    if raw and str(raw).strip():
        try:
            json.loads(str(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    return default_ascension_state()


def serialize_ascension_state(
    _boss_tiers: dict[str, int] | None = None,
    _extras: dict[str, bool] | None = None,
) -> str:
    st = default_ascension_state()
    return json.dumps(st, ensure_ascii=False, separators=(",", ":"))


def _difficulty_fallback_level(cfg: object) -> int:
    """Teto legado por dificuldade oficial (servidores sem painel de ascensão)."""
    gs = getattr(cfg, "game_settings", None)
    from .server_config_snapshot import _is_tek

    if _is_tek(cfg):
        if getattr(cfg, "enable_difficulty_override", False):
            diff = float(getattr(cfg, "override_official_difficulty", 5.0) or 5.0)
            return 105 + int(round(diff * 15))
        return ARK_DEFAULT_BASE_LEVEL
    if gs is not None:
        diff = float(getattr(gs, "override_official_difficulty", 5.0) or 5.0)
        return 105 + int(round(diff * 15))
    return ARK_DEFAULT_BASE_LEVEL


def resolve_theoretical_player_level(cfg: object) -> int:
    """Teto teórico: base + 100."""
    base = int(getattr(cfg, "player_base_level", 0) or 0)
    gs = getattr(cfg, "game_settings", None)
    if base <= 0 and gs is not None:
        base = int(getattr(gs, "player_base_level", 0) or 0)
    if base > 0:
        return calc_max_total_level(base)

    if gs is not None:
        cap = int(getattr(gs, "player_level_cap", 0) or 0)
        if cap > 0:
            return cap

    override_xp = int(getattr(cfg, "override_max_xp_player", 0) or 0)
    if override_xp > 0:
        return xp_to_level(override_xp)

    if gs is not None:
        gs_xp = int(getattr(gs, "override_max_experience_points_player", 0) or 0)
        if gs_xp > 0:
            return xp_to_level(gs_xp)

    return _difficulty_fallback_level(cfg)


def resolve_max_player_level(cfg: object) -> int:
    """Nível máximo exibido (Web / cards) — base + 100 quando configurado."""
    from .player_level_ramp import resolve_effective_ingame_cap

    return resolve_effective_ingame_cap(cfg)
