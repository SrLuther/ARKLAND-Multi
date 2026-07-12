"""
Sincroniza dinos Type:dino L1 do CustomShop → market_species_defaults.json.

Não inventa blueprints — só usa o BP do config.json.
Agrupa variantes conhecidas (ex.: Meraxes) no mesmo species_key.

Uso:
  python tools/sync_shop_catalog_to_market_defaults.py
  python tools/sync_shop_catalog_to_market_defaults.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugin" / "arkshop_web"
sys.path.insert(0, str(WEB))

import market_economy as me  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Não grava o JSON")
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "plugin" / "CustomShop" / "configs" / "config.json",
    )
    parser.add_argument(
        "--defaults",
        type=Path,
        default=WEB / "data" / "market_species_defaults.json",
    )
    args = parser.parse_args()

    me._DEFAULTS_FILE = args.defaults.resolve()
    catalog = json.loads(args.config.read_text(encoding="utf-8"))
    missing = me.find_catalog_dinos_missing_from_defaults(catalog)
    print(f"Catálogo: {args.config}")
    print(f"Defaults: {args.defaults}")
    print(f"Itens L1 em falta nos defaults: {len(missing)}")
    for item_id, entry in missing:
        print(f"  - {item_id}  Price={entry.get('Price')}  BP={me._catalog_item_blueprint(entry)[:60]}")

    result = me.ensure_catalog_species_in_defaults(catalog, write=not args.dry_run)
    print(result)
    if args.dry_run:
        print("(dry-run — ficheiro não alterado)")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
