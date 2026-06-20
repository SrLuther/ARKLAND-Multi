"""Persistência e sync do catálogo econômico do Mercado de Dinos."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from market_economy import (
    STAT_KEYS,
    SpeciesEconomy,
    StatMultiplier,
    build_multipliers_from_defaults,
    iter_catalog_dinos,
    load_default_species_map,
    merge_species_from_catalog_item,
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
    return SpeciesEconomy(
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


def sync_catalog_to_db(
    db: Session,
    catalog: dict[str, Any],
    *,
    activate: bool = False,
) -> dict[str, Any]:
    """Importa dinos Type:dino do config.json para market_species."""
    from app import MarketSpecies, MarketSpeciesStatMultiplier

    defaults_map = load_default_species_map()
    created = updated = 0
    items: list[str] = []
    now = datetime.now(timezone.utc)

    for item_id, entry in iter_catalog_dinos(catalog):
        species = merge_species_from_catalog_item(
            item_id,
            entry,
            defaults=defaults_map.get(item_id),
            status="ACTIVE" if activate else "PRE_REGISTERED",
        )
        row = db.query(MarketSpecies).filter(MarketSpecies.species_key == species.species_key).first()
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
                status=species.status,
                shop_price_synced_at=now,
            )
            db.add(row)
            db.flush()
            created += 1
        else:
            row.catalog_item_id = species.catalog_item_id
            row.display_name = species.display_name
            row.blueprint_path = species.blueprint_path
            row.reference_level = species.reference_level
            row.root_value = species.root_value
            row.tier = species.tier
            row.breeding_difficulty = species.breeding_difficulty
            row.breeding_notes = species.breeding_notes
            row.shop_price_synced_at = now
            row.updated_at = now
            updated += 1
        _apply_multipliers_row(db, row, species)
        items.append(species.species_key)

    db.commit()
    return {"created": created, "updated": updated, "species_keys": items}


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
        out.append(item)
    return out


def get_species_table_payload(db: Session) -> dict[str, Any]:
    species = list_species_public(db, active_only=True)
    labels = stat_labels()
    multiplier_legend = []
    if species:
        mults = species[0].get("multipliers") or {}
        for sk, data in sorted(mults.items()):
            if data.get("enabled") and data.get("multiplier", 0) > 0:
                multiplier_legend.append(
                    {
                        "stat_key": sk,
                        "label": data.get("label") or labels.get(sk, sk),
                        "multiplier": data["multiplier"],
                        "note": "Global por espécie — editável pelo admin",
                    }
                )
    return {
        "title": "Tabela Oficial — Valores Base (Nível 1)",
        "description": (
            "Valor raiz de referência por espécie homologada. "
            "Não inclui pontos de status — apenas o animal nível 1 da loja."
        ),
        "currency": "Âmbar",
        "species": [
            {
                "species_key": s["species_key"],
                "display_name": s["display_name"],
                "reference_level": s.get("reference_level", 1),
                "root_value": s["root_value"],
                "tier": s.get("tier"),
                "catalog_item_id": s.get("catalog_item_id"),
                "multipliers": s.get("multipliers"),
            }
            for s in species
        ],
        "multiplier_legend": multiplier_legend,
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
    species = merge_species_from_catalog_item(
        item_id,
        entry,
        defaults=defaults_map.get(item_id),
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
        row.display_name = species.display_name
        row.blueprint_path = species.blueprint_path
        row.reference_level = species.reference_level
        row.root_value = species.root_value
        row.tier = species.tier
        row.updated_at = now
        if row.status not in ("ACTIVE",):
            row.status = "PRE_REGISTERED"
    _apply_multipliers_row(db, row, species)
    db.commit()
    return {
        "species_key": species.species_key,
        "display_name": species.display_name,
        "root_value": species.root_value,
        "status": row.status,
        "created": created,
    }
