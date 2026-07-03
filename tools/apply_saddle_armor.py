#!/usr/bin/env python3
"""Define Armor em selas e BPs de selas no catálogo CustomShop (config.json)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.shop_catalog_import import normalize_blueprint  # noqa: E402

DEFAULT_CONFIG = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"

# Pastas de armadura de jogador — nunca selas.
_PLAYER_ARMOR_PATH_PARTS = (
    "/Armor/Leather/",
    "/Armor/Metal/",
    "/Armor/TEK/",
    "/Armor/Tek/",
    "/Armor/Ghillie/",
    "/Armor/Riot/",
    "/Armor/SCUBA/",
    "/Armor/HazardSuit/",
    "/Armor/Skin/",
    "/Blindado/",
    "/Roupa_Tek/",
)

# Substrings no nome do asset que indicam peça de armadura (não sela).
_PLAYER_ARMOR_NAME_PARTS = (
    "Helmet",
    "Shirt",
    "Gloves",
    "Pants",
    "Boots",
    "Glider",
    "Shield",
    "HazardSuit",
    "Ghillie",
    "Scuba",
    "Chibi",
)

# Selas vanilla sem "Saddle" no nome do asset.
_KNOWN_SADDLE_ASSETS = frozenset({"PrimalItemArmor_Gallimimus"})

_SADDLE_PATH_RE = re.compile(r"/Armor/Saddles/|/Items/Saddle/|/Saddles/", re.I)
_SMALLBOSSES_RE = re.compile(r"/Mods/SmallBosses/", re.I)
_PRIMAL_ARMOR_ASSET_RE = re.compile(r"^PrimalItemArmor_", re.I)


def is_saddle_blueprint(blueprint: str) -> bool:
    """True se o blueprint for sela ou BP de sela (exclui armadura de jogador)."""
    bp = normalize_blueprint(blueprint)
    if not bp.startswith("/Game/"):
        return False

    bp_lower = bp.lower()
    for part in _PLAYER_ARMOR_PATH_PARTS:
        if part.lower() in bp_lower:
            return False

    asset = bp.rsplit("/", 1)[-1].split(".")[0]
    if asset.startswith("PrimalItemSkin_"):
        return False

    asset_lower = asset.lower()
    for part in _PLAYER_ARMOR_NAME_PARTS:
        if part.lower() in asset_lower:
            return False

    if _SADDLE_PATH_RE.search(bp):
        return True

    if asset in _KNOWN_SADDLE_ASSETS:
        return True

    if not _PRIMAL_ARMOR_ASSET_RE.match(asset):
        return False

    if "saddle" in asset_lower:
        return True

    if _SMALLBOSSES_RE.search(bp) and ("armor" in asset_lower or "saddle" in asset_lower):
        return True

    return False


def apply_saddle_armor(
    data: dict[str, Any],
    armor: float = 350,
) -> tuple[int, list[str]]:
    """Percorre Items e Kits; retorna (contagem, caminhos atualizados)."""
    updated_paths: list[str] = []

    def patch(entry: dict[str, Any], label: str) -> None:
        bp = entry.get("Blueprint", "")
        if not bp or not is_saddle_blueprint(str(bp)):
            return
        entry["Armor"] = armor
        updated_paths.append(label)

    for section in ("Items", "Kits"):
        for key, entry in (data.get(section) or {}).items():
            if not isinstance(entry, dict):
                continue
            top_bp = entry.get("Blueprint", "")
            if top_bp and is_saddle_blueprint(str(top_bp)):
                patch(entry, f"{section}.{key}")
            for idx, item in enumerate(entry.get("Items") or []):
                if isinstance(item, dict):
                    patch(item, f"{section}.{key}.Items[{idx}]")

    return len(updated_paths), updated_paths


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Define Armor em selas e BPs de selas no config.json do CustomShop.",
    )
    parser.add_argument(
        "config",
        nargs="?",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Caminho do config.json (padrão: {DEFAULT_CONFIG.relative_to(ROOT)})",
    )
    parser.add_argument(
        "--armor",
        type=float,
        default=350,
        help="Valor de Armor a aplicar (padrão: 350)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra quantas entradas seriam atualizadas sem gravar o arquivo",
    )
    args = parser.parse_args()

    config_path: Path = args.config
    if not config_path.is_file():
        print(f"Arquivo não encontrado: {config_path}", file=sys.stderr)
        return 1

    data = json.loads(config_path.read_text(encoding="utf-8"))
    count, paths = apply_saddle_armor(data, armor=args.armor)

    print(f"Selas encontradas: {count} (Armor={args.armor:g})")
    for path in paths[:8]:
        print(f"  - {path}")
    if len(paths) > 8:
        print(f"  ... e mais {len(paths) - 8}")

    if args.dry_run:
        print("(dry-run — arquivo não alterado)")
        return 0

    config_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Gravado: {config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
