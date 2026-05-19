"""
Migrador ArkShop → CustomShop
-------------------------------
Uso:
    python _migrate_arkshop.py <config_arkshop.json> <saida_customshop.json>

Exemplo:
    python _migrate_arkshop.py "C:/Users/Ciano/Documents/Nova pasta/config.json" "C:/saida/config.json"

O que é convertido
──────────────────
  ShopItems  → Items    (item único por entrada; bundles viram Kits)
  Kits       → Kits     (Items + Dinos + Commands preservados)

O que é ignorado / anotado
──────────────────────────
  Mysql, General, SellItems, Messages   → não existem no CustomShop
  Kit.Permissions                       → sem suporte, será ignorado
  Kit.Dinos                             → Dinos (Level, ForceTame, Neutered)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


# ── helpers ─────────────────────────────────────────────────────────────────

def strip_bp(bp: str) -> str:
    """Remove o wrapper Blueprint'...' e retorna só o path."""
    m = re.match(r"Blueprint'([^']+)'", bp.strip())
    return m.group(1) if m else bp.strip()


def convert_item_entry(entry: dict) -> dict:
    """Converte um item de kit/shop do formato ArkShop → CustomShop."""
    return {
        "Blueprint":      strip_bp(entry.get("Blueprint", "")),
        "Quantity":       entry.get("Amount", 1),
        "Quality":        float(entry.get("Quality", 0)),
        "ForceBlueprint": entry.get("ForceBlueprint", False),
    }


def convert_commands(cmds: list) -> list:
    """Mantém Commands como lista de strings (comando bruto)."""
    result = []
    for c in cmds:
        if isinstance(c, dict):
            cmd = c.get("Command", "")
            if cmd:
                result.append(cmd)
        elif isinstance(c, str):
            result.append(c)
    return result


# ── conversão de ShopItems ───────────────────────────────────────────────────

def migrate_shop_items(shop_items: dict) -> tuple[dict, dict]:
    """
    Retorna (items_customshop, kits_extras).
    Itens com 1 blueprint → Items.
    Itens com vários blueprints (bundles) → Kits.
    Itens do tipo 'command' → ignorados (sem suporte).
    """
    items: dict = {}
    kits_extra: dict = {}
    skipped: list[str] = []

    for key, val in shop_items.items():
        tipo = val.get("Type", "item")
        desc = val.get("Description", key)
        price = val.get("Price", 0)
        sub_items = [i for i in val.get("Items", []) if "Blueprint" in i]

        if tipo == "command":
            skipped.append(f"  IGNORADO (type=command): {key}")
            continue

        if len(sub_items) == 1:
            # Item simples → Items do CustomShop
            entry = sub_items[0]
            items[key] = {
                "Type":           "item",
                "Price":          price,
                "Description":    desc,
                "Blueprint":      strip_bp(entry.get("Blueprint", "")),
                "Quantity":       entry.get("Amount", 1),
                "Quality":        float(entry.get("Quality", 0)),
                "ForceBlueprint": entry.get("ForceBlueprint", False),
            }
        elif len(sub_items) > 1:
            # Bundle → Kit
            kits_extra[key] = {
                "Price":         price,
                "Description":   desc,
                "DefaultAmount": 1,
                "Items":         [convert_item_entry(i) for i in sub_items],
                "Commands":      [],
            }
        else:
            skipped.append(f"  IGNORADO (sem Items com Blueprint): {key}")

    if skipped:
        print("\n[ShopItems ignorados]")
        for s in skipped:
            print(s)

    return items, kits_extra


# ── conversão de Kits ────────────────────────────────────────────────────────

def convert_dino_entry(entry: dict) -> dict:
    """Converte uma entrada de dino do formato ArkShop → CustomShop."""
    return {
        "Blueprint": strip_bp(entry.get("Blueprint", "")),
        "Level":     entry.get("Level", 150),
        "ForceTame": entry.get("ForceTame", True),
        "Neutered":  entry.get("Neutered", False),
    }


def migrate_kits(kits: dict) -> dict:
    result: dict = {}

    for key, val in kits.items():
        desc  = val.get("Description", key)
        price = val.get("Price", 0)
        default_amount = val.get("DefaultAmount", 1)
        sub_items = [i for i in val.get("Items", []) if "Blueprint" in i]
        dinos     = val.get("Dinos", [])
        cmds      = val.get("Commands", [])

        kit: dict = {
            "Price":         price,
            "Description":   desc,
            "DefaultAmount": default_amount,
            "Items":         [convert_item_entry(i) for i in sub_items],
            "Commands":      convert_commands(cmds),
        }

        if dinos:
            kit["Dinos"] = [convert_dino_entry(d) for d in dinos]
            print(f"  Kit '{key}': {len(dinos)} dino(s) convertido(s)")

        result[key] = kit

    return result


# ── main ─────────────────────────────────────────────────────────────────────

def migrate(src: Path, dst: Path) -> None:
    print(f"Lendo:   {src}")
    with open(src, encoding="utf-8") as f:
        ark = json.load(f)

    shop_items_raw = ark.get("ShopItems", {})
    kits_raw       = ark.get("Kits", {})

    print(f"\nEncontrado: {len(shop_items_raw)} ShopItems | {len(kits_raw)} Kits")

    items, kits_from_bundles = migrate_shop_items(shop_items_raw)
    kits                     = migrate_kits(kits_raw)

    # Bundles de ShopItems entram como Kits (prefixo "shop_" para não colidir)
    for k, v in kits_from_bundles.items():
        kit_key = f"shop_{k}" if k in kits else k
        kits[kit_key] = v

    output = {
        "Settings": {
            "ShopName":           "ARKLAND Shop",
            "UiKey":              "F3",
            "StartingPoints":     100,
            "DisableSellButton":  True,
            "DisableTradeButton": False,
        },
        "Database": {
            "Host":     ark.get("Mysql", {}).get("MysqlHost", "127.0.0.1"),
            "Port":     ark.get("Mysql", {}).get("MysqlPort", 3306),
            "User":     ark.get("Mysql", {}).get("MysqlUser", "arkland"),
            "Password": ark.get("Mysql", {}).get("MysqlPass", ""),
            "Database": ark.get("Mysql", {}).get("MysqlDB", "arkland_shop"),
        },
        "Items": items,
        "Kits":  kits,
    }

    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nResultado:")
    print(f"  Items   : {len(items)}")
    print(f"  Kits    : {len(kits)}")
    print(f"\nSalvo em: {dst}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    migrate(Path(sys.argv[1]), Path(sys.argv[2]))
