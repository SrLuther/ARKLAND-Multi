#!/usr/bin/env python3
"""Sincroniza dinos homologados no Comércio P2P → config.json da loja (Level 200).

Fontes (em ordem):
1. market_species no banco (ACTIVE/PRE_REGISTERED) se ARKSHOP_DATABASE_URL estiver definido
2. Overlay ark_species_registry.json + market_species_defaults.json (somente dinos criopodáveis)

Recursos, sementes e veículos NÃO entram — ficam só via sync_abyss_shop_catalog.py (Items Type:item).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugin" / "arkshop_web"
sys.path.insert(0, str(WEB))

from ark_species_registry import (  # noqa: E402
    is_cryopodable_dino_blueprint,
    load_registry_overlay_raw,
    registry_entry_is_commerce_dino,
)
from market_economy import load_defaults_file  # noqa: E402

CONFIGS = [
    ROOT / "plugin/CustomShop/configs/config.json",
    ROOT / "plugin/CustomShop/bin/config.json",
]

SHOP_LEVEL = 200


def _dino_entry(item_id: str, name: str, bp: str, price: int) -> dict:
    return {
        "Type": "dino",
        "Price": price,
        "Category": "Comércio",
        "Name": name,
        "Description": f"{name} Nível {SHOP_LEVEL}",
        "Dinos": [
            {
                "Blueprint": bp,
                "Level": SHOP_LEVEL,
                "ForceTame": True,
                "Neutered": False,
            }
        ],
    }


def _species_from_registry_files() -> list[tuple[str, str, str, int]]:
    """Retorna (item_id, display_name, blueprint, price) de dinos elegíveis."""
    out: list[tuple[str, str, str, int]] = []
    seen: set[str] = set()

    for defn in load_defaults_file().get("species") or []:
        sk = str(defn.get("species_key") or "").strip()
        bp = str(defn.get("blueprint_path") or "").strip()
        if not sk or not bp or not is_cryopodable_dino_blueprint(bp):
            continue
        if sk in seen:
            continue
        seen.add(sk)
        out.append(
            (
                str(defn.get("catalog_item_id") or sk),
                str(defn.get("display_name") or sk),
                bp,
                int(defn.get("root_value") or 0),
            )
        )

    for entry in load_registry_overlay_raw():
        if not registry_entry_is_commerce_dino(entry):
            continue
        sk = str(entry.get("species_key") or "").strip()
        if not sk or sk in seen:
            continue
        paths = [str(p).strip() for p in (entry.get("blueprint_paths") or []) if str(p).strip()]
        bp = next((p for p in paths if is_cryopodable_dino_blueprint(p)), "")
        if not bp:
            continue
        seen.add(sk)
        out.append(
            (
                str(entry.get("catalog_item_id") or sk),
                str(entry.get("display_name") or sk),
                bp,
                int(entry.get("root_value") or 0),
            )
        )
    return out


def _species_from_db() -> list[tuple[str, str, str, int]] | None:
    url = os.environ.get("ARKSHOP_DATABASE_URL", "").strip()
    if not url:
        return None
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app import Base
    from market_migrate import MARKET_TABLES
    from market_service import _species_row_is_commerce_dino

    engine = create_engine(url, future=True)
    market_tables = [Base.metadata.tables[n] for n in MARKET_TABLES if n in Base.metadata.tables]
    Base.metadata.create_all(bind=engine, tables=market_tables)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = Session()
    try:
        from app import MarketSpecies, MarketSpeciesAlias

        rows = (
            db.query(MarketSpecies)
            .filter(MarketSpecies.status.in_(("ACTIVE", "PRE_REGISTERED")))
            .all()
        )
        out: list[tuple[str, str, str, int]] = []
        for row in rows:
            if not _species_row_is_commerce_dino(db, row):
                continue
            item_id = str(row.catalog_item_id or row.species_key).strip()
            bp = str(row.blueprint_path or "").strip()
            if not bp:
                alias = (
                    db.query(MarketSpeciesAlias)
                    .filter(MarketSpeciesAlias.species_id == row.id)
                    .first()
                )
                bp = str(alias.blueprint_path or "").strip() if alias else ""
            if not bp:
                continue
            out.append((item_id, str(row.display_name or item_id), bp, int(row.root_value or 0)))
        return out
    finally:
        db.close()


def apply_to_configs(species: list[tuple[str, str, str, int]]) -> dict[str, int]:
    created = updated = 0
    for cfg in CONFIGS:
        if not cfg.is_file():
            continue
        data = json.loads(cfg.read_text(encoding="utf-8"))
        items = data.setdefault("Items", data.setdefault("ShopItems", {}))
        for item_id, name, bp, price in species:
            entry = _dino_entry(item_id, name, bp, price)
            if item_id not in items:
                items[item_id] = entry
                created += 1
            elif str(items[item_id].get("Type") or "").lower() == "dino":
                items[item_id] = entry
                updated += 1
        cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{cfg.relative_to(ROOT)}: {len(species)} dinos L{SHOP_LEVEL} (criados={created}, atualizados={updated})")
    return {"created": created, "updated": updated, "total": len(species)}


def main() -> None:
    db_species = _species_from_db()
    if db_species is not None:
        print(f"Fonte: market_species ({len(db_species)} dinos)")
        species = db_species
    else:
        species = _species_from_registry_files()
        print(f"Fonte: registry JSON ({len(species)} dinos — defina ARKSHOP_DATABASE_URL para usar o banco)")
    stats = apply_to_configs(species)
    print(f"Concluído: {stats['total']} dinos, +{stats['created']} novos, {stats['updated']} atualizados")


if __name__ == "__main__":
    main()
