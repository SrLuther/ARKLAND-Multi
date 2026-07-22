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
from market_audit import market_audit_event, market_audit_label
from market_notify import (
    SELLER_VITRINE_EVENT_TYPES,
    notify_seller_buyer_claimed,
    notify_seller_listing_flagged,
    notify_seller_listing_removed,
    notify_seller_listing_sold,
    notify_staff_market_alert,
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
from market_pair import (
    is_pair_listing,
    is_pair_primary,
    pair_checkout_price,
    pair_claim_refund,
    pair_pricing_breakdown,
    pair_prize_contribution,
    validate_pair_eligibility,
)
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
    from app import StoreUser

    row = db.get(StoreUser, steam_id)
    if not row:
        return None
    persona = (row.steam_persona or "").strip()
    if persona and persona != steam_id:
        return persona
    return None


def _steam_personas_map(db: Session, steam_ids: list[str]) -> dict[str, str]:
    from app import StoreUser

    if not steam_ids:
        return {}
    rows = db.query(StoreUser).filter(StoreUser.steam_id.in_(steam_ids)).all()
    out: dict[str, str] = {}
    for row in rows:
        persona = (row.steam_persona or "").strip()
        if persona and persona != row.steam_id:
            out[row.steam_id] = persona
    return out


def _listing_title_for_notify(db: Session, row: Any) -> str:
    species_row = resolve_species(db, species_key=row.species_key)
    return _listing_display_title(row, species_row)


def commerce_ready(db: Session, steam_id: str) -> tuple[bool, str | None]:
    prof = get_profile(db, steam_id)
    if not prof:
        return False, "Perfil de comércio não habilitado."
    if not prof.commerce_enabled:
        return False, "Perfil de comércio não habilitado."
    return True, None


def upsert_display_name(db: Session, steam_id: str, name: str) -> dict[str, Any]:
    """Legado: nick Steam vem da API — sincroniza market_display_name com steam_persona."""
    from app import MarketPlayerProfile, StoreUser

    row = db.get(StoreUser, steam_id)
    persona = (row.steam_persona or "").strip() if row else ""
    if not persona or persona == steam_id:
        raise ValueError("Nick Steam indisponível — faça login com Steam e configure STEAM_API_KEY.")
    now = _now()
    prof = get_profile(db, steam_id)
    if prof is None:
        prof = MarketPlayerProfile(
            steam_id=steam_id,
            market_display_name=persona,
            name_updated_at=now,
            commerce_enabled=True,
            created_at=now,
            updated_at=now,
        )
        db.add(prof)
    else:
        prof.market_display_name = persona
        prof.name_updated_at = now
        prof.commerce_enabled = True
        prof.updated_at = now
    db.commit()
    return {"steam_id": steam_id, "market_display_name": persona, "steam_persona": persona, "commerce_enabled": True}


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
    from dino_lab_block_service import (
        DINO_LAB_BLOCK_MESSAGE,
        enforce_market_dino_identity,
        lookup_blocked_from_metadata,
    )

    try:
        enforce_market_dino_identity(meta)
    except ValueError as exc:
        return {
            "ok": False,
            "blocked": True,
            "reason": "dino_identity_required",
            "error": str(exc),
            "message": str(exc),
            "computed_base_value": 0,
            "calculation_breakdown": [],
        }
    match = lookup_blocked_from_metadata(db, meta)
    if match:
        return {
            "ok": False,
            "blocked": True,
            "reason": "dino_lab_blocked",
            "error": match.get("message") or DINO_LAB_BLOCK_MESSAGE,
            "message": match.get("message") or DINO_LAB_BLOCK_MESSAGE,
            "order_id": match.get("order_id"),
            "canonical_id": match.get("canonical_id"),
            "matched_pair": match.get("matched_pair"),
            "computed_base_value": 0,
            "calculation_breakdown": [],
        }
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

    from dino_lab_block_service import (
        DINO_LAB_BLOCK_MESSAGE,
        enforce_market_dino_identity,
        lookup_blocked_from_metadata,
    )

    enforce_market_dino_identity(metadata)
    match = lookup_blocked_from_metadata(db, metadata)
    if match:
        raise ValueError(match.get("message") or DINO_LAB_BLOCK_MESSAGE)

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
        "is_pair": is_pair_listing(row),
        "pair_mate_listing_id": getattr(row, "pair_mate_listing_id", None),
        "pair_group_id": getattr(row, "pair_group_id", None),
        "is_pair_primary": is_pair_primary(row) if is_pair_listing(row) else False,
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


def _load_pair_mate(db: Session, row: Any) -> Any | None:
    mate_id = getattr(row, "pair_mate_listing_id", None)
    if not mate_id:
        return None
    from app import MarketListing

    return db.query(MarketListing).filter(MarketListing.id == int(mate_id)).first()


def enrich_listing_pair_fields(
    db: Session,
    item: dict[str, Any],
    row: Any,
    *,
    species_by_key: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Anexa mate + preço Y no payload público (sem badge −40%/taxa)."""
    if not is_pair_listing(row):
        item["listing_kind"] = "single"
        return item
    mate = _load_pair_mate(db, row)
    if not mate:
        item["listing_kind"] = "single"
        item["is_pair"] = False
        return item
    species_row = None
    if species_by_key is not None:
        species_row = species_by_key.get(mate.species_key or "")
    else:
        species_row = resolve_species(db, species_key=mate.species_key)
    mate_pub = listing_to_public(mate, species_row=species_row)
    asking_self = int(row.effective_price or 0)
    asking_mate = int(mate.effective_price or 0)
    pricing = pair_pricing_breakdown(asking_self, asking_mate)
    suggested_self = int(row.computed_base_value or 0)
    suggested_mate = int(mate.computed_base_value or 0)
    suggested_sum = suggested_self + suggested_mate
    # Pedido individual deste anúncio (nunca Y). UI de edição/vendedor usa isto.
    item["asking_price"] = asking_self
    mate_pub["asking_price"] = asking_mate
    item["listing_kind"] = "pair"
    item["is_pair"] = True
    item["is_pair_primary"] = is_pair_primary(row)
    item["pair_mate"] = mate_pub
    item["pair_asking_sum"] = pricing["sum_asking"]
    item["pair_checkout_price"] = pricing["checkout_price"]
    item["pair_suggested_sum"] = suggested_sum
    # Breakdown estável para UI (Macho/Fêmea · pedido · sugerido)
    def _creature_stats_fields(pub: dict[str, Any]) -> dict[str, Any]:
        return {
            "dino_level": pub.get("dino_level"),
            "mutations_male": pub.get("mutations_male"),
            "mutations_female": pub.get("mutations_female"),
            "stats": pub.get("stats") or {},
        }

    self_line = {
        "listing_id": int(row.id),
        "is_female": bool(row.is_female),
        "asking_price": asking_self,
        "suggested_value": suggested_self,
        "display_title": item.get("display_title") or item.get("species_display_name"),
        **_creature_stats_fields(item),
    }
    mate_line = {
        "listing_id": int(mate.id),
        "is_female": bool(mate.is_female),
        "asking_price": asking_mate,
        "suggested_value": suggested_mate,
        "display_title": mate_pub.get("display_title") or mate_pub.get("species_display_name"),
        **_creature_stats_fields(mate_pub),
    }
    male_line = mate_line if self_line["is_female"] else self_line
    female_line = self_line if self_line["is_female"] else mate_line
    item["pair_breakdown"] = {
        "male": male_line,
        "female": female_line,
        "sum_asking": pricing["sum_asking"],
        "checkout_price": pricing["checkout_price"],
        "suggested_sum": suggested_sum,
    }
    # Preço exibido na vitrine / ordenação = Y (checkout); pedidos individuais em asking_price
    if is_pair_primary(row):
        item["effective_price"] = pricing["checkout_price"]
        item["display_price"] = pricing["checkout_price"]
    else:
        item["display_price"] = pricing["checkout_price"]
    return item


def list_active_listings(
    db: Session,
    *,
    species_key: str | None = None,
    seller_steam_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    from app import MarketListing

    limit = max(1, min(100, int(limit)))
    offset = max(0, int(offset))
    q = db.query(MarketListing).filter(MarketListing.status == "ACTIVE")
    if species_key:
        q = q.filter(MarketListing.species_key == species_key)
    if seller_steam_id:
        q = q.filter(MarketListing.seller_steam_id == seller_steam_id)
    # Casal: só o primário (menor id) na vitrine — filtro no SQL (paginação correcta).
    q = q.filter(
        or_(
            MarketListing.pair_mate_listing_id.is_(None),
            MarketListing.id < MarketListing.pair_mate_listing_id,
        )
    )
    rows = (
        q.order_by(MarketListing.effective_price.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    names = _steam_personas_map(db, [r.seller_steam_id for r in rows])
    species_by_key = _species_map(db, {r.species_key for r in rows})
    out = []
    for row in rows:
        item = listing_to_public(row, species_row=species_by_key.get(row.species_key or ""))
        item["seller_display_name"] = names.get(row.seller_steam_id)
        enrich_listing_pair_fields(db, item, row, species_by_key=species_by_key)
        out.append(item)
    return out


def link_pair_listings(
    db: Session,
    listing_id: int,
    mate_listing_id: int,
    seller_steam_id: str,
) -> dict[str, Any]:
    """Vincula macho+fêmea da mesma espécie num anúncio de casal."""
    from app import MarketListing

    a = db.query(MarketListing).filter(MarketListing.id == listing_id).first()
    b = db.query(MarketListing).filter(MarketListing.id == mate_listing_id).first()
    if not a or not b:
        raise ValueError("Anúncio não encontrado")
    if a.seller_steam_id != seller_steam_id or b.seller_steam_id != seller_steam_id:
        raise ValueError("Sem permissão")
    validate_pair_eligibility(a, b)
    # Desvincula pares anteriores se re-link no mesmo par
    for row in (a, b):
        old_mate = getattr(row, "pair_mate_listing_id", None)
        if old_mate and int(old_mate) not in (int(a.id), int(b.id)):
            other = db.query(MarketListing).filter(MarketListing.id == int(old_mate)).first()
            if other:
                other.pair_mate_listing_id = None
                other.pair_group_id = None
                other.updated_at = _now()
    group_id = str(uuid.uuid4())
    a.pair_mate_listing_id = int(b.id)
    b.pair_mate_listing_id = int(a.id)
    a.pair_group_id = group_id
    b.pair_group_id = group_id
    a.updated_at = _now()
    b.updated_at = _now()
    db.commit()
    market_audit_event(
        db,
        "MARKET_PAIR_LINKED",
        steam_id=seller_steam_id,
        listing_id=a.id,
        market_trace_id=a.market_trace_id,
        metadata={
            "mate_listing_id": b.id,
            "pair_group_id": group_id,
            "species_key": a.species_key,
            "summary_pt": f"Casal vinculado: #{a.id} + #{b.id}",
        },
        commit=True,
    )
    species_row = resolve_species(db, species_key=a.species_key)
    item = listing_to_public(a, include_breakdown=True, species_row=species_row)
    enrich_listing_pair_fields(db, item, a)
    return item


def unlink_pair_listings(
    db: Session,
    listing_id: int,
    seller_steam_id: str,
) -> dict[str, Any]:
    """Remove vínculo de casal; ambos voltam a solteiros."""
    from app import MarketListing

    row = db.query(MarketListing).filter(MarketListing.id == listing_id).first()
    if not row:
        raise ValueError("Anúncio não encontrado")
    if row.seller_steam_id != seller_steam_id:
        raise ValueError("Sem permissão")
    if not is_pair_listing(row):
        raise ValueError("Anúncio não faz parte de um casal")
    if row.status not in ("DRAFT", "PAUSED", "PENDING_CLASSIFICATION", "ACTIVE"):
        raise ValueError(f"Status não permite desvincular casal: {row.status}")
    mate = _load_pair_mate(db, row)
    group_id = getattr(row, "pair_group_id", None)
    row.pair_mate_listing_id = None
    row.pair_group_id = None
    row.updated_at = _now()
    if mate:
        if mate.status in ("DRAFT", "PAUSED", "PENDING_CLASSIFICATION", "ACTIVE"):
            mate.pair_mate_listing_id = None
            mate.pair_group_id = None
            mate.updated_at = _now()
        else:
            raise ValueError("Parceiro do casal não está em status editável")
    db.commit()
    market_audit_event(
        db,
        "MARKET_PAIR_UNLINKED",
        steam_id=seller_steam_id,
        listing_id=row.id,
        market_trace_id=row.market_trace_id,
        metadata={
            "mate_listing_id": mate.id if mate else None,
            "pair_group_id": group_id,
            "summary_pt": f"Casal desvinculado: #{row.id}",
        },
        commit=True,
    )
    species_row = resolve_species(db, species_key=row.species_key)
    return listing_to_public(row, include_breakdown=True, species_row=species_row)


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
        # Casal: ambos devem estar prontos; snapshot de tribo usa Y (crédito do vendedor)
        split_price = int(row.effective_price or 0)
        mate_row = None
        if is_pair_listing(row):
            mate_row = _load_pair_mate(db, row)
            if not mate_row:
                raise ValueError("Parceiro do casal não encontrado")
            if mate_row.status not in ("DRAFT", "PAUSED", "ACTIVE"):
                raise ValueError("Parceiro do casal não está pronto para ativar")
            mate_meta = _json_loads(mate_row.metadata_json)
            if _needs_admin_classification(mate_row, mate_meta):
                raise ValueError("Parceiro do casal aguarda classificação admin")
            if int(mate_row.effective_price or 0) < int(mate_row.computed_base_value or 0):
                raise ValueError("Parceiro do casal com preço abaixo do sugerido")
            split_price = pair_checkout_price(
                int(row.effective_price or 0),
                int(mate_row.effective_price or 0),
            )
            mate_row.status = "ACTIVE"
            mate_row.updated_at = _now()
        row.status = "ACTIVE"
        # Opt-in: Q1 — when teams_enabled, only team split (tribe split ignored).
        try:
            snap = None
            team_split_id = None
            teams_on = False
            try:
                from team_service import get_team_split_snapshot_for_listing, teams_enabled
                teams_on = bool(teams_enabled())
                if teams_on:
                    snap = get_team_split_snapshot_for_listing(
                        db,
                        seller_steam_id=seller_steam_id,
                        price=split_price,
                    )
                    if snap:
                        team_split_id = int(snap["split_id"])
            except Exception as _team_split_exc:
                log.debug("team split snapshot skip listing=%s: %s", row.id, _team_split_exc)
            if not snap and not teams_on:
                from tribe_service import (
                    find_tribe_owner_id_for_seller,
                    get_split_snapshot_for_listing,
                )
                oid = find_tribe_owner_id_for_seller(db, seller_steam_id)
                if oid is not None:
                    snap = get_split_snapshot_for_listing(
                        db,
                        oid,
                        split_price,
                        seller_steam_id=seller_steam_id,
                    )
            if snap:
                if team_split_id is not None:
                    if hasattr(row, "team_split_id"):
                        row.team_split_id = team_split_id
                    row.tribe_split_id = None
                else:
                    row.tribe_split_id = int(snap["split_id"])
                    if hasattr(row, "team_split_id"):
                        row.team_split_id = None
                row.split_snapshot = _json_dumps(snap)
                if mate_row is not None:
                    if team_split_id is not None:
                        if hasattr(mate_row, "team_split_id"):
                            mate_row.team_split_id = team_split_id
                        mate_row.tribe_split_id = None
                    else:
                        mate_row.tribe_split_id = int(snap["split_id"])
                        if hasattr(mate_row, "team_split_id"):
                            mate_row.team_split_id = None
                    mate_row.split_snapshot = _json_dumps(snap)
            else:
                row.tribe_split_id = None
                row.split_snapshot = None
                if hasattr(row, "team_split_id"):
                    row.team_split_id = None
                if mate_row is not None:
                    mate_row.tribe_split_id = None
                    mate_row.split_snapshot = None
                    if hasattr(mate_row, "team_split_id"):
                        mate_row.team_split_id = None
        except Exception as _split_exc:
            log.warning(
                "Split snapshot na ativação falhou listing=%s: %s",
                row.id, _split_exc,
            )
            row.tribe_split_id = None
            row.split_snapshot = None
            if mate_row is not None:
                mate_row.tribe_split_id = None
                mate_row.split_snapshot = None

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
            "tribe_split_id": getattr(row, "tribe_split_id", None),
            "split_applied": bool(getattr(row, "split_snapshot", None)),
        },
        commit=True,
    )
    species_row = resolve_species(db, species_key=row.species_key)
    item = listing_to_public(row, include_breakdown=True, species_row=species_row)
    enrich_listing_pair_fields(db, item, row)
    return item


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

    from dino_lab_block_service import DINO_LAB_BLOCK_MESSAGE, lookup_blocked_from_metadata

    listing_meta = _json_loads(getattr(row, "metadata_json", None) or "{}")
    buy_match = lookup_blocked_from_metadata(
        db, listing_meta if isinstance(listing_meta, dict) else {}
    )
    if buy_match:
        raise ValueError(buy_match.get("message") or DINO_LAB_BLOCK_MESSAGE)

    mate: Any | None = None
    is_pair = is_pair_listing(row)
    if is_pair:
        if not is_pair_primary(row):
            mate_locked_id = int(row.id)
            primary_id = int(row.pair_mate_listing_id)
            row = (
                db.query(MarketListing)
                .filter(MarketListing.id == primary_id)
                .with_for_update()
                .first()
            )
            if not row or row.status != "ACTIVE":
                raise ValueError("Anúncio de casal não disponível")
            mate = (
                db.query(MarketListing)
                .filter(MarketListing.id == mate_locked_id)
                .with_for_update()
                .first()
            )
        else:
            mate = (
                db.query(MarketListing)
                .filter(MarketListing.id == int(row.pair_mate_listing_id))
                .with_for_update()
                .first()
            )
        if not mate or mate.status != "ACTIVE":
            raise ValueError("Parceiro do casal não está disponível")
        if mate.seller_steam_id != row.seller_steam_id:
            raise ValueError("Casal inválido")
        mate_meta = _json_loads(getattr(mate, "metadata_json", None) or "{}")
        mate_match = lookup_blocked_from_metadata(
            db, mate_meta if isinstance(mate_meta, dict) else {}
        )
        if mate_match:
            raise ValueError(mate_match.get("message") or DINO_LAB_BLOCK_MESSAGE)

    if is_pair and mate is not None:
        price = pair_checkout_price(
            int(row.effective_price or 0),
            int(mate.effective_price or 0),
        )
        prize_contrib = pair_prize_contribution(
            int(row.effective_price or 0),
            int(mate.effective_price or 0),
        )
        base_at_sale = int(row.computed_base_value or 0) + int(mate.computed_base_value or 0)
    else:
        price = int(row.effective_price or 0)
        prize_contrib = 0
        base_at_sale = int(row.computed_base_value or 0)

    buyer_before = _player_points(db, buyer_steam_id)
    if buyer_before < price:
        raise ValueError(f"Saldo insuficiente ({buyer_before} < {price})")

    seller_before = _player_points(db, row.seller_steam_id)
    status_before = row.status

    row.status = "RESERVING"
    if mate is not None:
        mate.status = "RESERVING"
    db.flush()

    buyer_after = _debit_points(db, buyer_steam_id, price)

    # ── Divisão de ganhos de tribo (§18 — tribe split) ────────
    # Em casal, o snapshot / crédito usam Y (não S). fee_amount permanece 0.
    _split_snapshot = getattr(row, "split_snapshot", None)
    _split_payouts: list[dict] = []
    if _split_snapshot:
        try:
            from tribe_service import apply_split_payout
            _split_payouts = apply_split_payout(
                db,
                split_snapshot_json=_split_snapshot,
                price=price,
                seller_steam_id=row.seller_steam_id,
                listing_id=row.id,
                credit_fn=_credit_points,
            )
            seller_after = _player_points(db, row.seller_steam_id)
        except Exception as _split_exc:
            log.warning(
                "Split payout falhou listing=%s: %s — crédito integral ao vendedor",
                row.id, _split_exc
            )
            seller_after = _credit_points(db, row.seller_steam_id, price)
    else:
        seller_after = _credit_points(db, row.seller_steam_id, price)

    now = _now()
    row.status = "AWAITING_CLAIM"
    row.buyer_steam_id = buyer_steam_id
    row.sold_at = now
    row.updated_at = now
    if mate is not None:
        mate.status = "AWAITING_CLAIM"
        mate.buyer_steam_id = buyer_steam_id
        mate.sold_at = now
        mate.updated_at = now

    tx = MarketTransaction(
        listing_id=row.id,
        buyer_steam_id=buyer_steam_id,
        seller_steam_id=row.seller_steam_id,
        price_paid=price,
        base_value_at_sale=base_at_sale,
        fee_amount=0,
        buyer_points_before=buyer_before,
        buyer_points_after=buyer_after,
        seller_points_before=seller_before,
        seller_points_after=seller_after,
        market_trace_id=row.market_trace_id,
        created_at=now,
    )
    db.add(tx)
    db.flush()

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
    mate_claim = None
    if mate is not None:
        mate_claim = MarketClaim(
            listing_id=mate.id,
            recipient_steam_id=buyer_steam_id,
            claim_type="BUYER",
            status="PENDENTE",
            market_trace_id=mate.market_trace_id or row.market_trace_id,
            created_at=now,
            updated_at=now,
        )
        _apply_claim_reservation(mate_claim, now=now)
        db.add(mate_claim)

    prize_result: dict[str, Any] = {"credited": 0}
    if prize_contrib > 0:
        try:
            from lottery_service import contribute_market_pair_to_prize

            prize_result = contribute_market_pair_to_prize(
                db,
                amount=prize_contrib,
                listing_id=row.id,
                tx_id=int(tx.id),
                seller_steam_id=row.seller_steam_id,
            )
        except Exception as pot_exc:
            log.warning(
                "Contribuição sorteio casal falhou listing=%s: %s",
                row.id,
                pot_exc,
            )

    db.commit()

    market_audit_event(
        db,
        "MARKET_PURCHASE_COMPLETED",
        steam_id=buyer_steam_id,
        counterparty_steam_id=row.seller_steam_id,
        listing_id=row.id,
        computed_base_value=base_at_sale,
        effective_price=price,
        points_delta=-price,
        points_before=buyer_before,
        points_after=buyer_after,
        market_trace_id=row.market_trace_id,
        metadata={
            "seller_steam_id": row.seller_steam_id,
            "buyer_steam_id": buyer_steam_id,
            "listing_status_before": status_before,
            "listing_status_after": row.status,
            "is_pair": bool(mate is not None),
            "pair_mate_listing_id": mate.id if mate else None,
            "prize_contribution": prize_contrib,
            "prize_campaign_id": prize_result.get("campaign_id"),
            "summary_pt": (
                f"Compra {'casal' if mate else 'solteiro'} #{row.id}"
                + (f"+#{mate.id}" if mate else "")
                + f" por {price:,} Âmbar"
            ).replace(",", "."),
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

    try:
        from amber_ledger import record_market_purchase

        record_market_purchase(
            db,
            tx_id=int(tx.id),
            listing_id=row.id,
            buyer_steam_id=buyer_steam_id,
            seller_steam_id=row.seller_steam_id,
            price=price,
            commit=True,
        )
    except Exception as amber_exc:
        log.warning("Âmbarômetro market purchase hook: %s", amber_exc)

    hrs = _hours_remaining(claim.claim_expires_at, now=now)
    result = {
        "listing_id": row.id,
        "claim_id": claim.id,
        "price_paid": price,
        "buyer_balance": buyer_after,
        "claim_expires_at": claim.claim_expires_at.isoformat() if claim.claim_expires_at else None,
        "hours_remaining": round(hrs, 2) if hrs is not None else CLAIM_RESERVATION_HOURS,
        "message": f"Você tem {CLAIM_RESERVATION_HOURS} horas para resgatar com /mercado in-game.",
        "is_pair": bool(mate is not None),
        "prize_contribution": prize_contrib,
    }
    if mate is not None and mate_claim is not None:
        result["pair_mate_listing_id"] = mate.id
        result["pair_mate_claim_id"] = mate_claim.id
        result["message"] = (
            f"Casal comprado! Resgate ambos os dinos em até {CLAIM_RESERVATION_HOURS}h com /mercado."
        )
    return result


def get_pending_claims(db: Session, steam_id: str) -> list[dict[str, Any]]:
    from app import MarketClaim, MarketCryopodVault, MarketListing

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


def _paid_amount_for_listing(db: Session, listing_id: int, listing: Any | None = None) -> int:
    """Valor pago na compra (Y no casal primário; preço no solteiro). Mate do casal → 0."""
    from app import MarketTransaction

    if listing is not None and is_pair_listing(listing) and not is_pair_primary(listing):
        return 0

    tx = (
        db.query(MarketTransaction)
        .filter(MarketTransaction.listing_id == listing_id)
        .order_by(MarketTransaction.created_at.desc())
        .first()
    )
    if tx:
        return int(tx.price_paid or 0)
    if listing is not None and is_pair_listing(listing) and is_pair_primary(listing):
        mate = _load_pair_mate(db, listing)
        if mate:
            return pair_checkout_price(
                int(listing.effective_price or 0),
                int(mate.effective_price or 0),
            )
    if listing is not None:
        return int(getattr(listing, "effective_price", 0) or 0)
    return 0


def _refund_amount_for_listing(db: Session, listing_id: int, listing: Any | None = None) -> int:
    """Valor a reembolsar ao comprador.

    Solteiro: 100% de price_paid (fee_amount=0).
    Casal: só o anúncio primário; reembolso = round(0,60 × Y). Mate → 0 (evita double-refund).
    """
    if listing is None:
        from app import MarketListing

        listing = db.query(MarketListing).filter(MarketListing.id == listing_id).first()

    paid = _paid_amount_for_listing(db, listing_id, listing)
    if paid <= 0:
        return 0
    if listing is not None and is_pair_listing(listing) and is_pair_primary(listing):
        return pair_claim_refund(paid)
    return paid


def _expire_buyer_claim(
    db: Session,
    claim: Any,
    listing: Any,
    *,
    now: datetime,
) -> dict[str, Any] | None:
    """Claim comprador expirado: reembolso + dino de volta ao vendedor.

    Solteiro: reembolso integral; estorno ao vendedor = valor pago.
    Casal (primário): comprador recebe 60% de Y; vendedor devolve Y (dinos voltam);
    parcela retida (40% de Y) fica no sistema; pote do sorteio não é estornado.
    Mate do casal: sem movimento de Âmbar (só devolve o dino).
    """
    if claim.claim_status in (CLAIM_STATUS_EXPIRED, CLAIM_STATUS_REFUNDED):
        return None
    if claim.status not in ("PENDENTE", "CLAIMED"):
        return None
    if not _claim_is_expired(claim, now=now):
        return None

    paid = _paid_amount_for_listing(db, listing.id, listing)
    refund = _refund_amount_for_listing(db, listing.id, listing)
    buyer_id = listing.buyer_steam_id or claim.recipient_steam_id
    seller_id = listing.seller_steam_id
    is_pair_primary_row = is_pair_listing(listing) and is_pair_primary(listing)

    buyer_before = _player_points(db, buyer_id) if buyer_id else 0
    seller_before = _player_points(db, seller_id) if seller_id else 0

    buyer_after = buyer_before
    seller_after = seller_before
    seller_debited = 0

    # Mate do casal: sem movimento de Âmbar (Y já tratado no primário); só devolve o dino
    pair_mate_no_cash = (
        is_pair_listing(listing)
        and not is_pair_primary(listing)
        and refund <= 0
        and paid <= 0
    )

    if refund <= 0 and paid <= 0 and not pair_mate_no_cash:
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

    if refund > 0 and buyer_id:
        buyer_after = _credit_points(db, buyer_id, refund)

    # Estorno ao vendedor = valor que recebeu (Y / preço), não o reembolso parcial do casal
    seller_reversal = paid if (paid > 0 and not pair_mate_no_cash) else 0
    if seller_reversal > 0 and seller_id:
        seller_balance = _player_points(db, seller_id)
        seller_debited = min(seller_balance, seller_reversal)
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

    if pair_mate_no_cash:
        policy = "Casal mate: sem Âmbar (Y no primário). "
    elif is_pair_primary_row:
        policy = (
            "Casal: reembolso 60% do valor pago ao comprador; "
            "estorno integral de Y ao vendedor; pote sem estorno. "
        )
    else:
        policy = "Reembolso integral ao comprador (fee_amount=0). "
    policy += "Vendedor devolve até o saldo disponível."

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
            "price_paid": paid,
            "seller_reversal": seller_reversal,
            "seller_debited": seller_debited,
            "seller_points_before": seller_before,
            "seller_points_after": seller_after,
            "seller_claim_id": seller_claim.id,
            "pair_mate_no_cash": pair_mate_no_cash,
            "is_pair": is_pair_listing(listing),
            "retained_from_buyer": max(0, paid - refund) if is_pair_primary_row else 0,
            "policy": policy,
        },
        commit=False,
    )
    if refund > 0 or seller_debited > 0:
        try:
            from amber_ledger import record_market_claim_refund

            record_market_claim_refund(
                db,
                listing_id=listing.id,
                claim_id=claim.id,
                buyer_steam_id=buyer_id or "",
                seller_steam_id=seller_id or "",
                refund=refund,
                seller_debited=seller_debited,
            )
        except Exception as amber_exc:
            log.warning("Âmbarômetro market claim refund hook: %s", amber_exc)
    return {
        "claim_id": claim.id,
        "listing_id": listing.id,
        "refund_amount": refund,
        "price_paid": paid,
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
    Comprador solteiro: reembolso integral + devolução do dino ao vendedor.
    Comprador casal: reembolso 60% de Y + devolução dos dinos; pote sem estorno.
    Vendedor (retirada): listing volta a PAUSED.

    Commit por claim (sem FOR UPDATE no lote) — evita long_transaction sob carga.
    """
    from app import MarketClaim, MarketListing

    now = _now()
    # Só IDs — lock por linha abaixo.
    claim_ids = [
        int(r[0])
        for r in (
            db.query(MarketClaim.id)
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
            .all()
        )
    ]

    buyer_refunds: list[dict[str, Any]] = []
    seller_expired: list[dict[str, Any]] = []

    for claim_id in claim_ids:
        row = (
            db.query(MarketClaim, MarketListing)
            .join(MarketListing, MarketListing.id == MarketClaim.listing_id)
            .filter(MarketClaim.id == claim_id)
            .with_for_update()
            .first()
        )
        if not row:
            continue
        claim, listing = row
        try:
            result = None
            if claim.claim_type == "BUYER":
                result = _expire_buyer_claim(db, claim, listing, now=now)
                if result:
                    buyer_refunds.append(result)
            elif claim.claim_type == "SELLER":
                result = _expire_seller_claim(db, claim, listing, now=now)
                if result:
                    seller_expired.append(result)
            if result:
                db.commit()
            else:
                db.rollback()
        except Exception:
            db.rollback()
            raise

    return {
        "processed": len(buyer_refunds) + len(seller_expired),
        "buyer_refunds": buyer_refunds,
        "seller_expired": seller_expired,
    }


def list_seller_listings(
    db: Session,
    seller_steam_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    from app import MarketClaim, MarketListing

    limit = max(1, min(100, int(limit)))
    offset = max(0, int(offset))
    rows = (
        db.query(MarketListing)
        .filter(
            MarketListing.seller_steam_id == seller_steam_id,
            MarketListing.status.notin_(list(TERMINAL_LISTING)),
        )
        .order_by(MarketListing.updated_at.desc())
        .offset(offset)
        .limit(limit)
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
    seller_name = _profile_display_name(db, seller_steam_id)
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
        enrich_listing_pair_fields(db, item, row, species_by_key=species_by_key)
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
    item["seller_display_name"] = _profile_display_name(db, row.seller_steam_id)
    item["is_owner"] = bool(is_owner)
    enrich_listing_pair_fields(db, item, row)
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
    if is_pair_listing(row):
        mate = _load_pair_mate(db, row)
        if mate and mate.status == "ACTIVE":
            mate.status = "PAUSED"
            mate.updated_at = _now()
    db.commit()
    market_audit_event(
        db,
        "MARKET_LISTING_PAUSED",
        steam_id=seller_steam_id,
        listing_id=row.id,
        market_trace_id=row.market_trace_id,
        commit=True,
    )
    item = listing_to_public(row)
    enrich_listing_pair_fields(db, item, row)
    return item


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

    status_before = row.status
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
        counterparty_steam_id=row.seller_steam_id,
        listing_id=row.id,
        claim_id=claim.id,
        market_trace_id=row.market_trace_id,
        severity="WARN",
        source="admin",
        metadata={
            "seller_steam_id": row.seller_steam_id,
            "admin_steam_id": admin_steam_id,
            "reason": reason[:280] if reason else None,
            "listing_status_before": status_before,
            "listing_status_after": row.status,
            "summary_pt": (
                f"Admin removeu anúncio #{row.id} do vendedor {row.seller_steam_id}"
                + (f" — motivo: {reason[:80]}" if reason else "")
            ),
        },
        commit=True,
    )
    try:
        notify_staff_market_alert(
            db,
            title=f"Moderação: anúncio #{row.id} removido",
            body=(
                f"Admin {admin_steam_id[-8:]} removeu anúncio #{row.id} "
                f"do vendedor {row.seller_steam_id}."
                + (f" Motivo: {reason[:120]}" if reason else "")
            ),
            listing_id=row.id,
            severity="WARN",
        )
    except Exception as exc:
        log.warning("notify_staff_market_alert remove listing=%s: %s", row.id, exc)
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
    price_before = int(row.effective_price or 0)
    status_before = row.status
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
        counterparty_steam_id=row.seller_steam_id,
        listing_id=row.id,
        effective_price=price,
        market_trace_id=row.market_trace_id,
        source="admin",
        metadata={
            "seller_steam_id": row.seller_steam_id,
            "admin_steam_id": admin_steam_id,
            "price_before": price_before,
            "price_after": price,
            "paused": pause,
            "listing_status_before": status_before,
            "listing_status_after": row.status,
            "summary_pt": (
                f"Admin ajustou preço do anúncio #{row.id}: "
                f"{price_before:,} → {price:,} Âmbar"
            ).replace(",", "."),
        },
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

    status_before = row.status
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
        counterparty_steam_id=row.seller_steam_id,
        listing_id=row.id,
        market_trace_id=row.market_trace_id,
        severity="WARN",
        source="admin",
        metadata={
            "seller_steam_id": row.seller_steam_id,
            "admin_steam_id": admin_steam_id,
            "reason": reason[:280] if reason else None,
            "paused": pause,
            "listing_status_before": status_before,
            "listing_status_after": row.status,
            "summary_pt": (
                f"Admin sinalizou anúncio #{row.id}"
                + (f" — motivo: {reason[:80]}" if reason else "")
            ),
        },
        commit=True,
    )
    try:
        notify_staff_market_alert(
            db,
            title=f"Moderação: anúncio #{row.id} sinalizado",
            body=(
                f"Admin {admin_steam_id[-8:]} sinalizou anúncio #{row.id} "
                f"do vendedor {row.seller_steam_id}."
                + (f" Motivo: {reason[:120]}" if reason else "")
            ),
            listing_id=row.id,
            severity="WARN",
        )
    except Exception as exc:
        log.warning("notify_staff_market_alert flag listing=%s: %s", row.id, exc)
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
    names = _steam_personas_map(db, [r.seller_steam_id for r in rows])
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
        enrich_listing_pair_fields(db, item, row, species_by_key=species_by_key)
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
    profile_names = _steam_personas_map(db, list(counterparty_ids)) if counterparty_ids else {}

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
            "species_key": pub.get("species_key"),
            "display_title": pub.get("display_title"),
            "species_display_name": pub.get("species_display_name"),
            "species_image_url": pub.get("species_image_url"),
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


def _market_audit_row_to_dict(row: Any) -> dict[str, Any]:
    meta = _json_loads(row.metadata_json) if row.metadata_json else {}
    summary = meta.get("summary_pt") or ""
    return {
        "id": row.id,
        "event_type": row.event_type,
        "event_label": market_audit_label(row.event_type),
        "severity": row.severity,
        "steam_id": row.steam_id,
        "counterparty_steam_id": row.counterparty_steam_id,
        "listing_id": row.listing_id,
        "vault_id": row.vault_id,
        "claim_id": row.claim_id,
        "blob_hash": row.blob_hash,
        "computed_base_value": row.computed_base_value,
        "effective_price": row.effective_price,
        "points_delta": row.points_delta,
        "points_before": row.points_before,
        "points_after": row.points_after,
        "market_trace_id": row.market_trace_id,
        "source": row.source,
        "parser_version": row.parser_version,
        "plugin_version": row.plugin_version,
        "web_version": row.web_version,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "summary_pt": summary,
        "metadata": meta,
    }


def _parse_audit_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def query_market_audit_events(
    db: Session,
    *,
    event_type: str | None = None,
    steam_id: str | None = None,
    steam_id_mode: str = "actor",
    market_trace_id: str | None = None,
    listing_id: int | None = None,
    claim_id: int | None = None,
    severity: str | None = None,
    source: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    from app import MarketAuditEvent

    query = db.query(MarketAuditEvent)
    if event_type:
        et = event_type.strip()
        if et.endswith("%"):
            query = query.filter(MarketAuditEvent.event_type.like(et))
        else:
            query = query.filter(MarketAuditEvent.event_type == et)
    if steam_id:
        sid = steam_id.strip()
        if steam_id_mode == "any":
            like_sid = f"%{sid}%"
            query = query.filter(
                or_(
                    MarketAuditEvent.steam_id == sid,
                    MarketAuditEvent.counterparty_steam_id == sid,
                    MarketAuditEvent.metadata_json.like(like_sid),
                )
            )
        else:
            query = query.filter(MarketAuditEvent.steam_id == sid)
    if market_trace_id:
        query = query.filter(MarketAuditEvent.market_trace_id == market_trace_id.strip())
    if listing_id is not None:
        query = query.filter(MarketAuditEvent.listing_id == int(listing_id))
    if claim_id is not None:
        query = query.filter(MarketAuditEvent.claim_id == int(claim_id))
    if severity:
        query = query.filter(MarketAuditEvent.severity == severity.strip().upper())
    if source:
        query = query.filter(MarketAuditEvent.source == source.strip().lower())
    dt_from = _parse_audit_datetime(date_from)
    if dt_from:
        query = query.filter(MarketAuditEvent.created_at >= dt_from)
    dt_to = _parse_audit_datetime(date_to)
    if dt_to:
        query = query.filter(MarketAuditEvent.created_at <= dt_to)
    search = (q or "").strip()
    if search:
        like = f"%{search}%"
        filters = [
            MarketAuditEvent.event_type.ilike(like),
            MarketAuditEvent.metadata_json.ilike(like),
            MarketAuditEvent.market_trace_id.ilike(like),
        ]
        if search.isdigit():
            num = int(search)
            filters.append(MarketAuditEvent.listing_id == num)
            filters.append(MarketAuditEvent.claim_id == num)
        query = query.filter(or_(*filters))

    total = query.count()
    rows = (
        query.order_by(MarketAuditEvent.created_at.desc())
        .offset(max(0, offset))
        .limit(min(max(1, limit), 500))
        .all()
    )
    return [_market_audit_row_to_dict(r) for r in rows], total


def list_market_audit_events(
    db: Session,
    *,
    event_type: str | None = None,
    steam_id: str | None = None,
    market_trace_id: str | None = None,
    listing_id: int | None = None,
    claim_id: int | None = None,
    severity: str | None = None,
    source: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    q: str | None = None,
    steam_id_mode: str = "actor",
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    events, _ = query_market_audit_events(
        db,
        event_type=event_type,
        steam_id=steam_id,
        steam_id_mode=steam_id_mode,
        market_trace_id=market_trace_id,
        listing_id=listing_id,
        claim_id=claim_id,
        severity=severity,
        source=source,
        date_from=date_from,
        date_to=date_to,
        q=q,
        limit=limit,
        offset=offset,
    )
    return events


def get_market_audit_event(db: Session, event_id: int) -> dict[str, Any] | None:
    from app import MarketAuditEvent

    row = db.query(MarketAuditEvent).filter(MarketAuditEvent.id == event_id).first()
    if not row:
        return None
    return _market_audit_row_to_dict(row)


def _claim_row_public(claim: Any) -> dict[str, Any]:
    return {
        "claim_id": claim.id,
        "listing_id": claim.listing_id,
        "recipient_steam_id": claim.recipient_steam_id,
        "claim_type": claim.claim_type,
        "status": claim.status,
        "market_trace_id": claim.market_trace_id,
        "claim_expires_at": claim.claim_expires_at.isoformat() if claim.claim_expires_at else None,
        "created_at": claim.created_at.isoformat() if claim.created_at else None,
        "updated_at": claim.updated_at.isoformat() if claim.updated_at else None,
    }


def _transaction_row_public(tx: Any) -> dict[str, Any]:
    return {
        "transaction_id": tx.id,
        "listing_id": tx.listing_id,
        "buyer_steam_id": tx.buyer_steam_id,
        "seller_steam_id": tx.seller_steam_id,
        "price_paid": tx.price_paid,
        "created_at": tx.created_at.isoformat() if tx.created_at else None,
    }


def get_listing_timeline(db: Session, listing_id: int) -> dict[str, Any]:
    """Timeline completa de um anúncio para admin/suporte."""
    from app import MarketAuditEvent, MarketClaim, MarketListing, MarketTransaction, SupportTicket

    row = db.query(MarketListing).filter(MarketListing.id == listing_id).first()
    if not row:
        raise ValueError("Anúncio não encontrado")

    species_row = resolve_species(db, species_key=row.species_key)
    listing = get_admin_listing_detail(db, listing_id)

    claims = (
        db.query(MarketClaim)
        .filter(MarketClaim.listing_id == listing_id)
        .order_by(MarketClaim.created_at.asc())
        .all()
    )
    transactions = (
        db.query(MarketTransaction)
        .filter(MarketTransaction.listing_id == listing_id)
        .order_by(MarketTransaction.created_at.asc())
        .all()
    )
    audit_events, _ = query_market_audit_events(
        db, listing_id=listing_id, limit=200, offset=0
    )
    tickets = (
        db.query(SupportTicket)
        .filter(SupportTicket.listing_id == listing_id)
        .order_by(SupportTicket.created_at.desc())
        .limit(20)
        .all()
    )

    seller_points = _player_points(db, row.seller_steam_id)
    buyer_points = None
    if row.buyer_steam_id:
        buyer_points = _player_points(db, row.buyer_steam_id)

    return {
        "listing": listing,
        "claims": [_claim_row_public(c) for c in claims],
        "transactions": [_transaction_row_public(t) for t in transactions],
        "audit_events": audit_events,
        "tickets": [
            {
                "id": t.id,
                "subject": t.subject,
                "status": t.status,
                "category": t.category,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tickets
        ],
        "amber_snapshot": {
            "seller_steam_id": row.seller_steam_id,
            "seller_points": seller_points,
            "buyer_steam_id": row.buyer_steam_id,
            "buyer_points": buyer_points,
        },
    }


def get_listing_timeline_summary(db: Session, listing_id: int) -> dict[str, Any]:
    """Resumo compacto para widget de ticket admin."""
    from app import MarketAuditEvent, MarketClaim, MarketListing

    row = db.query(MarketListing).filter(MarketListing.id == listing_id).first()
    if not row:
        return {"listing_id": listing_id, "found": False}
    species_row = resolve_species(db, species_key=row.species_key)
    item = listing_to_public(row, species_row=species_row)
    pending_claim = (
        db.query(MarketClaim)
        .filter(
            MarketClaim.listing_id == listing_id,
            MarketClaim.status.in_(("PENDENTE", "RESERVED")),
        )
        .order_by(MarketClaim.created_at.desc())
        .first()
    )
    recent_audit, _ = query_market_audit_events(
        db, listing_id=listing_id, limit=10, offset=0
    )
    meta = _json_loads(row.metadata_json)
    return {
        "found": True,
        "listing_id": listing_id,
        "display_title": item.get("display_title"),
        "status": row.status,
        "seller_steam_id": row.seller_steam_id,
        "buyer_steam_id": row.buyer_steam_id,
        "effective_price": row.effective_price,
        "dino_level": row.dino_level,
        "species_display_name": item.get("species_display_name"),
        "admin_flagged": bool(meta.get("admin_flagged")),
        "pending_claim": _claim_row_public(pending_claim) if pending_claim else None,
        "recent_audit": recent_audit,
        "market_trace_id": row.market_trace_id,
    }


def list_admin_listings(
    db: Session,
    *,
    q: str | None = None,
    status: str | None = None,
    seller_steam_id: str | None = None,
    flagged_only: bool = False,
    sort: str = "recent",
    limit: int = 50,
    offset: int = 0,
    include_total: bool = True,
) -> tuple[list[dict[str, Any]], int | None]:
    from app import MarketListing, MarketPlayerProfile

    limit = max(1, min(100, int(limit)))
    offset = max(0, int(offset))
    query = db.query(MarketListing)
    if status:
        st = status.strip().upper()
        if st == "FLAGGED":
            flagged_only = True
        else:
            query = query.filter(MarketListing.status == st)
    if seller_steam_id:
        query = query.filter(MarketListing.seller_steam_id == seller_steam_id.strip())
    if flagged_only:
        query = query.filter(
            or_(
                MarketListing.metadata_json.like('%"admin_flagged": true%'),
                MarketListing.metadata_json.like('%"admin_flagged":true%'),
            )
        )
    search = (q or "").strip()
    if search:
        if search.isdigit():
            query = query.filter(MarketListing.id == int(search))
        else:
            like = f"%{search}%"
            query = query.filter(
                or_(
                    MarketListing.seller_steam_id.like(like),
                    MarketListing.custom_name.like(like),
                    MarketListing.dino_display_name.like(like),
                    MarketListing.species_key.like(like),
                )
            )
    total: int | None = int(query.count()) if include_total else None
    if sort == "price_asc":
        query = query.order_by(MarketListing.effective_price.asc())
    elif sort == "price_desc":
        query = query.order_by(MarketListing.effective_price.desc())
    else:
        query = query.order_by(MarketListing.updated_at.desc())
    rows = query.offset(offset).limit(limit).all()
    seller_ids = {r.seller_steam_id for r in rows}
    names = _steam_personas_map(db, list(seller_ids)) if seller_ids else {}
    species_by_key = _species_map(db, {r.species_key for r in rows})
    out = []
    for row in rows:
        meta = _json_loads(row.metadata_json)
        item = listing_to_public(row, species_row=species_by_key.get(row.species_key or ""))
        item["seller_display_name"] = names.get(row.seller_steam_id)
        item["admin_flagged"] = bool(meta.get("admin_flagged"))
        item["admin_flag_reason"] = meta.get("admin_flag_reason")
        out.append(item)
    return out, total


def get_admin_listing_detail(db: Session, listing_id: int) -> dict[str, Any]:
    """Detalhe completo do anúncio para admin (inclui preview cryo)."""
    from app import MarketCryopodVault, MarketListing, MarketPlayerProfile

    row = db.query(MarketListing).filter(MarketListing.id == listing_id).first()
    if not row:
        raise ValueError("Anúncio não encontrado")
    species_row = resolve_species(db, species_key=row.species_key)
    item = listing_to_public(row, include_breakdown=True, species_row=species_row)
    prof = (
        db.query(MarketPlayerProfile)
        .filter(MarketPlayerProfile.steam_id == row.seller_steam_id)
        .first()
    )
    item["seller_display_name"] = _profile_display_name(db, row.seller_steam_id)
    meta = _json_loads(row.metadata_json)
    item["admin_flagged"] = bool(meta.get("admin_flagged"))
    item["admin_flag_reason"] = meta.get("admin_flag_reason")
    item["admin_removed"] = bool(meta.get("admin_removed"))
    item["buyer_steam_id"] = row.buyer_steam_id
    item["market_trace_id"] = row.market_trace_id
    vault = db.query(MarketCryopodVault).filter(MarketCryopodVault.id == row.vault_id).first()
    if vault:
        vault_meta = _json_loads(vault.metadata_json)
        item["cryo_preview"] = {
            "vault_id": vault.id,
            "blob_hash": vault.blob_hash,
            "parser_version": vault.parser_version,
            "uploaded_at": vault.uploaded_at.isoformat() if vault.uploaded_at else None,
            "metadata": vault_meta,
        }
    else:
        item["cryo_preview"] = None
    enrich_listing_pair_fields(db, item, row)
    return item


def admin_bulk_listing_action(
    db: Session,
    action: str,
    listing_ids: list[int],
    admin_steam_id: str,
    *,
    reason: str = "",
    pause: bool = True,
) -> dict[str, Any]:
    """Ações em lote: flag, remove, pause."""
    act = (action or "").strip().lower()
    ids = [int(i) for i in listing_ids if int(i) > 0]
    if not ids:
        raise ValueError("listing_ids obrigatório")
    if len(ids) > 50:
        raise ValueError("Máximo 50 anúncios por lote")

    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for lid in ids:
        try:
            if act in ("flag", "sinalizar"):
                results.append(
                    admin_flag_listing(
                        db, lid, admin_steam_id, reason=reason, pause=pause
                    )
                )
            elif act in ("remove", "remover"):
                results.append(
                    admin_remove_listing(db, lid, admin_steam_id, reason=reason)
                )
            elif act in ("pause", "pausar"):
                from app import MarketListing

                row = db.query(MarketListing).filter(MarketListing.id == lid).first()
                if not row:
                    raise ValueError("Anúncio não encontrado")
                if row.status == "ACTIVE":
                    status_before = row.status
                    row.status = "PAUSED"
                    row.updated_at = _now()
                    db.commit()
                    market_audit_event(
                        db,
                        "MARKET_LISTING_PAUSED",
                        steam_id=admin_steam_id,
                        counterparty_steam_id=row.seller_steam_id,
                        listing_id=row.id,
                        source="admin",
                        metadata={
                            "seller_steam_id": row.seller_steam_id,
                            "admin_steam_id": admin_steam_id,
                            "listing_status_before": status_before,
                            "listing_status_after": row.status,
                            "summary_pt": f"Admin pausou anúncio #{row.id} em lote",
                            "bulk": True,
                        },
                        commit=True,
                    )
                species_row = resolve_species(db, species_key=row.species_key)
                results.append(listing_to_public(row, species_row=species_row))
            else:
                raise ValueError(f"Ação desconhecida: {action}")
        except ValueError as exc:
            errors.append({"listing_id": lid, "error": str(exc)})

    market_audit_event(
        db,
        "MARKET_LISTING_BULK_ADMIN_ACTION",
        steam_id=admin_steam_id,
        severity="INFO",
        source="admin",
        metadata={
            "action": act,
            "listing_ids": ids,
            "success_count": len(results),
            "error_count": len(errors),
            "reason": reason[:280] if reason else None,
            "summary_pt": (
                f"Ação em lote '{act}': {len(results)} ok, {len(errors)} erro(s)"
            ),
        },
        commit=True,
    )
    return {
        "action": act,
        "processed": len(results),
        "errors": errors,
        "listings": results,
    }
