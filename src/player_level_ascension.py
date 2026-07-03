"""Modelo de níveis do jogador ARK — base, ascensões e bônus extras."""
from __future__ import annotations

import json
from typing import Any

ARK_DEFAULT_BASE_LEVEL = 105
TIER_BONUSES = (0, 5, 10, 15)  # nenhum, γ, β, α (cumulativo por mapa)

# (id, rótulo, boss)
ASCENSION_BOSSES: tuple[tuple[str, str, str], ...] = (
    ("island", "The Island", "Overseer"),
    ("scorched", "Scorched Earth", "Manticore"),
    ("aberration", "Aberration", "Rockwell"),
    ("extinction", "Extinction", "King Titan"),
    ("genesis1", "Genesis Pt.1", "Corrupted Master Controller"),
    ("genesis2", "Genesis Pt.2", "Rockwell Prime"),
    ("volcano", "The Volcano", "Volcano Guardian"),
)

# (id, rótulo, níveis)
EXTRA_BONUSES: tuple[tuple[str, str, int], ...] = (
    ("explorer_notes", "Notas de Explorador (todas)", 10),
    ("fjordur_runes", "Runas de Fjordur", 10),
    ("chibi", "Chibi nível 6", 5),
    ("aquatica", "Aquatica (DLC)", 5),
    ("pygocentrus", "Alpha Pygocentrus (Steam)", 15),
)

TIER_LABELS = ("—", "γ +5", "β +10", "α +15")


def tier_bonus(tier: int) -> int:
    idx = max(0, min(3, int(tier or 0)))
    return TIER_BONUSES[idx]


def calc_ascension_bonus(boss_tiers: dict[str, int]) -> int:
    total = 0
    for boss_id, _label, _boss in ASCENSION_BOSSES:
        total += tier_bonus(int(boss_tiers.get(boss_id, 0) or 0))
    return total


def calc_extra_bonus(extras: dict[str, bool]) -> int:
    total = 0
    for eid, _label, pts in EXTRA_BONUSES:
        if extras.get(eid):
            total += pts
    return total


def calc_total_player_level(
    base_level: int,
    boss_tiers: dict[str, int],
    extras: dict[str, bool],
) -> int:
    base = int(base_level or 0) or ARK_DEFAULT_BASE_LEVEL
    return base + calc_ascension_bonus(boss_tiers) + calc_extra_bonus(extras)


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


def empty_ascension_state() -> dict[str, Any]:
    return {
        "bosses": {bid: 0 for bid, _, _ in ASCENSION_BOSSES},
        "extras": {eid: False for eid, _, _ in EXTRA_BONUSES},
    }


def parse_ascension_state(raw: str | None) -> dict[str, Any]:
    if not raw or not str(raw).strip():
        return empty_ascension_state()
    try:
        data = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return empty_ascension_state()
    base = empty_ascension_state()
    bosses = data.get("bosses") if isinstance(data, dict) else {}
    extras = data.get("extras") if isinstance(data, dict) else {}
    if isinstance(bosses, dict):
        for bid, _, _ in ASCENSION_BOSSES:
            try:
                base["bosses"][bid] = max(0, min(3, int(bosses.get(bid, 0) or 0)))
            except (TypeError, ValueError):
                pass
    if isinstance(extras, dict):
        for eid, _, _ in EXTRA_BONUSES:
            base["extras"][eid] = bool(extras.get(eid))
    return base


def serialize_ascension_state(boss_tiers: dict[str, int], extras: dict[str, bool]) -> str:
    payload = {
        "bosses": {bid: max(0, min(3, int(boss_tiers.get(bid, 0) or 0))) for bid, _, _ in ASCENSION_BOSSES},
        "extras": {eid: bool(extras.get(eid)) for eid, _, _ in EXTRA_BONUSES},
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def resolve_max_player_level(cfg: object) -> int:
    """Nível máximo efetivo para exibição (web / cards)."""
    override_xp = int(getattr(cfg, "override_max_xp_player", 0) or 0)
    if override_xp > 0:
        return xp_to_level(override_xp)

    gs = getattr(cfg, "game_settings", None)
    if gs is not None:
        gs_xp = int(getattr(gs, "override_max_experience_points_player", 0) or 0)
        if gs_xp > 0:
            return xp_to_level(gs_xp)
        cap = int(getattr(gs, "player_level_cap", 0) or 0)
        if cap > 0:
            return cap

    base = int(getattr(cfg, "player_base_level", 0) or 0)
    if base <= 0 and gs is not None:
        base = int(getattr(gs, "player_base_level", 0) or 0)
    state_raw = str(getattr(cfg, "player_ascension_state", "") or "")
    if gs is not None and not state_raw.strip():
        state_raw = str(getattr(gs, "player_ascension_state", "") or "")
    if base > 0 or state_raw.strip():
        st = parse_ascension_state(state_raw)
        return calc_total_player_level(
            base or ARK_DEFAULT_BASE_LEVEL,
            st["bosses"],
            st["extras"],
        )

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
