#!/usr/bin/env python3
"""Gera variantes de nível por espécie no catálogo CustomShop (sem categorias fixas L1/L200).

Para cada dino de nível 1 (base) cria UMA entrada por nível configurado em ``--levels``
(ex.: ``1,50,100,150,200,225``). IDs: nível 1 mantém o id base; demais → ``<base>_l<N>``
(compatível com ``rex_femea_l200`` já existente). Idempotente: pula (blueprint, gênero, nível)
que já existem no catálogo, mesmo com outro id.

Preço: interpolação linear entre o preço L1 e uma referência (preço do maior nível já cadastrado
para a mesma espécie/gênero; se não houver, multiplicador legado de ``add_dino_lvl200_pairs`` em
``--ref-level``). Sempre revise preços (e market_species_defaults) antes de publicar.

Uso:
  python tools/generate_dino_level_variants.py --levels 50,100,150,200,225            # dry-run
  python tools/generate_dino_level_variants.py --levels 100,225 --apply --catalog docs/config.json
  python tools/generate_dino_level_variants.py --levels 150 --species rex,giga --apply
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugin" / "arkshop_web"))

from dino_levels import (  # noqa: E402
    base_item_id,
    dino_level_max,
    entry_dino_gender,
    entry_dino_level,
    interpolate_level_price,
    level_variant_id,
    parse_dino_level,
    retitle_for_level,
)

DEFAULT_CATALOG = ROOT / "plugin" / "CustomShop" / "catalog.json"


def _legacy_ref_multiplier(p1: int) -> float:
    """Mesmos degraus de tools/add_dino_lvl200_pairs.py (preço L200 ≈ p1 × mult)."""
    if p1 >= 35_000:
        return 1.43
    if p1 >= 20_000:
        return 1.75
    if p1 >= 8_000:
        return 2.5
    return 3.0


def _blueprint(entry: dict) -> str:
    dinos = entry.get("Dinos") or []
    return str(dinos[0].get("Blueprint") or "") if dinos and isinstance(dinos[0], dict) else ""


def parse_levels(raw: str | None) -> list[int]:
    raw = raw or os.environ.get("ARKSHOP_DINO_LEVELS", "1,50,100,150,200")
    cap = dino_level_max()
    out: list[int] = []
    for part in str(raw).split(","):
        lvl = parse_dino_level(part.strip(), max_level=cap)
        if lvl is None:
            raise SystemExit(f"Nível inválido em --levels: {part!r} (inteiro 1..{cap})")
        if lvl not in out:
            out.append(lvl)
    return sorted(out)


def generate(catalog: dict, levels: list[int], *, ref_level: int = 200,
             species: set[str] | None = None) -> list[tuple[str, dict]]:
    items = catalog.get("Items") or catalog.get("ShopItems") or {}
    existing = {}
    for key, e in items.items():
        if isinstance(e, dict) and str(e.get("Type") or "").lower() == "dino":
            existing[(_blueprint(e), entry_dino_gender(e, key), entry_dino_level(e, key))] = key
    created: list[tuple[str, dict]] = []
    for key, base in list(items.items()):
        if not isinstance(base, dict) or str(base.get("Type") or "").lower() != "dino":
            continue
        if entry_dino_level(base, key) != 1:
            continue
        sp = base_item_id(key)
        if species and not any(s in sp for s in species):
            continue
        gender = entry_dino_gender(base, key)
        bp = _blueprint(base)
        p1 = int(base.get("Price") or 0)
        # referência: maior nível já existente para a mesma espécie/gênero
        siblings = [(lvl, k) for (b, g, lvl), k in existing.items()
                    if b == bp and g == gender and lvl > 1]
        if siblings:
            ref_lvl, ref_key = max(siblings)
            p_ref = int(items[ref_key].get("Price") or 0)
        else:
            ref_lvl, p_ref = ref_level, int(round(p1 * _legacy_ref_multiplier(p1) / 100) * 100)
        for lvl in levels:
            if lvl == 1 or (bp, gender, lvl) in existing:
                continue
            new_id = level_variant_id(key, lvl)
            if new_id in items:
                continue
            entry = copy.deepcopy(base)
            for d in entry.get("Dinos") or []:
                if isinstance(d, dict):
                    d["Level"] = lvl
            for field in ("Description", "Name"):
                if entry.get(field):
                    entry[field] = retitle_for_level(entry[field], lvl)
            entry["Price"] = interpolate_level_price(p1, p_ref, lvl, ref_level=ref_lvl)
            created.append((new_id, entry))
            existing[(bp, gender, lvl)] = new_id
    return created


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    ap.add_argument("--levels", help="lista de níveis (padrão: env ARKSHOP_DINO_LEVELS ou 1,50,100,150,200)")
    ap.add_argument("--ref-level", type=int, default=200, help="nível de referência do multiplicador legado")
    ap.add_argument("--species", help="filtra por trecho do id base (csv)")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    path = Path(args.catalog)
    catalog = json.loads(path.read_text(encoding="utf-8-sig"))
    levels = parse_levels(args.levels)
    species = {s.strip().lower() for s in (args.species or "").split(",") if s.strip()} or None
    created = generate(catalog, levels, ref_level=args.ref_level, species=species)
    print(f"Níveis: {levels} | novas variantes: {len(created)}")
    for new_id, entry in created[:40]:
        print(f"  + {new_id}  Nv.{entry['Dinos'][0]['Level']}  {entry.get('Price')} Â")
    if len(created) > 40:
        print(f"  … (+{len(created) - 40})")
    if args.apply and created:
        items = catalog.get("Items") if "Items" in catalog else catalog.setdefault("ShopItems", {})
        for new_id, entry in created:
            items[new_id] = entry
        backup = path.with_suffix(path.suffix + ".bak")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Gravado: {path} (backup {backup.name})")
    elif not args.apply:
        print("(dry-run — use --apply para gravar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
