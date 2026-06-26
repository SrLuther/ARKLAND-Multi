#!/usr/bin/env python3
"""Apply VIP and license-tier kit pricing (10% of license) to CustomShop config.json."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.catalog_vip_pricing import apply_vip_pricing_to_catalog  # noqa: E402

CONFIG_PATHS = [
    ROOT / "plugin" / "CustomShop" / "configs" / "config.json",
    ROOT / "plugin" / "CustomShop" / "bin" / "config.json",
]


def apply(config_path: Path) -> tuple[list[str], list[str]]:
    data = json.loads(config_path.read_text(encoding="utf-8"))
    cleared, kit_updates = apply_vip_pricing_to_catalog(data)
    config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cleared, kit_updates


def main() -> None:
    source = CONFIG_PATHS[0]
    cleared, kit_updates = apply(source)
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
