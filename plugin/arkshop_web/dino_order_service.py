"""Encomenda de Dino — pedidos jogador-facing (spec ENCOMENDA_DINO MVP)."""
from __future__ import annotations

import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from custom_dino_service import (
    DEFAULT_LEVEL,
    ITEM_TYPE,
    STAT_MAX,
    _parse_payload,
    _row_val,
    _utcnow,
    is_custom_dino_enabled,
    validate_payload,
)
from market_economy import (
    calculate_suggested_value,
    load_default_species_map,
    normalize_stat_points,
    size_cap_for_class,
)

log = logging.getLogger("arkshop_web.dino_order")

ORDER_SOURCE = "dino_encomenda"
ORDER_SOURCE_JSON_LIKE = '%"order_source": "dino_encomenda"%'
PRICING_VERSION = 1
RATE_LIMIT_ORDERS = 3
RATE_LIMIT_DAYS = 7

_DEFAULT_PRICING = {
    "alpha": 0.25,
    "beta": 0.35,
    "delta_uniform": 0.08,
    "delta_base": 0.05,
    "delta_region": 0.02,
    "kappa": 1.15,
    "absolute_max": 500_000,
    "auto_approve_max": 200_000,
}

_settings_fn: Callable[[], dict[str, Any]] | None = None
_debit_fn: Callable[[Session, str, int], int] | None = None
_credit_fn: Callable[[Session, str, int], int] | None = None
_get_points_fn: Callable[[str], int | None] | None = None


def configure_dino_order(
    *,
    settings_fn: Callable[[], dict[str, Any]] | None = None,
    debit_fn: Callable[[Session, str, int], int] | None = None,
    credit_fn: Callable[[Session, str, int], int] | None = None,
    get_player_points_fn: Callable[[str], int | None] | None = None,
) -> None:
    global _settings_fn, _debit_fn, _credit_fn, _get_points_fn
    _settings_fn = settings_fn
    _debit_fn = debit_fn
    _credit_fn = credit_fn
    _get_points_fn = get_player_points_fn


def is_dino_order_enabled() -> bool:
    if _settings_fn is None:
        return False
    return bool(_settings_fn().get("dino_order_enabled", False))


def get_pricing_config() -> dict[str, Any]:
    cfg = dict(_DEFAULT_PRICING)
    if _settings_fn is None:
        return cfg
    s = _settings_fn()
    for key in _DEFAULT_PRICING:
        raw = s.get(f"dino_order_{key}")
        if raw is None:
            continue
        try:
            if key in ("absolute_max", "auto_approve_max"):
                cfg[key] = max(0, int(raw))
            else:
                cfg[key] = float(raw)
        except (TypeError, ValueError):
            continue
    return cfg


def _species_mod_source(species_key: str) -> str:
    defn = load_default_species_map().get(species_key) or {}
    return str(defn.get("mod_source") or "vanilla")


def _resolve_species_economy(db: Session, species_key: str) -> Any | None:
    """Espécie ACTIVE no mercado com economia completa."""
    try:
        from app import MarketSpecies, MarketSpeciesStatMultiplier
        from market_service import species_row_to_economy

        row = (
            db.query(MarketSpecies)
            .filter(
                MarketSpecies.species_key == species_key,
                MarketSpecies.status == "ACTIVE",
            )
            .first()
        )
        if not row:
            return None
        mult_rows = (
            db.query(MarketSpeciesStatMultiplier)
            .filter(MarketSpeciesStatMultiplier.species_id == row.id)
            .all()
        )
        return species_row_to_economy(row, mult_rows)
    except Exception as exc:
        log.debug("dino_order species db lookup: %s", exc)
        return None


def _species_image(species_key: str, tier: str | None = None) -> str:
    try:
        from ark_species_registry import get_registry_entry, resolve_species_image

        return resolve_species_image(get_registry_entry(species_key), tier=tier) or ""
    except Exception:
        return ""


def list_gallery_species(db: Session) -> list[dict[str, Any]]:
    """Espécies vanilla ACTIVE elegíveis para encomenda."""
    if not is_dino_order_enabled():
        return []
    try:
        from market_service import list_species_public

        rows = list_species_public(db, active_only=True)
    except Exception as exc:
        log.warning("dino_order gallery: %s", exc)
        return []

    cfg = get_pricing_config()
    out: list[dict[str, Any]] = []
    for item in rows:
        sk = str(item.get("species_key") or "")
        if _species_mod_source(sk) != "vanilla":
            continue
        economy = _resolve_species_economy(db, sk)
        if economy is None:
            continue
        min_quote = quote(
            {
                "species_key": sk,
                "level": DEFAULT_LEVEL,
                "gender": "female",
                "colors": [0, 0, 0, 0, 0, 0],
                "stat_points": {},
            },
            db=db,
            pricing_cfg=cfg,
        )
        out.append({
            "species_key": sk,
            "display_name": item.get("display_name") or sk,
            "tier": item.get("tier") or "",
            "root_value": int(item.get("root_value") or 0),
            "size_class": item.get("size_class") or "medium",
            "image_url": item.get("image_url") or _species_image(sk, item.get("tier")),
            "starting_price": int(min_quote.get("total") or 0),
        })
    out.sort(key=lambda x: str(x.get("display_name") or "").lower())
    return out


def calc_color_component(root_value: int, colors: list[int], cfg: dict[str, Any]) -> int:
    r = max(0, int(root_value))
    if not colors or all(int(c) <= 0 for c in colors):
        return 0
    non_default = [int(c) for c in colors if int(c) > 0]
    if not non_default:
        return 0
    distinct = set(non_default)
    if len(distinct) == 1 and len(non_default) == len(colors):
        return round(r * float(cfg["delta_uniform"]))
    base = round(r * float(cfg["delta_base"]))
    regions = sum(1 for c in colors if int(c) > 0)
    return base + regions * round(r * float(cfg["delta_region"]))


def _normalize_player_spec(raw: dict[str, Any]) -> dict[str, Any]:
    spec = dict(raw or {})
    stat_raw = spec.get("stat_points") or spec.get("stat_points_requested") or {}
    pts: dict[str, int] = {}
    if isinstance(stat_raw, dict):
        for key in ("health", "melee"):
            if key not in stat_raw:
                continue
            try:
                val = int(stat_raw[key])
            except (TypeError, ValueError):
                continue
            pts[key] = max(0, min(STAT_MAX, val))
    spec["stat_points"] = pts
    return spec


def _build_validate_body(spec: dict[str, Any]) -> dict[str, Any]:
    body = {
        "species_key": spec.get("species_key"),
        "level": spec.get("level", DEFAULT_LEVEL),
        "gender": spec.get("gender", "female"),
        "neutered": bool(spec.get("neutered")),
        "colors": spec.get("colors") or [0, 0, 0, 0, 0, 0],
        "deliver_as": "cryopod",
        "note": str(spec.get("note") or "Encomenda web — dino customizado"),
        "spawn_exact": {"enabled": False},
    }
    return body


def quote(
    spec: dict[str, Any],
    *,
    db: Session | None = None,
    pricing_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Cotação sem débito — retorna breakdown + total."""
    cfg = pricing_cfg or get_pricing_config()
    spec = _normalize_player_spec(spec)
    species_key = str(spec.get("species_key") or "").strip()
    if not species_key:
        raise ValueError("species_key obrigatório")

    if db is None:
        raise ValueError("db_required")
    economy = _resolve_species_economy(db, species_key)
    if economy is None:
        raise ValueError("species_not_available")
    if _species_mod_source(species_key) != "vanilla":
        raise ValueError("species_not_vanilla")

    stat_points = normalize_stat_points(spec.get("stat_points") or {})
    market_value, market_breakdown = calculate_suggested_value(economy, stat_points)
    r = int(economy.root_value)
    colors = [int(c) for c in (spec.get("colors") or [0] * 6)]
    color_component = calc_color_component(r, colors, cfg)
    base_surcharge = round(r * float(cfg["alpha"]))
    service_premium = round((market_value + color_component) * float(cfg["beta"]))
    subtotal = market_value + color_component + base_surcharge + service_premium
    floor = max(market_value, r)
    ceiling_species = round(size_cap_for_class(economy.size_class) * float(cfg["kappa"]))
    ceiling = min(ceiling_species, int(cfg["absolute_max"]))
    total = max(floor, min(subtotal, ceiling))

    quote_id = f"qt_{secrets.token_hex(6)}"
    return {
        "quote_id": quote_id,
        "quoted_at": _utcnow().isoformat(),
        "species_key": species_key,
        "species_display_name": economy.display_name,
        "root_value": r,
        "stats_component": market_value,
        "color_component": color_component,
        "base_surcharge": base_surcharge,
        "service_premium": service_premium,
        "subtotal": subtotal,
        "floor": floor,
        "ceiling": ceiling,
        "total": total,
        "market_equivalent": market_value,
        "market_breakdown": market_breakdown,
        "pricing_version": PRICING_VERSION,
        "service_surcharge_pct": round(float(cfg["beta"]) * 100),
        "auto_approve": total <= int(cfg["auto_approve_max"]),
    }


def _weekly_order_count(db: Session, steam_id: str) -> int:
    since = (_utcnow() - timedelta(days=RATE_LIMIT_DAYS)).replace(tzinfo=None)
    row = db.execute(
        text(
            "SELECT COUNT(*) FROM orders "
            "WHERE steam_id = :sid AND item_type = :it AND points_spent > 0 "
            "AND created_at >= :since AND payload_json LIKE :src"
        ),
        {
            "sid": steam_id,
            "it": ITEM_TYPE,
            "since": since,
            "src": ORDER_SOURCE_JSON_LIKE,
        },
    ).fetchone()
    return int(row[0] if row else 0)


def _new_order_id() -> str:
    return f"de_{uuid.uuid4().hex[:12]}"


def _order_to_player_dict(row: Any) -> dict[str, Any]:
    payload = _parse_payload(_row_val(row, "payload_json"))
    pricing = payload.get("pricing") if isinstance(payload.get("pricing"), dict) else {}
    return {
        "order_id": str(_row_val(row, "order_id", "")),
        "status": str(_row_val(row, "status", "")),
        "points_spent": int(_row_val(row, "points_spent", 0) or 0),
        "species_key": payload.get("species_key"),
        "species_display_name": payload.get("species_display_name"),
        "level": payload.get("level"),
        "gender": payload.get("gender"),
        "colors": payload.get("colors"),
        "stat_points_requested": payload.get("stat_points_requested"),
        "pricing": pricing,
        "created_at": _row_val(row, "created_at"),
        "updated_at": _row_val(row, "updated_at"),
        "last_error": _row_val(row, "last_error"),
    }


def list_player_orders(
    db: Session,
    steam_id: str,
    *,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(50, page_size))
    params: dict[str, Any] = {
        "sid": steam_id,
        "it": ITEM_TYPE,
        "src": ORDER_SOURCE_JSON_LIKE,
        "lim": page_size,
        "off": (page - 1) * page_size,
    }
    where = (
        "steam_id = :sid AND item_type = :it AND points_spent > 0 "
        "AND payload_json LIKE :src"
    )
    count_row = db.execute(text(f"SELECT COUNT(*) FROM orders WHERE {where}"), params).fetchone()
    total = int(count_row[0] if count_row else 0)
    rows = db.execute(
        text(f"SELECT * FROM orders WHERE {where} ORDER BY created_at DESC LIMIT :lim OFFSET :off"),
        params,
    ).fetchall()
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "orders": [_order_to_player_dict(r) for r in rows],
    }


def list_admin_queue(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 25,
    status: str | None = None,
) -> dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    statuses = ("AGUARDANDO_APROVACAO", "FALHA")
    params: dict[str, Any] = {
        "it": ITEM_TYPE,
        "src": ORDER_SOURCE_JSON_LIKE,
        "lim": page_size,
        "off": (page - 1) * page_size,
    }
    where = "item_type = :it AND payload_json LIKE :src AND points_spent > 0"
    if status:
        st = status.strip().upper()
        where += " AND status = :st"
        params["st"] = st
    else:
        where += " AND status IN ('AGUARDANDO_APROVACAO', 'FALHA')"
    count_row = db.execute(text(f"SELECT COUNT(*) FROM orders WHERE {where}"), params).fetchone()
    total = int(count_row[0] if count_row else 0)
    rows = db.execute(
        text(f"SELECT * FROM orders WHERE {where} ORDER BY created_at ASC LIMIT :lim OFFSET :off"),
        params,
    ).fetchall()
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "orders": [_order_to_player_dict(r) for r in rows],
    }


def checkout(
    db: Session,
    steam_id: str,
    spec: dict[str, Any],
    *,
    server_id: str = "default",
) -> dict[str, Any]:
    if not is_dino_order_enabled():
        raise ValueError("dino_order_disabled")
    if not is_custom_dino_enabled():
        raise ValueError("custom_dino_disabled")
    if _debit_fn is None:
        raise ValueError("dino_order_not_configured")

    spec = _normalize_player_spec(spec)
    if _weekly_order_count(db, steam_id) >= RATE_LIMIT_ORDERS:
        raise ValueError("rate_limit_exceeded")

    body = _build_validate_body(spec)
    payload, err = validate_payload(body, require_note=False)
    if err or payload is None:
        raise ValueError(err or "invalid_spec")

    species_key = str(spec.get("species_key") or "")
    if _species_mod_source(species_key) != "vanilla":
        raise ValueError("species_not_vanilla")

    q = quote(spec, db=db)
    total = int(q["total"])
    if total <= 0:
        raise ValueError("invalid_price")

    if _get_points_fn:
        balance = _get_points_fn(steam_id)
        if balance is not None and balance < total:
            raise ValueError("insufficient_balance")

    status = "PENDENTE" if q.get("auto_approve") else "AGUARDANDO_APROVACAO"

    payload["order_source"] = ORDER_SOURCE
    payload["created_by"] = steam_id
    payload["created_at"] = _utcnow().isoformat()
    payload["stat_points_requested"] = dict(spec.get("stat_points") or {})
    payload["pricing"] = {
        "version": PRICING_VERSION,
        "root_value": q["root_value"],
        "stats_component": q["stats_component"],
        "color_component": q["color_component"],
        "base_surcharge": q["base_surcharge"],
        "service_surcharge_pct": q["service_surcharge_pct"],
        "service_surcharge": q["service_premium"],
        "service_premium": q["service_premium"],
        "total": total,
        "market_equivalent": q["market_equivalent"],
        "quote_id": q["quote_id"],
        "quoted_at": q["quoted_at"],
    }

    order_id = _new_order_id()
    now = _utcnow().replace(tzinfo=None)

    _debit_fn(db, steam_id, total)

    db.execute(
        text(
            "INSERT INTO orders "
            "(order_id, steam_id, server_id, item_type, item_id, amount, points_spent, status, "
            "retry_count, contested, payload_json, created_at, updated_at) "
            "VALUES (:oid, :sid, :srv, :it, :iid, 1, :pts, :st, 0, 0, :pj, :now, :now)"
        ),
        {
            "oid": order_id,
            "sid": steam_id,
            "srv": server_id,
            "it": ITEM_TYPE,
            "iid": order_id,
            "pts": total,
            "st": status,
            "pj": json.dumps(payload, ensure_ascii=False),
            "now": now,
        },
    )
    return {
        "order_id": order_id,
        "status": status,
        "points_spent": total,
        "pricing": payload["pricing"],
        "payload": payload,
    }


def approve_order(db: Session, order_id: str, *, admin_steam_id: str) -> dict[str, Any]:
    row = db.execute(
        text(
            "SELECT * FROM orders WHERE order_id = :oid AND item_type = :it LIMIT 1"
        ),
        {"oid": order_id, "it": ITEM_TYPE},
    ).fetchone()
    if not row:
        raise ValueError("order_not_found")
    payload = _parse_payload(_row_val(row, "payload_json"))
    if payload.get("order_source") != ORDER_SOURCE:
        raise ValueError("not_dino_encomenda")
    status = str(_row_val(row, "status", ""))
    if status != "AGUARDANDO_APROVACAO":
        raise ValueError("invalid_status")
    now = _utcnow().replace(tzinfo=None)
    db.execute(
        text(
            "UPDATE orders SET status = 'PENDENTE', updated_at = :now, "
            "last_error = NULL WHERE order_id = :oid AND status = 'AGUARDANDO_APROVACAO'"
        ),
        {"now": now, "oid": order_id},
    )
    payload["approved_by"] = admin_steam_id
    payload["approved_at"] = _utcnow().isoformat()
    db.execute(
        text("UPDATE orders SET payload_json = :pj WHERE order_id = :oid"),
        {"pj": json.dumps(payload, ensure_ascii=False), "oid": order_id},
    )
    return {"order_id": order_id, "status": "PENDENTE", "approved_by": admin_steam_id}


def reject_order(
    db: Session,
    order_id: str,
    *,
    admin_steam_id: str,
    reason: str = "",
) -> dict[str, Any]:
    if _credit_fn is None:
        raise ValueError("dino_order_not_configured")
    row = db.execute(
        text("SELECT * FROM orders WHERE order_id = :oid AND item_type = :it LIMIT 1"),
        {"oid": order_id, "it": ITEM_TYPE},
    ).fetchone()
    if not row:
        raise ValueError("order_not_found")
    payload = _parse_payload(_row_val(row, "payload_json"))
    if payload.get("order_source") != ORDER_SOURCE:
        raise ValueError("not_dino_encomenda")
    status = str(_row_val(row, "status", ""))
    if status not in ("AGUARDANDO_APROVACAO", "FALHA"):
        raise ValueError("invalid_status")
    refund = int(_row_val(row, "points_spent", 0) or 0)
    steam_id = str(_row_val(row, "steam_id", ""))
    now = _utcnow().replace(tzinfo=None)
    new_balance = _credit_fn(db, steam_id, refund) if refund > 0 else None
    payload["rejected_by"] = admin_steam_id
    payload["rejected_at"] = _utcnow().isoformat()
    if reason:
        payload["reject_reason"] = reason[:500]
    db.execute(
        text(
            "UPDATE orders SET status = 'REJEITADO', updated_at = :now, "
            "last_error = :err, payload_json = :pj "
            "WHERE order_id = :oid"
        ),
        {
            "now": now,
            "oid": order_id,
            "err": (reason or "Rejeitado pelo admin")[:2000],
            "pj": json.dumps(payload, ensure_ascii=False),
        },
    )
    return {
        "order_id": order_id,
        "status": "REJEITADO",
        "refunded": refund,
        "new_balance": new_balance,
        "rejected_by": admin_steam_id,
    }
