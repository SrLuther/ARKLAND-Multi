#!/usr/bin/env python3
"""Sincroniza dinos faltantes no catálogo usando blueprints do cache Beacon (sem inventar paths).

Fontes de espécies: market_species_defaults.json + ark_species_registry.json (overlay).
Blueprint: campo ``path`` do cache Beacon (%APPDATA%/ARKLAND-ServerManager/beacon_blueprints_cache.json).

Mod dinos (Abyss, ARK Additions, etc.) normalmente NÃO estão no Beacon — use
sync_abyss_shop_catalog.py / sync_market_species_to_shop_catalog.py para esses casos.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugin" / "arkshop_web"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB))

from ark_species_registry import (  # noqa: E402
    is_cryopodable_dino_blueprint,
    load_registry_overlay_raw,
    registry_entry_is_commerce_dino,
)
from market_economy import load_defaults_file  # noqa: E402
from src.beacon_client import BeaconBlueprintClient, _CACHE_FILE  # noqa: E402
from src.catalog_sync import apply_catalog_sync  # noqa: E402
from src.shop_integration import catalog_entry_counts  # noqa: E402

CONFIGS = [
    ROOT / "plugin" / "CustomShop" / "configs" / "config.json",
    ROOT / "plugin" / "CustomShop" / "bin" / "config.json",
]

SHOP_LEVEL_COMMERCE = 200
SHOP_LEVEL_ABYSS = 1
FULL_CATALOG_ITEM_MIN = 200
FULL_CATALOG_KIT_MIN = 25
FUZZY_THRESHOLD = 0.88


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _load_beacon_creatures() -> list[dict[str, Any]]:
    """Carrega criaturas do cache Beacon (aceita cache expirado se ainda existir)."""
    client = BeaconBlueprintClient()
    try:
        client.ensure_loaded(force=False)
    except Exception:
        pass
    if not client.is_loaded() and _CACHE_FILE.is_file():
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        bps = data.get("blueprints") or []
        if isinstance(bps, list) and bps:
            client._blueprints = bps  # noqa: SLF001 — leitura offline do cache
            client._loaded = True
    if not client.is_loaded():
        if client.is_authenticated():
            client.ensure_loaded(force=True)
        else:
            raise RuntimeError(
                f"Cache Beacon indisponível em {_CACHE_FILE}. "
                "Conecte ao Beacon no Server Manager ou restaure o cache."
            )
    creatures = [
        bp
        for bp in client._blueprints  # noqa: SLF001
        if bp.get("creatureId")
        and "_Character_BP" in str(bp.get("path") or "")
        and str(bp.get("path") or "").strip()
    ]
    if not creatures:
        raise RuntimeError("Nenhuma criatura encontrada no cache Beacon.")
    return creatures


def _build_beacon_index(creatures: list[dict[str, Any]]) -> dict[str, str]:
    """Índice label normalizado → path (primeira ocorrência vence)."""
    index: dict[str, str] = {}
    for entry in creatures:
        path = str(entry.get("path") or "").strip()
        if not path:
            continue
        for field in ("label", "alternateLabel"):
            label = str(entry.get(field) or "").strip()
            key = _norm(label)
            if key and key not in index:
                index[key] = path
        class_str = str(entry.get("classString") or "")
        m = re.match(r"([A-Za-z0-9_]+)_Character_BP", class_str)
        if m:
            token = _norm(m.group(1).replace("_", " "))
            if token and token not in index:
                index[token] = path
    return index


def _match_beacon_path(
    display_name: str,
    species_key: str,
    index: dict[str, str],
) -> tuple[str | None, str]:
    candidates = [
        _norm(display_name),
        _norm(species_key.replace("_", " ")),
        _norm(species_key),
    ]
    for cand in candidates:
        if cand and cand in index:
            return index[cand], f"exact:{cand}"

    best_path = ""
    best_label = ""
    best_score = 0.0
    for cand in candidates:
        if not cand:
            continue
        for label_norm, path in index.items():
            score = SequenceMatcher(None, cand, label_norm).ratio()
            if score > best_score:
                best_score = score
                best_path = path
                best_label = label_norm
    if best_path and best_score >= FUZZY_THRESHOLD:
        return best_path, f"fuzzy:{best_label}:{best_score:.2f}"
    return None, ""


def _catalog_ids(defn: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for cid in defn.get("catalog_item_ids") or []:
        ids.append(str(cid).strip())
    for field in ("catalog_item_id", "reference_catalog_item_id"):
        val = str(defn.get(field) or "").strip()
        if val:
            ids.append(val)
    if not ids:
        sk = str(defn.get("species_key") or "").strip()
        if sk:
            ids.append(sk)
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _species_targets() -> list[dict[str, Any]]:
    """Espécies do registry que precisam de entrada Type:dino no catálogo."""
    targets: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for defn in load_defaults_file().get("species") or []:
        bp = str(defn.get("blueprint_path") or "").strip()
        if not bp or not is_cryopodable_dino_blueprint(bp):
            continue
        sk = str(defn.get("species_key") or "").strip()
        if not sk or sk in seen_keys:
            continue
        seen_keys.add(sk)
        mod = str(defn.get("mod_source") or "vanilla")
        for item_id in _catalog_ids(defn):
            targets.append(
                {
                    "item_id": item_id,
                    "species_key": sk,
                    "display_name": str(defn.get("display_name") or item_id),
                    "price": int(defn.get("root_value") or 0),
                    "mod": mod,
                    "source": "defaults",
                    "registry_bp": bp,
                }
            )

    for entry in load_registry_overlay_raw():
        if not registry_entry_is_commerce_dino(entry):
            continue
        sk = str(entry.get("species_key") or "").strip()
        if not sk or sk in seen_keys:
            continue
        seen_keys.add(sk)
        paths = [str(p).strip() for p in (entry.get("blueprint_paths") or []) if str(p).strip()]
        registry_bp = next((p for p in paths if is_cryopodable_dino_blueprint(p)), "")
        item_id = str(entry.get("catalog_item_id") or sk)
        targets.append(
            {
                "item_id": item_id,
                "species_key": sk,
                "display_name": str(entry.get("display_name") or item_id),
                "price": int(entry.get("root_value") or 0),
                "mod": str(entry.get("mod") or "overlay"),
                "source": "registry",
                "registry_bp": registry_bp,
            }
        )
    return targets


def _dino_entry(
    name: str,
    bp: str,
    price: int,
    *,
    level: int,
    category: str,
    description_suffix: str,
) -> dict[str, Any]:
    return {
        "Type": "dino",
        "Price": price,
        "Category": category,
        "Name": name,
        "Description": f"{name} Nível {level}{description_suffix}",
        "Dinos": [
            {
                "Blueprint": bp,
                "Level": level,
                "ForceTame": True,
                "Neutered": False,
            }
        ],
    }


def _level_and_category(target: dict[str, Any]) -> tuple[int, str, str]:
    mod = str(target.get("mod") or "").lower()
    if mod == "abyss" or str(target.get("source")) == "registry" and "abyss" in mod:
        return SHOP_LEVEL_ABYSS, "Abyss", " (Aquática)"
    return SHOP_LEVEL_COMMERCE, "Comércio", ""


def _config_has_dino(items: dict[str, Any], item_id: str) -> bool:
    entry = items.get(item_id)
    return isinstance(entry, dict) and str(entry.get("Type") or "").lower() == "dino"


def _assert_shrink_guard(before_items: int, before_kits: int, after_items: int, after_kits: int) -> None:
    if before_items >= FULL_CATALOG_ITEM_MIN and after_items < FULL_CATALOG_ITEM_MIN:
        raise RuntimeError(
            f"Guarda: itens {before_items} → {after_items} (mínimo {FULL_CATALOG_ITEM_MIN})"
        )
    if before_kits >= FULL_CATALOG_KIT_MIN and after_kits < FULL_CATALOG_KIT_MIN:
        raise RuntimeError(
            f"Guarda: kits {before_kits} → {after_kits} (mínimo {FULL_CATALOG_KIT_MIN})"
        )


def _write_config(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sync_dinos_from_beacon() -> dict[str, Any]:
    creatures = _load_beacon_creatures()
    index = _build_beacon_index(creatures)
    targets = _species_targets()

    master = CONFIGS[0]
    data = json.loads(master.read_text(encoding="utf-8"))
    items = data.setdefault("Items", {})
    before_items, before_kits = catalog_entry_counts(data)

    added: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    skipped = 0

    for target in targets:
        item_id = target["item_id"]
        if _config_has_dino(items, item_id):
            skipped += 1
            continue

        bp, match_info = _match_beacon_path(
            target["display_name"],
            target["species_key"],
            index,
        )
        if not bp:
            failed.append(
                {
                    "item_id": item_id,
                    "species_key": target["species_key"],
                    "display_name": target["display_name"],
                    "mod": target["mod"],
                    "registry_bp": target.get("registry_bp") or "",
                    "reason": "sem correspondência no Beacon",
                }
            )
            continue

        level, category, suffix = _level_and_category(target)
        items[item_id] = _dino_entry(
            target["display_name"],
            bp,
            target["price"],
            level=level,
            category=category,
            description_suffix=suffix,
        )
        added.append(
            {
                "item_id": item_id,
                "display_name": target["display_name"],
                "beacon_path": bp,
                "match": match_info,
            }
        )

    apply_catalog_sync(data)
    after_items, after_kits = catalog_entry_counts(data)
    _assert_shrink_guard(before_items, before_kits, after_items, after_kits)

    dino_count = sum(
        1 for v in items.values() if isinstance(v, dict) and str(v.get("Type") or "").lower() == "dino"
    )

    for cfg in CONFIGS:
        _write_config(cfg, data)

    return {
        "beacon_creatures": len(creatures),
        "beacon_index": len(index),
        "targets": len(targets),
        "skipped_existing": skipped,
        "added": added,
        "failed": failed,
        "before_items": before_items,
        "after_items": after_items,
        "before_kits": before_kits,
        "after_kits": after_kits,
        "dino_count": dino_count,
    }


def main() -> None:
    print("==> Beacon -> catalogo CustomShop (dinos faltantes)")
    print(f"Cache: {_CACHE_FILE}")
    result = sync_dinos_from_beacon()

    print(f"Beacon: {result['beacon_creatures']} criaturas, índice {result['beacon_index']} labels")
    print(f"Espécies alvo: {result['targets']}, já no catálogo: {result['skipped_existing']}")
    print(f"Itens: {result['before_items']} -> {result['after_items']}")
    print(f"Kits: {result['before_kits']} -> {result['after_kits']}")
    print(f"Dinos no catálogo: {result['dino_count']}")
    print(f"Adicionados: {len(result['added'])}")

    for row in result["added"]:
        print(f"  + {row['item_id']} ({row['display_name']}) <- {row['match']}")
        print(f"    {row['beacon_path']}")

    if result["failed"]:
        print(f"Sem match Beacon ({len(result['failed'])}) — não inventados:")
        for row in result["failed"]:
            print(
                f"  ! {row['item_id']} ({row['display_name']}) mod={row['mod']} "
                f"registry_bp={row['registry_bp'][:70] if row['registry_bp'] else '(vazio)'}"
            )

    for cfg in CONFIGS:
        print(f"Gravado: {cfg}")


if __name__ == "__main__":
    main()
