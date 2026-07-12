#!/usr/bin/env python3
"""Opção A: sincroniza Prices L1 (e kits breeding) a partir de root_value.

Fonte oficial: market_species_defaults.json → root_value (R).
  Items[Type:dino Level 1].Price = R
  Kits *_pack10 (25% off) → round(n × P1 × 0.75)

Uso:
  python tools/sync_shop_l1_prices_from_root.py
  python tools/sync_shop_l1_prices_from_root.py --dry-run -v
  python tools/sync_shop_l1_prices_from_root.py --skip-kits
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugin" / "arkshop_web"
sys.path.insert(0, str(WEB))

import market_economy as me  # noqa: E402


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _clear_caches() -> None:
    for fn_name in ("load_defaults_file", "load_default_species_map", "build_catalog_economy_map"):
        fn = getattr(me, fn_name, None)
        if fn is not None and hasattr(fn, "cache_clear"):
            fn.cache_clear()  # type: ignore[attr-defined]


def apply_to_catalog(catalog: dict[str, Any], *, sync_kits: bool = True) -> dict[str, Any]:
    l1 = me.sync_catalog_l1_prices_from_root(catalog)
    kits = (
        me.sync_breeding_kit_prices(catalog)
        if sync_kits
        else {"ok": True, "changed_count": 0, "unchanged_count": 0, "skipped_count": 0, "skipped": []}
    )
    return {"ok": bool(l1.get("ok")) and bool(kits.get("ok")), "l1": l1, "kits": kits}


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
    parser.add_argument("--skip-kits", action="store_true", help="Não recalcular Kits pack10")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    me._DEFAULTS_FILE = args.defaults.resolve()
    _clear_caches()

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
        summary = apply_to_catalog(catalog, sync_kits=not args.skip_kits)
        l1 = summary["l1"]
        kits = summary["kits"]
        print(f"=== {cfg_path}")
        print(
            f"L1: changed={l1['changed_count']} unchanged={l1['unchanged_count']} "
            f"skipped={l1['skipped_count']} | "
            f"Kits: changed={kits.get('changed_count', 0)} "
            f"unchanged={kits.get('unchanged_count', 0)} "
            f"skipped={kits.get('skipped_count', 0)}"
        )
        if args.verbose:
            for row in l1.get("changed") or []:
                print(
                    f"  L1 {row['l1_id']}: {row['old_price']} -> {row['new_price']}"
                )
            for row in (kits.get("changed") or [])[:40]:
                print(
                    f"  Kit {row['kit_id']}: {row['old_price']} -> {row['new_price']} "
                    f"(n={row['n']} × P1={row['p1']} × 0.75)"
                )
            for row in kits.get("skipped") or []:
                print(f"  · kit skip {row['kit_id']}: {row.get('reason')}")
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
