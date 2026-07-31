"""Season Pass — config persistente (calendário + preço Premium + recompensas).

Armazenamento: JSON em data dir (mesmo padrão de dino_order_vitrine).
Calendário / XP / grants: ver season_pass_service.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("arkshop_web.season_pass")

_DATA_VERSION = 1
_GRANT_TYPES = frozenset({"amber", "dino", "item", "kit", "license"})
_SEASON_TIERS = ("Delta", "Gamma", "Beta", "Alfa", "Omega", "Transcendente")
_FREE_LEVELS = tuple(n for n in range(4, 29, 4))
_PREMIUM_LEVELS = tuple(range(1, 31))

# Curva progressiva (§15.5): delta(n) = max(1, round(B * 1.25**(n-1))).
# B=3 → Free L28 = 6.192 XP (≤ budget 7.500 @ 30d×5h); L30 = 9.682 XP (freeze).
# B=4 rejeitado: XP_cum(28)=8.257 > 7.500. L1=B (pequeno) — pacing Free prioritário.
XP_BASE = 3
XP_GROWTH = 1.25
MAX_LEVEL = 30


def xp_delta(level: int, *, base: int = XP_BASE, growth: float = XP_GROWTH) -> int:
    """Custo (Δ) para subir ao nível `level` (1-based)."""
    n = int(level)
    if n < 1:
        raise ValueError("xp_delta_level_invalid")
    return max(1, round(int(base) * (float(growth) ** (n - 1))))


def build_xp_thresholds(
    *,
    levels: int = MAX_LEVEL,
    base: int = XP_BASE,
    growth: float = XP_GROWTH,
) -> list[int]:
    """XP cumulativo por nível: sum(delta(1)..delta(L))."""
    out: list[int] = []
    total = 0
    for n in range(1, int(levels) + 1):
        total += xp_delta(n, base=base, growth=growth)
        out.append(total)
    return out


_XP_THRESHOLDS = build_xp_thresholds()
MAX_XP = int(_XP_THRESHOLDS[-1]) if _XP_THRESHOLDS else 0

_DEFAULT_PREMIUM_PRICE: dict[str, int] = {
    "Delta": 15_000,
    "Gamma": 18_000,
    "Beta": 22_000,
    "Alfa": 28_000,
    "Omega": 35_000,
    "Transcendente": 45_000,
}

_config_file: Path | None = None
_claims_file: Path | None = None
_lock = threading.RLock()


def configure_season_pass(*, config_file: Path, claims_file: Path) -> None:
    global _config_file, _claims_file
    _config_file = config_file
    _claims_file = claims_file
    config_file.parent.mkdir(parents=True, exist_ok=True)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _utcnow()).astimezone(timezone.utc).isoformat()


def _config_path() -> Path:
    if _config_file is None:
        raise ValueError("season_pass_not_configured")
    return _config_file


def _claims_path() -> Path:
    if _claims_file is None:
        raise ValueError("season_pass_not_configured")
    return _claims_file


def _amber(amount: int, *, label: str | None = None) -> dict[str, Any]:
    amt = int(amount)
    return {
        "type": "amber",
        "id": None,
        "qty": amt,
        "days": None,
        "label": label or f"{amt:,}".replace(",", ".") + " Â",
    }


def _pending(
    gtype: str,
    label: str,
    *,
    qty: int = 1,
    days: int | None = None,
    grant_id: str | None = None,
) -> dict[str, Any]:
    return {
        "type": gtype,
        "id": grant_id,
        "qty": int(qty),
        "days": days,
        "label": label,
    }


def default_delta_config() -> dict[str, Any]:
    """Seed §15.6.1–15.6.2 — Â tipado; kits/dinos/items/licenses com IDs CustomShop."""
    free: dict[str, list[dict[str, Any]]] = {
        "4": [_amber(500)],
        "8": [_pending("kit", "Kit Recursos Emergencial (~stock/consumíveis)", grant_id="recursos")],
        "12": [_amber(1500)],
        "16": [
            _pending("item", "Cryopod", grant_id="cryopod"),
            _pending("dino", "Moschops L1 comum", grant_id="moschops"),
        ],
        "20": [_amber(3000)],
        "24": [
            _pending(
                "kit",
                "Kit selas vanilla (Raptor+Trike+Argentavis, Q100)",
                grant_id="kit_selas_vanilla",
            )
        ],
        "28": [_amber(5000)],
    }
    premium: dict[str, list[dict[str, Any]]] = {
        "1": [_amber(250)],
        "2": [_amber(500)],
        "3": [_amber(750)],
        "4": [
            _amber(400),
            _pending("item", "Rede de Mergulho (utilitário leve)", grant_id="dipping_net"),
        ],
        "5": [_amber(1000)],
        "6": [_pending("item", "Sushi Daco (consumível leve)", grant_id="daco_sushi")],
        "7": [_amber(1000)],
        "8": [
            _amber(500),
            _pending("item", "Basic Kibble (1000x)", grant_id="kibble_basic"),
        ],
        "9": [_amber(2000)],
        "10": [_pending("dino", "Parasaur L1 comum", grant_id="parasaur")],
        "11": [_amber(2000)],
        "12": [
            _amber(750),
            _pending("item", "Poção Médica (1000x)", grant_id="rec_medicalbrew"),
        ],
        "13": [_pending("dino", "Raptor L1 mid", grant_id="raptor")],
        "14": [_amber(2500)],
        "15": [_amber(2500, label="Boost curto (ou 2.500 Â)")],
        "16": [
            _amber(1000),
            _pending("item", "Estimulante (1000x)", grant_id="rec_stimulant"),
        ],
        "17": [_amber(3000)],
        "18": [
            _pending("item", "Foice ItensAlfa Delta", grant_id="foice_delta"),
        ],
        "19": [_amber(4000)],
        "20": [
            _amber(1200),
            _pending("item", "Soul Traps (utilitário leve)", grant_id="item_soultraps_20"),
        ],
        "21": [_pending("dino", "Moschops L1 fêmea", grant_id="moschops")],
        "22": [_amber(5500)],
        "23": [_pending("dino", "Parasaur L1 fêmea", grant_id="parasaur")],
        "24": [
            _amber(1500),
            _pending("item", "Sela de Raptor (Q100)", grant_id="sela_raptor"),
        ],
        "25": [
            _pending(
                "kit",
                "Kit selas vanilla (Raptor+Trike+Argentavis, Q100)",
                grant_id="kit_selas_vanilla",
            )
        ],
        "26": [
            _pending(
                "license",
                "Renovação parcial licença Delta (ou 7.500 Â)",
                days=5,
                grant_id="Delta",
            ),
        ],
        "27": [_pending("kit", "Kit Recursos Emergencial (utilitário mid)", grant_id="recursos")],
        "28": [
            _amber(2000),
            _pending("item", "Picareta ItensAlfa Delta", grant_id="picareta_delta"),
        ],
        "29": [
            _pending(
                "license",
                "Licença Delta 30 dias (ou Â catálogo se tier superior)",
                days=30,
                grant_id="Delta",
            ),
        ],
        "30": [_amber(20000)],
    }
    return {
        "version": _DATA_VERSION,
        "current_tier": "Delta",
        "duration_days": 30,
        "season_id": None,
        "starts_at": None,
        "ends_at": None,
        "tier_sequence": list(_SEASON_TIERS),
        "premium_price_by_tier": dict(_DEFAULT_PREMIUM_PRICE),
        "xp_thresholds": list(_XP_THRESHOLDS),
        "free_levels": list(_FREE_LEVELS),
        "free_rewards": free,
        "premium_rewards": premium,
        # Meta colectiva (§15.8) — Â into vault toward goal; ≠ Pass XP / ≠ vault balance
        "meta_target_amber": 0,
        "meta_reached": False,
        "meta_reached_at": None,
        "meta_event_at": None,
        "meta_event_notes": "",
        "updated_at": None,
        "updated_by_steam_id": None,
    }


def _normalize_meta_fields(raw: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    """Normaliza campos da meta colectiva persistidos na config da season."""
    try:
        target = int(raw.get("meta_target_amber", base.get("meta_target_amber", 0)) or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("meta_target_amber_invalid") from exc
    if target < 0:
        raise ValueError("meta_target_amber_negative")

    def _opt_iso(key: str) -> str | None:
        val = raw.get(key, base.get(key))
        if val is None or str(val).strip() == "":
            return None
        return str(val).strip()[:64]

    notes = raw.get("meta_event_notes", base.get("meta_event_notes", ""))
    if notes is None:
        notes = ""
    notes = str(notes).strip()[:2000]
    reached = bool(raw.get("meta_reached", base.get("meta_reached", False)))
    return {
        "meta_target_amber": target,
        "meta_reached": reached,
        "meta_reached_at": _opt_iso("meta_reached_at"),
        "meta_event_at": _opt_iso("meta_event_at"),
        "meta_event_notes": notes,
    }


def grant_ready(grant: dict[str, Any]) -> bool:
    """True se o grant tem IDs/qty mínimos para um motor futuro entregar."""
    gtype = str(grant.get("type") or "")
    if gtype == "amber":
        try:
            return int(grant.get("qty") or 0) > 0
        except (TypeError, ValueError):
            return False
    if gtype == "license":
        gid = str(grant.get("id") or "").strip()
        try:
            days = int(grant.get("days") or 0)
        except (TypeError, ValueError):
            days = 0
        return bool(gid) and days > 0
    if gtype in ("dino", "item", "kit"):
        return bool(str(grant.get("id") or "").strip())
    return False


def normalize_grant(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("grant_must_be_object")
    gtype = str(raw.get("type") or "").strip().lower()
    if gtype not in _GRANT_TYPES:
        raise ValueError(f"grant_type_invalid:{gtype or '?'}")
    label = str(raw.get("label") or "").strip()
    gid_raw = raw.get("id")
    gid = None if gid_raw is None or str(gid_raw).strip() == "" else str(gid_raw).strip()
    try:
        qty = int(raw.get("qty") if raw.get("qty") is not None else (raw.get("amount") or 1))
    except (TypeError, ValueError) as exc:
        raise ValueError("grant_qty_invalid") from exc
    if qty < 0:
        raise ValueError("grant_qty_negative")
    days = raw.get("days")
    days_out: int | None = None
    if days is not None and str(days).strip() != "":
        try:
            days_out = int(days)
        except (TypeError, ValueError) as exc:
            raise ValueError("grant_days_invalid") from exc
        if days_out < 0:
            raise ValueError("grant_days_negative")
    if gtype == "amber" and not label:
        label = f"{qty:,}".replace(",", ".") + " Â"
    if not label:
        label = f"{gtype}:{gid or '?'}"
    out = {
        "type": gtype,
        "id": gid,
        "qty": qty,
        "days": days_out,
        "label": label[:200],
    }
    out["grant_ready"] = grant_ready(out)
    # sku_pending some quando o ID/qty mínimos existirem (outro agente preenche SKUs).
    out["delivery"] = "ready" if out["grant_ready"] else "sku_pending"
    return out


def _normalize_reward_map(
    raw: Any,
    *,
    allowed_levels: tuple[int, ...],
) -> dict[str, list[dict[str, Any]]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("rewards_must_be_object")
    allowed = {str(n) for n in allowed_levels}
    out: dict[str, list[dict[str, Any]]] = {}
    for key, grants in raw.items():
        k = str(key).strip()
        if k not in allowed:
            raise ValueError(f"level_not_allowed:{k}")
        if grants is None:
            continue
        if not isinstance(grants, list):
            raise ValueError(f"grants_must_be_list:L{k}")
        if len(grants) > 8:
            raise ValueError(f"too_many_grants:L{k}")
        out[k] = [normalize_grant(g) for g in grants]
    return out


def annotate_grants(grants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_grant(g) for g in grants]


def grants_label(grants: list[dict[str, Any]]) -> str:
    if not grants:
        return "—"
    return " + ".join(str(g.get("label") or g.get("type")) for g in grants)


def delivery_summary(grants: list[dict[str, Any]]) -> dict[str, Any]:
    ready = sum(1 for g in grants if g.get("grant_ready"))
    pending = len(grants) - ready
    return {
        "grants_total": len(grants),
        "grants_ready": ready,
        "grants_sku_pending": pending,
        "in_game_delivery": ready > 0 and pending == 0,
        "note": (
            "Pronto para entrega (Â imediato; kit/item/dino → fila PENDENTE; licença → entitlement)."
            if pending == 0 and grants
            else (
                f"{pending} grant(s) com SKU pendente — claim bloqueado até preencher ID."
                if pending
                else "Sem grants configurados."
            )
        ),
    }


def normalize_config(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    base = default_delta_config()
    if not raw:
        cfg = base
    else:
        if not isinstance(raw, dict):
            raise ValueError("config_must_be_object")
        tier = str(raw.get("current_tier") or base["current_tier"]).strip()
        if tier not in _SEASON_TIERS:
            raise ValueError(f"tier_invalid:{tier}")
        try:
            duration = int(raw.get("duration_days") or base["duration_days"])
        except (TypeError, ValueError) as exc:
            raise ValueError("duration_invalid") from exc
        if duration < 1 or duration > 365:
            raise ValueError("duration_out_of_range")
        prices_raw = raw.get("premium_price_by_tier") or base["premium_price_by_tier"]
        if not isinstance(prices_raw, dict):
            raise ValueError("premium_price_by_tier_invalid")
        prices: dict[str, int] = {}
        for t in _SEASON_TIERS:
            try:
                prices[t] = int(prices_raw.get(t, _DEFAULT_PREMIUM_PRICE[t]))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"premium_price_invalid:{t}") from exc
            if prices[t] < 0:
                raise ValueError(f"premium_price_negative:{t}")
        free = _normalize_reward_map(
            raw.get("free_rewards", base["free_rewards"]),
            allowed_levels=_FREE_LEVELS,
        )
        premium = _normalize_reward_map(
            raw.get("premium_rewards", base["premium_rewards"]),
            allowed_levels=_PREMIUM_LEVELS,
        )
        season_id = raw.get("season_id")
        if season_id is not None and str(season_id).strip() == "":
            season_id = None
        elif season_id is not None:
            season_id = str(season_id).strip()[:80]
        starts_at = raw.get("starts_at")
        ends_at = raw.get("ends_at")
        if starts_at is not None and str(starts_at).strip() == "":
            starts_at = None
        if ends_at is not None and str(ends_at).strip() == "":
            ends_at = None
        meta = _normalize_meta_fields(raw, base)
        cfg = {
            "version": _DATA_VERSION,
            "current_tier": tier,
            "duration_days": duration,
            "season_id": season_id,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "tier_sequence": list(_SEASON_TIERS),
            "premium_price_by_tier": prices,
            "xp_thresholds": list(_XP_THRESHOLDS),
            "free_levels": list(_FREE_LEVELS),
            "free_rewards": free,
            "premium_rewards": premium,
            **meta,
            "updated_at": raw.get("updated_at"),
            "updated_by_steam_id": raw.get("updated_by_steam_id"),
        }
    # Annotate grant_ready on all grants
    for bucket in ("free_rewards", "premium_rewards"):
        annotated: dict[str, list[dict[str, Any]]] = {}
        for lv, grants in (cfg.get(bucket) or {}).items():
            annotated[str(lv)] = annotate_grants(grants)
        cfg[bucket] = annotated
    return cfg


def load_config() -> dict[str, Any]:
    with _lock:
        path = _config_path()
        if not path.is_file():
            cfg = normalize_config(None)
            _write_config_unlocked(cfg)
            return cfg
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("season_pass config load failed: %s — reseeding defaults", exc)
            cfg = normalize_config(None)
            _write_config_unlocked(cfg)
            return cfg
        try:
            return normalize_config(data if isinstance(data, dict) else None)
        except ValueError as exc:
            log.warning("season_pass config invalid (%s) — reseeding defaults", exc)
            cfg = normalize_config(None)
            _write_config_unlocked(cfg)
            return cfg


def _write_config_unlocked(cfg: dict[str, Any]) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = {
        "version": _DATA_VERSION,
        "current_tier": cfg["current_tier"],
        "duration_days": cfg["duration_days"],
        "season_id": cfg.get("season_id"),
        "starts_at": cfg.get("starts_at"),
        "ends_at": cfg.get("ends_at"),
        "tier_sequence": cfg["tier_sequence"],
        "premium_price_by_tier": cfg["premium_price_by_tier"],
        "xp_thresholds": cfg["xp_thresholds"],
        "free_levels": cfg["free_levels"],
        "free_rewards": cfg["free_rewards"],
        "premium_rewards": cfg["premium_rewards"],
        "meta_target_amber": int(cfg.get("meta_target_amber") or 0),
        "meta_reached": bool(cfg.get("meta_reached")),
        "meta_reached_at": cfg.get("meta_reached_at"),
        "meta_event_at": cfg.get("meta_event_at"),
        "meta_event_notes": str(cfg.get("meta_event_notes") or ""),
        "updated_at": cfg.get("updated_at"),
        "updated_by_steam_id": cfg.get("updated_by_steam_id"),
    }
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def save_config(
    raw: dict[str, Any],
    *,
    updated_by_steam_id: str | None = None,
    preserve_calendar: bool = True,
) -> dict[str, Any]:
    with _lock:
        merged = dict(raw or {})
        if preserve_calendar:
            # Admin PUT de rewards/preço não deve apagar o calendário activo.
            try:
                existing = None
                path = _config_path()
                if path.is_file():
                    existing = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                existing = None
            if isinstance(existing, dict):
                for key in ("season_id", "starts_at", "ends_at"):
                    if key not in merged or merged.get(key) in (None, ""):
                        if existing.get(key) not in (None, ""):
                            merged[key] = existing.get(key)
                # Meta: preservar quando omitida no PUT (admin não apaga latch/agenda por acidente)
                for key in (
                    "meta_reached",
                    "meta_reached_at",
                    "meta_target_amber",
                    "meta_event_at",
                    "meta_event_notes",
                ):
                    if key not in raw and key in existing:
                        merged[key] = existing[key]
        cfg = normalize_config(merged)
        cfg["updated_at"] = _iso()
        cfg["updated_by_steam_id"] = (updated_by_steam_id or "").strip() or None
        _write_config_unlocked(cfg)
        return cfg


def premium_price(cfg: dict[str, Any] | None = None, tier: str | None = None) -> int:
    c = cfg or load_config()
    t = tier or c.get("current_tier") or "Delta"
    prices = c.get("premium_price_by_tier") or _DEFAULT_PREMIUM_PRICE
    return int(prices.get(t, prices.get("Delta", 15_000)))


def rewards_for(cfg: dict[str, Any], track: str, level: int) -> list[dict[str, Any]]:
    bucket = "free_rewards" if track == "free" else "premium_rewards"
    return list((cfg.get(bucket) or {}).get(str(level)) or [])


def level_from_xp(xp: int, thresholds: list[int] | None = None) -> dict[str, Any]:
    thr = thresholds or list(_XP_THRESHOLDS)
    xp = max(0, int(xp))
    level = 0
    for i, t in enumerate(thr, start=1):
        if xp >= t:
            level = i
        else:
            prev = thr[i - 2] if i > 1 else 0
            return {
                "level": level,
                "next_level": i,
                "xp": xp,
                "xp_into_level": xp - prev,
                "xp_for_next": t - prev,
                "xp_to_next": t - xp,
                "next_threshold": t,
                "max_level": len(thr),
            }
    return {
        "level": level,
        "next_level": None,
        "xp": xp,
        "xp_into_level": 0,
        "xp_for_next": 0,
        "xp_to_next": 0,
        "next_threshold": thr[-1] if thr else 0,
        "max_level": len(thr),
    }


# ── Claim queue (intended grants; no in-game delivery) ────────────────────────


def _empty_claims() -> dict[str, Any]:
    return {"version": _DATA_VERSION, "claims": []}


def load_claims() -> dict[str, Any]:
    with _lock:
        path = _claims_path()
        if not path.is_file():
            return _empty_claims()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("season_pass claims load failed: %s", exc)
            return _empty_claims()
        if not isinstance(data, dict):
            return _empty_claims()
        claims = data.get("claims")
        if not isinstance(claims, list):
            data["claims"] = []
        data["version"] = _DATA_VERSION
        return data


def _save_claims_unlocked(data: dict[str, Any]) -> None:
    path = _claims_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = {"version": _DATA_VERSION, "claims": list(data.get("claims") or [])}
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def claim_key(steam_id: str, season_id: str, track: str, level: int) -> str:
    return f"{steam_id}:{season_id}:{track}:{level}"


def find_claim(
    claims: dict[str, Any],
    *,
    steam_id: str,
    season_id: str,
    track: str,
    level: int,
) -> dict[str, Any] | None:
    key = claim_key(steam_id, season_id, track, level)
    for row in claims.get("claims") or []:
        if isinstance(row, dict) and row.get("key") == key:
            return row
    return None


def enqueue_claim(
    *,
    steam_id: str,
    season_id: str,
    tier: str,
    track: str,
    level: int,
    grants: list[dict[str, Any]],
) -> dict[str, Any]:
    """Regista claim pretendido. Não entrega Â/kits/dinos no jogo."""
    if track not in ("free", "premium"):
        raise ValueError("track_invalid")
    if track == "free" and level not in _FREE_LEVELS:
        raise ValueError("free_level_invalid")
    if track == "premium" and level not in _PREMIUM_LEVELS:
        raise ValueError("premium_level_invalid")
    annotated = annotate_grants(grants)
    summary = delivery_summary(annotated)
    with _lock:
        data = load_claims()
        existing = find_claim(
            data, steam_id=steam_id, season_id=season_id, track=track, level=level
        )
        if existing:
            return {
                "already_queued": True,
                "claim": existing,
                "delivery": summary,
            }
        row = {
            "key": claim_key(steam_id, season_id, track, level),
            "steam_id": steam_id,
            "season_id": season_id,
            "tier": tier,
            "track": track,
            "level": int(level),
            "grants": annotated,
            "status": "queued_not_delivered",
            "in_game_delivered": False,
            "delivery_summary": summary,
            "created_at": _iso(),
        }
        data.setdefault("claims", []).append(row)
        # Keep last 5000 claims
        if len(data["claims"]) > 5000:
            data["claims"] = data["claims"][-5000:]
        _save_claims_unlocked(data)
        return {
            "already_queued": False,
            "claim": row,
            "delivery": summary,
        }


def player_claimed_set(
    steam_id: str,
    season_id: str,
) -> set[tuple[str, int]]:
    data = load_claims()
    out: set[tuple[str, int]] = set()
    for row in data.get("claims") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("steam_id")) != steam_id:
            continue
        if str(row.get("season_id")) != season_id:
            continue
        track = str(row.get("track") or "")
        try:
            lv = int(row.get("level"))
        except (TypeError, ValueError):
            continue
        if track in ("free", "premium"):
            out.add((track, lv))
    return out
