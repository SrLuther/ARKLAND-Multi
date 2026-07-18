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
    ensure_catalog_species_in_defaults,
    is_catalog_dino_level1,
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
    normalize_blueprint,
    shop_catalog_display_name,
    stat_labels,
)
from ark_species_registry import is_cryopodable_dino_blueprint, registry_entry_is_commerce_dino


def _filter_commerce_dino_rows(
    db: Session, rows: list[Any],
) -> tuple[list[Any], dict[int, list[dict[str, Any]]]]:
    """Filtra linhas market_species para dinos criopodáveis (batch — sem N+1)."""
    from collections import defaultdict

    from app import MarketSpeciesAlias

    empty_aliases: dict[int, list[dict[str, Any]]] = {}
    if not rows:
        return [], empty_aliases
    ids = [int(r.id) for r in rows]
    aliases_by_sid: dict[int, list[Any]] = defaultdict(list)
    for alias in (
        db.query(MarketSpeciesAlias)
        .filter(MarketSpeciesAlias.species_id.in_(ids))
        .order_by(MarketSpeciesAlias.id)
        .all()
    ):
        aliases_by_sid[int(alias.species_id)].append(alias)

    alias_payload: dict[int, list[dict[str, Any]]] = {
        sid: [
            {
                "catalog_item_id": a.catalog_item_id,
                "blueprint_path": a.blueprint_path,
                "variant_label": a.variant_label,
            }
            for a in rows_
        ]
        for sid, rows_ in aliases_by_sid.items()
    }

    filtered: list[Any] = []
    for row in rows:
        bp = str(row.blueprint_path or "").strip()
        if bp and is_cryopodable_dino_blueprint(bp):
            filtered.append(row)
            continue
        alias_rows = aliases_by_sid.get(int(row.id), [])
        if alias_rows and any(
            is_cryopodable_dino_blueprint(str(a.blueprint_path or "")) for a in alias_rows
        ):
            filtered.append(row)
            continue
        if not bp and not alias_rows:
            reg = None
            try:
                from ark_species_registry import get_registry_entry

                reg = get_registry_entry(row.species_key)
            except Exception:
                pass
            if reg:
                if registry_entry_is_commerce_dino(reg):
                    filtered.append(row)
            else:
                filtered.append(row)
    return filtered, alias_payload


def _species_row_is_commerce_dino(db: Session, row: Any) -> bool:
    """True se a linha market_species representa um dino criopodável."""
    filtered, _ = _filter_commerce_dino_rows(db, [row])
    return bool(filtered)


def deactivate_non_dino_species(db: Session) -> dict[str, Any]:
    """Desativa entradas de recursos/sementes/veículos em market_species."""
    from app import MarketSpecies

    deactivated: list[str] = []
    now = datetime.now(timezone.utc)
    for row in db.query(MarketSpecies).filter(MarketSpecies.status != "INACTIVE").all():
        if _species_row_is_commerce_dino(db, row):
            continue
        row.status = "INACTIVE"
        row.updated_at = now
        deactivated.append(row.species_key)
    if deactivated:
        db.commit()
    return {"deactivated": len(deactivated), "deactivated_keys": deactivated}


def sync_market_species_to_shop_catalog(
    db: Session,
    catalog: dict[str, Any],
    *,
    shop_level: int = 200,
) -> dict[str, Any]:
    """Garante dinos ACTIVE/PRE_REGISTERED no config.json (Type:dino, Level=shop_level)."""
    from app import MarketSpecies

    items = catalog.setdefault("Items", catalog.setdefault("ShopItems", {}))
    created = updated = skipped = 0
    keys: list[str] = []
    for row in (
        db.query(MarketSpecies)
        .filter(MarketSpecies.status.in_(("ACTIVE", "PRE_REGISTERED")))
        .order_by(MarketSpecies.species_key)
        .all()
    ):
        if not _species_row_is_commerce_dino(db, row):
            skipped += 1
            continue
        item_id = str(row.catalog_item_id or row.species_key).strip()
        bp = str(row.blueprint_path or "").strip()
        if not bp:
            from app import MarketSpeciesAlias

            alias = (
                db.query(MarketSpeciesAlias)
                .filter(MarketSpeciesAlias.species_id == row.id)
                .first()
            )
            bp = str(alias.blueprint_path or "").strip() if alias else ""
        if not bp:
            skipped += 1
            continue
        price = int(row.root_value or 0)
        name = str(row.display_name or item_id)
        entry = {
            "Type": "dino",
            "Price": price,
            "Category": "Comércio",
            "Name": name,
            "Description": f"{name} Nível {shop_level}",
            "Dinos": [
                {
                    "Blueprint": bp,
                    "Level": shop_level,
                    "ForceTame": True,
                    "Neutered": False,
                }
            ],
        }
        if item_id not in items:
            items[item_id] = entry
            created += 1
        else:
            existing = items[item_id]
            if str(existing.get("Type") or "").lower() != "dino":
                skipped += 1
                continue
            existing.update(entry)
            updated += 1
        keys.append(item_id)
    return {
        "shop_created": created,
        "shop_updated": updated,
        "shop_skipped": skipped,
        "shop_keys": keys,
    }


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
    return _list_species_aliases_batch(db, [species_id]).get(int(species_id), [])


def _list_species_aliases_batch(
    db: Session, species_ids: list[int],
) -> dict[int, list[dict[str, Any]]]:
    from app import MarketSpeciesAlias

    out: dict[int, list[dict[str, Any]]] = {int(sid): [] for sid in species_ids}
    if not species_ids:
        return out
    rows = (
        db.query(MarketSpeciesAlias)
        .filter(MarketSpeciesAlias.species_id.in_(species_ids))
        .order_by(MarketSpeciesAlias.species_id, MarketSpeciesAlias.variant_label)
        .all()
    )
    for row in rows:
        sid = int(row.species_id)
        out.setdefault(sid, []).append(
            {
                "catalog_item_id": row.catalog_item_id,
                "blueprint_path": row.blueprint_path,
                "variant_label": row.variant_label,
            }
        )
    return out


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


def _collect_blueprint_norms(species: SpeciesEconomy, aliases: list[dict[str, Any]]) -> set[str]:
    norms: set[str] = set()
    for bp in [species.blueprint_path, *[str(a.get("blueprint_path") or "") for a in aliases]]:
        nb = normalize_blueprint(bp)
        if nb:
            norms.add(nb)
    for alias in aliases:
        nb = str(alias.get("blueprint_norm") or "").strip()
        if nb:
            norms.add(nb)
    return norms


def _find_existing_species_row(
    db: Session,
    species: SpeciesEconomy,
    aliases: list[dict[str, Any]],
) -> tuple[Any | None, str | None]:
    """Localiza market_species por species_key, blueprint_norm ou catalog_item_id."""
    from app import MarketSpecies, MarketSpeciesAlias

    row = db.query(MarketSpecies).filter(MarketSpecies.species_key == species.species_key).first()
    if row:
        return row, "species_key"

    norms = _collect_blueprint_norms(species, aliases)
    for nb in norms:
        alias = (
            db.query(MarketSpeciesAlias)
            .filter(MarketSpeciesAlias.blueprint_norm == nb)
            .first()
        )
        if alias:
            row = db.query(MarketSpecies).filter(MarketSpecies.id == alias.species_id).first()
            if row:
                return row, "blueprint_norm"

    for nb in norms:
        for candidate in db.query(MarketSpecies).all():
            if normalize_blueprint(candidate.blueprint_path or "") == nb:
                return candidate, "blueprint_norm"

    catalog_ids: set[str] = set()
    if species.catalog_item_id:
        catalog_ids.add(species.catalog_item_id)
    for alias in aliases:
        cid = str(alias.get("catalog_item_id") or "").strip()
        if cid:
            catalog_ids.add(cid)

    for cid in catalog_ids:
        row = db.query(MarketSpecies).filter(MarketSpecies.catalog_item_id == cid).first()
        if row:
            return row, "catalog_item_id"
        alias = (
            db.query(MarketSpeciesAlias)
            .filter(MarketSpeciesAlias.catalog_item_id == cid)
            .first()
        )
        if alias:
            row = db.query(MarketSpecies).filter(MarketSpecies.id == alias.species_id).first()
            if row:
                return row, "catalog_item_id"

    return None, None


def _upsert_species_row(
    db: Session,
    species: SpeciesEconomy,
    aliases: list[dict[str, Any]],
    *,
    activate: bool,
    display_name_overrides: dict[str, str] | None,
    reset_display_names: bool,
    now: datetime,
) -> tuple[Any, bool, bool]:
    """Insere ou atualiza espécie + aliases. Retorna (row, created, merged_into_existing)."""
    from app import MarketSpecies

    existing, match_reason = _find_existing_species_row(db, species, aliases)
    merged_into_existing = bool(
        existing
        and match_reason in ("blueprint_norm", "catalog_item_id")
        and existing.species_key != species.species_key
    )
    override_name = _resolve_display_name_override(species, display_name_overrides)
    created = False
    row = existing
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
        if species.catalog_item_id and (
            not row.catalog_item_id or row.catalog_item_id == species.catalog_item_id
        ):
            row.catalog_item_id = species.catalog_item_id
        if override_name is not None:
            row.display_name = override_name
        elif reset_display_names and not merged_into_existing:
            row.display_name = species.display_name
        if species.blueprint_path and not row.blueprint_path:
            row.blueprint_path = species.blueprint_path
        elif species.blueprint_path and merged_into_existing:
            pass
        elif species.blueprint_path:
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
    return row, created, merged_into_existing


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
        _, was_created, _ = _upsert_species_row(
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
    """Importa espécies do overlay ark_species_registry.json (mods — ex.: Abyss 40 entradas).

    Apenas dinos criopodáveis — recursos, sementes e veículos ficam só no catálogo da loja.
    """
    from ark_species_registry import load_registry_overlay_raw

    from app import MarketSpecies

    skip = skip_keys or set()
    created = updated = skipped = filtered = 0
    items: list[str] = []
    filtered_keys: list[str] = []
    now = datetime.now(timezone.utc)
    status = "ACTIVE" if activate else "PRE_REGISTERED"
    existing_keys: set[str] = set()
    if only_missing:
        existing_keys = {str(r.species_key) for r in db.query(MarketSpecies.species_key).all()}

    for entry in load_registry_overlay_raw():
        sk = str(entry.get("species_key") or "").strip()
        if not sk or sk in skip:
            continue
        if not registry_entry_is_commerce_dino(entry):
            filtered += 1
            filtered_keys.append(sk)
            continue
        if only_missing and sk in existing_keys:
            skipped += 1
            continue
        species, aliases = merge_species_from_registry_entry(entry, status=status)
        _, was_created, _ = _upsert_species_row(
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
        "registry_filtered": filtered,
        "registry_filtered_keys": filtered_keys,
        "registry_keys": items,
    }


def feed_catalog_to_market(
    db: Session,
    catalog: dict[str, Any],
    *,
    activate: bool = False,
    level1_only: bool = True,
    only_missing: bool = False,
    item_ids: list[str] | None = None,
    include_reference_and_registry: bool = True,
    display_name_overrides: dict[str, str] | None = None,
    reset_display_names: bool = False,
) -> dict[str, Any]:
    """Auto-feed catálogo (ShopItems) → market_species com deduplicação forte.

    - Agrupa variantes pelo species_key de market_species_defaults.json.
    - Deduplica por blueprint_norm e catalog_item_id (não cria linhas duplicadas).
    - Kits não são processados (bundles, não espécies).
    - Por padrão considera só Type:dino com Dinos[0].Level == 1 (piso econômico).
    """
    created = updated = merged = skipped_duplicate = skipped = 0
    items: list[str] = []
    errors: list[dict[str, str]] = []
    now = datetime.now(timezone.utc)
    seen_groups: set[str] = set()
    seen_bp_norms: set[str] = set()

    # Garante defaults para dinos L1 da loja ainda sem espécie econômica.
    defaults_sync: dict[str, Any] = {}
    try:
        defaults_sync = ensure_catalog_species_in_defaults(catalog, write=True)
    except Exception as exc:
        defaults_sync = {"ok": False, "error": str(exc), "added": 0}

    feed_catalog = catalog
    if item_ids:
        allowed = {str(i).strip() for i in item_ids if str(i).strip()}
        items_map = catalog.get("Items") or catalog.get("ShopItems") or {}
        subset = {k: v for k, v in items_map.items() if k in allowed}
        feed_catalog = dict(catalog)
        if "ShopItems" in catalog:
            feed_catalog["ShopItems"] = subset
        else:
            feed_catalog["Items"] = subset

    for group_key, defn, catalog_items in iter_economy_groups(
        feed_catalog, level1_only=level1_only
    ):
        if not catalog_items:
            continue
        if group_key in seen_groups:
            skipped_duplicate += len(catalog_items)
            continue

        try:
            species, aliases = merge_economy_group(
                group_key,
                catalog_items,
                defaults=defn,
                catalog=feed_catalog,
                status="ACTIVE" if activate else "PRE_REGISTERED",
            )
        except Exception as exc:
            for item_id, _ in catalog_items:
                errors.append({"catalog_item_id": item_id, "error": str(exc)})
            continue

        group_norms = _collect_blueprint_norms(species, aliases)
        if group_norms & seen_bp_norms:
            skipped_duplicate += len(catalog_items)
            continue

        existing, _ = _find_existing_species_row(db, species, aliases)
        if only_missing and existing and existing.status in ("ACTIVE", "PRE_REGISTERED"):
            skipped_duplicate += len(catalog_items)
            seen_groups.add(group_key)
            seen_bp_norms.update(group_norms)
            continue

        try:
            row, was_created, was_merged = _upsert_species_row(
                db,
                species,
                aliases,
                activate=activate,
                display_name_overrides=display_name_overrides,
                reset_display_names=reset_display_names,
                now=now,
            )
        except Exception as exc:
            for item_id, _ in catalog_items:
                errors.append({"catalog_item_id": item_id, "error": str(exc)})
            continue

        canonical_key = row.species_key
        if canonical_key not in items:
            items.append(canonical_key)
        seen_groups.add(group_key)
        seen_groups.add(canonical_key)
        seen_bp_norms.update(group_norms)

        sibling_folded = max(0, len(catalog_items) - 1)
        if was_merged:
            merged += 1 + sibling_folded
        elif sibling_folded:
            merged += sibling_folded

        if was_created:
            created += 1
        else:
            updated += 1

    db.commit()

    ref: dict[str, Any] = {}
    reg: dict[str, Any] = {}
    if include_reference_and_registry:
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

    cleanup = deactivate_non_dino_species(db)
    from market_listings import reconcile_pending_listings

    promoted = reconcile_pending_listings(db)
    return {
        "created": created,
        "updated": updated,
        "merged": merged,
        "skipped_duplicate": skipped_duplicate,
        "skipped": skipped,
        "errors": errors,
        "species_keys": items,
        "promoted_listings": promoted,
        "level1_only": level1_only,
        "defaults_sync": defaults_sync,
        **ref,
        **reg,
        **cleanup,
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
    return feed_catalog_to_market(
        db,
        catalog,
        activate=activate,
        level1_only=True,
        only_missing=False,
        include_reference_and_registry=True,
        display_name_overrides=display_name_overrides,
        reset_display_names=reset_display_names,
    )


def list_species_public(db: Session, *, active_only: bool = True) -> list[dict[str, Any]]:
    from collections import defaultdict

    from app import MarketSpecies, MarketSpeciesAlias, MarketSpeciesStatMultiplier

    q = db.query(MarketSpecies).order_by(MarketSpecies.display_name)
    if active_only:
        q = q.filter(MarketSpecies.status == "ACTIVE")
    else:
        q = q.filter(MarketSpecies.status != "INACTIVE")
    rows = q.all()
    if not rows:
        return []

    rows, aliases_by_sid = _filter_commerce_dino_rows(db, rows)
    if not rows:
        return []

    ids = [r.id for r in rows]
    mults_by_sid: dict[int, list[Any]] = defaultdict(list)
    for m in (
        db.query(MarketSpeciesStatMultiplier)
        .filter(MarketSpeciesStatMultiplier.species_id.in_(ids))
        .all()
    ):
        mults_by_sid[int(m.species_id)].append(m)

    out = []
    for row in rows:
        mult_rows = mults_by_sid.get(int(row.id), [])
        economy = species_row_to_economy(row, mult_rows)
        item = economy.to_dict()
        item["reference_level"] = row.reference_level
        item["level1_base_value"] = row.root_value
        item["linked_variants"] = aliases_by_sid.get(int(row.id), [])
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


def _species_status_for_catalog_item(
    db: Session,
    catalog: dict[str, Any],
    item_id: str,
    entry: dict[str, Any],
) -> dict[str, Any]:
    """Status do Comércio para um item Type:dino do catálogo."""
    from app import MarketSpecies, MarketSpeciesAlias

    catalog_map = build_catalog_economy_map()
    defn = catalog_map.get(item_id) or {}
    group_key = str(defn.get("species_key") or item_id)
    row = db.query(MarketSpecies).filter(MarketSpecies.species_key == group_key).first()
    if row is None:
        alias = (
            db.query(MarketSpeciesAlias)
            .filter(MarketSpeciesAlias.catalog_item_id == item_id)
            .first()
        )
        if alias:
            row = db.query(MarketSpecies).filter(MarketSpecies.id == alias.species_id).first()
    status = row.status if row else None
    return {
        "catalog_item_id": item_id,
        "name": shop_catalog_display_name(catalog, item_id),
        "price": int(entry.get("Price") or 0),
        "species_key": group_key,
        "market_status": status,
        "market_registered": status in ("ACTIVE", "PRE_REGISTERED"),
        "market_active": status == "ACTIVE",
        "market_include": bool(entry.get("MarketInclude")),
        "display_name": row.display_name if row else None,
    }


def list_catalog_dinos_market_status(
    db: Session,
    catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    """Lista dinos do catálogo com status em market_species (para admin)."""
    out: list[dict[str, Any]] = []
    for item_id, entry in iter_catalog_dinos(catalog):
        out.append(_species_status_for_catalog_item(db, catalog, item_id, entry))
    return out


def bulk_pre_register_catalog_items(
    db: Session,
    catalog: dict[str, Any],
    *,
    item_ids: list[str] | None = None,
    only_missing: bool = True,
    activate: bool = False,
) -> dict[str, Any]:
    """Pré-cadastra dinos do catálogo no Comércio (agrupados, com deduplicação)."""
    result = feed_catalog_to_market(
        db,
        catalog,
        activate=activate,
        level1_only=True,
        only_missing=only_missing,
        item_ids=item_ids,
        include_reference_and_registry=False,
    )
    activated = 0
    if activate:
        from app import MarketSpecies

        for sk in result.get("species_keys") or []:
            row = db.query(MarketSpecies).filter(MarketSpecies.species_key == sk).first()
            if row and row.status == "ACTIVE":
                activated += 1
    return {
        "created": result.get("created", 0),
        "updated": result.get("updated", 0),
        "merged": result.get("merged", 0),
        "skipped_duplicate": result.get("skipped_duplicate", 0),
        "skipped": result.get("skipped_duplicate", 0) + result.get("skipped", 0),
        "activated": activated,
        "results": [],
        "errors": result.get("errors") or [],
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
