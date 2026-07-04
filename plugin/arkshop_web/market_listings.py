"""Vault, listings, compra e claims do Mercado de Dinos."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from ark_species_registry import (
    ensure_pre_registered_species,
    get_registry_entry,
    is_raw_blueprint_label,
    lookup_species,
    resolve_species_image,
    suggestion_to_public,
)
from market_audit import market_audit_event
from market_notify import (
    SELLER_VITRINE_EVENT_TYPES,
    notify_seller_buyer_claimed,
    notify_seller_listing_flagged,
    notify_seller_listing_removed,
    notify_seller_listing_sold,
)
from market_economy import (
    STAT_KEYS,
    calculate_listing_price_ceiling,
    calculate_suggested_value,
    format_price_ceiling_error,
    load_price_ceiling_config,
    normalize_blueprint,
    normalize_stat_points,
    species_economy_meta_from_defaults,
)
from market_service import species_row_to_economy
from stat_points_asb import enrich_stats_with_points

log = logging.getLogger("arkshop.market_listings")

PARSER_VERSION = "1.0.0"
ACTIVE_VAULT_STATUSES = {
    "DRAFT",
    "ACTIVE",
    "PAUSED",
    "PENDING_CLASSIFICATION",
    "RESERVING",
    "SOLD",
    "AWAITING_CLAIM",
}
TERMINAL_LISTING = {"DELIVERED", "WITHDRAWN", "CANCELLED"}
DISPLAY_NAME_RE = re.compile(r"^[A-Za-z0-9_\-\.]{2,32}$")
HTML_TAG_RE = re.compile(r"<[^>]+>")
CUSTOM_NAME_MAX = 80
CUSTOM_DESC_MAX = 280
LISTING_CATEGORIES = frozenset({"S+", "S", "A", "B", "C"})
CLAIM_RESERVATION_HOURS = 24
CLAIM_STATUS_PENDING = "pending"
CLAIM_STATUS_COMPLETED = "completed"
CLAIM_STATUS_EXPIRED = "expired"
CLAIM_STATUS_REFUNDED = "refunded"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _claim_reservation_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Retorna (reserved_at, expires_at) para janela padrão de resgate."""
    start = now or _now()
    return start, start + timedelta(hours=CLAIM_RESERVATION_HOURS)


def _hours_remaining(expires_at: datetime | None, *, now: datetime | None = None) -> float | None:
    if expires_at is None:
        return None
    ref = now or _now()
    exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    delta = (exp - ref).total_seconds() / 3600.0
    return max(0.0, delta)


def _claim_is_expired(claim: Any, *, now: datetime | None = None) -> bool:
    if getattr(claim, "claim_status", None) in (CLAIM_STATUS_EXPIRED, CLAIM_STATUS_REFUNDED):
        return True
    exp = getattr(claim, "claim_expires_at", None)
    if exp is None:
        return False
    ref = now or _now()
    exp_tz = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
    return exp_tz <= ref


def _apply_claim_reservation(claim: Any, *, now: datetime | None = None) -> None:
    reserved, expires = _claim_reservation_window(now)
    claim.claim_reserved_at = reserved
    claim.claim_expires_at = expires
    claim.claim_status = CLAIM_STATUS_PENDING


def _claim_to_public(claim: Any) -> dict[str, Any]:
    hrs = _hours_remaining(getattr(claim, "claim_expires_at", None))
    return {
        "claim_id": claim.id,
        "claim_type": claim.claim_type,
        "claim_status": claim.claim_status or CLAIM_STATUS_PENDING,
        "claim_reserved_at": (
            claim.claim_reserved_at.isoformat() if claim.claim_reserved_at else None
        ),
        "claim_expires_at": (
            claim.claim_expires_at.isoformat() if claim.claim_expires_at else None
        ),
        "hours_remaining": round(hrs, 2) if hrs is not None else None,
        "expired": _claim_is_expired(claim),
    }


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _json_loads(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        val = json.loads(raw)
        return val if isinstance(val, dict) else {}
    except Exception:
        return {}


def hex_to_bytes(hex_str: str) -> bytes:
    h = (hex_str or "").strip()
    if h.startswith("0x"):
        h = h[2:]
    if len(h) % 2:
        raise ValueError("hex inválido")
    return bytes.fromhex(h)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _norm_bp(bp: str) -> str:
    return normalize_blueprint(bp)


def resolve_species(db: Session, *, species_key: str | None = None, blueprint: str | None = None) -> Any | None:
    from app import MarketSpecies, MarketSpeciesAlias

    if species_key:
        row = db.query(MarketSpecies).filter(MarketSpecies.species_key == species_key).first()
        if row:
            return row
    if blueprint:
        nb = _norm_bp(blueprint)
        if nb:
            alias = (
                db.query(MarketSpeciesAlias)
                .filter(MarketSpeciesAlias.blueprint_norm == nb)
                .first()
            )
            if alias:
                row = db.query(MarketSpecies).filter(MarketSpecies.id == alias.species_id).first()
                if row:
                    return row
        for row in db.query(MarketSpecies).order_by(MarketSpecies.status.desc()).all():
            if _norm_bp(row.blueprint_path or "") == nb:
                return row
    return None


def get_profile(db: Session, steam_id: str) -> Any | None:
    from app import MarketPlayerProfile

    return db.query(MarketPlayerProfile).filter(MarketPlayerProfile.steam_id == steam_id).first()


def _profile_display_name(db: Session, steam_id: str) -> str | None:
    prof = get_profile(db, steam_id)
    return prof.market_display_name if prof else None


def _listing_title_for_notify(db: Session, row: Any) -> str:
    species_row = resolve_species(db, species_key=row.species_key)
    return _listing_display_title(row, species_row)


def commerce_ready(db: Session, steam_id: str) -> tuple[bool, str | None]:
    prof = get_profile(db, steam_id)
    if not prof or not prof.market_display_name:
        return False, "Defina seu nome de exibição em Minha Área antes de usar o Comércio."
    if not prof.commerce_enabled:
        return False, "Perfil de comércio não habilitado."
    return True, None


def upsert_display_name(db: Session, steam_id: str, name: str) -> dict[str, Any]:
    from app import MarketPlayerProfile

    name = (name or "").strip()
    if not DISPLAY_NAME_RE.match(name):
        raise ValueError("Nome deve ter 2–32 caracteres (letras, números, _ - .)")
    now = _now()
    row = get_profile(db, steam_id)
    if row is None:
        row = MarketPlayerProfile(
            steam_id=steam_id,
            market_display_name=name,
            name_updated_at=now,
            commerce_enabled=True,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.market_display_name = name
        row.name_updated_at = now
        row.commerce_enabled = True
        row.updated_at = now
    db.commit()
    try:
        market_audit_event(
            db,
            "MARKET_DISPLAY_NAME_CHANGED",
            steam_id=steam_id,
            metadata={"market_display_name": name},
            commit=True,
        )
    except Exception as exc:
        log.warning("MARKET_DISPLAY_NAME_CHANGED audit falhou (perfil já salvo): %s", exc)
    return {"steam_id": steam_id, "market_display_name": name, "commerce_enabled": True}


def _load_economy(db: Session, species_row: Any) -> Any:
    from app import MarketSpeciesStatMultiplier

    mult_rows = (
        db.query(MarketSpeciesStatMultiplier)
        .filter(MarketSpeciesStatMultiplier.species_id == species_row.id)
        .all()
    )
    return species_row_to_economy(species_row, mult_rows)


def _denorm_stats(metadata: dict[str, Any]) -> dict[str, int]:
    stats = metadata.get("stats_max") or {}
    points = normalize_stat_points(stats)
    return {
        "stat_health": points.get("health", 0),
        "stat_melee": points.get("melee", 0),
        "stat_weight": points.get("weight", 0),
        "stat_stamina": points.get("stamina", 0),
        "stat_oxygen": points.get("oxygen", 0),
        "stat_food": points.get("food", 0),
        "stat_speed": points.get("speed", 0),
    }


def _compute_economy(db: Session, species_row: Any, metadata: dict[str, Any]) -> tuple[int, list, Any]:
    economy = _load_economy(db, species_row)
    meta = dict(metadata)
    stats_max = meta.get("stats_max") or {}
    imprint = float(meta.get("imprint_pct") or meta.get("imprint") or 0)
    sk = getattr(species_row, "species_key", None) or ""
    if stats_max and sk:
        meta["stats_max"] = enrich_stats_with_points(sk, stats_max, imprint_pct=imprint)
        meta["extraction_method"] = meta.get("extraction_method") or "inverse_calc"
    points = normalize_stat_points(meta.get("stats_max") or {})
    total, breakdown = calculate_suggested_value(economy, points)
    return total, breakdown, economy


def preview_plugin_economy(db: Session, metadata: dict[str, Any]) -> dict[str, Any]:
    """Preview de valor sugerido para /enviar in-game (sem persistir)."""
    meta = dict(metadata or {})
    species_key = str(meta.get("species_key") or "").strip()
    blueprint = str(meta.get("species_blueprint") or meta.get("blueprint") or "")
    species_row = resolve_species(db, species_key=species_key or None, blueprint=blueprint or None)
    if not species_row:
        return {
            "ok": True,
            "species_key": None,
            "species_status": None,
            "computed_base_value": 0,
            "calculation_breakdown": [],
            "message": "Especie nao cadastrada — aguarda classificacao admin.",
        }
    status = str(getattr(species_row, "status", "") or "")
    if status != "ACTIVE":
        return {
            "ok": True,
            "species_key": species_row.species_key,
            "species_status": status,
            "computed_base_value": 0,
            "calculation_breakdown": [],
            "message": f"Especie {status} — valor sugerido apos ativacao admin.",
        }
    computed, breakdown, economy = _compute_economy(db, species_row, meta)
    tier = getattr(species_row, "tier", None) or "B"
    ceiling = calculate_listing_price_ceiling(
        computed,
        tier=tier,
        size_class=getattr(economy, "size_class", "medium"),
    )
    return {
        "ok": True,
        "species_key": species_row.species_key,
        "species_status": status,
        "computed_base_value": computed,
        "price_ceiling": ceiling,
        "calculation_breakdown": breakdown,
    }


def vault_hash_in_use(db: Session, blob_hash: str) -> bool:
    from app import MarketCryopodVault, MarketListing

    rows = (
        db.query(MarketListing)
        .join(MarketCryopodVault, MarketCryopodVault.id == MarketListing.vault_id)
        .filter(
            MarketCryopodVault.blob_hash == blob_hash,
            MarketListing.status.in_(list(ACTIVE_VAULT_STATUSES)),
        )
        .first()
    )
    return rows is not None


def process_plugin_upload(db: Session, body: dict[str, Any]) -> dict[str, Any]:
    from app import MarketCryopodVault, MarketListing

    if not body.get("inventory_removed"):
        raise ValueError("inventory_removed obrigatório — cryopod deve sair do inventário antes do vault")
    if not body.get("inventory_verified_empty"):
        raise ValueError("inventory_verified_empty obrigatório")

    steam_id = str(body.get("steam_id") or "").strip()
    if not steam_id:
        raise ValueError("steam_id obrigatório")

    upload_id = str(body.get("upload_id") or body.get("market_trace_id") or "").strip()
    if upload_id:
        existing = (
            db.query(MarketCryopodVault)
            .filter(MarketCryopodVault.market_trace_id == upload_id)
            .first()
        )
        if existing:
            listing = (
                db.query(MarketListing)
                .filter(MarketListing.vault_id == existing.id)
                .first()
            )
            if listing:
                return {
                    "vault_id": existing.id,
                    "listing_id": listing.id,
                    "blob_hash": existing.blob_hash,
                    "market_trace_id": upload_id,
                    "status": listing.status,
                    "computed_base_value": listing.computed_base_value,
                    "calculation_breakdown": _json_loads(listing.metadata_json).get(
                        "calculation_breakdown", []
                    ),
                    "deduplicated": True,
                }

    ok, err = commerce_ready(db, steam_id)
    if not ok:
        raise ValueError(err or "Perfil de comércio incompleto")

    hex_blob = str(body.get("item_blob_hex") or body.get("item_blob") or "").strip()
    item_bytes = hex_to_bytes(hex_blob)
    blob_hash = sha256_hex(item_bytes)

    if vault_hash_in_use(db, blob_hash):
        raise ValueError("Cryopod já registrada no mercado (hash duplicado)")

    metadata = body.get("metadata") or body.get("metadata_json") or {}
    if isinstance(metadata, str):
        metadata = _json_loads(metadata)

    imprint = float(metadata.get("imprint_pct") or metadata.get("imprint") or 0)
    if imprint < 0.999:
        raise ValueError("Imprint 100% obrigatório para anunciar")

    species_key = str(metadata.get("species_key") or body.get("species_key") or "").strip()
    blueprint = str(metadata.get("species_blueprint") or metadata.get("blueprint") or "")
    species_row = resolve_species(db, species_key=species_key or None, blueprint=blueprint or None)

    suggestion = lookup_species(
        blueprint=blueprint or None,
        species_key=species_key or None,
        name_hint=str(metadata.get("name_map") or metadata.get("dino_name") or ""),
    )
    if suggestion and (not species_row or species_row.status != "ACTIVE"):
        try:
            species_row = ensure_pre_registered_species(db, suggestion, blueprint=blueprint)
            species_key = species_row.species_key
            metadata["classification_suggestion"] = suggestion
        except Exception:
            metadata["classification_suggestion"] = suggestion
    elif suggestion:
        metadata["classification_suggestion"] = suggestion

    if species_row and not species_key:
        species_key = species_row.species_key

    if species_row and metadata.get("stats_max"):
        sk = species_row.species_key
        metadata["stats_max"] = enrich_stats_with_points(
            sk,
            metadata["stats_max"],
            imprint_pct=imprint,
        )
        metadata["extraction_method"] = metadata.get("extraction_method") or "inverse_calc"

    trace_id = str(body.get("market_trace_id") or body.get("upload_id") or uuid.uuid4())
    now = _now()

    vault = MarketCryopodVault(
        seller_steam_id=steam_id,
        item_blob=item_bytes,
        blob_hash=blob_hash,
        metadata_json=_json_dumps(metadata),
        species_key=species_row.species_key if species_row else species_key or None,
        market_trace_id=trace_id,
        parser_version=str(body.get("parser_version") or PARSER_VERSION),
        uploaded_at=now,
    )
    db.add(vault)
    db.flush()

    computed = 0
    breakdown: list = []
    listing_status = "PENDING_CLASSIFICATION"
    if species_row and species_row.status == "ACTIVE":
        listing_status = "DRAFT"
        computed, breakdown, _ = _compute_economy(db, species_row, metadata)
        metadata["admin_classification_approved"] = True
    elif species_row and species_row.status != "ACTIVE":
        listing_status = "PENDING_CLASSIFICATION"
        metadata.pop("admin_classification_approved", None)
        if suggestion:
            computed = 0
    elif suggestion:
        listing_status = "PENDING_CLASSIFICATION"
        metadata.pop("admin_classification_approved", None)

    denorm = _denorm_stats(metadata)
    listing = MarketListing(
        vault_id=vault.id,
        seller_steam_id=steam_id,
        species_key=species_row.species_key if species_row else species_key or None,
        status=listing_status,
        price_mode="ABSOLUTE",
        computed_base_value=computed,
        effective_price=max(computed, 0),
        market_trace_id=trace_id,
        dino_display_name=str(metadata.get("name_map") or metadata.get("dino_name") or ""),
        mutations_male=int(metadata.get("mutations_male") or 0),
        mutations_female=int(metadata.get("mutations_female") or 0),
        dino_level=int(metadata.get("dino_level") or 0),
        imprint_pct=imprint,
        is_female=bool(metadata.get("is_female") or metadata.get("sex") == "female"),
        is_neutered=bool(metadata.get("is_neutered")),
        metadata_json=_json_dumps({**metadata, "calculation_breakdown": breakdown}),
        created_at=now,
        updated_at=now,
        **denorm,
    )
    db.add(listing)
    db.commit()

    event = "MARKET_UPLOAD_CONFIRMED" if listing_status == "DRAFT" else "MARKET_SPECIES_PENDING"
    market_audit_event(
        db,
        event,
        severity="INFO",
        source="plugin",
        steam_id=steam_id,
        vault_id=vault.id,
        listing_id=listing.id,
        blob_hash=blob_hash,
        computed_base_value=computed,
        market_trace_id=trace_id,
        parser_version=vault.parser_version,
        plugin_version=str(body.get("plugin_version") or ""),
        metadata={
            "inventory_removed": True,
            "inventory_verified_empty": True,
            "listing_status": listing_status,
            "metadata": metadata,
        },
        commit=True,
    )

    return {
        "vault_id": vault.id,
        "listing_id": listing.id,
        "blob_hash": blob_hash,
        "market_trace_id": trace_id,
        "status": listing_status,
        "computed_base_value": computed,
        "price_ceiling": listing_price_ceiling(listing, species_row=species_row),
        "calculation_breakdown": breakdown,
    }


def _strip_html(text: str) -> str:
    return HTML_TAG_RE.sub("", text).strip()


def _sanitize_listing_text(
    text: str | None,
    *,
    max_len: int,
    field_label: str,
    allow_empty: bool = True,
) -> str | None:
    if text is None:
        return None
    cleaned = _strip_html(str(text).strip())
    if not cleaned:
        return None if allow_empty else ""
    if len(cleaned) > max_len:
        raise ValueError(f"{field_label}: máximo {max_len} caracteres")
    return cleaned


def validate_custom_name(name: str | None) -> str | None:
    return _sanitize_listing_text(name, max_len=CUSTOM_NAME_MAX, field_label="Nome do anúncio")


def validate_custom_description(desc: str | None) -> str | None:
    return _sanitize_listing_text(desc, max_len=CUSTOM_DESC_MAX, field_label="Descrição")


def _listing_tier_for_ceiling(row: Any, species_row: Any | None, meta: dict[str, Any]) -> str:
    if getattr(row, "category", None):
        return str(row.category)
    if species_row and getattr(species_row, "tier", None):
        return str(species_row.tier)
    suggestion = _resolve_listing_suggestion(row, species_row=species_row, meta=meta)
    if suggestion and suggestion.get("tier"):
        return str(suggestion["tier"])
    return "B"


def _listing_size_class(row: Any, species_row: Any | None) -> str:
    if species_row and getattr(species_row, "species_key", None):
        meta = species_economy_meta_from_defaults(species_row.species_key)
        return str(meta.get("size_class") or "medium")
    sk = getattr(row, "species_key", None)
    if sk:
        meta = species_economy_meta_from_defaults(sk)
        return str(meta.get("size_class") or "medium")
    return "medium"


def listing_price_ceiling(
    row: Any,
    *,
    species_row: Any | None = None,
    meta: dict[str, Any] | None = None,
) -> int:
    meta = meta if meta is not None else _json_loads(row.metadata_json)
    suggested = int(row.computed_base_value or 0)
    tier = _listing_tier_for_ceiling(row, species_row, meta)
    size_class = _listing_size_class(row, species_row)
    return calculate_listing_price_ceiling(
        suggested,
        tier=tier,
        size_class=size_class,
    )


def validate_listing_price_ceiling(
    row: Any,
    price: int,
    *,
    species_row: Any | None = None,
    skip: bool = False,
) -> None:
    if skip:
        return
    meta = _json_loads(row.metadata_json)
    suggested = int(row.computed_base_value or 0)
    if suggested <= 0:
        return
    ceiling = listing_price_ceiling(row, species_row=species_row, meta=meta)
    if int(price) > ceiling:
        tier = _listing_tier_for_ceiling(row, species_row, meta)
        raise ValueError(format_price_ceiling_error(int(price), suggested, ceiling, tier=tier))


def validate_listing_category(category: str | None) -> str | None:
    if category is None:
        return None
    cat = str(category).strip()
    if not cat:
        return None
    if cat not in LISTING_CATEGORIES:
        raise ValueError("Categoria inválida — use S+, S, A, B ou C")
    return cat


def _species_map(db: Session, species_keys: set[str | None]) -> dict[str, Any]:
    from app import MarketSpecies

    keys = {k for k in species_keys if k}
    if not keys:
        return {}
    rows = db.query(MarketSpecies).filter(MarketSpecies.species_key.in_(list(keys))).all()
    return {r.species_key: r for r in rows}


def _classification_from_meta(meta: dict[str, Any]) -> dict[str, Any] | None:
    raw = meta.get("classification_suggestion")
    return raw if isinstance(raw, dict) and raw.get("species_key") else None


def _needs_admin_classification(row: Any, meta: dict[str, Any] | None = None) -> bool:
    """Listing aguarda confirmação admin antes de o vendedor poder ativar."""
    meta = meta if meta is not None else _json_loads(row.metadata_json)
    if row.status == "PENDING_CLASSIFICATION":
        return True
    if row.status == "DRAFT" and not meta.get("admin_classification_approved"):
        return True
    return False


def _resolve_listing_suggestion(
    row: Any,
    *,
    species_row: Any | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    meta = meta if meta is not None else _json_loads(row.metadata_json)
    stored = _classification_from_meta(meta)
    if stored:
        return stored
    if species_row and species_row.status == "ACTIVE":
        return None
    blueprint = meta.get("species_blueprint") or meta.get("blueprint")
    return lookup_species(
        blueprint=str(blueprint or ""),
        species_key=row.species_key,
        name_hint=row.dino_display_name or meta.get("name_map"),
    )


def _friendly_species_name(
    row: Any,
    species_row: Any | None,
    suggestion: dict[str, Any] | None,
) -> str | None:
    if species_row and species_row.display_name:
        return species_row.display_name
    if suggestion and suggestion.get("display_name"):
        return str(suggestion["display_name"])
    name = row.dino_display_name or ""
    if name and not is_raw_blueprint_label(name):
        return name
    if row.species_key and not is_raw_blueprint_label(row.species_key):
        return row.species_key
    return None


def _listing_display_title(
    row: Any,
    species_row: Any | None,
    *,
    suggestion: dict[str, Any] | None = None,
) -> str:
    if getattr(row, "custom_name", None):
        return row.custom_name
    friendly = _friendly_species_name(row, species_row, suggestion)
    if friendly:
        return friendly
    if row.dino_display_name and not is_raw_blueprint_label(row.dino_display_name):
        return row.dino_display_name
    if suggestion and suggestion.get("display_name"):
        return str(suggestion["display_name"])
    return "Dino aguardando classificação"


def _listing_effective_category(row: Any, species_row: Any | None) -> str | None:
    if getattr(row, "category", None):
        return row.category
    if species_row and species_row.tier:
        return species_row.tier
    return None


def listing_to_public(
    row: Any,
    *,
    include_breakdown: bool = False,
    species_row: Any | None = None,
) -> dict[str, Any]:
    meta = _json_loads(row.metadata_json)
    suggestion = _resolve_listing_suggestion(row, species_row=species_row, meta=meta)
    species_name = _friendly_species_name(row, species_row, suggestion)
    species_tier = species_row.tier if species_row else (suggestion or {}).get("tier")
    effective_category = _listing_effective_category(row, species_row)
    if not effective_category and suggestion:
        effective_category = suggestion.get("tier")
    suggested_value = row.computed_base_value or (suggestion or {}).get("root_value") or 0
    price_ceiling_val = listing_price_ceiling(row, species_row=species_row, meta=meta)
    awaiting = _needs_admin_classification(row, meta)
    sk = row.species_key or (suggestion or {}).get("species_key")
    reg_entry = get_registry_entry(sk) if sk else None
    species_image_url = resolve_species_image(reg_entry, tier=species_tier)
    out: dict[str, Any] = {
        "listing_id": row.id,
        "seller_steam_id": row.seller_steam_id,
        "seller_display_name": None,
        "species_key": sk,
        "species_display_name": species_name,
        "species_tier": species_tier,
        "species_image_url": species_image_url,
        "custom_name": getattr(row, "custom_name", None),
        "display_title": _listing_display_title(row, species_row, suggestion=suggestion),
        "category": getattr(row, "category", None),
        "effective_category": effective_category,
        "custom_description": getattr(row, "custom_description", None),
        "status": row.status,
        "awaiting_classification": awaiting,
        "classification_message": (
            "Aguardando aprovação da equipe"
            if awaiting
            else None
        ),
        "computed_base_value": row.computed_base_value,
        "suggested_base_value": int(suggested_value) if suggested_value else 0,
        "price_ceiling": price_ceiling_val,
        "effective_price": row.effective_price,
        "price_mode": row.price_mode,
        "dino_display_name": row.dino_display_name,
        "blueprint_raw": meta.get("species_blueprint") or meta.get("blueprint"),
        "classification_suggestion": suggestion_to_public(suggestion),
        "imprint_pct": row.imprint_pct,
        "mutations_male": row.mutations_male,
        "mutations_female": row.mutations_female,
        "dino_level": row.dino_level,
        "is_female": row.is_female,
        "stats": {
            "health": row.stat_health,
            "melee": row.stat_melee,
            "weight": row.stat_weight,
            "stamina": row.stat_stamina,
            "oxygen": row.stat_oxygen,
            "food": row.stat_food,
            "speed": row.stat_speed,
        },
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    if include_breakdown:
        out["calculation_breakdown"] = meta.get("calculation_breakdown") or []
    return out


def list_active_listings(
    db: Session,
    *,
    species_key: str | None = None,
    seller_steam_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    from app import MarketListing, MarketPlayerProfile

    q = db.query(MarketListing).filter(MarketListing.status == "ACTIVE")
    if species_key:
        q = q.filter(MarketListing.species_key == species_key)
    if seller_steam_id:
        q = q.filter(MarketListing.seller_steam_id == seller_steam_id)
    rows = q.order_by(MarketListing.effective_price.asc()).offset(offset).limit(limit).all()
    names = {
        p.steam_id: p.market_display_name
        for p in db.query(MarketPlayerProfile)
        .filter(MarketPlayerProfile.steam_id.in_([r.seller_steam_id for r in rows]))
        .all()
    }
    species_by_key = _species_map(db, {r.species_key for r in rows})
    out = []
    for row in rows:
        item = listing_to_public(row, species_row=species_by_key.get(row.species_key or ""))
        item["seller_display_name"] = names.get(row.seller_steam_id)
        out.append(item)
    return out


def set_listing_price(
    db: Session,
    listing_id: int,
    seller_steam_id: str,
    *,
    price_absolute: int | None = None,
    activate: bool = False,
    custom_name: str | None | object = ...,
    category: str | None | object = ...,
    custom_description: str | None | object = ...,
    skip_price_ceiling: bool = False,
) -> dict[str, Any]:
    from app import MarketListing

    row = db.query(MarketListing).filter(MarketListing.id == listing_id).first()
    if not row:
        raise ValueError("Anúncio não encontrado")
    if row.seller_steam_id != seller_steam_id:
        raise ValueError("Sem permissão")
    if row.status not in ("DRAFT", "PAUSED", "PENDING_CLASSIFICATION"):
        raise ValueError(f"Status não permite edição: {row.status}")

    species_row = resolve_species(db, species_key=row.species_key)

    if price_absolute is not None:
        price = int(price_absolute)
        if price < row.computed_base_value:
            raise ValueError(
                f"Preço mínimo: {row.computed_base_value} Âmbar (valor sugerido)"
            )
        validate_listing_price_ceiling(
            row, price, species_row=species_row, skip=skip_price_ceiling
        )
        row.price_absolute = price
        row.effective_price = price
        row.price_mode = "ABSOLUTE"

    if custom_name is not ...:
        row.custom_name = validate_custom_name(
            None if custom_name is None else str(custom_name)
        )
    if category is not ...:
        row.category = validate_listing_category(
            None if category is None else str(category)
        )
    if custom_description is not ...:
        row.custom_description = validate_custom_description(
            None if custom_description is None else str(custom_description)
        )

    if activate:
        meta = _json_loads(row.metadata_json)
        if _needs_admin_classification(row, meta):
            raise ValueError("Espécie aguardando classificação admin")
        validate_listing_price_ceiling(
            row,
            int(row.effective_price or 0),
            species_row=species_row,
            skip=skip_price_ceiling,
        )
        row.status = "ACTIVE"

    row.updated_at = _now()
    db.commit()
    market_audit_event(
        db,
        "MARKET_LISTING_ACTIVATED" if activate else "MARKET_LISTING_PRICE_SET",
        steam_id=seller_steam_id,
        listing_id=row.id,
        computed_base_value=row.computed_base_value,
        effective_price=row.effective_price,
        market_trace_id=row.market_trace_id,
        metadata={
            "custom_name": row.custom_name,
            "category": row.category,
            "has_description": bool(row.custom_description),
        },
        commit=True,
    )
    species_row = resolve_species(db, species_key=row.species_key)
    return listing_to_public(row, include_breakdown=True, species_row=species_row)


def _player_points(db: Session, steam_id: str) -> int:
    row = db.execute(
        text("SELECT points FROM players WHERE steam_id = :sid"),
        {"sid": steam_id},
    ).fetchone()
    return int(row[0]) if row else 0


def _debit_points(db: Session, steam_id: str, amount: int) -> int:
    if amount <= 0:
        return _player_points(db, steam_id)
    result = db.execute(
        text(
            "UPDATE players SET points = points - :amt WHERE steam_id = :sid AND points >= :amt"
        ),
        {"amt": amount, "sid": steam_id},
    )
    if getattr(result, "rowcount", 0) == 0:
        raise ValueError("Saldo insuficiente")
    return _player_points(db, steam_id)


def _credit_points(db: Session, steam_id: str, amount: int) -> int:
    if amount <= 0:
        return _player_points(db, steam_id)
    url = str(getattr(db, "bind", None).url if getattr(db, "bind", None) else "").lower()
    if "sqlite" in url:
        db.execute(
            text(
                "INSERT INTO players (steam_id, points) VALUES (:sid, :amt) "
                "ON CONFLICT(steam_id) DO UPDATE SET points = points + :amt"
            ),
            {"sid": steam_id, "amt": amount},
        )
    else:
        db.execute(
            text(
                "INSERT INTO players (steam_id, points) VALUES (:sid, :amt) "
                "ON DUPLICATE KEY UPDATE points = points + :amt"
            ),
            {"sid": steam_id, "amt": amount},
        )
    return _player_points(db, steam_id)


def purchase_listing(db: Session, listing_id: int, buyer_steam_id: str) -> dict[str, Any]:
    from app import MarketClaim, MarketListing, MarketTransaction

    ok, err = commerce_ready(db, buyer_steam_id)
    if not ok:
        raise ValueError(err or "Perfil incompleto")

    row = (
        db.query(MarketListing)
        .filter(MarketListing.id == listing_id)
        .with_for_update()
        .first()
    )
    if not row:
        raise ValueError("Anúncio não encontrado")
    if row.status != "ACTIVE":
        raise ValueError("Anúncio não disponível")
    if row.seller_steam_id == buyer_steam_id:
        raise ValueError("Não é possível comprar seu próprio anúncio")

    price = int(row.effective_price or 0)
    buyer_before = _player_points(db, buyer_steam_id)
    if buyer_before < price:
        raise ValueError(f"Saldo insuficiente ({buyer_before} < {price})")

    seller_before = _player_points(db, row.seller_steam_id)

    row.status = "RESERVING"
    db.flush()

    buyer_after = _debit_points(db, buyer_steam_id, price)
    seller_after = _credit_points(db, row.seller_steam_id, price)

    now = _now()
    row.status = "AWAITING_CLAIM"
    row.buyer_steam_id = buyer_steam_id
    row.sold_at = now
    row.updated_at = now

    tx = MarketTransaction(
        listing_id=row.id,
        buyer_steam_id=buyer_steam_id,
        seller_steam_id=row.seller_steam_id,
        price_paid=price,
        base_value_at_sale=row.computed_base_value,
        fee_amount=0,
        buyer_points_before=buyer_before,
        buyer_points_after=buyer_after,
        seller_points_before=seller_before,
        seller_points_after=seller_after,
        market_trace_id=row.market_trace_id,
        created_at=now,
    )
    db.add(tx)

    claim = MarketClaim(
        listing_id=row.id,
        recipient_steam_id=buyer_steam_id,
        claim_type="BUYER",
        status="PENDENTE",
        market_trace_id=row.market_trace_id,
        created_at=now,
        updated_at=now,
    )
    _apply_claim_reservation(claim, now=now)
    db.add(claim)
    db.commit()

    market_audit_event(
        db,
        "MARKET_PURCHASE_COMPLETED",
        steam_id=buyer_steam_id,
        counterparty_steam_id=row.seller_steam_id,
        listing_id=row.id,
        computed_base_value=row.computed_base_value,
        effective_price=price,
        points_delta=-price,
        points_before=buyer_before,
        points_after=buyer_after,
        market_trace_id=row.market_trace_id,
        metadata={
            "claim_expires_at": claim.claim_expires_at.isoformat() if claim.claim_expires_at else None,
            "reservation_hours": CLAIM_RESERVATION_HOURS,
        },
        commit=True,
    )

    try:
        notify_seller_listing_sold(
            db,
            seller_steam_id=row.seller_steam_id,
            listing_id=row.id,
            listing_title=_listing_title_for_notify(db, row),
            price=price,
            buyer_display_name=_profile_display_name(db, buyer_steam_id),
            market_trace_id=row.market_trace_id,
        )
    except Exception as exc:
        log.warning("notify_seller_listing_sold falhou listing=%s: %s", row.id, exc)

    hrs = _hours_remaining(claim.claim_expires_at, now=now)
    return {
        "listing_id": row.id,
        "claim_id": claim.id,
        "price_paid": price,
        "buyer_balance": buyer_after,
        "claim_expires_at": claim.claim_expires_at.isoformat() if claim.claim_expires_at else None,
        "hours_remaining": round(hrs, 2) if hrs is not None else CLAIM_RESERVATION_HOURS,
        "message": f"Você tem {CLAIM_RESERVATION_HOURS} horas para resgatar com /mercado in-game.",
    }


def get_pending_claims(db: Session, steam_id: str) -> list[dict[str, Any]]:
    from app import MarketClaim, MarketCryopodVault, MarketListing

    expire_stale_claims(db)
    now = _now()
    rows = (
        db.query(MarketClaim, MarketListing, MarketCryopodVault)
        .join(MarketListing, MarketListing.id == MarketClaim.listing_id)
        .join(MarketCryopodVault, MarketCryopodVault.id == MarketListing.vault_id)
        .filter(
            MarketClaim.recipient_steam_id == steam_id,
            MarketClaim.status == "PENDENTE",
            or_(
                MarketClaim.claim_status == CLAIM_STATUS_PENDING,
                MarketClaim.claim_status.is_(None),
            ),
        )
        .all()
    )
    out = []
    for claim, listing, vault in rows:
        if _claim_is_expired(claim, now=now):
            continue
        pub = _claim_to_public(claim)
        out.append(
            {
                **pub,
                "listing_id": listing.id,
                "blob_hash": vault.blob_hash,
                "species_key": listing.species_key,
                "dino_display_name": listing.dino_display_name,
                "item_blob_hex": vault.item_blob.hex(),
            }
        )
    return out


def release_claims(db: Session, steam_id: str, claim_ids: list[int]) -> list[dict[str, Any]]:
    from app import MarketClaim

    if not claim_ids:
        return []
    rows = (
        db.query(MarketClaim)
        .filter(
            MarketClaim.recipient_steam_id == steam_id,
            MarketClaim.id.in_(claim_ids),
            MarketClaim.status == "CLAIMED",
        )
        .all()
    )
    now = _now()
    released = []
    for row in rows:
        row.status = "PENDENTE"
        row.updated_at = now
        released.append({"claim_id": row.id, "listing_id": row.listing_id})
    db.commit()
    for r in released:
        market_audit_event(
            db,
            "MARKET_CLAIM_RELEASED",
            source="plugin",
            steam_id=steam_id,
            claim_id=r["claim_id"],
            listing_id=r["listing_id"],
            commit=True,
        )
    return released


def claim_deliveries(db: Session, steam_id: str, claim_ids: list[int]) -> list[dict[str, Any]]:
    from app import MarketClaim

    expire_stale_claims(db)
    now = _now()
    q = db.query(MarketClaim).filter(
        MarketClaim.recipient_steam_id == steam_id,
        MarketClaim.status == "PENDENTE",
        or_(
            MarketClaim.claim_status == CLAIM_STATUS_PENDING,
            MarketClaim.claim_status.is_(None),
        ),
    )
    if claim_ids:
        q = q.filter(MarketClaim.id.in_(claim_ids))
    rows = q.all()
    claimed = []
    for row in rows:
        if _claim_is_expired(row, now=now):
            raise ValueError(
                "Resgate expirado — o prazo de 24h terminou. "
                "Reembolso automático em processamento; tente /mercado em alguns minutos."
            )
        row.status = "CLAIMED"
        row.updated_at = now
        claimed.append({"claim_id": row.id, "listing_id": row.listing_id})
    db.commit()
    for c in claimed:
        market_audit_event(
            db,
            "MARKET_CLAIM_CLAIMED",
            source="plugin",
            steam_id=steam_id,
            claim_id=c["claim_id"],
            listing_id=c["listing_id"],
            commit=True,
        )
    return claimed


def mark_claim_delivered(db: Session, claim_id: int, steam_id: str) -> dict[str, Any]:
    from app import MarketClaim, MarketListing

    claim = (
        db.query(MarketClaim)
        .filter(MarketClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if not claim:
        raise ValueError("Claim não encontrado")
    if claim.recipient_steam_id != steam_id:
        raise ValueError("SteamID não corresponde")
    if _claim_is_expired(claim):
        raise ValueError(
            "Resgate expirado — prazo de 24h encerrado. "
            "Comprador reembolsado automaticamente; contate suporte se necessário."
        )
    listing = (
        db.query(MarketListing)
        .filter(MarketListing.id == claim.listing_id)
        .with_for_update()
        .first()
    )
    if not listing:
        raise ValueError("Listing não encontrado")

    now = _now()
    claim.status = "DELIVERED"
    claim.claim_status = CLAIM_STATUS_COMPLETED
    claim.delivered_at = now
    claim.updated_at = now
    listing.status = "DELIVERED"
    listing.updated_at = now
    db.commit()

    market_audit_event(
        db,
        "MARKET_CLAIM_DELIVERED",
        source="plugin",
        steam_id=steam_id,
        claim_id=claim.id,
        listing_id=listing.id,
        market_trace_id=listing.market_trace_id,
        commit=True,
    )
    if claim.claim_type == "SELLER":
        market_audit_event(
            db,
            "MARKET_SELLER_RECLAIM_DELIVERED",
            source="plugin",
            steam_id=steam_id,
            claim_id=claim.id,
            listing_id=listing.id,
            market_trace_id=listing.market_trace_id,
            commit=True,
        )
    elif claim.claim_type == "BUYER":
        try:
            notify_seller_buyer_claimed(
                db,
                seller_steam_id=listing.seller_steam_id,
                listing_id=listing.id,
                listing_title=_listing_title_for_notify(db, listing),
                buyer_display_name=_profile_display_name(db, steam_id),
                market_trace_id=listing.market_trace_id,
                claim_id=claim.id,
            )
        except Exception as exc:
            log.warning("notify_seller_buyer_claimed falhou listing=%s: %s", listing.id, exc)
    return {"claim_id": claim.id, "listing_id": listing.id, "status": "DELIVERED"}


def _refund_amount_for_listing(db: Session, listing_id: int, listing: Any | None = None) -> int:
    """Valor integral a reembolsar ao comprador (preço + taxas). Taxa atual: 0."""
    from app import MarketTransaction

    tx = (
        db.query(MarketTransaction)
        .filter(MarketTransaction.listing_id == listing_id)
        .order_by(MarketTransaction.created_at.desc())
        .first()
    )
    if tx:
        return int(tx.price_paid or 0) + int(tx.fee_amount or 0)
    if listing is not None:
        return int(getattr(listing, "effective_price", 0) or 0)
    return 0


def _expire_buyer_claim(
    db: Session,
    claim: Any,
    listing: Any,
    *,
    now: datetime,
) -> dict[str, Any] | None:
    """Reembolso justo: comprador recebe 100% do pago; vendedor devolve o que tiver em saldo."""
    if claim.claim_status in (CLAIM_STATUS_EXPIRED, CLAIM_STATUS_REFUNDED):
        return None
    if claim.status not in ("PENDENTE", "CLAIMED"):
        return None
    if not _claim_is_expired(claim, now=now):
        return None

    refund = _refund_amount_for_listing(db, listing.id, listing)
    buyer_id = listing.buyer_steam_id or claim.recipient_steam_id
    seller_id = listing.seller_steam_id

    buyer_before = _player_points(db, buyer_id) if buyer_id else 0
    seller_before = _player_points(db, seller_id) if seller_id else 0

    buyer_after = buyer_before
    seller_after = seller_before
    seller_debited = 0

    if refund <= 0:
        claim.claim_status = CLAIM_STATUS_EXPIRED
        claim.updated_at = now
        market_audit_event(
            db,
            "MARKET_CLAIM_EXPIRED_NO_REFUND",
            severity="ERROR",
            source="scheduler",
            steam_id=buyer_id,
            listing_id=listing.id,
            claim_id=claim.id,
            market_trace_id=listing.market_trace_id,
            metadata={"reason": "missing_transaction_and_price"},
            commit=False,
        )
        return None

    if buyer_id:
        buyer_after = _credit_points(db, buyer_id, refund)

    if refund > 0 and seller_id:
        seller_balance = _player_points(db, seller_id)
        seller_debited = min(seller_balance, refund)
        if seller_debited > 0:
            seller_after = _debit_points(db, seller_id, seller_debited)

    claim.status = "REEMBOLSADO"
    claim.claim_status = CLAIM_STATUS_REFUNDED
    claim.updated_at = now

    listing.buyer_steam_id = None
    listing.sold_at = None
    listing.status = "AWAITING_CLAIM"
    listing.updated_at = now

    from app import MarketClaim

    seller_claim = MarketClaim(
        listing_id=listing.id,
        recipient_steam_id=seller_id,
        claim_type="SELLER",
        status="PENDENTE",
        market_trace_id=listing.market_trace_id,
        created_at=now,
        updated_at=now,
    )
    _apply_claim_reservation(seller_claim, now=now)
    db.add(seller_claim)
    db.flush()

    market_audit_event(
        db,
        "MARKET_CLAIM_EXPIRED_REFUND",
        severity="WARN",
        source="scheduler",
        steam_id=buyer_id,
        counterparty_steam_id=seller_id,
        listing_id=listing.id,
        claim_id=claim.id,
        effective_price=refund,
        points_delta=refund,
        points_before=buyer_before,
        points_after=buyer_after,
        market_trace_id=listing.market_trace_id,
        metadata={
            "refund_amount": refund,
            "seller_debited": seller_debited,
            "seller_points_before": seller_before,
            "seller_points_after": seller_after,
            "seller_claim_id": seller_claim.id,
            "policy": "Reembolso integral ao comprador (preço + taxas=0). Vendedor devolve até o saldo disponível.",
        },
        commit=False,
    )
    return {
        "claim_id": claim.id,
        "listing_id": listing.id,
        "refund_amount": refund,
        "seller_claim_id": seller_claim.id,
    }


def _expire_seller_claim(db: Session, claim: Any, listing: Any, *, now: datetime) -> dict[str, Any] | None:
    """Resgate de retirada expirado — listing volta para PAUSED (vendedor pode reativar)."""
    if claim.claim_status in (CLAIM_STATUS_EXPIRED, CLAIM_STATUS_REFUNDED, CLAIM_STATUS_COMPLETED):
        return None
    if claim.claim_type != "SELLER":
        return None
    if claim.status not in ("PENDENTE", "CLAIMED"):
        return None
    if not _claim_is_expired(claim, now=now):
        return None

    claim.status = "EXPIRADO"
    claim.claim_status = CLAIM_STATUS_EXPIRED
    claim.updated_at = now

    if listing.status == "AWAITING_CLAIM" and listing.buyer_steam_id is None:
        listing.status = "PAUSED"
        listing.updated_at = now

    market_audit_event(
        db,
        "MARKET_CLAIM_EXPIRED_SELLER",
        severity="WARN",
        source="scheduler",
        steam_id=claim.recipient_steam_id,
        listing_id=listing.id,
        claim_id=claim.id,
        market_trace_id=listing.market_trace_id,
        metadata={"reverted_to": listing.status},
        commit=False,
    )
    return {"claim_id": claim.id, "listing_id": listing.id, "reverted_to": listing.status}


def expire_stale_claims(db: Session, *, batch_size: int = 50) -> dict[str, Any]:
    """
    Processa claims expirados (idempotente).
    Comprador: reembolso integral + devolução do dino ao vendedor via novo claim SELLER.
    Vendedor (retirada): listing volta a PAUSED.
    """
    from app import MarketClaim, MarketListing

    now = _now()
    rows = (
        db.query(MarketClaim, MarketListing)
        .join(MarketListing, MarketListing.id == MarketClaim.listing_id)
        .filter(
            MarketClaim.status.in_(["PENDENTE", "CLAIMED"]),
            or_(
                MarketClaim.claim_status == CLAIM_STATUS_PENDING,
                MarketClaim.claim_status.is_(None),
            ),
            MarketClaim.claim_expires_at.isnot(None),
            MarketClaim.claim_expires_at <= now,
        )
        .order_by(MarketClaim.claim_expires_at.asc())
        .limit(batch_size)
        .with_for_update()
        .all()
    )

    buyer_refunds: list[dict[str, Any]] = []
    seller_expired: list[dict[str, Any]] = []

    for claim, listing in rows:
        if claim.claim_type == "BUYER":
            result = _expire_buyer_claim(db, claim, listing, now=now)
            if result:
                buyer_refunds.append(result)
        elif claim.claim_type == "SELLER":
            result = _expire_seller_claim(db, claim, listing, now=now)
            if result:
                seller_expired.append(result)

    if buyer_refunds or seller_expired:
        db.commit()

    return {
        "processed": len(buyer_refunds) + len(seller_expired),
        "buyer_refunds": buyer_refunds,
        "seller_expired": seller_expired,
    }


def list_seller_listings(db: Session, seller_steam_id: str) -> list[dict[str, Any]]:
    from app import MarketClaim, MarketListing

    expire_stale_claims(db)
    rows = (
        db.query(MarketListing)
        .filter(
            MarketListing.seller_steam_id == seller_steam_id,
            MarketListing.status.notin_(list(TERMINAL_LISTING)),
        )
        .order_by(MarketListing.updated_at.desc())
        .all()
    )
    listing_ids = [r.id for r in rows]
    claims_by_listing: dict[int, Any] = {}
    if listing_ids:
        for claim in (
            db.query(MarketClaim)
            .filter(
                MarketClaim.listing_id.in_(listing_ids),
                MarketClaim.status == "PENDENTE",
                or_(
                    MarketClaim.claim_status == CLAIM_STATUS_PENDING,
                    MarketClaim.claim_status.is_(None),
                ),
            )
            .all()
        ):
            if not _claim_is_expired(claim):
                claims_by_listing[claim.listing_id] = claim

    species_by_key = _species_map(db, {r.species_key for r in rows})
    prof = get_profile(db, seller_steam_id)
    seller_name = prof.market_display_name if prof else None
    out = []
    for row in rows:
        item = listing_to_public(
            row,
            include_breakdown=True,
            species_row=species_by_key.get(row.species_key or ""),
        )
        item["seller_display_name"] = seller_name
        pending = claims_by_listing.get(row.id)
        if pending:
            item.update(_claim_to_public(pending))
        out.append(item)
    return out


def get_listing_detail(
    db: Session,
    listing_id: int,
    *,
    viewer_steam_id: str | None = None,
) -> dict[str, Any]:
    from app import MarketListing, MarketPlayerProfile

    row = db.query(MarketListing).filter(MarketListing.id == listing_id).first()
    if not row:
        raise ValueError("Anúncio não encontrado")
    is_owner = viewer_steam_id and row.seller_steam_id == viewer_steam_id
    if row.status != "ACTIVE" and not is_owner:
        raise ValueError("Anúncio não disponível")
    species_row = resolve_species(db, species_key=row.species_key)
    item = listing_to_public(row, include_breakdown=True, species_row=species_row)
    prof = (
        db.query(MarketPlayerProfile)
        .filter(MarketPlayerProfile.steam_id == row.seller_steam_id)
        .first()
    )
    item["seller_display_name"] = prof.market_display_name if prof else None
    item["is_owner"] = bool(is_owner)
    return item


def pause_listing(db: Session, listing_id: int, seller_steam_id: str) -> dict[str, Any]:
    from app import MarketListing

    row = db.query(MarketListing).filter(MarketListing.id == listing_id).first()
    if not row:
        raise ValueError("Anúncio não encontrado")
    if row.seller_steam_id != seller_steam_id:
        raise ValueError("Sem permissão")
    if row.status != "ACTIVE":
        raise ValueError("Somente anúncios ACTIVE podem ser pausados")
    row.status = "PAUSED"
    row.updated_at = _now()
    db.commit()
    market_audit_event(
        db,
        "MARKET_LISTING_PAUSED",
        steam_id=seller_steam_id,
        listing_id=row.id,
        market_trace_id=row.market_trace_id,
        commit=True,
    )
    return listing_to_public(row)


def withdraw_listing(db: Session, listing_id: int, seller_steam_id: str) -> dict[str, Any]:
    from app import MarketClaim, MarketListing

    row = db.query(MarketListing).filter(MarketListing.id == listing_id).first()
    if not row:
        raise ValueError("Anúncio não encontrado")
    if row.seller_steam_id != seller_steam_id:
        raise ValueError("Sem permissão")
    if row.status not in ("DRAFT", "ACTIVE", "PAUSED", "PENDING_CLASSIFICATION"):
        raise ValueError(f"Status não permite resgate: {row.status}")

    now = _now()
    row.status = "AWAITING_CLAIM"
    row.updated_at = now
    claim = MarketClaim(
        listing_id=row.id,
        recipient_steam_id=seller_steam_id,
        claim_type="SELLER",
        status="PENDENTE",
        market_trace_id=row.market_trace_id,
        created_at=now,
        updated_at=now,
    )
    _apply_claim_reservation(claim, now=now)
    db.add(claim)
    db.commit()
    hrs = _hours_remaining(claim.claim_expires_at, now=now)
    market_audit_event(
        db,
        "MARKET_LISTING_WITHDRAW_REQUESTED",
        steam_id=seller_steam_id,
        listing_id=row.id,
        claim_id=claim.id,
        market_trace_id=row.market_trace_id,
        metadata={
            "claim_expires_at": claim.claim_expires_at.isoformat() if claim.claim_expires_at else None,
            "reservation_hours": CLAIM_RESERVATION_HOURS,
        },
        commit=True,
    )
    return {
        "listing_id": row.id,
        "claim_id": claim.id,
        "claim_expires_at": claim.claim_expires_at.isoformat() if claim.claim_expires_at else None,
        "hours_remaining": round(hrs, 2) if hrs is not None else CLAIM_RESERVATION_HOURS,
        "message": f"Use /mercado in-game em até {CLAIM_RESERVATION_HOURS}h para recuperar a cryopod.",
    }


def admin_remove_listing(
    db: Session,
    listing_id: int,
    admin_steam_id: str,
    *,
    reason: str = "",
) -> dict[str, Any]:
    """Remove anúncio abusivo — pausa e devolve cryopod ao vendedor (claim)."""
    from app import MarketClaim, MarketListing

    row = db.query(MarketListing).filter(MarketListing.id == listing_id).first()
    if not row:
        raise ValueError("Anúncio não encontrado")
    if row.status in TERMINAL_LISTING | {"AWAITING_CLAIM", "CANCELLED"}:
        raise ValueError(f"Status não permite remoção: {row.status}")

    now = _now()
    meta = _json_loads(row.metadata_json)
    meta["admin_removed"] = True
    meta["admin_removed_by"] = admin_steam_id
    if reason:
        meta["admin_remove_reason"] = reason[:280]
    row.metadata_json = _json_dumps(meta)
    row.status = "AWAITING_CLAIM"
    row.updated_at = now

    claim = MarketClaim(
        listing_id=row.id,
        recipient_steam_id=row.seller_steam_id,
        claim_type="SELLER",
        status="PENDENTE",
        market_trace_id=row.market_trace_id,
        created_at=now,
        updated_at=now,
    )
    _apply_claim_reservation(claim, now=now)
    db.add(claim)
    db.commit()

    market_audit_event(
        db,
        "MARKET_LISTING_ADMIN_REMOVED",
        steam_id=admin_steam_id,
        listing_id=row.id,
        claim_id=claim.id,
        market_trace_id=row.market_trace_id,
        metadata={"reason": reason[:280] if reason else None, "seller": row.seller_steam_id},
        commit=True,
    )
    try:
        notify_seller_listing_removed(
            db,
            seller_steam_id=row.seller_steam_id,
            listing_id=row.id,
            listing_title=_listing_title_for_notify(db, row),
            admin_steam_id=admin_steam_id,
            reason=reason,
            claim_id=claim.id,
            market_trace_id=row.market_trace_id,
        )
    except Exception as exc:
        log.warning("notify_seller_listing_removed falhou listing=%s: %s", row.id, exc)
    return {
        "listing_id": row.id,
        "claim_id": claim.id,
        "status": row.status,
        "message": "Anúncio removido — vendedor pode resgatar com /mercado.",
    }


def admin_set_listing_price(
    db: Session,
    listing_id: int,
    admin_steam_id: str,
    price_absolute: int,
    *,
    pause: bool = False,
) -> dict[str, Any]:
    """Ajusta preço de anúncio (admin — ignora teto)."""
    from app import MarketListing

    row = db.query(MarketListing).filter(MarketListing.id == listing_id).first()
    if not row:
        raise ValueError("Anúncio não encontrado")
    if row.status in TERMINAL_LISTING | {"AWAITING_CLAIM"}:
        raise ValueError(f"Status não permite edição: {row.status}")

    price = max(0, int(price_absolute))
    row.price_absolute = price
    row.effective_price = price
    row.price_mode = "ABSOLUTE"
    if pause and row.status == "ACTIVE":
        row.status = "PAUSED"
    meta = _json_loads(row.metadata_json)
    meta["admin_price_adjusted_by"] = admin_steam_id
    row.metadata_json = _json_dumps(meta)
    row.updated_at = _now()
    db.commit()

    market_audit_event(
        db,
        "MARKET_LISTING_ADMIN_PRICE",
        steam_id=admin_steam_id,
        listing_id=row.id,
        effective_price=price,
        market_trace_id=row.market_trace_id,
        metadata={"paused": pause},
        commit=True,
    )
    species_row = resolve_species(db, species_key=row.species_key)
    return listing_to_public(row, include_breakdown=True, species_row=species_row)


def admin_flag_listing(
    db: Session,
    listing_id: int,
    admin_steam_id: str,
    *,
    reason: str = "",
    pause: bool = True,
) -> dict[str, Any]:
    """Marca anúncio como abusivo e opcionalmente pausa."""
    from app import MarketListing

    row = db.query(MarketListing).filter(MarketListing.id == listing_id).first()
    if not row:
        raise ValueError("Anúncio não encontrado")

    meta = _json_loads(row.metadata_json)
    meta["admin_flagged"] = True
    meta["admin_flagged_by"] = admin_steam_id
    if reason:
        meta["admin_flag_reason"] = reason[:280]
    row.metadata_json = _json_dumps(meta)
    if pause and row.status == "ACTIVE":
        row.status = "PAUSED"
    row.updated_at = _now()
    db.commit()

    market_audit_event(
        db,
        "MARKET_LISTING_ADMIN_FLAGGED",
        steam_id=admin_steam_id,
        listing_id=row.id,
        market_trace_id=row.market_trace_id,
        metadata={"reason": reason[:280] if reason else None, "paused": pause},
        commit=True,
    )
    try:
        notify_seller_listing_flagged(
            db,
            seller_steam_id=row.seller_steam_id,
            listing_id=row.id,
            listing_title=_listing_title_for_notify(db, row),
            admin_steam_id=admin_steam_id,
            reason=reason,
            paused=pause and row.status == "PAUSED",
            market_trace_id=row.market_trace_id,
        )
    except Exception as exc:
        log.warning("notify_seller_listing_flagged falhou listing=%s: %s", row.id, exc)
    species_row = resolve_species(db, species_key=row.species_key)
    return listing_to_public(row, species_row=species_row)


def process_plugin_admin_action(db: Session, body: dict[str, Any]) -> dict[str, Any]:
    """Ações admin in-game (/mercado_admin) via plugin."""
    admin_steam_id = str(body.get("admin_steam_id") or "").strip()
    action = str(body.get("action") or "").strip().lower()
    listing_id = int(body.get("listing_id") or 0)
    if not admin_steam_id:
        raise ValueError("admin_steam_id obrigatório")
    if listing_id <= 0:
        raise ValueError("listing_id inválido")

    from app import STAFF_ROLE_GROUPS, _get_player_staff_roles, _is_admin_steamid

    allowed = _is_admin_steamid(admin_steam_id)
    if not allowed:
        for role in _get_player_staff_roles(admin_steam_id):
            if str(role.get("group") or "") in STAFF_ROLE_GROUPS:
                allowed = True
                break
    if not allowed:
        raise ValueError("Sem permissão de admin")

    if action in ("remover", "remove"):
        return admin_remove_listing(
            db,
            listing_id,
            admin_steam_id,
            reason=str(body.get("reason") or ""),
        )
    if action in ("preco", "price"):
        price = body.get("price_absolute") or body.get("price")
        if price is None:
            raise ValueError("price obrigatório para ação preco")
        return admin_set_listing_price(
            db,
            listing_id,
            admin_steam_id,
            int(price),
            pause=bool(body.get("pause", False)),
        )
    if action in ("flag", "flaggar"):
        return admin_flag_listing(
            db,
            listing_id,
            admin_steam_id,
            reason=str(body.get("reason") or ""),
            pause=bool(body.get("pause", True)),
        )
    raise ValueError("Ação inválida — use remover, preco ou flag")


def _apply_economy_to_listing_row(db: Session, row: Any, species_row: Any) -> int:
    """Recalcula valor sugerido, breakdown e stats denormalizados."""
    meta = _json_loads(row.metadata_json or "{}")
    computed, breakdown, _ = _compute_economy(db, species_row, meta)
    row.computed_base_value = computed
    row.effective_price = computed
    meta["calculation_breakdown"] = breakdown
    if meta.get("stats_max"):
        meta["extraction_method"] = meta.get("extraction_method") or "inverse_calc"
    row.metadata_json = _json_dumps(meta)
    denorm = _denorm_stats(meta)
    for k, v in denorm.items():
        setattr(row, k, v)
    row.updated_at = _now()
    return computed


def promote_listings_on_species_activate(db: Session, species_key: str) -> int:
    """Espécie ativada na economia não promove listings — classificação admin é obrigatória."""
    return 0


def _finalize_listing_classification(db: Session, row: Any, species_row: Any) -> int:
    """Aplica economia, marca aprovação admin e promove para DRAFT."""
    meta = _json_loads(row.metadata_json)
    meta["admin_classification_approved"] = True
    meta.pop("classification_suggestion", None)
    row.metadata_json = _json_dumps(meta)
    if species_row.species_key and row.species_key != species_row.species_key:
        row.species_key = species_row.species_key
    computed = _apply_economy_to_listing_row(db, row, species_row)
    row.status = "DRAFT"
    market_audit_event(
        db,
        "MARKET_LISTING_PROMOTED",
        steam_id=row.seller_steam_id,
        listing_id=row.id,
        computed_base_value=computed,
        market_trace_id=row.market_trace_id,
        metadata={"promoted_to": "DRAFT", "species_key": species_row.species_key},
        commit=False,
    )
    return computed


def _promote_pending_listing_row(
    db: Session, row: Any, *, species_key: str | None = None, species_row: Any | None = None
) -> bool:
    """DRAFT + computed_base_value se espécie ACTIVE e listing ainda não aprovado."""
    sk = species_key or row.species_key
    resolved = species_row or (resolve_species(db, species_key=sk) if sk else None)
    if not resolved or resolved.status != "ACTIVE":
        return False
    meta = _json_loads(row.metadata_json)
    if not _needs_admin_classification(row, meta):
        return False
    _finalize_listing_classification(db, row, resolved)
    return True


def recompute_draft_listings(db: Session) -> int:
    """Recalcula preço sugerido de anúncios DRAFT/PAUSED (corrige cálculo antigo)."""
    from app import MarketListing

    rows = (
        db.query(MarketListing)
        .filter(MarketListing.status.in_(["DRAFT", "PAUSED"]))
        .all()
    )
    count = 0
    for row in rows:
        species_row = resolve_species(db, species_key=row.species_key)
        if not species_row:
            meta = _json_loads(row.metadata_json or "{}")
            bp = meta.get("species_blueprint") or meta.get("blueprint")
            if bp:
                species_row = resolve_species(db, blueprint=str(bp))
        if not species_row or species_row.status != "ACTIVE":
            continue
        if species_row.species_key and row.species_key != species_row.species_key:
            row.species_key = species_row.species_key
        _apply_economy_to_listing_row(db, row, species_row)
        count += 1
        market_audit_event(
            db,
            "MARKET_LISTING_RECOMPUTED",
            steam_id=row.seller_steam_id,
            listing_id=row.id,
            computed_base_value=row.computed_base_value,
            market_trace_id=row.market_trace_id,
            metadata={"species_key": species_row.species_key},
            commit=False,
        )
    if count:
        db.commit()
    return count


def reconcile_pending_listings(db: Session) -> int:
    """Recalcula DRAFT já aprovados; não promove fila de classificação sem admin."""
    recompute_draft_listings(db)
    return 0


def list_pending_classification(db: Session, *, limit: int = 100) -> list[dict[str, Any]]:
    from app import MarketListing, MarketPlayerProfile

    rows = (
        db.query(MarketListing)
        .filter(MarketListing.status.in_(["PENDING_CLASSIFICATION", "DRAFT"]))
        .order_by(MarketListing.created_at.desc())
        .limit(min(limit, 200))
        .all()
    )
    rows = [r for r in rows if _needs_admin_classification(r)]
    names = {
        p.steam_id: p.market_display_name
        for p in db.query(MarketPlayerProfile)
        .filter(MarketPlayerProfile.steam_id.in_([r.seller_steam_id for r in rows]))
        .all()
    }
    species_by_key = _species_map(db, {r.species_key for r in rows})
    out = []
    for row in rows:
        meta = _json_loads(row.metadata_json)
        sug = _classification_from_meta(meta) or _resolve_listing_suggestion(row, meta=meta)
        sk = row.species_key or (sug or {}).get("species_key")
        item = listing_to_public(
            row,
            include_breakdown=True,
            species_row=species_by_key.get(sk or ""),
        )
        item["seller_display_name"] = names.get(row.seller_steam_id)
        out.append(item)
    return out


def admin_classify_listing(
    db: Session,
    listing_id: int,
    *,
    species_key: str | None = None,
    display_name: str | None = None,
    tier: str | None = None,
    root_value: int | None = None,
    approve: bool = True,
) -> dict[str, Any]:
    """Confirma ou ajusta classificação admin e promove listing para DRAFT."""
    from datetime import datetime, timezone

    from app import MarketListing, MarketSpecies

    row = (
        db.query(MarketListing)
        .filter(MarketListing.id == listing_id)
        .with_for_update()
        .first()
    )
    if not row:
        raise ValueError("Anúncio não encontrado")
    meta = _json_loads(row.metadata_json)
    if not _needs_admin_classification(row, meta):
        raise ValueError(f"Status não permite classificação: {row.status}")

    blueprint = str(meta.get("species_blueprint") or meta.get("blueprint") or "")
    suggestion = _classification_from_meta(meta) or lookup_species(
        blueprint=blueprint,
        species_key=row.species_key,
        name_hint=row.dino_display_name,
    )

    sk = (species_key or row.species_key or (suggestion or {}).get("species_key") or "").strip()
    if not sk:
        raise ValueError("species_key obrigatório para classificar")

    species_row = resolve_species(db, species_key=sk, blueprint=blueprint or None)
    if species_row is None:
        base_sug = dict(suggestion or {})
        base_sug.update(
            {
                "species_key": sk,
                "display_name": display_name or base_sug.get("display_name") or sk,
                "tier": tier or base_sug.get("tier") or "B",
                "root_value": root_value if root_value is not None else base_sug.get("root_value", 2500),
            }
        )
        species_row = ensure_pre_registered_species(db, base_sug, blueprint=blueprint)

    if display_name:
        species_row.display_name = display_name.strip()
    if tier:
        validated = validate_listing_category(tier)
        if validated:
            species_row.tier = validated
    if root_value is not None:
        species_row.root_value = int(root_value)

    if approve:
        species_row.status = "ACTIVE"
        species_row.activated_at = datetime.now(timezone.utc)

    row.species_key = species_row.species_key
    db.flush()

    promoted = False
    if approve and species_row.status == "ACTIVE":
        promoted = _finalize_listing_classification(db, row, species_row)
    elif approve:
        meta["admin_classification_approved"] = True
        meta.pop("classification_suggestion", None)
        row.metadata_json = _json_dumps(meta)
        row.status = "DRAFT"
        row.updated_at = _now()

    db.commit()

    market_audit_event(
        db,
        "MARKET_LISTING_CLASSIFIED",
        listing_id=row.id,
        steam_id=row.seller_steam_id,
        computed_base_value=row.computed_base_value,
        market_trace_id=row.market_trace_id,
        metadata={
            "species_key": species_row.species_key,
            "tier": species_row.tier,
            "root_value": species_row.root_value,
            "approved": approve,
            "promoted": promoted,
        },
        commit=True,
    )

    return {
        "listing_id": row.id,
        "species_key": species_row.species_key,
        "species_status": species_row.status,
        "listing_status": row.status,
        "promoted": promoted,
        "computed_base_value": row.computed_base_value,
    }


def admin_bulk_classify_listings(
    db: Session,
    *,
    listing_ids: list[int] | None = None,
    min_confidence: str = "high",
    limit: int = 50,
) -> dict[str, Any]:
    """Aprova em lote listings com sugestão de confiança >= min_confidence."""
    from app import MarketListing

    conf_rank = {"high": 3, "medium": 2, "low": 1}
    min_rank = conf_rank.get(min_confidence, 3)

    q = db.query(MarketListing).filter(MarketListing.status.in_(["PENDING_CLASSIFICATION", "DRAFT"]))
    if listing_ids:
        q = q.filter(MarketListing.id.in_(listing_ids))
    rows = q.order_by(MarketListing.created_at.asc()).limit(min(limit, 100)).all()

    approved: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for row in rows:
        meta = _json_loads(row.metadata_json)
        if not _needs_admin_classification(row, meta):
            continue
        suggestion = _classification_from_meta(meta) or lookup_species(
            blueprint=str(meta.get("species_blueprint") or meta.get("blueprint") or ""),
            species_key=row.species_key,
            name_hint=row.dino_display_name,
        )
        conf = conf_rank.get((suggestion or {}).get("confidence", ""), 0)
        if not suggestion or conf < min_rank or suggestion.get("needs_review"):
            skipped.append({"listing_id": row.id, "reason": "low_confidence"})
            continue
        try:
            result = admin_classify_listing(db, row.id, approve=True)
            approved.append(result)
        except ValueError as exc:
            skipped.append({"listing_id": row.id, "reason": str(exc)})

    return {"approved": approved, "skipped": skipped, "approved_count": len(approved)}


def _sale_delivery_status(listing: Any | None, claim: Any | None) -> str:
    if listing is None:
        return "desconhecido"
    st = listing.status
    if st == "DELIVERED":
        return "entregue"
    claim_status = getattr(claim, "claim_status", None)
    if claim_status in (CLAIM_STATUS_EXPIRED, CLAIM_STATUS_REFUNDED):
        return "expirado"
    if getattr(claim, "status", None) == "REEMBOLSADO":
        return "reembolsado"
    if st == "AWAITING_CLAIM":
        return "aguardando_resgate"
    if st == "RESERVING":
        return "processando"
    return (st or "vendido").lower()


def player_market_history(db: Session, steam_id: str, *, limit: int = 50) -> dict[str, Any]:
    from app import MarketClaim, MarketListing, MarketPlayerProfile, MarketTransaction

    expire_stale_claims(db)
    sales = (
        db.query(MarketTransaction)
        .filter(MarketTransaction.seller_steam_id == steam_id)
        .order_by(MarketTransaction.created_at.desc())
        .limit(limit)
        .all()
    )
    purchases = (
        db.query(MarketTransaction)
        .filter(MarketTransaction.buyer_steam_id == steam_id)
        .order_by(MarketTransaction.created_at.desc())
        .limit(limit)
        .all()
    )
    uploads = (
        db.query(MarketListing)
        .filter(MarketListing.seller_steam_id == steam_id)
        .order_by(MarketListing.created_at.desc())
        .limit(limit)
        .all()
    )

    sale_listing_ids = list({t.listing_id for t in sales})
    purchase_listing_ids = [t.listing_id for t in purchases]
    all_listing_ids = list(set(sale_listing_ids + purchase_listing_ids))

    listings_by_id: dict[int, Any] = {}
    if all_listing_ids:
        listings_by_id = {
            row.id: row
            for row in db.query(MarketListing).filter(MarketListing.id.in_(all_listing_ids)).all()
        }

    species_by_key = _species_map(
        db, {getattr(l, "species_key", None) for l in listings_by_id.values()}
    )

    counterparty_ids: set[str] = set()
    for t in sales:
        counterparty_ids.add(t.buyer_steam_id)
    for t in purchases:
        counterparty_ids.add(t.seller_steam_id)
    profile_names = (
        {
            p.steam_id: p.market_display_name
            for p in db.query(MarketPlayerProfile)
            .filter(MarketPlayerProfile.steam_id.in_(counterparty_ids))
            .all()
        }
        if counterparty_ids
        else {}
    )

    claims_by_listing_buyer: dict[int, Any] = {}
    if purchase_listing_ids:
        for claim in (
            db.query(MarketClaim)
            .filter(
                MarketClaim.listing_id.in_(purchase_listing_ids),
                MarketClaim.recipient_steam_id == steam_id,
                MarketClaim.claim_type == "BUYER",
            )
            .order_by(MarketClaim.created_at.desc())
            .all()
        ):
            if claim.listing_id not in claims_by_listing_buyer:
                claims_by_listing_buyer[claim.listing_id] = claim

    claims_by_listing_seller: dict[int, Any] = {}
    buyer_by_listing = {t.listing_id: t.buyer_steam_id for t in sales}
    if sale_listing_ids:
        for claim in (
            db.query(MarketClaim)
            .filter(
                MarketClaim.listing_id.in_(sale_listing_ids),
                MarketClaim.claim_type == "BUYER",
            )
            .order_by(MarketClaim.created_at.desc())
            .all()
        ):
            if claim.listing_id in claims_by_listing_seller:
                continue
            if claim.recipient_steam_id == buyer_by_listing.get(claim.listing_id):
                claims_by_listing_seller[claim.listing_id] = claim

    def _listing_summary(listing: Any | None) -> dict[str, Any]:
        if listing is None:
            return {}
        species_row = species_by_key.get(listing.species_key or "")
        pub = listing_to_public(listing, species_row=species_row)
        return {
            "display_title": pub.get("display_title"),
            "species_display_name": pub.get("species_display_name"),
            "custom_name": pub.get("custom_name"),
            "dino_display_name": pub.get("dino_display_name"),
            "status": listing.status,
        }

    def tx_row(t: Any, *, is_purchase: bool = False) -> dict[str, Any]:
        listing = listings_by_id.get(t.listing_id)
        row: dict[str, Any] = {
            "listing_id": t.listing_id,
            "price_paid": t.price_paid,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        row.update(_listing_summary(listing))
        if is_purchase:
            claim = claims_by_listing_buyer.get(t.listing_id)
            row["seller_steam_id"] = t.seller_steam_id
            row["seller_display_name"] = profile_names.get(t.seller_steam_id)
            if claim:
                row.update(_claim_to_public(claim))
        else:
            row["buyer_steam_id"] = t.buyer_steam_id
            row["buyer_display_name"] = profile_names.get(t.buyer_steam_id)
            claim = claims_by_listing_seller.get(t.listing_id)
            if claim:
                row.update(_claim_to_public(claim))
            row["delivery_status"] = _sale_delivery_status(listing, claim)
        return row

    return {
        "sales": [tx_row(t) for t in sales],
        "purchases": [tx_row(t, is_purchase=True) for t in purchases],
        "uploads": [
            {
                "listing_id": u.id,
                "status": u.status,
                "species_key": u.species_key,
                "dino_display_name": u.dino_display_name,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in uploads
        ],
        "reservation_hours": CLAIM_RESERVATION_HOURS,
    }


def list_seller_vitrine_audit_events(
    db: Session,
    seller_steam_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Eventos da vitrine visíveis ao vendedor (vendas, moderação, resgates)."""
    from app import MarketAuditEvent

    q = (
        db.query(MarketAuditEvent)
        .filter(
            MarketAuditEvent.steam_id == seller_steam_id,
            MarketAuditEvent.event_type.in_(SELLER_VITRINE_EVENT_TYPES),
        )
        .order_by(MarketAuditEvent.created_at.desc())
    )
    rows = q.offset(offset).limit(min(limit, 100)).all()
    out = []
    for row in rows:
        meta = _json_loads(row.metadata_json) if row.metadata_json else {}
        out.append(
            {
                "id": row.id,
                "event_type": row.event_type,
                "listing_id": row.listing_id,
                "claim_id": row.claim_id,
                "effective_price": row.effective_price,
                "counterparty_steam_id": row.counterparty_steam_id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "metadata": meta,
            }
        )
    return out


def list_market_audit_events(
    db: Session,
    *,
    event_type: str | None = None,
    steam_id: str | None = None,
    market_trace_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    from app import MarketAuditEvent

    q = db.query(MarketAuditEvent).order_by(MarketAuditEvent.created_at.desc())
    if event_type:
        q = q.filter(MarketAuditEvent.event_type == event_type)
    if steam_id:
        q = q.filter(MarketAuditEvent.steam_id == steam_id)
    if market_trace_id:
        q = q.filter(MarketAuditEvent.market_trace_id == market_trace_id)
    rows = q.offset(offset).limit(min(limit, 500)).all()
    out = []
    for row in rows:
        meta = _json_loads(row.metadata_json) if row.metadata_json else {}
        out.append(
            {
                "id": row.id,
                "event_type": row.event_type,
                "severity": row.severity,
                "steam_id": row.steam_id,
                "counterparty_steam_id": row.counterparty_steam_id,
                "listing_id": row.listing_id,
                "vault_id": row.vault_id,
                "claim_id": row.claim_id,
                "blob_hash": row.blob_hash,
                "computed_base_value": row.computed_base_value,
                "effective_price": row.effective_price,
                "market_trace_id": row.market_trace_id,
                "source": row.source,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "metadata": meta,
            }
        )
    return out
