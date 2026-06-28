"""Limite de resgates de kits (DefaultAmount / players.kits) — compatível com ArkShop."""
from __future__ import annotations

import json
from typing import Any


def kit_default_amount(entry: dict[str, Any]) -> int:
    """Usos iniciais/restantes quando o jogador ainda não tem entrada no stash."""
    return max(0, int(entry.get("DefaultAmount", 0) or 0))


def kit_has_limit(entry: dict[str, Any]) -> bool:
    """True quando o kit tem limite de resgates (DefaultAmount > 0)."""
    return kit_default_amount(entry) > 0


def parse_kit_stash(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def get_kit_remaining(stash: dict[str, Any], kit_id: str, entry: dict[str, Any]) -> int:
    """Resgates restantes do kit para o jogador."""
    if kit_id in stash:
        return max(0, int((stash.get(kit_id) or {}).get("Amount", 0) or 0))
    return kit_default_amount(entry)


def change_kit_amount(
    stash: dict[str, Any],
    kit_id: str,
    delta: int,
    entry: dict[str, Any],
) -> dict[str, Any]:
    """Aplica delta ao contador de usos (inicializa com DefaultAmount se ausente)."""
    out = dict(stash)
    if kit_id in out:
        current = max(0, int((out[kit_id] or {}).get("Amount", 0) or 0))
    else:
        current = kit_default_amount(entry)
    out[kit_id] = {"Amount": max(0, current + delta)}
    return out


def reset_kit_limit(
    stash: dict[str, Any],
    kit_id: str,
    entry: dict[str, Any],
) -> dict[str, Any]:
    """Restaura resgates ao DefaultAmount (admin revoke)."""
    out = dict(stash)
    limit = kit_default_amount(entry)
    if limit > 0:
        out[kit_id] = {"Amount": limit}
    else:
        out.pop(kit_id, None)
    return out


def kit_limit_status(
    stash: dict[str, Any],
    kit_id: str,
    entry: dict[str, Any],
    *,
    pending_orders: int = 0,
) -> dict[str, int]:
    """Resumo usado/limite/restante para UI admin."""
    limit = kit_default_amount(entry)
    remaining = get_kit_remaining(stash, kit_id, entry)
    effective = max(0, remaining - max(0, pending_orders))
    used = max(0, limit - remaining) if limit > 0 else 0
    return {
        "limit": limit,
        "remaining": remaining,
        "used": used,
        "pending_orders": max(0, pending_orders),
        "effective_remaining": effective,
    }
