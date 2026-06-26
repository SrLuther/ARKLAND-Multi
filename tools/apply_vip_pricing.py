#!/usr/bin/env python3
"""Apply VIP and license-tier kit pricing (10% of license) to CustomShop config.json."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.catalog_vip_pricing import (  # noqa: E402
    apply_vip_pricing_to_catalog,
    catalog_has_placeholder_kit_prices,
)
from src.shop_catalog_import import restore_backup_catalog  # noqa: E402
from src.shop_integration import catalog_entry_counts  # noqa: E402

CONFIG_PATHS = [
    ROOT / "plugin" / "CustomShop" / "configs" / "config.json",
    ROOT / "plugin" / "CustomShop" / "bin" / "config.json",
]

FULL_CATALOG_ITEM_MIN = 200
FULL_CATALOG_KIT_MIN = 30


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _assert_catalog_guard(
    before_items: int,
    before_kits: int,
    after_items: int,
    after_kits: int,
) -> None:
    """Falha se o backup era catálogo completo e o resultado perdeu itens/kits."""
    if before_items < FULL_CATALOG_ITEM_MIN and before_kits < FULL_CATALOG_KIT_MIN:
        return
    if before_items >= FULL_CATALOG_ITEM_MIN and after_items < FULL_CATALOG_ITEM_MIN:
        raise RuntimeError(
            f"Guarda de catálogo: itens caíram de {before_items} para {after_items} "
            f"(mínimo {FULL_CATALOG_ITEM_MIN})"
        )
    if before_kits >= FULL_CATALOG_KIT_MIN and after_kits < FULL_CATALOG_KIT_MIN:
        raise RuntimeError(
            f"Guarda de catálogo: kits caíram de {before_kits} para {after_kits} "
            f"(mínimo {FULL_CATALOG_KIT_MIN})"
        )


def apply(config_path: Path, *, data: dict | None = None) -> tuple[list[str], list[str], dict]:
    if data is None:
        data = _load_json(config_path)
    before_items, before_kits = catalog_entry_counts(data)
    cleared, kit_updates = apply_vip_pricing_to_catalog(data)
    after_items, after_kits = catalog_entry_counts(data)
    _assert_catalog_guard(before_items, before_kits, after_items, after_kits)
    _write_json(config_path, data)
    return cleared, kit_updates, data


def restore_from_backup(backup_path: Path, template_path: Path | None = None) -> dict:
    template_path = template_path or CONFIG_PATHS[0]
    backup = _load_json(backup_path)
    template = _load_json(template_path)
    before_items, before_kits = catalog_entry_counts(backup)

    data = restore_backup_catalog(backup, template)
    cleared, kit_updates = apply_vip_pricing_to_catalog(data)
    after_items, after_kits = catalog_entry_counts(data)
    _assert_catalog_guard(before_items, before_kits, after_items, after_kits)

    for dest in CONFIG_PATHS:
        _write_json(dest, data)

    return {
        "backup_path": str(backup_path),
        "before_items": before_items,
        "before_kits": before_kits,
        "after_items": after_items,
        "after_kits": after_kits,
        "cleared": cleared,
        "kit_updates": kit_updates,
        "data": data,
        "had_placeholders": catalog_has_placeholder_kit_prices(backup),
    }


def _print_report(result: dict) -> None:
    data = result["data"]
    items = data.get("Items") or {}
    kits = data.get("Kits") or {}

    print(f"Backup: {result['backup_path']}")
    print(f"Itens: {result['before_items']} → {result['after_items']}")
    print(f"Kits: {result['before_kits']} → {result['after_kits']}")
    if result.get("had_placeholders"):
        print("Placeholders 99M detectados no backup — corrigidos.")
    if result["cleared"]:
        print(f"  Placeholders removidos: {', '.join(result['cleared'][:15])}")
        if len(result["cleared"]) > 15:
            print(f"  ... +{len(result['cleared']) - 15} mais")
    if result["kit_updates"]:
        print(f"  Kits (10% licença): {', '.join(result['kit_updates'][:15])}")
        if len(result["kit_updates"]) > 15:
            print(f"  ... +{len(result['kit_updates']) - 15} mais")

    bronze = items.get("licenca_vip_bronze") or {}
    print(f"licenca_vip_bronze price: {bronze.get('Price')}")

    diamante_kit = kits.get("diamante") or {}
    print(f"diamante kit price: {diamante_kit.get('Price')}")
    print(f"diamante permissions: {diamante_kit.get('Permissions')}")

    for kid in ("vip_bronze", "prata", "ouro"):
        k = kits.get(kid) or {}
        print(f"  {kid}: price={k.get('Price')} perms={k.get('Permissions')}")

    for iid in ("struct_transmitter", "struct_generatortek", "item_soultraps_20", "struct_tekreplicator_vip"):
        i = items.get(iid) or {}
        print(f"  {iid}: price={i.get('Price')} perms={i.get('Permissions')}")

    settings = data.get("Settings") or {}
    print(f"ShopName: {settings.get('ShopName')}")
    print(f"WebsiteUrl: {settings.get('WebsiteUrl')}")
    print(f"WebApiUrl: {settings.get('WebApiUrl')}")
    print(f"WebApiKey: {'(definida)' if settings.get('WebApiKey') else '(vazia)'}")

    for dest in CONFIG_PATHS:
        print(f"Written: {dest}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Aplica preços VIP ao catálogo CustomShop.")
    parser.add_argument(
        "--from",
        dest="from_path",
        metavar="BACKUP",
        help="Restaura catálogo a partir de config.json de backup antes de aplicar VIP pricing.",
    )
    parser.add_argument(
        "--template",
        metavar="PATH",
        help="Template de defaults (padrão: plugin/CustomShop/configs/config.json).",
    )
    args = parser.parse_args()

    if args.from_path:
        backup_path = Path(args.from_path)
        template_path = Path(args.template) if args.template else CONFIG_PATHS[0]
        if not backup_path.is_file():
            raise SystemExit(f"Backup não encontrado: {backup_path}")
        result = restore_from_backup(backup_path, template_path)
        _print_report(result)
        return

    source = CONFIG_PATHS[0]
    cleared, kit_updates, data = apply(source)
    print(f"Updated {source}")
    if cleared:
        print(f"  Placeholders removidos: {', '.join(cleared)}")
    if kit_updates:
        print(f"  Kits (10% licença): {', '.join(kit_updates)}")
    for dest in CONFIG_PATHS[1:]:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        print(f"Synced {dest}")


if __name__ == "__main__":
    main()
