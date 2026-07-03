#!/usr/bin/env python3
"""Define Armor em selas e BPs de selas no catÃƒÆ’Ã‚Â¡logo CustomShop (config.json)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Iterator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.shop_catalog_import import normalize_blueprint  # noqa: E402

DEFAULT_CONFIG = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"
CONFIG_PATHS = [
    ROOT / "plugin" / "CustomShop" / "configs" / "config.json",
    ROOT / "plugin" / "CustomShop" / "bin" / "config.json",
]

# Pastas de armadura de jogador ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â nunca selas.
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

# Substrings no nome do asset que indicam peÃƒÆ’Ã‚Â§a de armadura (nÃƒÆ’Ã‚Â£o sela).
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

_SADDLE_PATH_RE = re.compile(
    r"/Armor/Saddles/|/Items/Saddle/|/Saddles/|/Saddle/",
    re.I,
)
_SMALLBOSSES_RE = re.compile(r"/Mods/SmallBosses/", re.I)
_PRIMAL_ARMOR_ASSET_RE = re.compile(r"^PrimalItemArmor_", re.I)
_SADDLE_ASSET_RE = re.compile(r"saddle|_Saddle|Platform", re.I)


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

    if _SADDLE_ASSET_RE.search(asset):
        return True

    if _SMALLBOSSES_RE.search(bp) and "armor" in asset_lower:
        return True

    return False

def _patch_nested_blueprint_items(
    entry: dict[str, Any],
    label_prefix: str,
    updated_paths: list[str],
    armor: float,
    *,
    include: Callable[[dict[str, Any]], bool] | None = None,
) -> None:
    for idx, item in enumerate(entry.get("Items") or []):
        if not isinstance(item, dict):
            continue
        if include is not None and not include(item):
            continue
        label = f"{label_prefix}.Items[{idx}]"
        if item.get("Armor") == armor:
            continue
        item["Armor"] = armor
        updated_paths.append(label)


def apply_saddle_armor(
    data: dict[str, Any],
    armor: float = 350,
) -> tuple[int, list[str]]:
    updated_paths: list[str] = []
    for key, entry in (data.get("Items") or {}).items():
        if not isinstance(entry, dict) or not key.startswith("sela_"):
            continue
        _patch_nested_blueprint_items(entry, f"Items.{key}", updated_paths, armor)
    for key, entry in (data.get("Kits") or {}).items():
        if not isinstance(entry, dict):
            continue
        if key.startswith("sela_"):
            _patch_nested_blueprint_items(entry, f"Kits.{key}", updated_paths, armor)
            continue
        _patch_nested_blueprint_items(
            entry,
            f"Kits.{key}",
            updated_paths,
            armor,
            include=lambda item: bool(item.get("Blueprint"))
            and is_saddle_blueprint(str(item["Blueprint"])),
        )
    return len(updated_paths), updated_paths


def validate_saddle_armor(
    data: dict[str, Any],
    armor: float = 350,
) -> list[tuple[str, str, Any]]:
    missing: list[tuple[str, str, Any]] = []

    def check_nested(
        entry: dict[str, Any],
        label_prefix: str,
        *,
        include: Callable[[dict[str, Any]], bool] | None = None,
    ) -> None:
        for idx, item in enumerate(entry.get("Items") or []):
            if not isinstance(item, dict):
                continue
            if include is not None and not include(item):
                continue
            label = f"{label_prefix}.Items[{idx}]"
            if item.get("Armor") != armor:
                missing.append((label, str(item.get("Blueprint", "")), item.get("Armor")))

    for key, entry in (data.get("Items") or {}).items():
        if not isinstance(entry, dict) or not key.startswith("sela_"):
            continue
        check_nested(entry, f"Items.{key}")

    for key, entry in (data.get("Kits") or {}).items():
        if not isinstance(entry, dict):
            continue
        if key.startswith("sela_"):
            check_nested(entry, f"Kits.{key}")
            continue
        check_nested(
            entry,
            f"Kits.{key}",
            include=lambda item: bool(item.get("Blueprint"))
            and is_saddle_blueprint(str(item["Blueprint"])),
        )
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Define Armor em selas e BPs de selas no config.json do CustomShop.",
    )
    parser.add_argument(
        "config",
        nargs="*",
        type=Path,
        help="Caminho(s) do config.json (padrÃƒÆ’Ã‚Â£o: configs/ e bin/)",
    )
    parser.add_argument(
        "--armor",
        type=float,
        default=350,
        help="Valor de Armor a aplicar (padrÃƒÆ’Ã‚Â£o: 350)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra quantas entradas seriam atualizadas sem gravar o arquivo",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Sai com cÃƒÆ’Ã‚Â³digo 1 se alguma sela nÃƒÆ’Ã‚Â£o tiver o Armor esperado",
    )
    args = parser.parse_args()

    config_paths = args.config or CONFIG_PATHS
    exit_code = 0

    for config_path in config_paths:
        if not config_path.is_file():
            print(f"Arquivo nÃƒÆ’Ã‚Â£o encontrado: {config_path}", file=sys.stderr)
            exit_code = 1
            continue

        data = json.loads(config_path.read_text(encoding="utf-8"))
        rel = config_path.relative_to(ROOT) if config_path.is_relative_to(ROOT) else config_path

        if args.validate:
            missing = validate_saddle_armor(data, armor=args.armor)
            if missing:
                print(f"{rel}: {len(missing)} sela(s) sem Armor={args.armor:g}")
                for label, bp, armor_val in missing[:8]:
                    print(f"  - {label}: Armor={armor_val!r}")
                if len(missing) > 8:
                    print(f"  ... e mais {len(missing) - 8}")
                exit_code = 1
            else:
                total = sum(
                    1
                    for key, entry in (data.get("Items") or {}).items()
                    if isinstance(entry, dict) and key.startswith("sela_")
                    for item in entry.get("Items") or []
                    if isinstance(item, dict)
                ) + sum(
                    1
                    for key, entry in (data.get("Kits") or {}).items()
                    if isinstance(entry, dict)
                    for item in entry.get("Items") or []
                    if isinstance(item, dict)
                    and item.get("Blueprint")
                    and is_saddle_blueprint(str(item["Blueprint"]))
                )
                print(f"{rel}: OK - {total} sela(s) com Armor={args.armor:g}")
            continue

        count, paths = apply_saddle_armor(data, armor=args.armor)
        print(f"{rel}: {count} sela(s) atualizada(s) (Armor={args.armor:g})")
        for path in paths[:8]:
            print(f"  - {path}")
        if len(paths) > 8:
            print(f"  ... e mais {len(paths) - 8}")

        if args.dry_run:
            print("(dry-run ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â arquivo nÃƒÆ’Ã‚Â£o alterado)")
            continue

        config_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Gravado: {config_path}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
