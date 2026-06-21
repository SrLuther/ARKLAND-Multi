"""Vault, listings, compra e claims do Mercado de Dinos."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from market_audit import market_audit_event
from market_economy import STAT_KEYS, calculate_suggested_value, normalize_blueprint, normalize_stat_points
from market_service import species_row_to_economy
from stat_points_asb import enrich_stats_with_points

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
DISPLAY_NAME_RE = re.compile(r"^[A-Za-z0-9_\-\.]{3,32}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
        raise ValueError("Nome deve ter 3–32 caracteres (letras, números, _ - .)")
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
    market_audit_event(
        db,
        "MARKET_DISPLAY_NAME_CHANGED",
        steam_id=steam_id,
        metadata={"market_display_name": name},
        commit=True,
    )
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
    computed, breakdown, _economy = _compute_economy(db, species_row, meta)
    return {
        "ok": True,
        "species_key": species_row.species_key,
        "species_status": status,
        "computed_base_value": computed,
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
    elif species_row and species_row.status != "ACTIVE":
        listing_status = "PENDING_CLASSIFICATION"

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
        "calculation_breakdown": breakdown,
    }


def listing_to_public(row: Any, *, include_breakdown: bool = False) -> dict[str, Any]:
    meta = _json_loads(row.metadata_json)
    out: dict[str, Any] = {
        "listing_id": row.id,
        "seller_steam_id": row.seller_steam_id,
        "seller_display_name": None,
        "species_key": row.species_key,
        "status": row.status,
        "computed_base_value": row.computed_base_value,
        "effective_price": row.effective_price,
        "price_mode": row.price_mode,
        "dino_display_name": row.dino_display_name,
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
    out = []
    for row in rows:
        item = listing_to_public(row)
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
) -> dict[str, Any]:
    from app import MarketListing

    row = db.query(MarketListing).filter(MarketListing.id == listing_id).first()
    if not row:
        raise ValueError("Anúncio não encontrado")
    if row.seller_steam_id != seller_steam_id:
        raise ValueError("Sem permissão")
    if row.status not in ("DRAFT", "PAUSED", "PENDING_CLASSIFICATION"):
        raise ValueError(f"Status não permite edição: {row.status}")

    if price_absolute is not None:
        price = int(price_absolute)
        if price < row.computed_base_value:
            raise ValueError(
                f"Preço mínimo: {row.computed_base_value} Âmbar (valor sugerido)"
            )
        row.price_absolute = price
        row.effective_price = price
        row.price_mode = "ABSOLUTE"

    if activate:
        if row.status == "PENDING_CLASSIFICATION":
            raise ValueError("Espécie aguardando classificação admin")
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
        commit=True,
    )
    return listing_to_public(row, include_breakdown=True)


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
        commit=True,
    )

    return {
        "listing_id": row.id,
        "claim_id": claim.id,
        "price_paid": price,
        "buyer_balance": buyer_after,
    }


def get_pending_claims(db: Session, steam_id: str) -> list[dict[str, Any]]:
    from app import MarketClaim, MarketCryopodVault, MarketListing

    rows = (
        db.query(MarketClaim, MarketListing, MarketCryopodVault)
        .join(MarketListing, MarketListing.id == MarketClaim.listing_id)
        .join(MarketCryopodVault, MarketCryopodVault.id == MarketListing.vault_id)
        .filter(
            MarketClaim.recipient_steam_id == steam_id,
            MarketClaim.status == "PENDENTE",
        )
        .all()
    )
    out = []
    for claim, listing, vault in rows:
        out.append(
            {
                "claim_id": claim.id,
                "listing_id": listing.id,
                "claim_type": claim.claim_type,
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

    q = db.query(MarketClaim).filter(
        MarketClaim.recipient_steam_id == steam_id,
        MarketClaim.status == "PENDENTE",
    )
    if claim_ids:
        q = q.filter(MarketClaim.id.in_(claim_ids))
    rows = q.all()
    now = _now()
    claimed = []
    for row in rows:
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

    claim = db.query(MarketClaim).filter(MarketClaim.id == claim_id).first()
    if not claim:
        raise ValueError("Claim não encontrado")
    if claim.recipient_steam_id != steam_id:
        raise ValueError("SteamID não corresponde")
    listing = db.query(MarketListing).filter(MarketListing.id == claim.listing_id).first()
    if not listing:
        raise ValueError("Listing não encontrado")

    now = _now()
    claim.status = "DELIVERED"
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
    return {"claim_id": claim.id, "listing_id": listing.id, "status": "DELIVERED"}


def list_seller_listings(db: Session, seller_steam_id: str) -> list[dict[str, Any]]:
    from app import MarketListing

    rows = (
        db.query(MarketListing)
        .filter(
            MarketListing.seller_steam_id == seller_steam_id,
            MarketListing.status.notin_(list(TERMINAL_LISTING)),
        )
        .order_by(MarketListing.updated_at.desc())
        .all()
    )
    return [listing_to_public(r, include_breakdown=True) for r in rows]


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
    item = listing_to_public(row, include_breakdown=True)
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
    db.add(claim)
    db.commit()
    market_audit_event(
        db,
        "MARKET_LISTING_WITHDRAW_REQUESTED",
        steam_id=seller_steam_id,
        listing_id=row.id,
        claim_id=claim.id,
        market_trace_id=row.market_trace_id,
        commit=True,
    )
    return {
        "listing_id": row.id,
        "claim_id": claim.id,
        "message": "Use /resgatarmercado in-game para recuperar a cryopod.",
    }


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
    """Promove listings PENDING_CLASSIFICATION → DRAFT quando espécie vira ACTIVE."""
    from app import MarketListing

    rows = (
        db.query(MarketListing)
        .filter(
            MarketListing.species_key == species_key,
            MarketListing.status == "PENDING_CLASSIFICATION",
        )
        .all()
    )
    count = 0
    for row in rows:
        if _promote_pending_listing_row(db, row, species_key=species_key):
            count += 1
    if count:
        db.commit()
    return count


def _promote_pending_listing_row(
    db: Session, row: Any, *, species_key: str | None = None, species_row: Any | None = None
) -> bool:
    """DRAFT + computed_base_value se espécie ACTIVE. Retorna True se promoveu."""
    sk = species_key or row.species_key
    resolved = species_row or (resolve_species(db, species_key=sk) if sk else None)
    if not resolved or resolved.status != "ACTIVE":
        return False
    if resolved.species_key and row.species_key != resolved.species_key:
        row.species_key = resolved.species_key
    computed = _apply_economy_to_listing_row(db, row, resolved)
    row.status = "DRAFT"
    market_audit_event(
        db,
        "MARKET_LISTING_PROMOTED",
        steam_id=row.seller_steam_id,
        listing_id=row.id,
        computed_base_value=computed,
        market_trace_id=row.market_trace_id,
        metadata={"promoted_to": "DRAFT", "species_key": resolved.species_key},
        commit=False,
    )
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
    """Promove PENDING_CLASSIFICATION cujo espécie já está ACTIVE (ex.: sync sem /activate)."""
    from app import MarketListing

    rows = (
        db.query(MarketListing)
        .filter(MarketListing.status == "PENDING_CLASSIFICATION")
        .all()
    )
    promoted = 0
    for row in rows:
        species_row = None
        if row.species_key:
            species_row = resolve_species(db, species_key=row.species_key)
        if not species_row:
            meta = _json_loads(row.metadata_json or "{}")
            bp = meta.get("species_blueprint") or meta.get("blueprint")
            if bp:
                species_row = resolve_species(db, blueprint=str(bp))
        if _promote_pending_listing_row(db, row, species_row=species_row):
            promoted += 1
    if promoted:
        db.commit()
    recompute_draft_listings(db)
    return promoted


def list_pending_classification(db: Session, *, limit: int = 100) -> list[dict[str, Any]]:
    from app import MarketListing, MarketPlayerProfile

    rows = (
        db.query(MarketListing)
        .filter(MarketListing.status == "PENDING_CLASSIFICATION")
        .order_by(MarketListing.created_at.desc())
        .limit(min(limit, 200))
        .all()
    )
    names = {
        p.steam_id: p.market_display_name
        for p in db.query(MarketPlayerProfile)
        .filter(MarketPlayerProfile.steam_id.in_([r.seller_steam_id for r in rows]))
        .all()
    }
    out = []
    for row in rows:
        item = listing_to_public(row, include_breakdown=True)
        item["seller_display_name"] = names.get(row.seller_steam_id)
        out.append(item)
    return out


def player_market_history(db: Session, steam_id: str, *, limit: int = 50) -> dict[str, Any]:
    from app import MarketListing, MarketTransaction

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

    def tx_row(t: Any) -> dict[str, Any]:
        return {
            "listing_id": t.listing_id,
            "price_paid": t.price_paid,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }

    return {
        "sales": [tx_row(t) for t in sales],
        "purchases": [tx_row(t) for t in purchases],
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
    }


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
