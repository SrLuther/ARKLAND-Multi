#!/usr/bin/env python3
"""Migra catálogos CustomShop para o modelo unificado «Dinos» (nível = campo, sem L1/L200 fixos).

O que faz (idempotente — rodar N vezes dá o mesmo resultado):
  - ``Dinos[].Level`` ausente → grava o nível inferido (categoria «Dinos 200», id ``_l200``/``_200``,
    nome/descrição «LVL 200», «Nível 150»…). Níveis já válidos NUNCA são alterados.
  - ``Category`` «Dinos 200» (e variantes) em itens dino → «Dinos».
  - ``--write-inferred-gender`` (opt-in): grava ``Gender`` inferido do id/nome nos ``Dinos[]`` sem
    gênero. ATENÇÃO: muda a entrega de «aleatório» para sexo fixo.

Uso:
  python tools/migrate_dinos_unified.py                       # dry-run no catálogo padrão
  python tools/migrate_dinos_unified.py --catalog docs/config.json --apply
  python tools/migrate_dinos_unified.py --apply --write-inferred-gender
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugin" / "arkshop_web"))

from dino_levels import (  # noqa: E402
    collect_level_options,
    dino_level_max,
    migrate_catalog_dinos,
    validate_catalog_dino_levels,
)

DEFAULT_CATALOGS = (
    ROOT / "plugin" / "CustomShop" / "catalog.json",
    ROOT / "docs" / "config.json",
)


def _items(catalog: dict) -> dict:
    items = catalog.get("Items") or catalog.get("ShopItems") or {}
    return items if isinstance(items, dict) else {}


def migrate_file(path: Path, *, apply: bool, write_gender: bool) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    catalog = json.loads(raw)
    errors = validate_catalog_dino_levels(catalog, max_level=dino_level_max())
    report = migrate_catalog_dinos(catalog, write_inferred_gender=write_gender)
    dinos = [e for e in _items(catalog).values()
             if isinstance(e, dict) and str(e.get("Type") or "").lower() == "dino"]
    report["levels"] = collect_level_options(dinos)
    report["invalid_levels"] = errors
    report["path"] = str(path)
    if apply and report["changed_items"]:
        backup = path.with_suffix(path.suffix + ".bak")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        report["written"] = True
    else:
        report["written"] = False
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--catalog", action="append", help="catálogo JSON (repetível)")
    ap.add_argument("--apply", action="store_true", help="grava (default: dry-run)")
    ap.add_argument("--write-inferred-gender", action="store_true",
                    help="grava Gender inferido (muda entrega aleatória → fixa)")
    args = ap.parse_args()

    paths = [Path(p) for p in (args.catalog or [])] or [p for p in DEFAULT_CATALOGS if p.is_file()]
    if not paths:
        print("Nenhum catálogo encontrado.")
        return 1
    rc = 0
    for path in paths:
        rep = migrate_file(path, apply=args.apply, write_gender=args.write_inferred_gender)
        mode = "APLICADO" if rep["written"] else ("dry-run" if not args.apply else "sem mudanças")
        print(f"\n[{mode}] {rep['path']}")
        print(f"  itens alterados: {rep['changed_items']} | Level preenchido: {rep['level_filled']} "
              f"| categoria corrigida: {rep['category_fixed']} | Gender gravado: {rep['gender_filled']}")
        lv = Counter({o['level']: o['count'] for o in rep["levels"]})
        print("  níveis no catálogo:", ", ".join(f"Nv.{k}×{v}" for k, v in sorted(lv.items())) or "—")
        if rep["unresolved_level"]:
            print(f"  ⚠ sem nível inferível ({len(rep['unresolved_level'])}): "
                  + ", ".join(rep["unresolved_level"][:15]))
        if rep["invalid_levels"]:
            rc = 2
            print(f"  ✖ níveis inválidos ({len(rep['invalid_levels'])}):")
            for e in rep["invalid_levels"][:15]:
                print("    -", e["error"])
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
