#!/usr/bin/env python3
"""Gera/atualiza entradas Type:dino Level 200 no CustomShop (idempotente).

Regras aprovadas (Jul/2026, opção A):
  R = root_value, B = premium_budget (market_species_defaults)
  V254 = min(R + B, market_absolute_max)   # Q=1 full 254
  P200 = round(0.40 × V254)                # L200_OF_V254_RATIO
  Se P200 <= P1 → não listar (remove par *_l200 se existir)

Uso:
  python tools/apply_shop_l200_prices.py
  python tools/apply_shop_l200_prices.py --dry-run
  python tools/apply_shop_l200_prices.py --config plugin/CustomShop/configs/config.json
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugin" / "arkshop_web"
sys.path.insert(0, str(WEB))

import market_economy as me  # noqa: E402

_LEVEL_IN_TEXT = re.compile(r"N[ií]vel\s+\d+", re.I)
_SEX_IN_TEXT = re.compile(r"\s*F[eê]mea\s*", re.I)


def _rewrite_level_text(text: str, level: int) -> str:
    raw = str(text or "").strip()
    if not raw:
        return raw
    if _LEVEL_IN_TEXT.search(raw):
        return _LEVEL_IN_TEXT.sub(f"Nível {level}", raw)
    return f"{raw} Nível {level}"


def _strip_fixed_sex_text(text: str) -> str:
    """L200 não tem sexo fixo — remove 'Fêmea' do nome/descrição."""
    raw = str(text or "").strip()
    if not raw:
        return raw
    out = _SEX_IN_TEXT.sub(" ", raw)
    return re.sub(r"\s+", " ", out).strip()


def _build_l200_entry(l1_entry: dict[str, Any], price: int) -> dict[str, Any]:
    entry = copy.deepcopy(l1_entry)
    entry["Type"] = "dino"
    entry["Price"] = int(price)
    dinos = entry.get("Dinos") or []
    if not dinos:
        raise ValueError("L1 sem Dinos[]")
    d0 = dict(dinos[0])
    d0["Level"] = 200
    d0.setdefault("ForceTame", True)
    d0.setdefault("Neutered", False)
    # Sexo aleatório: omitir Gender (plugin ApplyGender só força male/female)
    d0.pop("Gender", None)
    entry["Dinos"] = [d0]
    if entry.get("Description"):
        entry["Description"] = _strip_fixed_sex_text(
            _rewrite_level_text(str(entry["Description"]), 200)
        )
    if entry.get("Name"):
        entry["Name"] = _strip_fixed_sex_text(
            _rewrite_level_text(str(entry["Name"]), 200)
        )
    elif entry.get("Description"):
        entry["Name"] = str(entry["Description"])
    return entry


def apply_l200_to_catalog(
    catalog: dict[str, Any],
    *,
    ratio: float = me.L200_OF_V254_RATIO,
) -> dict[str, Any]:
    """Aplica L200 in-place. Devolve resumo {created, updated, skipped, removed, details}."""
    items: dict[str, Any] = catalog.setdefault("Items", {})
    created: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    market_cap = me.load_market_absolute_max()

    l1_pairs = me.iter_catalog_dinos(catalog, level1_only=True)
    wanted_l200_ids: set[str] = set()

    for l1_id, l1_entry in l1_pairs:
        p1 = int(l1_entry.get("Price") or 0)
        root = me.resolve_species_root_value(l1_id, l1_entry)
        budget = me.resolve_species_premium_budget(l1_id, l1_entry)
        l200_id = me.l200_shop_id(l1_id)
        if root is None or root < 0 or budget is None:
            skipped.append(
                {
                    "l1_id": l1_id,
                    "l200_id": l200_id,
                    "reason": "missing_economy",
                    "p1": p1,
                    "root": root,
                    "premium_budget": budget,
                }
            )
            continue
        v254 = me.compute_v254(root, budget, market_cap)
        price = me.compute_l200_price(
            p1, root, budget, market_absolute_max=market_cap, ratio=ratio
        )
        if price is None:
            skipped.append(
                {
                    "l1_id": l1_id,
                    "l200_id": l200_id,
                    "reason": "p200_leq_p1",
                    "p1": p1,
                    "root": root,
                    "premium_budget": budget,
                    "v254": v254,
                    "p200": int(round(float(ratio) * float(v254))),
                }
            )
            if l200_id in items and me.is_catalog_dino_level200(items[l200_id]):
                del items[l200_id]
                removed.append(
                    {
                        "l200_id": l200_id,
                        "reason": "p200_leq_p1",
                        "p1": p1,
                        "v254": v254,
                    }
                )
            continue

        wanted_l200_ids.add(l200_id)
        new_entry = _build_l200_entry(l1_entry, price)
        detail = {
            "l1_id": l1_id,
            "l200_id": l200_id,
            "p1": p1,
            "root": root,
            "premium_budget": budget,
            "v254": v254,
            "price": price,
        }
        if l200_id in items:
            prev = items[l200_id]
            items[l200_id] = new_entry
            detail["prev_price"] = int(prev.get("Price") or 0)
            updated.append(detail)
        else:
            items[l200_id] = new_entry
            created.append(detail)

    # Remove órfãos *_l200 que já não têm L1 elegível
    for item_id in list(items.keys()):
        if not str(item_id).endswith(me.L200_ID_SUFFIX):
            continue
        if item_id in wanted_l200_ids:
            continue
        entry = items.get(item_id)
        if isinstance(entry, dict) and me.is_catalog_dino_level200(entry):
            del items[item_id]
            removed.append({"l200_id": item_id, "reason": "orphan_or_skipped"})

    return {
        "ok": True,
        "ratio": ratio,
        "market_absolute_max": market_cap,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "removed": removed,
        "created_count": len(created),
        "updated_count": len(updated),
        "skipped_count": len(skipped),
        "removed_count": len(removed),
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--config",
        type=Path,
        action="append",
        dest="configs",
        help="config.json (pode repetir). Default: configs + bin",
    )
    parser.add_argument(
        "--defaults",
        type=Path,
        default=WEB / "data" / "market_species_defaults.json",
    )
    parser.add_argument(
        "--ratio",
        type=float,
        default=me.L200_OF_V254_RATIO,
        help="Fração de V254 para o preço L200 (default 0.40)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    me._DEFAULTS_FILE = args.defaults.resolve()
    # limpar caches de defaults se existirem
    for fn_name in ("load_defaults_file", "load_default_species_map", "build_catalog_economy_map"):
        fn = getattr(me, fn_name, None)
        if fn is not None and hasattr(fn, "cache_clear"):
            fn.cache_clear()  # type: ignore[attr-defined]

    configs = args.configs or [
        ROOT / "plugin" / "CustomShop" / "configs" / "config.json",
        ROOT / "plugin" / "CustomShop" / "bin" / "config.json",
    ]

    exit_code = 0
    for cfg_path in configs:
        if not cfg_path.is_file():
            print(f"SKIP (ausente): {cfg_path}")
            continue
        catalog = json.loads(cfg_path.read_text(encoding="utf-8"))
        summary = apply_l200_to_catalog(catalog, ratio=float(args.ratio))
        print(f"=== {cfg_path}")
        print(
            f"ratio={summary['ratio']} cap={summary['market_absolute_max']} | "
            f"created={summary['created_count']} updated={summary['updated_count']} "
            f"skipped={summary['skipped_count']} removed={summary['removed_count']}"
        )
        if args.verbose:
            for row in summary["created"]:
                print(
                    f"  + {row['l1_id']} -> {row['l200_id']}  "
                    f"P1={row['p1']} V254={row['v254']} P200={row['price']}"
                )
            for row in summary["updated"][:20]:
                print(
                    f"  ~ {row['l1_id']} -> {row['l200_id']}  "
                    f"P1={row['p1']} V254={row['v254']} "
                    f"P200={row['prev_price']}->{row['price']}"
                )
            for row in summary["skipped"][:30]:
                print(
                    f"  · skip {row['l1_id']}: {row['reason']} "
                    f"P1={row.get('p1')} V254={row.get('v254')} P200={row.get('p200')}"
                )
            if summary["skipped_count"] > 30:
                print(f"  · … +{summary['skipped_count'] - 30} skips")
        if not args.dry_run:
            _write_json(cfg_path, catalog)
            print("  wrote OK")
        else:
            print("  (dry-run — não gravou)")
        if not summary.get("ok"):
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
