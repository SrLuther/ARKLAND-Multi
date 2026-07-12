"""Dino Lab — entrega administrativa de dinos customizados (spec DINO_LAB v1.0, Fase 0)."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

log = logging.getLogger("arkshop_web.custom_dino")

ITEM_TYPE = "custom_dino"
SCHEMA_VERSION = 1
COLOR_REGIONS = 6
COLOR_MIN = 0
COLOR_MAX = 255
LEVEL_MIN = 1
DEFAULT_LEVEL = 150
RATE_LIMIT_PER_HOUR = 30
STALE_ENTREGANDO_MINUTES_DEFAULT = 5
STAT_COUNT = 7
STAT_MAX = 254
STAT_NAMES = ("health", "stamina", "oxygen", "food", "weight", "melee", "speed")

_settings_fn: Callable[[], dict[str, Any]] | None = None


def configure_custom_dino(*, settings_fn: Callable[[], dict[str, Any]] | None = None) -> None:
    global _settings_fn
    _settings_fn = settings_fn


def is_custom_dino_enabled() -> bool:
    if _settings_fn is None:
        return False
    return bool(_settings_fn().get("custom_dino_enabled", False))


def is_custom_dino_spawn_exact_enabled() -> bool:
    if _settings_fn is None:
        return False
    return bool(_settings_fn().get("custom_dino_spawn_exact", False))


def get_stale_entregando_minutes() -> int:
    """Minutos antes de reabrir pedidos ENTREGANDO presos (0 = desabilitado)."""
    if _settings_fn is None:
        return STALE_ENTREGANDO_MINUTES_DEFAULT
    raw = _settings_fn().get("custom_dino_stale_entregando_minutes", STALE_ENTREGANDO_MINUTES_DEFAULT)
    try:
        return max(0, int(raw if raw is not None else STALE_ENTREGANDO_MINUTES_DEFAULT))
    except (TypeError, ValueError):
        return STALE_ENTREGANDO_MINUTES_DEFAULT


def recover_stale_entregando_custom_dino_orders(
    db: Session,
    steam_id: str,
    *,
    minutes: int | None = None,
) -> int:
    """Reabre pedidos ENTREGANDO cujo claim expirou (plugin crashou ou travou)."""
    stale_minutes = get_stale_entregando_minutes() if minutes is None else max(0, int(minutes))
    if stale_minutes <= 0:
        return 0
    cutoff = (_utcnow() - timedelta(minutes=stale_minutes)).replace(tzinfo=None)
    now = _utcnow().replace(tzinfo=None)
    result = db.execute(
        text(
            "UPDATE orders SET status = 'PENDENTE', updated_at = :now, "
            "last_error = :err, retry_count = retry_count + 1 "
            "WHERE steam_id = :sid AND item_type = :it AND status = 'ENTREGANDO' "
            "AND updated_at < :cutoff"
        ),
        {
            "now": now,
            "cutoff": cutoff,
            "sid": steam_id,
            "it": ITEM_TYPE,
            "err": "Recuperado automaticamente: entrega anterior expirou (timeout ENTREGANDO)",
        },
    )
    recovered = int(getattr(result, "rowcount", 0) or 0)
    if recovered:
        log.warning(
            "custom_dino: recovered %s stale ENTREGANDO order(s) for %s (>%s min)",
            recovered,
            steam_id,
            stale_minutes,
        )
    return recovered


def get_custom_dino_level_max() -> int:
    """Teto total de nível (0 = sem limite; só valida 0–STAT_MAX por stat)."""
    if _settings_fn is None:
        return 0
    raw = _settings_fn().get("custom_dino_level_max", 0)
    try:
        return max(0, int(raw or 0))
    except (TypeError, ValueError):
        return 0


def _validate_total_level(level: int) -> str | None:
    if level < LEVEL_MIN:
        return f"Nível mínimo é {LEVEL_MIN}."
    cap = get_custom_dino_level_max()
    if cap > 0 and level > cap:
        return (
            f"Nível ({level}) excede o limite configurado ({cap}). "
            f"Ajuste wild/tamed/nível ou altere custom_dino_level_max em Configurações (0 = sem limite total)."
        )
    return None


def ensure_custom_dino_schema(engine: Engine) -> None:
    """Adiciona payload_json em orders se ausente (idempotente)."""
    is_sqlite = "sqlite" in str(engine.url).lower()
    with engine.connect() as conn:
        if is_sqlite:
            if not _table_exists(conn, "orders"):
                return
            cols = {str(r[1]) for r in conn.execute(text("PRAGMA table_info(orders)")).fetchall()}
            if "payload_json" not in cols:
                conn.execute(text("ALTER TABLE orders ADD COLUMN payload_json TEXT NULL"))
                conn.commit()
                log.info("orders: coluna payload_json adicionada (sqlite)")
            return
        row = conn.execute(text("SHOW TABLES LIKE 'orders'")).fetchone()
        if row is None:
            return
        col = conn.execute(text("SHOW COLUMNS FROM `orders` LIKE 'payload_json'")).fetchone()
        if col is None:
            conn.execute(text("ALTER TABLE `orders` ADD COLUMN `payload_json` TEXT NULL"))
            conn.commit()
            log.info("orders: coluna payload_json adicionada (mysql)")


def _table_exists(conn: Any, table: str) -> bool:
    row = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
        {"t": table},
    ).fetchone()
    return row is not None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _format_blueprint(path: str) -> str:
    """Canonical ``Blueprint'/Game/.../Class.Class'`` (strip quotes / nested wraps)."""
    p = (path or "").strip()
    if not p:
        return ""

    def _strip_outer_quotes(s: str) -> str:
        while len(s) >= 2 and (
            (s[0] == "'" and s[-1] == "'") or (s[0] == '"' and s[-1] == '"')
        ):
            s = s[1:-1].strip()
        return s

    p = _strip_outer_quotes(p)
    # Unwrap nested Blueprint'Blueprint'/Game/...'...'
    for _ in range(4):
        if p.startswith("Blueprint'") and p.endswith("'") and len(p) > 11:
            inner = _strip_outer_quotes(p[10:-1].strip())
            if inner.startswith("Blueprint'"):
                p = inner
                continue
            p = inner
            break
        break

    if not p:
        return ""
    if p.startswith("Blueprint'"):
        return p
    if not p.startswith("/"):
        p = f"/{p}" if p.startswith("Game/") else f"/Game/{p}"
    return f"Blueprint'{p}'"


def _is_valid_blueprint_raw(path: str) -> bool:
    formatted = _format_blueprint(path)
    if not formatted:
        return False
    if formatted.startswith("Blueprint'") and formatted.endswith("'"):
        inner = formatted[10:-1].strip()
        return bool(inner) and inner.startswith("/Game/")
    return False


def _blueprint_inner(path: str) -> str:
    formatted = _format_blueprint(path)
    if formatted.startswith("Blueprint'") and formatted.endswith("'"):
        return formatted[10:-1].strip()
    return formatted


def _looks_like_dino_species_blueprint(path: str) -> bool:
    """Rejeita blueprints obviamente nao-dino (sela, item, arma, etc.)."""
    inner = _blueprint_inner(path).lower()
    if not inner.startswith("/game/"):
        return False
    forbidden = (
        "primalitem",
        "saddle",
        "primalstructure",
        "weapon",
        "consumable",
        "emote",
        "buff_",
        "skin",
        "costume",
        "armor",
        "cryopod",
        "eggitem",
        "supplycrate",
        "beacon",
    )
    if any(token in inner for token in forbidden):
        return False
    if "character_bp" in inner:
        return True
    if "_character." in inner:
        return True
    if "/dinos/" in inner and "_bp." in inner:
        return True
    stem = inner.rsplit(".", 1)[0]
    if stem.endswith("_bp"):
        return True
    return False


def _validate_species_blueprint(path: str) -> str | None:
    if not _is_valid_blueprint_raw(path):
        return "Blueprint inválido (use Blueprint'/Game/...' ou /Game/...)."
    if not _looks_like_dino_species_blueprint(path):
        return (
            "Blueprint não parece ser de criatura (ex.: sela, item ou estrutura). "
            "Use um Character_BP de dino."
        )
    return None

def _species_catalog() -> dict[str, dict[str, Any]]:
    try:
        from market_economy import load_default_species_map

        return dict(load_default_species_map())
    except Exception as exc:
        log.warning("custom_dino species catalog: %s", exc)
        return {}


def list_species_admin(*, vanilla_only: bool = False) -> list[dict[str, Any]]:
    """Lista espécies homologadas para Dino Lab — deduplicada por species_key.

    Prioridade: market_species (DB) → market_species_defaults.json → catálogo shop (Type:dino).
    """
    seen: set[str] = set()
    items: list[dict[str, Any]] = []

    try:
        import app as app_module

        session_factory = app_module._SessionLocal
        if session_factory is not None:
            from app import MarketSpecies

            db = session_factory()
            try:
                rows = (
                    db.query(MarketSpecies)
                    .filter(MarketSpecies.status.in_(("ACTIVE", "PRE_REGISTERED")))
                    .order_by(MarketSpecies.display_name)
                    .all()
                )
                defaults = _species_catalog()
                for row in rows:
                    key = str(row.species_key or "").strip()
                    if not key or key in seen:
                        continue
                    defn = defaults.get(key, {})
                    bp = (
                        str(row.blueprint_path or "").strip()
                        or _blueprint_from_catalog(defn)
                        or _blueprint_from_catalog_item(key)
                    )
                    if not bp:
                        continue
                    if not _looks_like_dino_species_blueprint(bp):
                        continue
                    mod = _infer_mod_source(bp, defn)
                    if vanilla_only and mod != "vanilla":
                        continue
                    seen.add(key)
                    items.append({
                        "species_key": key,
                        "display_name": str(row.display_name or defn.get("display_name") or key),
                        "blueprint_path": _format_blueprint(bp),
                        "mod_source": mod,
                        "tier": str(row.tier or defn.get("tier") or ""),
                    })
            finally:
                db.close()
    except Exception as exc:
        log.debug("list_species_admin db: %s", exc)

    for key, defn in sorted(
        _species_catalog().items(),
        key=lambda kv: str(kv[1].get("display_name") or kv[0]),
    ):
        if key in seen:
            continue
        bp = (
            str(defn.get("blueprint_path") or "").strip()
            or _blueprint_from_catalog(defn)
            or _blueprint_from_catalog_item(key)
        )
        if not bp:
            continue
        if not _looks_like_dino_species_blueprint(bp):
            continue
        mod = _infer_mod_source(bp, defn)
        if vanilla_only and mod != "vanilla":
            continue
        seen.add(key)
        items.append({
            "species_key": key,
            "display_name": str(defn.get("display_name") or key),
            "blueprint_path": _format_blueprint(bp),
            "mod_source": mod,
            "tier": str(defn.get("tier") or ""),
        })

    # Fallback: dinos Type:dino do config.json ainda sem defaults/DB.
    try:
        from market_economy import (
            _catalog_item_blueprint,
            _species_key_from_catalog_item_id,
            iter_catalog_dinos,
        )

        from app import _read_shop_config

        catalog = _read_shop_config()
        for item_id, entry in iter_catalog_dinos(catalog, level1_only=True):
            sk = _species_key_from_catalog_item_id(item_id)
            if sk in seen or item_id in seen:
                continue
            bp = str(_catalog_item_blueprint(entry) or "").strip()
            if not bp or not _looks_like_dino_species_blueprint(bp):
                continue
            mod = _infer_mod_source(bp, {})
            if vanilla_only and mod != "vanilla":
                continue
            display = str(entry.get("Name") or entry.get("Description") or sk).strip()
            for suffix in (" Fêmea Nível 1", " Nível 1", " Level 1"):
                if display.endswith(suffix):
                    display = display[: -len(suffix)].strip()
            if display.endswith(")") and "(" in display:
                display = display[: display.rfind("(")].strip()
            seen.add(sk)
            items.append({
                "species_key": sk,
                "display_name": display or sk,
                "blueprint_path": _format_blueprint(bp),
                "mod_source": mod,
                "tier": "",
                "catalog_item_id": item_id,
            })
    except Exception as exc:
        log.debug("list_species_admin catalog fallback: %s", exc)

    items.sort(key=lambda s: str(s.get("display_name") or s.get("species_key") or "").lower())
    return items


def _infer_mod_source(blueprint: str, defn: dict[str, Any] | None = None) -> str:
    """Rótulo de origem — defaults JSON ou pasta do mod no blueprint."""
    defn = defn or {}
    mod = str(defn.get("mod_source") or "").strip()
    if mod and mod != "vanilla":
        return mod
    inner = _blueprint_inner(blueprint).lower()
    if "/game/mods/" in inner:
        parts = inner.split("/game/mods/", 1)[1].split("/")
        if parts and parts[0]:
            return parts[0].replace(" ", "_").lower()
    return mod or "vanilla"


def _blueprint_from_catalog_item(item_id: str) -> str:
    """Blueprint de um item Type:dino do config.json (ex.: sb_drake_fire)."""
    item_id = str(item_id or "").strip()
    if not item_id:
        return ""
    try:
        from market_economy import _catalog_item_blueprint

        from app import _read_shop_config

        catalog = _read_shop_config()
        items = (
            catalog.get("Items")
            or catalog.get("items")
            or catalog.get("ShopItems")
            or {}
        )
        entry = items.get(item_id) or items.get(item_id.lower())
        if isinstance(entry, dict) and str(entry.get("Type") or "").lower() == "dino":
            return str(_catalog_item_blueprint(entry) or "").strip()
    except Exception as exc:
        log.debug("blueprint catalog item lookup: %s", exc)
    return ""


def _blueprint_from_catalog(defn: dict[str, Any]) -> str:
    ref_id = str(
        defn.get("reference_catalog_item_id") or defn.get("catalog_item_id") or ""
    ).strip()
    if not ref_id:
        return ""
    return _blueprint_from_catalog_item(ref_id)


def calc_spawn_exact_level(wild_stats: list[int], tamed_stats: list[int]) -> int:
    """Nível efetivo ARK: 1 + soma(wild) + soma(tamed)."""
    return 1 + sum(wild_stats) + sum(tamed_stats)


def _parse_stat_array(raw: Any, *, label: str) -> tuple[list[int] | None, str | None]:
    if not isinstance(raw, list) or len(raw) != STAT_COUNT:
        return None, f"{label} deve ter exatamente {STAT_COUNT} valores."
    out: list[int] = []
    for i, v in enumerate(raw):
        try:
            n = int(v)
        except (TypeError, ValueError):
            return None, f"{label}[{i}] inválido."
        if n < 0 or n > STAT_MAX:
            return None, f"Cada stat em {label} deve estar entre 0 e {STAT_MAX}."
        out.append(n)
    return out, None


def _normalize_imprint_pct(raw: Any) -> float:
    try:
        pct = float(raw or 0)
    except (TypeError, ValueError):
        return 0.0
    if pct > 1.0:
        pct /= 100.0
    return max(0.0, min(1.0, pct))


def _resolve_species_from_db(species_key: str) -> dict[str, Any] | None:
    """Resolve espécie homologada em market_species (feed do catálogo)."""
    try:
        import app as app_module

        session_factory = app_module._SessionLocal
        if session_factory is None:
            return None
        from app import MarketSpecies

        db = session_factory()
        try:
            row = (
                db.query(MarketSpecies)
                .filter(MarketSpecies.species_key == species_key)
                .filter(MarketSpecies.status.in_(("ACTIVE", "PRE_REGISTERED")))
                .first()
            )
            if not row:
                return None
            defn = _species_catalog().get(species_key, {})
            bp = (
                str(row.blueprint_path or "").strip()
                or _blueprint_from_catalog(defn)
                or _blueprint_from_catalog_item(species_key)
            )
            if not bp:
                return None
            return {
                "species_key": species_key,
                "display_name": str(row.display_name or defn.get("display_name") or species_key),
                "species_blueprint": _format_blueprint(bp),
                "mod_source": _infer_mod_source(bp, defn),
            }
        finally:
            db.close()
    except Exception as exc:
        log.debug("_resolve_species_from_db: %s", exc)
    return None


def _resolve_species(species_key: str) -> dict[str, Any] | None:
    species_key = str(species_key or "").strip()
    if not species_key:
        return None

    defn = _species_catalog().get(species_key, {})
    bp = (
        str(defn.get("blueprint_path") or "").strip()
        or _blueprint_from_catalog(defn)
        or _blueprint_from_catalog_item(species_key)
    )
    display_name = str(defn.get("display_name") or species_key)

    if not bp:
        # Tentar species_key derivado do item_id (ex.: meraxes_femea → meraxes).
        try:
            from market_economy import _species_key_from_catalog_item_id

            alt = _species_key_from_catalog_item_id(species_key)
            if alt and alt != species_key:
                defn = _species_catalog().get(alt, {})
                bp = (
                    str(defn.get("blueprint_path") or "").strip()
                    or _blueprint_from_catalog(defn)
                    or _blueprint_from_catalog_item(alt)
                    or _blueprint_from_catalog_item(species_key)
                )
                if bp:
                    species_key = alt
                    display_name = str(defn.get("display_name") or alt)
        except Exception:
            pass

    if not bp:
        return _resolve_species_from_db(species_key)
    return {
        "species_key": species_key,
        "display_name": display_name,
        "species_blueprint": _format_blueprint(bp),
        "mod_source": _infer_mod_source(bp, defn),
    }


def _payload_to_quote_spec(payload: dict[str, Any]) -> dict[str, Any]:
    """Converte payload Dino Lab → spec de cotação (encomenda / simulação)."""
    spawn = payload.get("spawn_exact") if isinstance(payload.get("spawn_exact"), dict) else {}
    wild = list(spawn.get("wild_stats") or [0] * STAT_COUNT)
    tamed = list(spawn.get("tamed_stats") or [0] * STAT_COUNT)
    while len(wild) < STAT_COUNT:
        wild.append(0)
    while len(tamed) < STAT_COUNT:
        tamed.append(0)
    stat_points: dict[str, int] = {}
    for i, name in enumerate(STAT_NAMES):
        try:
            pts = int(wild[i] or 0) + int(tamed[i] or 0)
        except (TypeError, ValueError, IndexError):
            pts = 0
        stat_points[name] = max(0, min(STAT_MAX, pts))
    return {
        "species_key": payload.get("species_key"),
        "level": payload.get("level", DEFAULT_LEVEL),
        "gender": payload.get("gender", "female"),
        "neutered": bool(payload.get("neutered")),
        "colors": payload.get("colors") or [0, 0, 0, 0, 0, 0],
        "stat_points": stat_points,
        "note": payload.get("note") or "Simulação Dino Lab",
    }


def simulate_purchase(
    body: dict[str, Any],
    *,
    db: Session | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Simula preço de encomenda a partir do formulário Dino Lab — sem débito.

    Reutiliza a fórmula de ``dino_order_service.quote`` (floor_quality + cores + taxas).
    """
    # Nota opcional na simulação (admin não precisa do motivo mínimo).
    payload, err = validate_payload(body, require_note=False)
    if err or payload is None:
        return None, err or "payload inválido"

    species_key = str(payload.get("species_key") or "").strip()
    if not species_key or species_key == "custom":
        return None, (
            "Simulação de preço requer espécie do catálogo (não blueprint manual)."
        )

    if db is None:
        try:
            import app as app_module

            session_factory = app_module._SessionLocal
            if session_factory is None:
                return None, "Banco não configurado"
            db = session_factory()
            close_db = True
        except Exception as exc:
            return None, f"Banco não configurado: {exc}"
    else:
        close_db = False

    try:
        from dino_order_service import quote

        spec = _payload_to_quote_spec(payload)
        q = quote(
            spec,
            db=db,
            skip_gallery_check=True,
            skip_vanilla_check=True,
        )
        return {
            "ok": True,
            "dry_run": True,
            "payload": payload,
            "quote": q,
            "total": q.get("total"),
            "breakdown": {
                "root_value": q.get("root_value"),
                "stats_component": q.get("stats_component"),
                "color_component": q.get("color_component"),
                "base_surcharge": q.get("base_surcharge"),
                "service_premium": q.get("service_premium"),
                "floor": q.get("floor"),
                "ceiling": q.get("ceiling"),
                "market_breakdown": q.get("market_breakdown"),
            },
        }, None
    except ValueError as exc:
        code = str(exc)
        msgs = {
            "species_not_available": "Espécie sem economia de mercado (sincronize o catálogo).",
            "species_key obrigatório": "Informe a espécie.",
            "db_required": "Banco não configurado.",
        }
        return None, msgs.get(code, code)
    except Exception as exc:
        log.exception("simulate_purchase: %s", exc)
        return None, str(exc)
    finally:
        if close_db and db is not None:
            db.close()


def validate_payload(body: dict[str, Any], *, require_note: bool = True) -> tuple[dict[str, Any] | None, str | None]:
    species_blueprint_raw = str(body.get("species_blueprint") or "").strip()
    species_key = str(body.get("species_key") or "").strip()

    if species_blueprint_raw:
        bp_err = _validate_species_blueprint(species_blueprint_raw)
        if bp_err:
            return None, bp_err
        resolved_blueprint = _format_blueprint(species_blueprint_raw)
        species_key = species_key or "custom"
        display_name = (
            str(body.get("species_display_name") or "").strip()
            or species_key
            or "Custom"
        )
        mod_source = "manual"
    elif species_key:
        species = _resolve_species(species_key)
        if not species:
            return None, "Espécie inválida ou sem blueprint homologado."
        resolved_blueprint = species["species_blueprint"]
        if not _looks_like_dino_species_blueprint(resolved_blueprint):
            return None, (
                f"Espécie '{species_key}' tem blueprint inválido no catálogo "
                "(não parece ser dino)."
            )
        display_name = species["display_name"]
        mod_source = species["mod_source"]
    else:
        return None, "Informe species_key ou species_blueprint."

    spawn_exact = body.get("spawn_exact") if isinstance(body.get("spawn_exact"), dict) else {}
    spawn_enabled = bool(spawn_exact.get("enabled"))
    if spawn_enabled and not bool((_settings_fn() if _settings_fn else {}).get("custom_dino_spawn_exact")):
        return None, "SpawnExact desabilitado neste servidor (custom_dino_spawn_exact)."

    wild_stats, wild_err = _parse_stat_array(
        spawn_exact.get("wild_stats") if spawn_enabled else [0] * STAT_COUNT,
        label="wild_stats",
    )
    if wild_err:
        return None, wild_err
    tamed_stats, tamed_err = _parse_stat_array(
        spawn_exact.get("tamed_stats") if spawn_enabled else [0] * STAT_COUNT,
        label="tamed_stats",
    )
    if tamed_err:
        return None, tamed_err
    assert wild_stats is not None and tamed_stats is not None

    if spawn_enabled:
        level = calc_spawn_exact_level(wild_stats, tamed_stats)
        level_err = _validate_total_level(level)
        if level_err:
            return None, level_err
    else:
        try:
            level = int(body.get("level", DEFAULT_LEVEL))
        except (TypeError, ValueError):
            return None, "Nível inválido."
        level_err = _validate_total_level(level)
        if level_err:
            return None, level_err

    gender = str(body.get("gender") or "female").strip().lower()
    if gender not in ("male", "female", "m", "f"):
        return None, "Sexo inválido (male/female)."
    gender = "female" if gender in ("female", "f") else "male"

    raw_colors = body.get("colors")
    if not isinstance(raw_colors, list) or len(raw_colors) != COLOR_REGIONS:
        return None, f"Informe exatamente {COLOR_REGIONS} cores (índices 0–{COLOR_MAX})."
    colors: list[int] = []
    for c in raw_colors:
        try:
            n = int(c)
        except (TypeError, ValueError):
            return None, "Cor inválida."
        if n < COLOR_MIN or n > COLOR_MAX:
            return None, f"Cada cor deve estar entre {COLOR_MIN} e {COLOR_MAX}."
        colors.append(n)

    note = str(body.get("note") or "").strip()
    if require_note and len(note) < 10:
        return None, "Motivo obrigatório (mínimo 10 caracteres)."

    deliver_as = str(body.get("deliver_as") or "cryopod").strip().lower()
    if deliver_as not in ("cryopod", "ground"):
        return None, "Entrega inválida (cryopod ou ground)."

    ticket_id = str(body.get("ticket_id") or "").strip() or None
    if _settings_fn and bool(_settings_fn().get("custom_dino_require_ticket")) and not ticket_id:
        return None, "ticket_id obrigatório para compensações (custom_dino_require_ticket)."

    imprint_pct = _normalize_imprint_pct(spawn_exact.get("imprint_pct")) if spawn_enabled else 0.0
    imprinter_name = str(spawn_exact.get("imprinter_name") or "").strip() if spawn_enabled else ""
    imprinter_id_hex = str(spawn_exact.get("imprinter_id_hex") or "").strip() if spawn_enabled else ""

    saddle_blueprint = str(body.get("saddle_blueprint") or "").strip()
    if saddle_blueprint:
        if not _is_valid_blueprint_raw(saddle_blueprint):
            return None, "Blueprint de sela inválido."
        saddle_inner = _blueprint_inner(saddle_blueprint).lower()
        if "saddle" not in saddle_inner and "primalitem" not in saddle_inner:
            return None, "saddle_blueprint deve ser um PrimalItem de sela."

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "species_blueprint": resolved_blueprint,
        "species_key": species_key,
        "species_display_name": display_name,
        "mod_source": mod_source,
        "level": level,
        "gender": gender,
        "neutered": bool(body.get("neutered")),
        "colors": colors,
        "deliver_as": deliver_as,
        "note": note,
        "ticket_id": ticket_id,
        "preset_id": body.get("preset_id"),
        "spawn_exact": {
            "enabled": spawn_enabled,
            "wild_stats": wild_stats,
            "tamed_stats": tamed_stats,
            "imprint_pct": imprint_pct,
            "imprinter_name": imprinter_name,
            "imprinter_id_hex": imprinter_id_hex,
        },
        "saddle_blueprint": saddle_blueprint,
        "force_tame": bool(body.get("force_tame", True)),
        "custom_name": str(body.get("custom_name") or "").strip(),
    }
    return payload, None


def _new_order_id() -> str:
    return f"cd_{uuid.uuid4().hex[:12]}"


def _hourly_deliver_count(db: Session, admin_steam_id: str) -> int:
    since = _utcnow() - timedelta(hours=1)
    row = db.execute(
        text(
            "SELECT COUNT(*) FROM orders "
            "WHERE item_type = :it AND created_at >= :since AND payload_json LIKE :actor"
        ),
        {"it": ITEM_TYPE, "since": since.replace(tzinfo=None), "actor": f'%"created_by":"{admin_steam_id}"%'},
    ).fetchone()
    return int(row[0] if row else 0)


def create_custom_dino_order(
    db: Session,
    *,
    steam_id: str,
    payload: dict[str, Any],
    admin_steam_id: str,
    server_id: str = "default",
) -> dict[str, Any]:
    if not is_custom_dino_enabled():
        raise ValueError("custom_dino_disabled")
    if _hourly_deliver_count(db, admin_steam_id) >= RATE_LIMIT_PER_HOUR:
        raise ValueError("rate_limit_exceeded")

    payload = dict(payload)
    payload["created_by"] = admin_steam_id
    payload["created_at"] = _utcnow().isoformat()

    order_id = _new_order_id()
    original_order_id = None
    if payload.get("ticket_id"):
        original_order_id = f"ticket:#{payload['ticket_id']}"

    now = _utcnow().replace(tzinfo=None)
    db.execute(
        text(
            "INSERT INTO orders "
            "(order_id, steam_id, server_id, item_type, item_id, amount, points_spent, status, "
            "original_order_id, payload_json, created_at, updated_at) "
            "VALUES (:oid, :sid, :srv, :it, :iid, 1, 0, 'PENDENTE', :orig, :pj, :now, :now)"
        ),
        {
            "oid": order_id,
            "sid": steam_id,
            "srv": server_id,
            "it": ITEM_TYPE,
            "iid": order_id,
            "orig": original_order_id,
            "pj": json.dumps(payload, ensure_ascii=False),
            "now": now,
        },
    )
    return {
        "order_id": order_id,
        "status": "PENDENTE",
        "steam_id": steam_id,
        "payload": payload,
    }


def _parse_payload(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(str(raw))
    except Exception:
        return {}


def _row_val(row: Any, key: str, default: Any = None) -> Any:
    try:
        return row._mapping.get(key, default)
    except Exception:
        try:
            return getattr(row, key, default)
        except Exception:
            return default


def _iso_dt(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val)


def order_to_admin_dict(row: Any) -> dict[str, Any]:
    payload = _parse_payload(_row_val(row, "payload_json"))
    species_key = payload.get("species_key")
    species_tier = payload.get("tier")
    species_image_url = ""
    try:
        from ark_species_registry import resolve_species_image_for_key

        species_image_url = resolve_species_image_for_key(species_key, tier=species_tier)
    except Exception:
        species_image_url = ""
    return {
        "order_id": str(_row_val(row, "order_id", "")),
        "steam_id": str(_row_val(row, "steam_id", "")),
        "status": str(_row_val(row, "status", "")),
        "server_id": str(_row_val(row, "server_id", "") or ""),
        "original_order_id": _row_val(row, "original_order_id"),
        "species_key": species_key,
        "species_display_name": payload.get("species_display_name"),
        "species_image_url": species_image_url,
        "level": payload.get("level"),
        "gender": payload.get("gender"),
        "colors": payload.get("colors"),
        "note": payload.get("note"),
        "ticket_id": payload.get("ticket_id"),
        "created_by": payload.get("created_by"),
        "deliver_as": payload.get("deliver_as"),
        "retry_count": int(_row_val(row, "retry_count", 0) or 0),
        "last_error": _row_val(row, "last_error"),
        "created_at": _iso_dt(_row_val(row, "created_at")),
        "updated_at": _iso_dt(_row_val(row, "updated_at")),
        "payload": payload,
    }


def is_player_dino_encomenda(payload: dict[str, Any]) -> bool:
    return str(payload.get("order_source") or "") == "dino_encomenda"


def list_custom_dino_orders_admin(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 25,
    status: str | None = None,
    steam_id: str | None = None,
    exclude_player_orders: bool = True,
) -> dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    params: dict[str, Any] = {"it": ITEM_TYPE, "lim": page_size, "off": (page - 1) * page_size}
    where = "item_type = :it"
    if exclude_player_orders:
        where += " AND (payload_json IS NULL OR payload_json NOT LIKE :no_encomenda)"
        params["no_encomenda"] = '%"order_source": "dino_encomenda"%'
    if status:
        where += " AND status = :st"
        params["st"] = status.strip().upper()
    if steam_id:
        where += " AND steam_id = :sid"
        params["sid"] = steam_id.strip()
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
        "orders": [order_to_admin_dict(r) for r in rows],
    }


def get_custom_dino_order(db: Session, order_id: str) -> dict[str, Any] | None:
    row = db.execute(
        text("SELECT * FROM orders WHERE order_id = :oid AND item_type = :it LIMIT 1"),
        {"oid": order_id, "it": ITEM_TYPE},
    ).fetchone()
    if not row:
        return None
    return order_to_admin_dict(row)


def claim_custom_dino_orders(
    db: Session,
    steam_id: str,
    *,
    order_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    recover_stale_entregando_custom_dino_orders(db, steam_id)
    params: dict[str, Any] = {"sid": steam_id, "it": ITEM_TYPE}
    sql = (
        "SELECT * FROM orders WHERE steam_id = :sid AND item_type = :it AND status = 'PENDENTE' "
        "ORDER BY created_at ASC"
    )
    rows = db.execute(text(sql), params).fetchall()
    targets = {str(x).strip() for x in order_ids} if order_ids else None
    claimed: list[dict[str, Any]] = []
    now = _utcnow().replace(tzinfo=None)
    for row in rows:
        oid = str(_row_val(row, "order_id", ""))
        if targets is not None and oid not in targets:
            continue
        updated = db.execute(
            text(
                "UPDATE orders SET status = 'ENTREGANDO', updated_at = :now "
                "WHERE order_id = :oid AND steam_id = :sid AND status = 'PENDENTE' AND item_type = :it"
            ),
            {"now": now, "oid": oid, "sid": steam_id, "it": ITEM_TYPE},
        )
        if int(getattr(updated, "rowcount", 0) or 0) <= 0:
            continue
        payload = _parse_payload(_row_val(row, "payload_json"))
        claimed.append({
            "order_id": oid,
            "item_type": ITEM_TYPE,
            "item_id": oid,
            "amount": 1,
            "payload": payload,
        })
    return claimed


def release_custom_dino_orders(db: Session, steam_id: str, order_ids: list[str]) -> list[str]:
    released: list[str] = []
    now = _utcnow().replace(tzinfo=None)
    for oid in order_ids:
        order_id = str(oid).strip()
        if not order_id:
            continue
        updated = db.execute(
            text(
                "UPDATE orders SET status = 'PENDENTE', updated_at = :now "
                "WHERE order_id = :oid AND steam_id = :sid AND status = 'ENTREGANDO' AND item_type = :it"
            ),
            {"now": now, "oid": order_id, "sid": steam_id, "it": ITEM_TYPE},
        )
        if int(getattr(updated, "rowcount", 0) or 0) > 0:
            released.append(order_id)
    return released


def mark_custom_dino_delivered(
    db: Session,
    steam_id: str,
    order_ids: list[str],
    *,
    last_error: str | None = None,
) -> list[str]:
    delivered: list[str] = []
    now = _utcnow().replace(tzinfo=None)
    for oid in order_ids:
        order_id = str(oid).strip()
        if not order_id:
            continue
        updated = db.execute(
            text(
                "UPDATE orders SET status = 'ENTREGUE', last_error = :err, updated_at = :now "
                "WHERE order_id = :oid AND steam_id = :sid AND status IN ('PENDENTE', 'ENTREGANDO') "
                "AND item_type = :it"
            ),
            {"now": now, "oid": order_id, "sid": steam_id, "it": ITEM_TYPE, "err": last_error},
        )
        if int(getattr(updated, "rowcount", 0) or 0) > 0:
            delivered.append(order_id)
    return delivered


def mark_custom_dino_failed(
    db: Session,
    steam_id: str,
    order_id: str,
    *,
    error: str,
) -> bool:
    now = _utcnow().replace(tzinfo=None)
    result = db.execute(
        text(
            "UPDATE orders SET status = 'FALHA', last_error = :err, "
            "retry_count = retry_count + 1, updated_at = :now "
            "WHERE order_id = :oid AND steam_id = :sid AND item_type = :it"
        ),
        {"now": now, "oid": order_id, "sid": steam_id, "it": ITEM_TYPE, "err": error[:2000]},
    )
    return int(getattr(result, "rowcount", 0) or 0) > 0
