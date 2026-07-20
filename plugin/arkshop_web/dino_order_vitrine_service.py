"""Vitrine rotativa de encomenda — 10 slots por porte + até 5 permanentes."""
from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("arkshop_web.dino_order_vitrine")

_DATA_VERSION = 1
ROTATING_SLOTS = 10
MAX_PERMANENT = 5
DEFAULT_ROTATION_DAYS = 7
MIN_ROTATION_DAYS = 1
MAX_ROTATION_DAYS = 90
ROTATION_PRESETS = (7, 15)

# Mix alvo: 6 grande + 2 médio + 2 pequeno
TARGET_MIX: tuple[tuple[str, int], ...] = (
    ("large", 6),
    ("medium", 2),
    ("small", 2),
)
SIZE_ORDER = ("large", "medium", "small")
_SIZE_ALIASES = {
    "large": "large",
    "grande": "large",
    "l": "large",
    "medium": "medium",
    "medio": "medium",
    "médio": "medium",
    "m": "medium",
    "small": "small",
    "pequeno": "small",
    "s": "small",
}

_vitrine_file: Path | None = None
_vanilla_only_fn: Callable[[str], bool] | None = None

# Cache curto de candidatos — evita re-listar catálogo a cada GET/rotate no mesmo segundo.
_CANDIDATES_TTL_S = 30.0
_candidates_cache: dict[str, Any] = {"at": 0.0, "rows": None}
_candidates_lock = __import__("threading").Lock()

# Snapshot admin (slots + meta); candidates paginados à parte. TTL curto — dados mudam pouco.
_SNAPSHOT_TTL_S = 30.0
_snapshot_cache: dict[str, Any] = {"at": 0.0, "sig": None, "payload": None}
_SNAPSHOT_LOCK = __import__("threading").Lock()

DEFAULT_CANDIDATES_LIMIT = 100
MAX_CANDIDATES_LIMIT = 500


def configure_dino_order_vitrine(
    *,
    vitrine_file: Path,
    vanilla_only_fn: Callable[[str], bool] | None = None,
) -> None:
    global _vitrine_file, _vanilla_only_fn
    _vitrine_file = vitrine_file
    _vanilla_only_fn = vanilla_only_fn
    invalidate_vitrine_caches()


def invalidate_vitrine_caches() -> None:
    """Invalida caches de candidatos e snapshot (rotate / permanentes / settings)."""
    with _candidates_lock:
        _candidates_cache["at"] = 0.0
        _candidates_cache["rows"] = None
    with _SNAPSHOT_LOCK:
        _snapshot_cache["at"] = 0.0
        _snapshot_cache["sig"] = None
        _snapshot_cache["payload"] = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _store_path() -> Path:
    if _vitrine_file is None:
        raise ValueError("vitrine_not_configured")
    return _vitrine_file


def normalize_size_class(raw: Any) -> str:
    key = str(raw or "medium").strip().lower()
    return _SIZE_ALIASES.get(key, "medium")


def _default_store() -> dict[str, Any]:
    return {
        "version": _DATA_VERSION,
        "rotation_days": DEFAULT_ROTATION_DAYS,
        "rotation_ends_at": None,
        "rotating_species_keys": [],
        "permanent_species_keys": [],
        "last_rotation_at": None,
        "last_rotation_fallback": False,
        "history": [],
    }


def load_store() -> dict[str, Any]:
    path = _store_path()
    if not path.is_file():
        return _default_store()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("vitrine load failed: %s", exc)
        return _default_store()
    if not isinstance(data, dict):
        return _default_store()
    out = _default_store()
    out.update(data)
    out["version"] = _DATA_VERSION
    out["rotation_days"] = _clamp_days(out.get("rotation_days"))
    out["rotating_species_keys"] = _normalize_key_list(
        out.get("rotating_species_keys"), max_len=ROTATING_SLOTS
    )
    out["permanent_species_keys"] = _normalize_key_list(
        out.get("permanent_species_keys"), max_len=MAX_PERMANENT
    )
    if not isinstance(out.get("history"), list):
        out["history"] = []
    return out


def save_store(data: dict[str, Any]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": _DATA_VERSION,
        "rotation_days": _clamp_days(data.get("rotation_days")),
        "rotation_ends_at": data.get("rotation_ends_at"),
        "rotating_species_keys": _normalize_key_list(
            data.get("rotating_species_keys"), max_len=ROTATING_SLOTS
        ),
        "permanent_species_keys": _normalize_key_list(
            data.get("permanent_species_keys"), max_len=MAX_PERMANENT
        ),
        "last_rotation_at": data.get("last_rotation_at"),
        "last_rotation_fallback": bool(data.get("last_rotation_fallback")),
        "history": list(data.get("history") or [])[-20:],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _clamp_days(raw: Any) -> int:
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = DEFAULT_ROTATION_DAYS
    return max(MIN_ROTATION_DAYS, min(MAX_ROTATION_DAYS, days))


def _normalize_key_list(raw: Any, *, max_len: int) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        key = str(item or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
        if len(out) >= max_len:
            break
    return out


def _parse_iso(raw: Any) -> datetime | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_vanilla(species_key: str) -> bool:
    if _vanilla_only_fn is not None:
        try:
            return bool(_vanilla_only_fn(species_key))
        except Exception:
            return True
    try:
        from market_economy import load_default_species_map

        defn = load_default_species_map().get(species_key) or {}
        return str(defn.get("mod_source") or "vanilla") == "vanilla"
    except Exception:
        return True


def _size_for_key(species_key: str, fallback: str | None = None) -> str:
    if fallback:
        return normalize_size_class(fallback)
    try:
        from market_economy import species_economy_meta_from_defaults

        return normalize_size_class(species_economy_meta_from_defaults(species_key).get("size_class"))
    except Exception:
        return "medium"


def _is_vanilla_cached(species_key: str, defaults: dict[str, Any] | None) -> bool:
    if _vanilla_only_fn is not None:
        try:
            return bool(_vanilla_only_fn(species_key))
        except Exception:
            return True
    if defaults is not None:
        defn = defaults.get(species_key) or {}
        return str(defn.get("mod_source") or "vanilla") == "vanilla"
    return _is_vanilla(species_key)


def _load_candidates_lightweight(db: Any) -> list[dict[str, Any]]:
    """Pool vanilla ACTIVE — sem multipliers, economia completa nem imagens.

    O admin só precisa de key/name/size para o <select>; rotate usa o mesmo pool.
    """
    try:
        from app import MarketSpecies
        from market_service import _filter_commerce_dino_rows
    except Exception as exc:
        log.warning("vitrine candidates import: %s", exc)
        return []

    try:
        from sqlalchemy.orm import load_only

        rows = (
            db.query(MarketSpecies)
            .options(
                load_only(
                    MarketSpecies.id,
                    MarketSpecies.species_key,
                    MarketSpecies.display_name,
                    MarketSpecies.root_value,
                    MarketSpecies.tier,
                    MarketSpecies.blueprint_path,
                    MarketSpecies.status,
                )
            )
            .filter(MarketSpecies.status == "ACTIVE")
            .order_by(MarketSpecies.display_name)
            .all()
        )
    except Exception:
        try:
            rows = (
                db.query(MarketSpecies)
                .filter(MarketSpecies.status == "ACTIVE")
                .order_by(MarketSpecies.display_name)
                .all()
            )
        except Exception as exc:
            log.warning("vitrine candidates query: %s", exc)
            return []

    try:
        rows, _aliases = _filter_commerce_dino_rows(db, rows)
    except Exception as exc:
        log.warning("vitrine candidates filter: %s", exc)
        return []

    defaults: dict[str, Any] | None = None
    try:
        from market_economy import load_default_species_map

        defaults = load_default_species_map()
    except Exception:
        defaults = None

    try:
        from market_economy import friendly_species_display_name
    except Exception:
        friendly_species_display_name = None  # type: ignore[assignment]

    shop_catalog = None
    if friendly_species_display_name is not None:
        try:
            from app import _peek_shop_config

            shop_catalog = _peek_shop_config()
        except Exception:
            try:
                from app import _read_shop_config

                shop_catalog = _read_shop_config()
            except Exception:
                shop_catalog = None

    by_name: dict[str, dict[str, Any]] = {}
    for item in rows:
        sk = str(getattr(item, "species_key", "") or "").strip()
        if not sk or not _is_vanilla_cached(sk, defaults):
            continue
        defn = (defaults or {}).get(sk) or {}
        size = normalize_size_class(defn.get("size_class") or _size_for_key(sk))
        raw_name = getattr(item, "display_name", None) or sk
        if friendly_species_display_name is not None:
            display_name = friendly_species_display_name(
                sk, fallback=raw_name, catalog=shop_catalog
            )
        else:
            display_name = raw_name
        name_key = str(display_name or sk).strip().lower()
        entry = {
            "species_key": sk,
            "display_name": display_name or sk,
            "size_class": size,
            "tier": str(getattr(item, "tier", None) or defn.get("tier") or ""),
            "root_value": int(getattr(item, "root_value", None) or defn.get("root_value") or 0),
            "image_url": "",
        }
        prev = by_name.get(name_key)
        if prev is None:
            by_name[name_key] = entry
            continue
        if int(entry["root_value"]) < int(prev["root_value"]):
            by_name[name_key] = entry
        elif int(entry["root_value"]) == int(prev["root_value"]) and len(sk) < len(
            str(prev["species_key"])
        ):
            by_name[name_key] = entry
    out = list(by_name.values())
    out.sort(key=lambda x: str(x.get("display_name") or "").lower())
    return out


def list_candidate_species(db: Any, *, force_refresh: bool = False) -> list[dict[str, Any]]:
    """Espécies ACTIVE vanilla do mercado com size_class — pool da rotação.

    Cache TTL 30s. Não usa list_species_public (multipliers + imagens = lento).
    """
    now_m = __import__("time").monotonic()
    with _candidates_lock:
        cached = _candidates_cache.get("rows")
        if (
            not force_refresh
            and cached is not None
            and (now_m - float(_candidates_cache.get("at") or 0)) < _CANDIDATES_TTL_S
        ):
            return list(cached)

    out = _load_candidates_lightweight(db)
    with _candidates_lock:
        _candidates_cache["at"] = now_m
        _candidates_cache["rows"] = list(out)
    return out


def page_candidates(
    candidates: list[dict[str, Any]],
    *,
    q: str = "",
    limit: int | None = DEFAULT_CANDIDATES_LIMIT,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int, bool]:
    """Filtra/pagina candidatos para o select admin."""
    filtered = candidates
    needle = str(q or "").strip().lower()
    if needle:
        filtered = [
            c
            for c in candidates
            if needle in str(c.get("display_name") or "").lower()
            or needle in str(c.get("species_key") or "").lower()
        ]
    total = len(filtered)
    try:
        lim = int(limit) if limit is not None else DEFAULT_CANDIDATES_LIMIT
    except (TypeError, ValueError):
        lim = DEFAULT_CANDIDATES_LIMIT
    lim = max(1, min(MAX_CANDIDATES_LIMIT, lim))
    try:
        off = max(0, int(offset or 0))
    except (TypeError, ValueError):
        off = 0
    page = filtered[off : off + lim]
    has_more = (off + len(page)) < total
    return page, total, has_more


def _store_signature(store: dict[str, Any]) -> tuple[Any, ...]:
    return (
        store.get("rotation_days"),
        store.get("rotation_ends_at"),
        store.get("last_rotation_at"),
        tuple(store.get("rotating_species_keys") or []),
        tuple(store.get("permanent_species_keys") or []),
        bool(store.get("last_rotation_fallback")),
    )


def _attach_slot_images(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve imagens só para os ~15 slots (não para o pool inteiro)."""
    try:
        from ark_species_registry import resolve_species_image_for_key
    except Exception:
        return entries
    out: list[dict[str, Any]] = []
    for entry in entries:
        row = dict(entry)
        if not str(row.get("image_url") or "").strip():
            try:
                row["image_url"] = resolve_species_image_for_key(
                    str(row.get("species_key") or ""),
                    tier=str(row.get("tier") or "") or None,
                )
            except Exception:
                row["image_url"] = ""
        out.append(row)
    return out


def draw_rotating_species(
    candidates: list[dict[str, Any]],
    *,
    exclude: set[str] | frozenset[str] | None = None,
    rng: random.Random | None = None,
    slots: int = ROTATING_SLOTS,
) -> tuple[list[str], dict[str, Any]]:
    """Sorteia `slots` espécies com mix 6+2+2.

    Fallback: se um porte não tiver candidatos suficientes, preenche o restante
    a partir dos outros portes (large → medium → small → qualquer restante).
    """
    rng = rng or random.Random()
    exclude = set(exclude or ())
    pool = [
        c
        for c in candidates
        if str(c.get("species_key") or "").strip()
        and str(c["species_key"]).strip() not in exclude
    ]
    by_size: dict[str, list[dict[str, Any]]] = {s: [] for s in SIZE_ORDER}
    for c in pool:
        by_size[normalize_size_class(c.get("size_class"))].append(c)

    picked: list[str] = []
    used: set[str] = set()
    filled_by_target: dict[str, int] = {s: 0 for s in SIZE_ORDER}
    filled_actual: dict[str, int] = {s: 0 for s in SIZE_ORDER}
    fallback_used = False

    def _take_from(bucket: list[dict[str, Any]], n: int) -> list[str]:
        available = [c for c in bucket if str(c["species_key"]) not in used]
        if n <= 0 or not available:
            return []
        chosen = rng.sample(available, k=min(n, len(available)))
        keys = [str(c["species_key"]) for c in chosen]
        for key, c in zip(keys, chosen):
            used.add(key)
            filled_actual[normalize_size_class(c.get("size_class"))] += 1
        return keys

    for size, need in TARGET_MIX:
        got = _take_from(by_size[size], need)
        filled_by_target[size] = len(got)
        picked.extend(got)
        if len(got) < need:
            fallback_used = True

    remaining = slots - len(picked)
    if remaining > 0:
        fallback_used = True
        # Preferência de reposição: portes com maior deficit relativo, depois ordem SIZE_ORDER
        deficit_order = sorted(
            SIZE_ORDER,
            key=lambda s: (
                -(dict(TARGET_MIX).get(s, 0) - filled_by_target.get(s, 0)),
                SIZE_ORDER.index(s),
            ),
        )
        for size in deficit_order:
            if remaining <= 0:
                break
            got = _take_from(by_size[size], remaining)
            picked.extend(got)
            remaining = slots - len(picked)

        if remaining > 0:
            leftover = [c for c in pool if str(c["species_key"]) not in used]
            got = _take_from(leftover, remaining)
            picked.extend(got)

    meta = {
        "requested_mix": {s: n for s, n in TARGET_MIX},
        "filled_by_target": filled_by_target,
        "actual_mix": filled_actual,
        "fallback_used": fallback_used,
        "pool_size": len(pool),
        "drawn": len(picked),
    }
    return picked[:slots], meta


def _append_history(store: dict[str, Any], *, reason: str, keys: list[str], meta: dict[str, Any]) -> None:
    history = list(store.get("history") or [])
    history.append({
        "at": _utcnow().isoformat(),
        "reason": reason,
        "species_keys": list(keys),
        "fallback_used": bool(meta.get("fallback_used")),
        "actual_mix": dict(meta.get("actual_mix") or {}),
    })
    store["history"] = history[-20:]


def _apply_rotation(
    store: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    reason: str,
    rng: random.Random | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or _utcnow()
    days = _clamp_days(store.get("rotation_days"))
    permanents = set(_normalize_key_list(store.get("permanent_species_keys"), max_len=MAX_PERMANENT))
    keys, meta = draw_rotating_species(candidates, exclude=permanents, rng=rng)
    store["rotating_species_keys"] = keys
    store["rotation_days"] = days
    store["rotation_ends_at"] = (now + timedelta(days=days)).isoformat()
    store["last_rotation_at"] = now.isoformat()
    store["last_rotation_fallback"] = bool(meta.get("fallback_used"))
    _append_history(store, reason=reason, keys=keys, meta=meta)
    save_store(store)
    invalidate_vitrine_caches()
    return {
        "rotated": True,
        "reason": reason,
        "rotating_species_keys": keys,
        "rotation_ends_at": store["rotation_ends_at"],
        "meta": meta,
    }


def _needs_rotation(store: dict[str, Any], *, now: datetime | None = None) -> bool:
    now = now or _utcnow()
    ends = _parse_iso(store.get("rotation_ends_at"))
    if ends is None:
        # Nunca rodou (ou store corrompido sem prazo)
        return True
    return now >= ends


def ensure_vitrine(
    db: Any,
    *,
    force: bool = False,
    reason: str = "auto",
    rng: random.Random | None = None,
    now: datetime | None = None,
    candidates_q: str = "",
    candidates_limit: int | None = DEFAULT_CANDIDATES_LIMIT,
    candidates_offset: int = 0,
    include_candidates: bool = True,
) -> dict[str, Any]:
    """Garante vitrine válida; auto-roda se expirada ou incompleta."""
    store = load_store()
    now = now or _utcnow()
    if force or _needs_rotation(store, now=now):
        if force:
            invalidate_vitrine_caches()
        candidates = list_candidate_species(db, force_refresh=force)
        result = _apply_rotation(
            store,
            candidates,
            reason="force" if force else reason,
            rng=rng,
            now=now,
        )
        store = load_store()
        # Reutiliza candidates — evita 2× listagem no mesmo request.
        payload = get_vitrine_snapshot(
            db,
            store=store,
            now=now,
            candidates=candidates,
            candidates_q=candidates_q,
            candidates_limit=candidates_limit,
            candidates_offset=candidates_offset,
            include_candidates=include_candidates,
            use_cache=False,
        )
        payload["rotation"] = result
        return payload
    return get_vitrine_snapshot(
        db,
        store=store,
        now=now,
        candidates_q=candidates_q,
        candidates_limit=candidates_limit,
        candidates_offset=candidates_offset,
        include_candidates=include_candidates,
    )


def get_vitrine_snapshot(
    db: Any,
    *,
    store: dict[str, Any] | None = None,
    now: datetime | None = None,
    candidates: list[dict[str, Any]] | None = None,
    candidates_q: str = "",
    candidates_limit: int | None = DEFAULT_CANDIDATES_LIMIT,
    candidates_offset: int = 0,
    include_candidates: bool = True,
    use_cache: bool = True,
) -> dict[str, Any]:
    store = store or load_store()
    now = now or _utcnow()
    sig = _store_signature(store)
    page_key = (
        sig,
        bool(include_candidates),
        str(candidates_q or ""),
        int(candidates_limit if candidates_limit is not None else DEFAULT_CANDIDATES_LIMIT),
        int(candidates_offset or 0),
    )

    if use_cache and candidates is None:
        now_m = __import__("time").monotonic()
        with _SNAPSHOT_LOCK:
            cached = _snapshot_cache.get("payload")
            if (
                cached is not None
                and _snapshot_cache.get("sig") == page_key
                and (now_m - float(_snapshot_cache.get("at") or 0)) < _SNAPSHOT_TTL_S
            ):
                payload = dict(cached)
                ends = _parse_iso(payload.get("rotation_ends_at"))
                payload["seconds_remaining"] = (
                    max(0, int((ends - now).total_seconds())) if ends is not None else None
                )
                return payload

    if candidates is None:
        candidates = list_candidate_species(db)
    by_key = {str(c["species_key"]): c for c in candidates}

    def _enrich(keys: list[str], *, slot_kind: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for sk in keys:
            base = by_key.get(sk)
            if base is None:
                try:
                    from market_economy import friendly_species_display_name

                    label = friendly_species_display_name(sk, fallback=sk)
                except Exception:
                    label = sk
                base = {
                    "species_key": sk,
                    "display_name": label or sk,
                    "size_class": _size_for_key(sk),
                    "tier": "",
                    "root_value": 0,
                    "image_url": "",
                }
            out.append({**base, "slot_kind": slot_kind})
        return _attach_slot_images(out)

    rotating_keys = _normalize_key_list(store.get("rotating_species_keys"), max_len=ROTATING_SLOTS)
    permanent_keys = _normalize_key_list(store.get("permanent_species_keys"), max_len=MAX_PERMANENT)
    ends = _parse_iso(store.get("rotation_ends_at"))
    seconds_left = None
    if ends is not None:
        seconds_left = max(0, int((ends - now).total_seconds()))

    orderable = list(dict.fromkeys([*rotating_keys, *permanent_keys]))
    cand_page: list[dict[str, Any]] = []
    cand_total = 0
    cand_more = False
    if include_candidates:
        cand_page, cand_total, cand_more = page_candidates(
            candidates,
            q=candidates_q,
            limit=candidates_limit,
            offset=candidates_offset,
        )
    else:
        cand_total = len(candidates)

    payload = {
        "rotation_days": _clamp_days(store.get("rotation_days")),
        "rotation_presets": list(ROTATION_PRESETS),
        "rotation_ends_at": store.get("rotation_ends_at"),
        "seconds_remaining": seconds_left,
        "last_rotation_at": store.get("last_rotation_at"),
        "last_rotation_fallback": bool(store.get("last_rotation_fallback")),
        "rotating_species_keys": rotating_keys,
        "permanent_species_keys": permanent_keys,
        "rotating": _enrich(rotating_keys, slot_kind="rotating"),
        "permanents": _enrich(permanent_keys, slot_kind="permanent"),
        "orderable_species_keys": orderable,
        "orderable_count": len(orderable),
        "max_rotating": ROTATING_SLOTS,
        "max_permanent": MAX_PERMANENT,
        "target_mix": {s: n for s, n in TARGET_MIX},
        "candidates": cand_page,
        "candidates_total": cand_total,
        "candidates_offset": int(candidates_offset or 0),
        "candidates_limit": int(
            candidates_limit if candidates_limit is not None else DEFAULT_CANDIDATES_LIMIT
        ),
        "candidates_has_more": cand_more,
        "candidates_q": str(candidates_q or ""),
        "history": list(store.get("history") or [])[-10:],
    }

    if use_cache:
        now_m = __import__("time").monotonic()
        with _SNAPSHOT_LOCK:
            _snapshot_cache["at"] = now_m
            _snapshot_cache["sig"] = page_key
            # Sem seconds_remaining volátil — recomputa no hit
            cached_body = dict(payload)
            cached_body.pop("seconds_remaining", None)
            _snapshot_cache["payload"] = cached_body

    return payload


def set_rotation_days(days: int) -> dict[str, Any]:
    """Atualiza duração; mantém o fim atual (não reinicia o timer)."""
    store = load_store()
    store["rotation_days"] = _clamp_days(days)
    save_store(store)
    invalidate_vitrine_caches()
    return {
        "rotation_days": store["rotation_days"],
        "rotation_ends_at": store.get("rotation_ends_at"),
    }


def set_permanent_species(species_keys: list[str] | Any) -> dict[str, Any]:
    keys = _normalize_key_list(species_keys, max_len=MAX_PERMANENT + 1)
    if len(keys) > MAX_PERMANENT:
        raise ValueError("permanent_limit_exceeded")
    store = load_store()
    # Permanents não podem duplicar os rotativos atuais — remove do rotating
    permanents = keys[:MAX_PERMANENT]
    prev_rotating = _normalize_key_list(store.get("rotating_species_keys"), max_len=ROTATING_SLOTS)
    rotating = [k for k in prev_rotating if k not in set(permanents)]
    store["permanent_species_keys"] = permanents
    store["rotating_species_keys"] = rotating
    save_store(store)
    invalidate_vitrine_caches()
    return {
        "permanent_species_keys": permanents,
        "rotating_species_keys": rotating,
        "removed_from_rotating": len(prev_rotating) - len(rotating),
    }


def add_permanent_species(species_key: str) -> dict[str, Any]:
    key = str(species_key or "").strip()
    if not key:
        raise ValueError("species_key_required")
    store = load_store()
    permanents = _normalize_key_list(store.get("permanent_species_keys"), max_len=MAX_PERMANENT)
    if key in permanents:
        return {"permanent_species_keys": permanents, "added": False}
    if len(permanents) >= MAX_PERMANENT:
        raise ValueError("permanent_limit_exceeded")
    permanents.append(key)
    return set_permanent_species(permanents) | {"added": True}


def remove_permanent_species(species_key: str) -> dict[str, Any]:
    key = str(species_key or "").strip()
    store = load_store()
    permanents = [
        k
        for k in _normalize_key_list(store.get("permanent_species_keys"), max_len=MAX_PERMANENT)
        if k != key
    ]
    store["permanent_species_keys"] = permanents
    save_store(store)
    invalidate_vitrine_caches()
    return {"permanent_species_keys": permanents, "removed": key}


def force_rotate(
    db: Any,
    *,
    rng: random.Random | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Rodar agora: novo sorteio dos 10 + reinicia timer (now + rotation_days)."""
    return ensure_vitrine(db, force=True, reason="force", rng=rng, now=now)


def orderable_species_keys(db: Any | None = None) -> set[str]:
    """Chaves encomendáveis (rotating ∪ permanent), com auto-rotação se preciso.

    Caminho quente (cotação): só lê o store JSON — não lista todo o catálogo.
    """
    store = load_store()
    if db is not None and _needs_rotation(store):
        ensure_vitrine(db, reason="auto")
        store = load_store()
    return set(
        _normalize_key_list(store.get("rotating_species_keys"), max_len=ROTATING_SLOTS)
        + _normalize_key_list(store.get("permanent_species_keys"), max_len=MAX_PERMANENT)
    )


def is_species_on_vitrine(species_key: str, db: Any | None = None) -> bool:
    key = str(species_key or "").strip()
    if not key:
        return False
    keys = orderable_species_keys(db)
    if key in keys:
        return True
    try:
        from market_economy import canonicalize_species_key

        canon = canonicalize_species_key(key)
        if canon and canon in keys:
            return True
        # Chave canônica na vitrine vs variante pedida (ou o inverso)
        return any(canonicalize_species_key(k) == (canon or key) for k in keys)
    except Exception:
        return False
