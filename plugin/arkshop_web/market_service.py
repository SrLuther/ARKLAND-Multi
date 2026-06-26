"""Persistência e sync do catálogo econômico do Mercado de Dinos."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from market_economy import (
    STAT_KEYS,
    SpeciesEconomy,
    StatMultiplier,
    apply_economy_meta,
    build_multipliers_from_defaults,
    build_catalog_economy_map,
    iter_catalog_dinos,
    iter_economy_groups,
    load_default_species_map,
    load_defaults_file,
    load_pts_reference,
    load_size_caps,
    load_tier_legend,
    merge_economy_group,
    merge_species_from_catalog_item,
    merge_species_from_defaults,
    merge_species_from_registry_entry,
    shop_catalog_display_name,
    stat_labels,
)


def _apply_multipliers_row(db: Session, row: Any, species: SpeciesEconomy) -> None:
    from app import MarketSpeciesStatMultiplier

    db.query(MarketSpeciesStatMultiplier).filter(
        MarketSpeciesStatMultiplier.species_id == row.id
    ).delete()
    for sk in STAT_KEYS:
        sm = species.multipliers.get(sk)
        if not sm:
            continue
        db.add(
            MarketSpeciesStatMultiplier(
                species_id=row.id,
                stat_key=sk,
                multiplier=sm.multiplier,
                enabled=sm.enabled,
            )
        )


def _sync_species_aliases(db: Session, species_row: Any, aliases: list[dict[str, Any]]) -> None:
    from app import MarketSpeciesAlias

    seen_catalog: set[str] = set()
    seen_bp: set[str] = set()
    for alias in aliases:
        cid = str(alias.get("catalog_item_id") or "").strip() or None
        bp_norm = str(alias.get("blueprint_norm") or "").strip()
        if not bp_norm and not cid:
            continue
        if cid:
            seen_catalog.add(cid)
        if bp_norm:
            seen_bp.add(bp_norm)
        row = None
        if cid:
            row = (
                db.query(MarketSpeciesAlias)
                .filter(MarketSpeciesAlias.catalog_item_id == cid)
                .first()
            )
        if row is None and bp_norm:
            row = (
                db.query(MarketSpeciesAlias)
                .filter(MarketSpeciesAlias.blueprint_norm == bp_norm)
                .first()
            )
        if row is None:
            row = MarketSpeciesAlias(species_id=species_row.id)
            db.add(row)
        row.species_id = species_row.id
        row.catalog_item_id = cid
        row.blueprint_path = str(alias.get("blueprint_path") or "")
        row.blueprint_norm = bp_norm
        row.variant_label = str(alias.get("variant_label") or "") or None

    existing = (
        db.query(MarketSpeciesAlias)
        .filter(MarketSpeciesAlias.species_id == species_row.id)
        .all()
    )
    for row in existing:
        cid = row.catalog_item_id or ""
        bp = row.blueprint_norm or ""
        if (cid and cid not in seen_catalog) or (bp and bp not in seen_bp):
            db.delete(row)


def _list_species_aliases(db: Session, species_id: int) -> list[dict[str, Any]]:
    from app import MarketSpeciesAlias

    rows = (
        db.query(MarketSpeciesAlias)
        .filter(MarketSpeciesAlias.species_id == species_id)
        .order_by(MarketSpeciesAlias.variant_label)
        .all()
    )
    return [
        {
            "catalog_item_id": r.catalog_item_id,
            "blueprint_path": r.blueprint_path,
            "variant_label": r.variant_label,
        }
        for r in rows
    ]


def species_row_to_economy(row: Any, mult_rows: list[Any]) -> SpeciesEconomy:
    labels = stat_labels()
    mults: dict[str, StatMultiplier] = {}
    for m in mult_rows:
        mults[m.stat_key] = StatMultiplier(
            stat_key=m.stat_key,
            multiplier=m.multiplier,
            enabled=m.enabled,
            label=labels.get(m.stat_key, m.stat_key),
        )
    for sk in STAT_KEYS:
        if sk not in mults:
            default = build_multipliers_from_defaults(row.species_key).get(sk)
            if default:
                mults[sk] = default
    species = SpeciesEconomy(
        species_key=row.species_key,
        catalog_item_id=row.catalog_item_id or "",
        display_name=row.display_name,
        blueprint_path=row.blueprint_path or "",
        reference_level=row.reference_level,
        root_value=row.root_value,
        tier=row.tier or "B",
        breeding_difficulty=row.breeding_difficulty or "",
        breeding_notes=row.breeding_notes or "",
        status=row.status,
        multipliers=mults,
    )
    apply_economy_meta(species)
    return species


def _resolve_display_name_override(
    species: SpeciesEconomy,
    overrides: dict[str, str] | None,
) -> str | None:
    if not overrides:
        return None
    for key in (species.species_key, species.catalog_item_id):
        if not key:
            continue
        val = overrides.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return None


def _upsert_species_row(
    db: Session,
    species: SpeciesEconomy,
    aliases: list[dict[str, Any]],
    *,
    activate: bool,
    display_name_overrides: dict[str, str] | None,
    reset_display_names: bool,
    now: datetime,
) -> tuple[Any, bool]:
    """Insere ou atualiza espécie + aliases. Retorna (row, created)."""
    from app import MarketSpecies

    row = db.query(MarketSpecies).filter(MarketSpecies.species_key == species.species_key).first()
    override_name = _resolve_display_name_override(species, display_name_overrides)
    created = False
    if row is None:
        row = MarketSpecies(
            species_key=species.species_key,
            catalog_item_id=species.catalog_item_id,
            display_name=override_name or species.display_name,
            blueprint_path=species.blueprint_path,
            reference_level=species.reference_level,
            root_value=species.root_value,
            tier=species.tier,
            breeding_difficulty=species.breeding_difficulty,
            breeding_notes=species.breeding_notes,
            status=species.status,
            shop_price_synced_at=now if species.catalog_item_id else None,
        )
        db.add(row)
        db.flush()
        created = True
    else:
        if species.catalog_item_id:
            row.catalog_item_id = species.catalog_item_id
        if override_name is not None:
            row.display_name = override_name
        elif reset_display_names:
            row.display_name = species.display_name
        if species.blueprint_path:
            row.blueprint_path = species.blueprint_path
        if species.reference_level:
            row.reference_level = species.reference_level
        if species.root_value:
            row.root_value = species.root_value
        row.tier = species.tier
        row.breeding_difficulty = species.breeding_difficulty
        row.breeding_notes = species.breeding_notes
        if species.catalog_item_id:
            row.shop_price_synced_at = now
        row.updated_at = now
        if activate:
            row.status = "ACTIVE"
        elif row.status != "ACTIVE":
            row.status = species.status
    _apply_multipliers_row(db, row, species)
    _sync_species_aliases(db, row, aliases)
    return row, created


def sync_reference_species_to_db(
    db: Session,
    *,
    activate: bool = False,
    skip_keys: set[str] | None = None,
    display_name_overrides: dict[str, str] | None = None,
    reset_display_names: bool = False,
) -> dict[str, Any]:
    """Pré-cadastra espécies do JSON sem item Type:dino na loja (mods, referência P2P)."""
    skip = skip_keys or set()
    created = updated = 0
    items: list[str] = []
    now = datetime.now(timezone.utc)
    status = "ACTIVE" if activate else "PRE_REGISTERED"

    for defn in load_defaults_file().get("species", []):
        sk = str(defn.get("species_key") or "")
        if not sk or sk in skip:
            continue
        has_catalog = bool(defn.get("catalog_item_id") or defn.get("catalog_item_ids"))
        has_blueprint = bool(defn.get("blueprint_path") or defn.get("blueprint_aliases"))
        if has_catalog or not has_blueprint:
            continue
        species, aliases = merge_species_from_defaults(defn, status=status)
        _, was_created = _upsert_species_row(
            db,
            species,
            aliases,
            activate=activate,
            display_name_overrides=display_name_overrides,
            reset_display_names=reset_display_names,
            now=now,
        )
        if was_created:
            created += 1
        else:
            updated += 1
        items.append(sk)

    db.commit()
    return {"reference_created": created, "reference_updated": updated, "reference_keys": items}


def sync_registry_overlay_to_db(
    db: Session,
    *,
    activate: bool = False,
    only_missing: bool = False,
    skip_keys: set[str] | None = None,
    display_name_overrides: dict[str, str] | None = None,
    reset_display_names: bool = False,
) -> dict[str, Any]:
    """Importa espécies do overlay ark_species_registry.json (mods — ex.: Abyss 40 entradas)."""
    from ark_species_registry import load_registry_overlay_raw

    from app import MarketSpecies

    skip = skip_keys or set()
    created = updated = skipped = 0
    items: list[str] = []
    now = datetime.now(timezone.utc)
    status = "ACTIVE" if activate else "PRE_REGISTERED"
    existing_keys: set[str] = set()
    if only_missing:
        existing_keys = {str(r.species_key) for r in db.query(MarketSpecies.species_key).all()}

    for entry in load_registry_overlay_raw():
        sk = str(entry.get("species_key") or "").strip()
        if not sk or sk in skip:
            continue
        if only_missing and sk in existing_keys:
            skipped += 1
            continue
        species, aliases = merge_species_from_registry_entry(entry, status=status)
        _, was_created = _upsert_species_row(
            db,
            species,
            aliases,
            activate=activate,
            display_name_overrides=display_name_overrides,
            reset_display_names=reset_display_names,
            now=now,
        )
        if was_created:
            created += 1
        else:
            updated += 1
        items.append(sk)

    db.commit()
    return {
        "registry_created": created,
        "registry_updated": updated,
        "registry_skipped": skipped,
        "registry_keys": items,
    }


def sync_catalog_to_db(
    db: Session,
    catalog: dict[str, Any],
    *,
    activate: bool = False,
    display_name_overrides: dict[str, str] | None = None,
    reset_display_names: bool = False,
) -> dict[str, Any]:
    """Importa dinos Type:dino do config.json para market_species (grupos econômicos).

    Variantes de loja (Rex Tek, Volcano Rex, …) viram aliases do mesmo grupo (rex).
    display_name na loja (config.json) não é alterado.
    """
    created = updated = 0
    items: list[str] = []
    now = datetime.now(timezone.utc)

    for group_key, defn, catalog_items in iter_economy_groups(catalog):
        species, aliases = merge_economy_group(
            group_key,
            catalog_items,
            defaults=defn,
            catalog=catalog,
            status="ACTIVE" if activate else "PRE_REGISTERED",
        )
        _, was_created = _upsert_species_row(
            db,
            species,
            aliases,
            activate=activate,
            display_name_overrides=display_name_overrides,
            reset_display_names=reset_display_names,
            now=now,
        )
        if was_created:
            created += 1
        else:
            updated += 1
        items.append(species.species_key)

    db.commit()
    ref = sync_reference_species_to_db(
        db,
        activate=activate,
        skip_keys=set(items),
        display_name_overrides=display_name_overrides,
        reset_display_names=reset_display_names,
    )
    reg = sync_registry_overlay_to_db(
        db,
        activate=activate,
        skip_keys=set(items) | set(ref.get("reference_keys") or []),
        display_name_overrides=display_name_overrides,
        reset_display_names=reset_display_names,
    )
    promoted = 0
    from market_listings import reconcile_pending_listings

    promoted = reconcile_pending_listings(db)
    return {
        "created": created,
        "updated": updated,
        "species_keys": items,
        "promoted_listings": promoted,
        **ref,
        **reg,
    }


def list_species_public(db: Session, *, active_only: bool = True) -> list[dict[str, Any]]:
    from app import MarketSpecies, MarketSpeciesStatMultiplier

    q = db.query(MarketSpecies).order_by(MarketSpecies.display_name)
    if active_only:
        q = q.filter(MarketSpecies.status == "ACTIVE")
    rows = q.all()
    labels = stat_labels()
    global_mults = []
    if rows:
        first_id = rows[0].id
        for m in db.query(MarketSpeciesStatMultiplier).filter(
            MarketSpeciesStatMultiplier.species_id == first_id,
            MarketSpeciesStatMultiplier.enabled.is_(True),
            MarketSpeciesStatMultiplier.multiplier > 0,
        ):
            global_mults.append(
                {"stat_key": m.stat_key, "label": labels.get(m.stat_key, m.stat_key), "multiplier": m.multiplier}
            )
    out = []
    for row in rows:
        mult_rows = (
            db.query(MarketSpeciesStatMultiplier)
            .filter(MarketSpeciesStatMultiplier.species_id == row.id)
            .all()
        )
        economy = species_row_to_economy(row, mult_rows)
        item = economy.to_dict()
        item["reference_level"] = row.reference_level
        item["level1_base_value"] = row.root_value
        item["linked_variants"] = _list_species_aliases(db, row.id)
        from ark_species_registry import get_registry_entry, resolve_species_image

        item["image_url"] = resolve_species_image(
            get_registry_entry(row.species_key),
            tier=row.tier,
        )
        out.append(item)
    return out


def get_species_table_payload(db: Session) -> dict[str, Any]:
    from ark_species_registry import get_registry_entry, resolve_species_image

    species = list_species_public(db, active_only=True)
    stat_labels_map = stat_labels()
    size_caps = load_size_caps()
    return {
        "title": "Tabela Oficial — Valores Base (Nível 1)",
        "description": (
            "Valor raiz (piso) por espécie homologada — preço nível 1 na loja, sem pontos de breeding. "
            "O valor sugerido de um dino preenche o espaço bônus até o teto do porte conforme stats base (Spyglass)."
        ),
        "currency": "Âmbar",
        "size_caps": size_caps,
        "pts_reference": load_pts_reference(),
        "species": [
            {
                "species_key": s["species_key"],
                "display_name": s["display_name"],
                "reference_level": s.get("reference_level", 1),
                "root_value": s["root_value"],
                "tier": s.get("tier"),
                "image_url": resolve_species_image(
                    get_registry_entry(s["species_key"]),
                    tier=s.get("tier"),
                ),
                "catalog_item_id": s.get("catalog_item_id"),
                "diet_class": s.get("diet_class"),
                "size_class": s.get("size_class"),
                "size_cap": s.get("size_cap"),
                "bonus_space": s.get("bonus_space"),
                "economy_stats": s.get("economy_stats"),
                "economy_stat_labels": {
                    sk: stat_labels_map.get(sk, sk)
                    for sk in ("health", "melee", "weight", "stamina", "speed")
                },
            }
            for s in species
        ],
        "tier_legend": load_tier_legend(),
        "tier_icon_urls": {
            "S+": "/species/tier-s-plus.svg",
            "S": "/species/tier-s.svg",
            "A": "/species/tier-a.svg",
            "B": "/species/tier-b.svg",
            "C": "/species/tier-c.svg",
        },
    }


def pre_register_catalog_item(
    db: Session,
    catalog: dict[str, Any],
    catalog_item_id: str,
) -> dict[str, Any]:
    """Pré-cadastra uma espécie a partir de item Type:dino do catálogo (checkbox TEK)."""
    from app import MarketSpecies

    item_id = (catalog_item_id or "").strip()
    if not item_id:
        raise ValueError("catalog_item_id obrigatório")

    items = catalog.get("Items") or catalog.get("ShopItems") or {}
    entry = items.get(item_id)
    if not entry:
        raise ValueError(f"Item '{item_id}' não encontrado no catálogo")
    if str(entry.get("Type") or "").lower() != "dino":
        raise ValueError("Somente itens Type:dino podem ser pré-cadastrados no Comércio")

    defaults_map = load_default_species_map()
    defn = build_catalog_economy_map().get(item_id) or defaults_map.get(item_id, {})
    group_key = str(defn.get("species_key") or item_id)
    species, aliases = merge_economy_group(
        group_key,
        [(item_id, entry)],
        defaults=defaults_map.get(group_key, defn),
        catalog=catalog,
        status="PRE_REGISTERED",
    )
    now = datetime.now(timezone.utc)
    row = db.query(MarketSpecies).filter(MarketSpecies.species_key == species.species_key).first()
    created = False
    if row is None:
        row = MarketSpecies(
            species_key=species.species_key,
            catalog_item_id=species.catalog_item_id,
            display_name=species.display_name,
            blueprint_path=species.blueprint_path,
            reference_level=species.reference_level,
            root_value=species.root_value,
            tier=species.tier,
            breeding_difficulty=species.breeding_difficulty,
            breeding_notes=species.breeding_notes,
            status="PRE_REGISTERED",
            shop_price_synced_at=now,
        )
        db.add(row)
        db.flush()
        created = True
    else:
        row.catalog_item_id = species.catalog_item_id
        row.blueprint_path = species.blueprint_path
        row.reference_level = species.reference_level
        row.root_value = species.root_value
        row.tier = species.tier
        row.updated_at = now
        if row.status not in ("ACTIVE",):
            row.status = "PRE_REGISTERED"
    _apply_multipliers_row(db, row, species)
    _sync_species_aliases(db, row, aliases)
    db.commit()
    return {
        "species_key": species.species_key,
        "display_name": row.display_name,
        "shop_catalog_name": shop_catalog_display_name(catalog, row.catalog_item_id),
        "root_value": species.root_value,
        "status": row.status,
        "created": created,
    }


def update_species_display_name(
    db: Session,
    species_key: str,
    display_name: str,
    *,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Atualiza só o nome exibido no Comércio — não altera config.json da loja."""
    from app import MarketSpecies

    key = (species_key or "").strip()
    name = (display_name or "").strip()
    if not key:
        raise ValueError("species_key obrigatório")
    if not name or len(name) > 128:
        raise ValueError("Nome do Comércio deve ter 1–128 caracteres")

    row = db.query(MarketSpecies).filter(MarketSpecies.species_key == key).first()
    if row is None:
        raise ValueError("Espécie não encontrada")

    row.display_name = name
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    out: dict[str, Any] = {
        "species_key": row.species_key,
        "display_name": row.display_name,
        "catalog_item_id": row.catalog_item_id,
    }
    if catalog is not None:
        out["shop_catalog_name"] = shop_catalog_display_name(catalog, row.catalog_item_id)
    return out
