#!/usr/bin/env python3
"""Simula precos do Mercado (modelo proporcional) — validacao e exemplos."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin" / "arkshop_web"))

from market_economy import (  # noqa: E402
    calculate_suggested_value,
    load_default_species_map,
    merge_species_from_catalog_item,
    normalize_stat_points,
    simulate_economy,
)


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def run_scenarios() -> list[dict]:
    scenarios = [
        ("carcha_femea", 29994, {"health": 0, "melee": 0}, "Carcha zero pts"),
        ("carcha_femea", 29994, {"health": 7, "melee": 12}, "Carcha screenshot"),
        ("carcha_femea", 29994, {"health": 78, "melee": 105}, "Carcha moderada"),
        ("carcha_femea", 29994, {"health": 254, "melee": 254}, "Carcha top 254"),
    ]
    rows: list[dict] = []
    for species_key, root, pts_map, label in scenarios:
        stat_points = {k: {"points_base": v} for k, v in pts_map.items()}
        result = simulate_economy(species_key, stat_points, root_value=root)
        if not result:
            rows.append({"label": label, "error": "species not found"})
            continue
        rows.append(
            {
                "label": label,
                "species_key": species_key,
                "root": root,
                "total": result["computed_base_value"],
                "stat_points": pts_map,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Simula economia do Mercado de Dinos")
    parser.add_argument("--write", action="store_true", help="Reservado — nao altera JSON")
    parser.add_argument("--species", help="Simular uma especie (key)")
    parser.add_argument("--root", type=int, default=None)
    parser.add_argument("--json", action="store_true", help="Saida JSON")
    args = parser.parse_args()

    if args.species:
        pts = {"health": {"points_base": 78}, "melee": {"points_base": 105}}
        result = simulate_economy(args.species, pts, root_value=args.root)
        if not result:
            print(f"Especie nao encontrada: {args.species}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"{args.species}: sugerido = {fmt(result['computed_base_value'])}")
        return 0

    rows = run_scenarios()
    defaults = load_default_species_map()
    if args.json:
        print(json.dumps({"species_count": len(defaults), "scenarios": rows}, ensure_ascii=False, indent=2))
        return 0

    print(f"Especies no JSON: {len(defaults)}")
    print()
    print(f"{'Cenario':<22} {'Root':>10} {'Total':>12}")
    print("-" * 48)
    for row in rows:
        if row.get("error"):
            print(f"{row['label']:<22} ERRO: {row['error']}")
            continue
        print(f"{row['label']:<22} {fmt(row['root']):>10} {fmt(row['total']):>12}")
    if args.write:
        print("\n--write: modelo proporcional nao usa sync de multiplicadores (no-op).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
