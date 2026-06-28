#!/usr/bin/env python3
"""Sincroniza criaturas e itens de mods no catálogo CustomShop usando paths verificados.

Prioridade de blueprint (nunca inventar /Game/Mods/...):
1. Beacon cache (creatureId / engramId + path)
2. mod_catalog_verified.json (spawn codes oficiais Steam, paths de kits em producao)
3. market_species_defaults.json + ark_species_registry.json
4. Falha com log — sem path adivinhado
"""
from __future__ import annotations

import json
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
VERIFIED = WEB / "data" / "mod_catalog_verified.json"
SHOP_LEVEL_COMMERCE = 200
FULL_CATALOG_ITEM_MIN = 200
FULL_CATALOG_KIT_MIN = 25
FUZZY_THRESHOLD = 0.88


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _load_beacon_index() -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    """Retorna (label_index -> path, path_index -> entry)."""
    client = BeaconBlueprintClient()
    try:
        client.ensure_loaded(force=False)
    except Exception:
        pass
    if not client.is_loaded() and _CACHE_FILE.is_file():
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        bps = data.get("blueprints") or []
        if isinstance(bps, list) and bps:
            client._blueprints = bps  # noqa: SLF001
            client._loaded = True

    label_index: dict[str, str] = {}
    path_index: dict[str, dict[str, Any]] = {}
    if not client.is_loaded():
        return label_index, path_index

    for entry in client._blueprints:  # noqa: SLF001
        path = str(entry.get("path") or "").strip()
        if not path:
            continue
        if not (entry.get("creatureId") or entry.get("engramId")):
            continue
        path_index[path] = entry
        for field in ("label", "alternateLabel"):
            label = str(entry.get(field) or "").strip()
            key = _norm(label)
            if key and key not in label_index:
                label_index[key] = path
        class_str = str(entry.get("classString") or "")
        m = re.match(r"([A-Za-z0-9_]+)_Character_BP", class_str)
        if m:
            token = _norm(m.group(1).replace("_", " "))
            if token and token not in label_index:
                label_index[token] = path
    return label_index, path_index


def _beacon_match_path(
    display_name: str,
    species_key: str,
    label_index: dict[str, str],
) -> tuple[str | None, str]:
    candidates = [_norm(display_name), _norm(species_key.replace("_", " ")), _norm(species_key)]
    for cand in candidates:
        if cand and cand in label_index:
            return label_index[cand], f"beacon_exact:{cand}"
    best_path = ""
    best_label = ""
    best_score = 0.0
    for cand in candidates:
        if not cand:
            continue
        for label_norm, path in label_index.items():
            score = SequenceMatcher(None, cand, label_norm).ratio()
            if score > best_score:
                best_score = score
                best_path = path
                best_label = label_norm
    if best_path and best_score >= FUZZY_THRESHOLD:
        return best_path, f"beacon_fuzzy:{best_label}:{best_score:.2f}"
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


def _registry_targets() -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    seen: set[str] = set()

    for defn in load_defaults_file().get("species") or []:
        bp = str(defn.get("blueprint_path") or "").strip()
        if not bp or not is_cryopodable_dino_blueprint(bp):
            continue
        sk = str(defn.get("species_key") or "").strip()
        if not sk or sk in seen:
            continue
        seen.add(sk)
        mod = str(defn.get("mod_source") or "vanilla")
        price = int(defn.get("root_value") or 0)
        for item_id in _catalog_ids(defn):
            targets.append(
                {
                    "item_id": item_id,
                    "display_name": str(defn.get("display_name") or item_id),
                    "mod": mod,
                    "type": "dino",
                    "level": SHOP_LEVEL_COMMERCE,
                    "price": price,
                    "category": "Comercio",
                    "registry_bp": bp,
                    "source_hint": "market_species_defaults",
                }
            )

    for entry in load_registry_overlay_raw():
        if not registry_entry_is_commerce_dino(entry):
            continue
        sk = str(entry.get("species_key") or "").strip()
        if not sk or sk in seen:
            continue
        seen.add(sk)
        paths = [str(p).strip() for p in (entry.get("blueprint_paths") or []) if str(p).strip()]
        registry_bp = next((p for p in paths if is_cryopodable_dino_blueprint(p)), "")
        item_id = str(entry.get("catalog_item_id") or sk)
        targets.append(
            {
                "item_id": item_id,
                "display_name": str(entry.get("display_name") or item_id),
                "mod": str(entry.get("mod") or "overlay").lower(),
                "type": "dino",
                "level": 1 if str(entry.get("mod") or "").lower() == "abyss" else SHOP_LEVEL_COMMERCE,
                "price": int(entry.get("root_value") or 0),
                "category": "Abyss" if str(entry.get("mod") or "").lower() == "abyss" else "Comercio",
                "registry_bp": registry_bp,
                "source_hint": "ark_species_registry",
            }
        )
    return targets


def _verified_targets() -> list[dict[str, Any]]:
    if not VERIFIED.is_file():
        return []
    data = json.loads(VERIFIED.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    for entry in data.get("entries") or []:
        if not isinstance(entry, dict) or not entry.get("item_id"):
            continue
        out.append(
            {
                "item_id": str(entry["item_id"]),
                "display_name": str(entry.get("display_name") or entry["item_id"]),
                "mod": str(entry.get("mod") or ""),
                "type": str(entry.get("type") or "item").lower(),
                "level": int(entry.get("level") or SHOP_LEVEL_COMMERCE),
                "price": int(entry.get("price") or 0),
                "category": str(entry.get("category") or "Geral"),
                "registry_bp": str(entry.get("blueprint_path") or ""),
                "source_hint": str(entry.get("source") or "mod_catalog_verified"),
            }
        )
    return out


def _resolve_blueprint(
    target: dict[str, Any],
    label_index: dict[str, str],
    path_index: dict[str, dict[str, Any]],
) -> tuple[str | None, str]:
    registry_bp = str(target.get("registry_bp") or "").strip()
    if registry_bp:
        if registry_bp in path_index:
            return registry_bp, "beacon_path_match"
        return registry_bp, target.get("source_hint") or "registry"

    bp, info = _beacon_match_path(
        target["display_name"],
        target.get("item_id", ""),
        label_index,
    )
    if bp:
        return bp, info
    return None, ""


def _dino_entry(name: str, bp: str, price: int, level: int, category: str) -> dict[str, Any]:
    return {
        "Type": "dino",
        "Price": price,
        "Category": category,
        "Name": name,
        "Description": f"{name} Nivel {level}",
        "Dinos": [
            {
                "Blueprint": bp,
                "Level": level,
                "ForceTame": True,
                "Neutered": False,
            }
        ],
    }


def _item_entry(name: str, bp: str, price: int, category: str) -> dict[str, Any]:
    return {
        "Type": "item",
        "Price": price,
        "Category": category,
        "Name": name,
        "Description": f"{name} (1x)",
        "Items": [{"Blueprint": bp, "Quantity": 1}],
    }


def _config_has_entry(items: dict[str, Any], item_id: str, entry_type: str) -> bool:
    entry = items.get(item_id)
    if not isinstance(entry, dict):
        return False
    if entry_type == "dino":
        return str(entry.get("Type") or "").lower() == "dino"
    return str(entry.get("Type") or "").lower() in ("item", "command")


def _assert_shrink_guard(before_items: int, before_kits: int, after_items: int, after_kits: int) -> None:
    if before_items >= FULL_CATALOG_ITEM_MIN and after_items < FULL_CATALOG_ITEM_MIN:
        raise RuntimeError(f"Guarda: itens {before_items} -> {after_items}")
    if before_kits >= FULL_CATALOG_KIT_MIN and after_kits < FULL_CATALOG_KIT_MIN:
        raise RuntimeError(f"Guarda: kits {before_kits} -> {after_kits}")


def _write_config(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sync_mod_catalog() -> dict[str, Any]:
    label_index, path_index = _load_beacon_index()
    targets_by_id: dict[str, dict[str, Any]] = {}
    for t in _registry_targets() + _verified_targets():
        targets_by_id.setdefault(t["item_id"], t)

    master = CONFIGS[0]
    data = json.loads(master.read_text(encoding="utf-8"))
    items = data.setdefault("Items", {})
    before_items, before_kits = catalog_entry_counts(data)

    added: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    skipped = 0
    by_mod: dict[str, int] = {}

    for item_id, target in sorted(targets_by_id.items()):
        entry_type = str(target.get("type") or "dino")
        if _config_has_entry(items, item_id, entry_type):
            skipped += 1
            continue

        bp, match_info = _resolve_blueprint(target, label_index, path_index)
        if not bp:
            failed.append(
                {
                    "item_id": item_id,
                    "display_name": target["display_name"],
                    "mod": target.get("mod") or "",
                    "reason": "sem blueprint verificado (Beacon/registry)",
                }
            )
            continue

        mod = str(target.get("mod") or "unknown")
        if entry_type == "dino":
            items[item_id] = _dino_entry(
                target["display_name"],
                bp,
                int(target.get("price") or 0),
                int(target.get("level") or SHOP_LEVEL_COMMERCE),
                str(target.get("category") or "Comercio"),
            )
        else:
            items[item_id] = _item_entry(
                target["display_name"],
                bp,
                int(target.get("price") or 0),
                str(target.get("category") or "Geral"),
            )
        added.append({"item_id": item_id, "mod": mod, "match": match_info, "path": bp})
        by_mod[mod] = by_mod.get(mod, 0) + 1

    apply_catalog_sync(data)
    after_items, after_kits = catalog_entry_counts(data)
    _assert_shrink_guard(before_items, before_kits, after_items, after_kits)

    dino_count = sum(
        1 for v in items.values() if isinstance(v, dict) and str(v.get("Type") or "").lower() == "dino"
    )

    for cfg in CONFIGS:
        _write_config(cfg, data)

    skipped_list: list[dict[str, str]] = []
    if VERIFIED.is_file():
        vdata = json.loads(VERIFIED.read_text(encoding="utf-8"))
        for row in vdata.get("skipped_no_verified_path") or []:
            if isinstance(row, dict):
                skipped_list.append(
                    {
                        "item_id": str(row.get("item_id") or ""),
                        "display_name": str(row.get("display_name") or ""),
                        "mod": str(row.get("mod") or ""),
                        "reason": str(row.get("reason") or ""),
                    }
                )

    return {
        "beacon_labels": len(label_index),
        "beacon_paths": len(path_index),
        "targets": len(targets_by_id),
        "skipped_existing": skipped,
        "added": added,
        "failed": failed + skipped_list,
        "by_mod": by_mod,
        "before_items": before_items,
        "after_items": after_items,
        "before_kits": before_kits,
        "after_kits": after_kits,
        "dino_count": dino_count,
    }


def main() -> None:
    print("==> Sync mod catalog (Beacon + paths verificados)")
    result = sync_mod_catalog()
    print(f"Beacon: {result['beacon_paths']} paths, {result['beacon_labels']} labels")
    print(f"Alvos: {result['targets']}, existentes: {result['skipped_existing']}")
    print(f"Itens: {result['before_items']} -> {result['after_items']}")
    print(f"Kits: {result['before_kits']} -> {result['after_kits']}")
    print(f"Dinos: {result['dino_count']}")
    print(f"Adicionados: {len(result['added'])}")
    for mod, n in sorted(result["by_mod"].items()):
        print(f"  [{mod}] +{n}")
    for row in result["added"]:
        print(f"  + {row['item_id']} ({row['mod']}) <- {row['match']}")
    if result["failed"]:
        print(f"Sem blueprint ({len(result['failed'])}):")
        for row in result["failed"]:
            print(f"  ! {row['item_id']} ({row.get('display_name','')}) mod={row.get('mod','')} - {row.get('reason','')}")
    for cfg in CONFIGS:
        print(f"Gravado: {cfg}")


if __name__ == "__main__":
    main()
