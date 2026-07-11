#!/usr/bin/env python3
"""Recalibração total do catálogo L1 e economia por blueprint.

Uso:
  python tools/recalibrate_market_economy.py --dry-run
  python tools/recalibrate_market_economy.py --apply-catalog --apply-economy
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugin" / "arkshop_web"
sys.path.insert(0, str(WEB))

from market_economy import (  # noqa: E402
    ECONOMY_STAT_KEYS,
    SpeciesEconomy,
    apply_economy_meta,
    blueprint_short_key,
    calculate_encomenda_value,
    calculate_quality_index,
    calculate_suggested_value,
    is_catalog_dino_level1,
    load_species_root_ladder,
    normalize_blueprint,
)

CONFIG_PATH = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"
DEFAULTS_PATH = WEB / "data" / "market_species_defaults.json"
MATRIX_PATH = ROOT / "tools" / "blueprint_catalog_matrix.csv"
MIGRATION_PATH = ROOT / "tools" / "catalog_id_migration.json"
MARKET_CAP = 150_000


@dataclass
class BlueprintRow:
    blueprint_path: str
    blueprint_short: str
    display_name: str
    species_key: str
    dino_role: str
    tier: str
    prestige_rank: int
    commerce_channel: str
    R: int
    B: int
    id_loja_novo: str
    id_loja_antigo_l1: str = ""
    id_loja_antigo_l200: str = ""
    price_antigo_l1: int = 0
    price_antigo_l200: int = 0
    template_entry: dict[str, Any] = field(default_factory=dict)
    template_item_id: str = ""

    @property
    def mercado_0(self) -> int:
        return self.R

    @property
    def mercado_254(self) -> int:
        return min(self.R + self.B, MARKET_CAP)

    def encomenda(self, market_value: int) -> int:
        species = SpeciesEconomy(
            species_key=self.species_key,
            display_name=self.display_name,
            root_value=self.R,
            premium_budget=self.B,
            dino_role=self.dino_role,
            tier=self.tier,
            prestige_rank=self.prestige_rank,
            pricing_mode="floor_quality",
        )
        apply_economy_meta(species)
        return calculate_encomenda_value(species, market_value)


def _clean_shop_id(item_id: str) -> str:
    s = str(item_id or "").strip()
    for suffix in ("_femea", "_female", "_1"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    if s.endswith("_200"):
        s = s[:-4]
    return s or item_id


def _display_name_from_entry(entry: dict[str, Any], fallback: str) -> str:
    name = str(entry.get("Name") or entry.get("Description") or fallback)
    name = re.sub(r"\s+N[ií]vel\s+\d+.*$", "", name, flags=re.I)
    name = re.sub(r"\s+F[eê]mea.*$", "", name, flags=re.I)
    name = re.sub(r"\s*\(SmallBosses\).*$", "", name, flags=re.I)
    return name.strip() or fallback


def _load_catalog() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _iter_dinos_by_blueprint(catalog: dict[str, Any]) -> dict[str, list[tuple[str, dict[str, Any]]]]:
    items = catalog.get("Items") or catalog.get("ShopItems") or {}
    grouped: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for item_id, entry in items.items():
        if str(entry.get("Type") or "").lower() != "dino":
            continue
        dino = (entry.get("Dinos") or [{}])[0]
        bp = str(dino.get("Blueprint") or "").strip()
        if not bp:
            continue
        grouped.setdefault(bp, []).append((item_id, entry))
    return grouped


def _r_from_ladder(role: str, tier: str, prestige: int, ladder: dict[str, Any]) -> int:
    ranges = (ladder.get("r_ranges") or {}).get(role, {}).get(tier)
    if not ranges:
        return 5000
    lo = int(ranges.get("min", 1000))
    hi = int(ranges.get("max", lo))
    prestige = max(1, min(100, int(prestige)))
    if hi <= lo:
        return lo
    return int(lo + (hi - lo) * (prestige - 1) / 99)


def _b_from_ladder(role: str, tier: str, r: int, ladder: dict[str, Any]) -> int:
    targets = (ladder.get("mercado_254_targets") or {}).get(role, {})
    target = int(targets.get(tier, min(MARKET_CAP, r + 20_000)))
    target = min(target, MARKET_CAP)
    return max(0, target - r)


def _classify_blueprint(
    bp: str,
    items: list[tuple[str, dict[str, Any]]],
    ladder: dict[str, Any],
    defaults_map: dict[str, dict[str, Any]],
) -> BlueprintRow:
    short = blueprint_short_key(bp)
    overrides = ladder.get("blueprint_overrides") or {}
    anchors = ladder.get("anchors") or {}
    ov = dict(overrides.get(short) or {})

    l1_items = [(iid, e) for iid, e in items if is_catalog_dino_level1(e)]
    l200_items = [(iid, e) for iid, e in items if not is_catalog_dino_level1(e)]
    id_l1, entry_l1 = l1_items[0] if l1_items else ("", {})
    id_l200, entry_l200 = l200_items[0] if l200_items else ("", {})
    template_id, template_entry = (id_l1, entry_l1) if entry_l1 else (id_l200, entry_l200)

    # species_key from defaults JSON by blueprint
    species_key = str(ov.get("species_key") or "")
    if not species_key:
        for sk, defn in defaults_map.items():
            if normalize_blueprint(defn.get("blueprint_path")) == normalize_blueprint(bp):
                species_key = sk
                break
    if not species_key:
        species_key = _clean_shop_id(id_l200 or id_l1 or short)

    anchor = anchors.get(species_key) or {}
    dino_role = str(ov.get("dino_role") or anchor.get("dino_role") or "ataque")
    tier = str(ov.get("tier") or anchor.get("tier") or "B")
    prestige = int(ov.get("prestige_rank") or anchor.get("prestige_rank") or 50)
    commerce_channel = str(
        ov.get("commerce_channel") or anchor.get("commerce_channel") or "market_p2p"
    )

    if "tekstrider" in short or species_key == "tekstrider":
        commerce_channel = "catalog_only"

    r = int(anchor.get("R") or _r_from_ladder(dino_role, tier, prestige, ladder))
    b = _b_from_ladder(dino_role, tier, r, ladder)

    display = _display_name_from_entry(
        template_entry, defaults_map.get(species_key, {}).get("display_name") or species_key
    )
    id_novo = _clean_shop_id(species_key if species_key else (id_l200 or id_l1))

    return BlueprintRow(
        blueprint_path=bp,
        blueprint_short=short,
        display_name=display,
        species_key=species_key,
        dino_role=dino_role,
        tier=tier,
        prestige_rank=prestige,
        commerce_channel=commerce_channel,
        R=r,
        B=b,
        id_loja_novo=id_novo,
        id_loja_antigo_l1=id_l1,
        id_loja_antigo_l200=id_l200,
        price_antigo_l1=int(entry_l1.get("Price") or 0) if entry_l1 else 0,
        price_antigo_l200=int(entry_l200.get("Price") or 0) if entry_l200 else 0,
        template_entry=deepcopy(template_entry),
        template_item_id=template_id,
    )


def build_matrix(catalog: dict[str, Any] | None = None) -> list[BlueprintRow]:
    catalog = catalog or _load_catalog()
    ladder = load_species_root_ladder()
    defaults_map = {
        s["species_key"]: s
        for s in json.loads(DEFAULTS_PATH.read_text(encoding="utf-8")).get("species", [])
        if s.get("species_key")
    }
    grouped = _iter_dinos_by_blueprint(catalog)
    rows = [_classify_blueprint(bp, items, ladder, defaults_map) for bp, items in sorted(grouped.items())]
    return rows


def write_matrix_csv(rows: list[BlueprintRow], path: Path = MATRIX_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "blueprint_path",
                "blueprint_short",
                "species_key",
                "display_name_pt",
                "dino_role",
                "tier",
                "prestige_rank",
                "commerce_channel",
                "R",
                "B",
                "mercado_0",
                "mercado_254",
                "encomenda_0",
                "encomenda_254",
                "id_loja_novo",
                "id_loja_antigo_l1",
                "id_loja_antigo_l200",
                "price_antigo_l1",
                "price_antigo_l200",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "blueprint_path": row.blueprint_path,
                    "blueprint_short": row.blueprint_short,
                    "species_key": row.species_key,
                    "display_name_pt": row.display_name,
                    "dino_role": row.dino_role,
                    "tier": row.tier,
                    "prestige_rank": row.prestige_rank,
                    "commerce_channel": row.commerce_channel,
                    "R": row.R,
                    "B": row.B,
                    "mercado_0": row.mercado_0,
                    "mercado_254": row.mercado_254,
                    "encomenda_0": row.encomenda(row.mercado_0),
                    "encomenda_254": row.encomenda(row.mercado_254),
                    "id_loja_novo": row.id_loja_novo,
                    "id_loja_antigo_l1": row.id_loja_antigo_l1,
                    "id_loja_antigo_l200": row.id_loja_antigo_l200,
                    "price_antigo_l1": row.price_antigo_l1,
                    "price_antigo_l200": row.price_antigo_l200,
                }
            )


def _aquatica_label(name: str) -> str:
    name = str(name or "").strip()
    if not name or "(Aquática)" in name or "(Aquatica)" in name:
        return name
    return f"{name} (Aquática)"


def _build_l1_entry(row: BlueprintRow) -> dict[str, Any]:
    base = deepcopy(row.template_entry) if row.template_entry else {"Type": "dino"}
    dino = deepcopy((base.get("Dinos") or [{}])[0])
    dino["Blueprint"] = row.blueprint_path
    dino["Level"] = 1
    dino["ForceTame"] = True
    dino["Neutered"] = False
    dino["Gender"] = "female"
    base["Type"] = "dino"
    base["Price"] = row.R
    base["Category"] = base.get("Category") or "Comércio"
    label = _aquatica_label(row.display_name) if "/Game/Abyss" in row.blueprint_path else row.display_name
    base["Name"] = f"{label} Nível 1"
    base["Description"] = f"{label} Fêmea Nível 1"
    base["Dinos"] = [dino]
    if row.commerce_channel == "catalog_only":
        base["CommerceChannel"] = "catalog_only"
    return base


def apply_catalog(rows: list[BlueprintRow], catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    catalog = deepcopy(catalog or _load_catalog())
    items = catalog.setdefault("Items", catalog.setdefault("ShopItems", {}))

    remove_ids: set[str] = set()
    migration: dict[str, str] = {}
    for row in rows:
        for old_id in (row.id_loja_antigo_l1, row.id_loja_antigo_l200):
            if old_id and old_id != row.id_loja_novo:
                remove_ids.add(old_id)
                migration[old_id] = row.id_loja_novo

    for rid in remove_ids:
        items.pop(rid, None)

    for row in rows:
        items[row.id_loja_novo] = _build_l1_entry(row)

    CONFIG_PATH.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    MIGRATION_PATH.write_text(
        json.dumps({"aliases": migration, "generated_by": "recalibrate_market_economy.py"}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return {"removed": len(remove_ids), "items": len(rows), "migration": len(migration)}


def apply_economy(rows: list[BlueprintRow]) -> dict[str, Any]:
    data = json.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))
    ladder = load_species_root_ladder()

    data["_floor_quality"] = {
        "enabled": True,
        "gamma": ladder.get("gamma", 0.82),
        "market_absolute_max": MARKET_CAP,
        "encomenda_absolute_max": ladder.get("encomenda_absolute_max", 275_000),
        "encomenda_alpha": ladder.get("encomenda_alpha", 0.25),
        "encomenda_beta": ladder.get("encomenda_beta", 0.35),
    }
    data["_role_stat_weights"] = ladder.get("role_stat_weights") or {}
    data["_price_ceiling"] = {"enabled": False}
    data["_size_caps"] = data.get("_size_caps") or {"small": MARKET_CAP, "medium": MARKET_CAP, "large": MARKET_CAP}

    existing = {s["species_key"]: s for s in data.get("species", []) if s.get("species_key")}
    new_species: list[dict[str, Any]] = []

    for row in rows:
        if row.commerce_channel == "catalog_only":
            continue
        prev = deepcopy(existing.get(row.species_key, {}))
        economy_stats = {sk: {"enabled": True} for sk in ECONOMY_STAT_KEYS}
        entry = {
            "species_key": row.species_key,
            "display_name": row.display_name,
            "blueprint_path": row.blueprint_path,
            "catalog_item_id": row.id_loja_novo,
            "reference_catalog_item_id": row.id_loja_novo,
            "catalog_item_ids": [row.id_loja_novo],
            "root_value": row.R,
            "premium_budget": row.B,
            "tier": row.tier,
            "dino_role": row.dino_role,
            "prestige_rank": row.prestige_rank,
            "commerce_channel": row.commerce_channel,
            "pricing_mode": "floor_quality",
            "diet_class": prev.get("diet_class") or "carnivore",
            "size_class": prev.get("size_class") or "medium",
            "breeding_difficulty": prev.get("breeding_difficulty") or "",
            "breeding_notes": prev.get("breeding_notes") or prev.get("breeding_notes", ""),
            "mod_source": prev.get("mod_source") or "",
            "economy_stats": economy_stats,
            "blueprint_aliases": prev.get("blueprint_aliases") or [],
        }
        new_species.append(entry)

    data["species"] = sorted(new_species, key=lambda s: (-int(s.get("root_value") or 0), s["species_key"]))
    DEFAULTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"species": len(new_species), "skipped_catalog_only": sum(1 for r in rows if r.commerce_channel == "catalog_only")}


def print_dry_run(rows: list[BlueprintRow]) -> None:
    print(f"Blueprints únicos: {len(rows)}")
    print(f"{'species_key':<22} {'role':<12} {'tier':<4} {'R':>8} {'B':>8} {'@254':>8} {'id_novo':<22}")
    for row in sorted(rows, key=lambda r: -r.mercado_254):
        print(
            f"{row.species_key:<22} {row.dino_role:<12} {row.tier:<4} "
            f"{row.R:>8} {row.B:>8} {row.mercado_254:>8} {row.id_loja_novo:<22}"
        )
    arma = next((r for r in rows if r.species_key == "armaedron"), None)
    indo = next((r for r in rows if r.species_key == "indominus"), None)
    carcha = next((r for r in rows if r.species_key == "carcha"), None)
    if arma and indo and carcha:
        ok = arma.R > indo.R > carcha.R
        print(f"\nHierarquia R: armaedron({arma.R}) > indominus({indo.R}) > carcha({carcha.R}) -> {'OK' if ok else 'FALHA'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Recalibra catálogo L1 e economia por blueprint")
    parser.add_argument("--dry-run", action="store_true", help="Imprime matriz sem gravar")
    parser.add_argument("--write-matrix", action="store_true", help="Grava blueprint_catalog_matrix.csv")
    parser.add_argument("--apply-catalog", action="store_true", help="Aplica config.json L1-only")
    parser.add_argument("--apply-economy", action="store_true", help="Atualiza market_species_defaults.json")
    args = parser.parse_args()

    rows = build_matrix()
    if args.write_matrix or args.dry_run or not (args.apply_catalog or args.apply_economy):
        write_matrix_csv(rows)
        print(f"Matriz gravada em {MATRIX_PATH.relative_to(ROOT)} ({len(rows)} linhas)")

    print_dry_run(rows)

    if args.apply_catalog:
        stats = apply_catalog(rows)
        print(f"Catálogo aplicado: {stats}")

    if args.apply_economy:
        stats = apply_economy(rows)
        print(f"Economia aplicada: {stats}")

    if not any([args.dry_run, args.write_matrix, args.apply_catalog, args.apply_economy]):
        print("\nUse --apply-catalog --apply-economy para gravar alterações.")


if __name__ == "__main__":
    main()
