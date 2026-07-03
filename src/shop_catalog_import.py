"""Conversão de catálogo ArkShop → formato CustomShop (config.json)."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, Tuple

_BP_RE = re.compile(r"^Blueprint'(.+)'$")
_GAME_BP_RE = re.compile(r"(/Game/[^\s\"',]+)")

# Caminhos comuns copiados errado do ArkShop (pasta Resources vs Consumables).
_KNOWN_BLUEPRINT_FIXES: dict[str, str] = {
    "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemConsumable_RawMeat.PrimalItemConsumable_RawMeat": (
        "/Game/PrimalEarth/CoreBlueprints/Items/Consumables/"
        "PrimalItemConsumable_RawMeat.PrimalItemConsumable_RawMeat"
    ),
}


def normalize_blueprint(value: str) -> str:
    """ArkShop: Blueprint'/Game/...' → /Game/...; corrige fragmentos JSON malformados."""
    if not value:
        return ""
    text = value.strip()
    m = _BP_RE.match(text)
    if m:
        return m.group(1)
    if text.startswith("{") or text.startswith('"Blueprint"'):
        try:
            blob = text if text.startswith("{") else "{" + text + "}"
            parsed = json.loads(blob)
            if isinstance(parsed, dict):
                return normalize_blueprint(str(parsed.get("Blueprint") or ""))
        except json.JSONDecodeError:
            pass
    game = _GAME_BP_RE.search(text)
    if game:
        path = game.group(1).rstrip("\"',")
        return _KNOWN_BLUEPRINT_FIXES.get(path, path)
    return _KNOWN_BLUEPRINT_FIXES.get(text, text)


def _copy_item_stat_fields(entry: dict, out: dict) -> None:
    """Preserva stats opcionais de item (compatível com ArkShop)."""
    for key in ("Damage", "Durability", "Armor"):
        if key not in entry or entry[key] in (None, ""):
            continue
        try:
            val = float(entry[key])
        except (TypeError, ValueError):
            continue
        if val > 0:
            out[key] = val


def _normalize_item_entry(entry: dict | str) -> dict:
    if isinstance(entry, str):
        bp = normalize_blueprint(entry)
        return {"Blueprint": bp, "Quantity": 1} if bp else {}
    out: dict[str, Any] = {}
    if "Blueprint" in entry:
        out["Blueprint"] = normalize_blueprint(str(entry["Blueprint"]))
    qty = entry.get("Quantity", entry.get("Amount", 1))
    out["Quantity"] = int(qty) if qty is not None else 1
    for key in ("Quality", "ForceBlueprint"):
        if key in entry:
            out[key] = entry[key]
    _copy_item_stat_fields(entry, out)
    return out


def _normalize_dino_entry(entry: dict) -> dict:
    out: dict[str, Any] = {
        "Blueprint": normalize_blueprint(str(entry.get("Blueprint", ""))),
        "Level": int(entry.get("Level", 150)),
        "ForceTame": bool(entry.get("ForceTame", True)),
        "Neutered": bool(entry.get("Neutered", False)),
    }
    if "Gender" in entry:
        out["Gender"] = entry["Gender"]
    return out


def _commands_from_arkshop(raw: dict) -> list[str]:
    cmds: list[str] = []
    for entry in raw.get("Items", []):
        cmd = entry.get("Command")
        if not cmd:
            continue
        cmds.append(
            str(cmd).replace("{steamid}", "{SteamID}").replace("{SteamID}", "{SteamID}")
        )
    for entry in raw.get("Commands", []):
        if isinstance(entry, str):
            cmds.append(entry.replace("{steamid}", "{SteamID}"))
    return cmds


def convert_shop_item(key: str, raw: dict) -> dict:
    """Converte um ShopItem/Item ArkShop para CustomShop."""
    item_type = str(raw.get("Type", "item")).lower()
    out: dict[str, Any] = {
        "Type": item_type,
        "Price": int(raw.get("Price", 0)),
        "Description": str(raw.get("Description", key)),
    }

    if item_type == "dino":
        if raw.get("Dinos"):
            out["Dinos"] = [_normalize_dino_entry(d) for d in raw["Dinos"]]
        elif raw.get("Blueprint"):
            dino = _normalize_dino_entry(raw)
            out["Dinos"] = [dino]
        return out

    if item_type == "command":
        cmds = _commands_from_arkshop(raw)
        if cmds:
            out["Commands"] = cmds
        return out

    if raw.get("Items"):
        out["Items"] = [
            e for e in (_normalize_item_entry(x) for x in raw["Items"])
            if e.get("Blueprint")
        ]
    elif raw.get("Blueprint"):
        out["Blueprint"] = normalize_blueprint(str(raw["Blueprint"]))
        out["Quantity"] = int(raw.get("Quantity", raw.get("Amount", 1)))
        for key in ("Quality", "ForceBlueprint"):
            if key in raw:
                out[key] = raw[key]
        _copy_item_stat_fields(raw, out)

    return out


def convert_kit(key: str, raw: dict) -> dict:
    """Converte um Kit ArkShop para CustomShop."""
    out: dict[str, Any] = {
        "Price": int(raw.get("Price", 0)),
        "Description": str(raw.get("Description", key)),
    }
    if "DefaultAmount" in raw:
        out["DefaultAmount"] = int(raw["DefaultAmount"])
    if raw.get("Permissions"):
        out["Permissions"] = str(raw["Permissions"])
    if raw.get("Items"):
        out["Items"] = [
            e for e in (_normalize_item_entry(x) for x in raw["Items"])
            if e.get("Blueprint")
        ]
    if raw.get("Dinos"):
        out["Dinos"] = [_normalize_dino_entry(d) for d in raw["Dinos"]]
    cmds = _commands_from_arkshop(raw)
    if cmds:
        out["Commands"] = cmds
    return out


def detect_format(raw: dict) -> str:
    if "ShopItems" in raw or ("Mysql" in raw and "General" in raw):
        return "arkshop"
    if "Items" in raw or "Kits" in raw:
        return "customshop"
    return "unknown"


def extract_catalog(raw: dict) -> Tuple[dict, dict, dict | None]:
    """Retorna (items, kits, timed_points_reward|None) no formato CustomShop."""
    fmt = detect_format(raw)
    items_src = raw.get("ShopItems") or raw.get("Items") or {}
    kits_src = raw.get("Kits") or {}

    items = {k: convert_shop_item(k, v) for k, v in items_src.items() if isinstance(v, dict)}
    kits = {k: convert_kit(k, v) for k, v in kits_src.items() if isinstance(v, dict)}

    timed: dict | None = None
    if fmt == "arkshop":
        general = raw.get("General") or {}
        if isinstance(general.get("TimedPointsReward"), dict):
            timed = copy.deepcopy(general["TimedPointsReward"])
    elif isinstance(raw.get("TimedPointsReward"), dict):
        timed = copy.deepcopy(raw["TimedPointsReward"])

    # Normaliza blueprints em catálogo já CustomShop (re-importação)
    if fmt == "customshop":
        for itm in items.values():
            if itm.get("Blueprint"):
                itm["Blueprint"] = normalize_blueprint(str(itm["Blueprint"]))
            if itm.get("Items"):
                itm["Items"] = [
                    e for e in (_normalize_item_entry(x) for x in itm["Items"])
                    if e.get("Blueprint")
                ]
            if itm.get("Dinos"):
                itm["Dinos"] = [_normalize_dino_entry(d) for d in itm["Dinos"]]
        for kit in kits.values():
            if kit.get("Items"):
                kit["Items"] = [
                    e for e in (_normalize_item_entry(x) for x in kit["Items"])
                    if e.get("Blueprint")
                ]
            if kit.get("Dinos"):
                kit["Dinos"] = [_normalize_dino_entry(d) for d in kit["Dinos"]]

    return items, kits, timed


def sanitize_catalog_blueprints(data: dict[str, Any]) -> None:
    """Normaliza Blueprints em Items/Kits (in-place). Corrige entradas malformadas."""
    items = data.get("Items") or data.get("ShopItems") or {}
    if isinstance(items, dict):
        for itm in items.values():
            if not isinstance(itm, dict):
                continue
            if itm.get("Blueprint"):
                itm["Blueprint"] = normalize_blueprint(str(itm["Blueprint"]))
            if itm.get("Items"):
                itm["Items"] = [
                    e for e in (_normalize_item_entry(x) for x in itm["Items"])
                    if e.get("Blueprint")
                ]
    kits = data.get("Kits") or {}
    if isinstance(kits, dict):
        for kit in kits.values():
            if not isinstance(kit, dict) or not kit.get("Items"):
                continue
            kit["Items"] = [
                e for e in (_normalize_item_entry(x) for x in kit["Items"])
                if e.get("Blueprint")
            ]


def apply_catalog_to_target(
    target: dict,
    items: dict,
    kits: dict,
    timed: dict | None = None,
    *,
    merge: bool = True,
    import_timed: bool = False,
) -> dict[str, int]:
    """Mescla catálogo convertido em `target` (config CustomShop in-place)."""
    stats = {"items_added": 0, "kits_added": 0, "items_skipped": 0, "kits_skipped": 0}

    tgt_items = target.setdefault("Items", {})
    tgt_kits = target.setdefault("Kits", {})

    if not merge:
        tgt_items.clear()
        tgt_kits.clear()

    for key, itm in items.items():
        if merge and key in tgt_items:
            stats["items_skipped"] += 1
        tgt_items[key] = itm
        stats["items_added"] += 1

    for key, kit in kits.items():
        if merge and key in tgt_kits:
            stats["kits_skipped"] += 1
        tgt_kits[key] = kit
        stats["kits_added"] += 1

    if import_timed and timed is not None:
        target["TimedPointsReward"] = timed

    return stats


def restore_backup_catalog(backup: dict, template: dict) -> dict[str, Any]:
    """Restaura catálogo completo do backup preservando Settings/Database do usuário.

    Items, Kits, Downloads e TimedPointsReward vêm do backup (substituição total).
    Settings mescla defaults do template com valores do backup (backup vence).
    Database usa credenciais do backup, mantendo metadados (_comment) do template.
    CrossChat e demais seções estruturais permanecem do template.
    """
    out = copy.deepcopy(template)

    for key in ("Items", "Kits", "Downloads"):
        if key in backup:
            out[key] = copy.deepcopy(backup[key])
    if isinstance(backup.get("TimedPointsReward"), dict):
        out["TimedPointsReward"] = copy.deepcopy(backup["TimedPointsReward"])

    tmpl_settings = copy.deepcopy(template.get("Settings") or {})
    backup_settings = backup.get("Settings") or {}
    out["Settings"] = {**tmpl_settings, **backup_settings}

    if isinstance(backup.get("Database"), dict):
        db = copy.deepcopy(template.get("Database") or {})
        db.update(backup["Database"])
        out["Database"] = db

    if "_comment" in template:
        out["_comment"] = template["_comment"]

    return out


def import_catalog_from_file(
    source_path: str | Path,
    target: dict,
    *,
    merge: bool = True,
    import_timed: bool = False,
) -> dict[str, Any]:
    """Lê JSON (ArkShop ou CustomShop) e aplica ao `target`."""
    path = Path(source_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    items, kits, timed = extract_catalog(raw)
    stats = apply_catalog_to_target(
        target, items, kits, timed, merge=merge, import_timed=import_timed,
    )
    return {
        "source": str(path),
        "format": detect_format(raw),
        "items_total": len(items),
        "kits_total": len(kits),
        **stats,
    }
