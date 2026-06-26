#!/usr/bin/env python3
"""Apply VIP and license-tier kit pricing (10% of license) to CustomShop config.json."""
from __future__ import annotations

import json
import math
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATHS = [
    ROOT / "plugin" / "CustomShop" / "configs" / "config.json",
    ROOT / "plugin" / "CustomShop" / "bin" / "config.json",
]

# Preços placeholder comuns em lojas ARK (bloqueio de compra)
PLACEHOLDER_PRICE_MIN = 1_000_000

# Licenças VIP — fonte de verdade para Items + preço de referência
VIP_LICENSES = {
    "licenca_vip_bronze": {
        "group": "VIPBronze",
        "name": "Licença VIP Bronze",
        "price": 3000,
        "brl": 20,
        "description": "Licença VIP Bronze (30 dias) — necessária para resgatar o Kit VIP Bronze",
    },
    "licenca_vip_prata": {
        "group": "VIPPrata",
        "name": "Licença VIP Prata",
        "price": 4500,
        "brl": 30,
        "description": "Licença VIP Prata (30 dias) — necessária para resgatar o Kit VIP Prata",
    },
    "licenca_vip_ouro": {
        "group": "VIPOuro",
        "name": "Licença VIP Ouro",
        "price": 7500,
        "brl": 50,
        "description": "Licença VIP Ouro (30 dias) — necessária para resgatar o Kit VIP Ouro",
    },
    "licenca_vip_diamante": {
        "group": "VIPDiamante",
        "name": "Licença VIP Diamante",
        "price": 11250,
        "brl": 75,
        "description": "Licença VIP Diamante (30 dias) — somente Âmbar; não disponível em doações PIX",
    },
}

# Kits VIP — mapeamento explícito (evita confundir ouro com licença Alfa)
KIT_TO_LICENSE: dict[str, str] = {
    "vip_bronze": "licenca_vip_bronze",
    "prata": "licenca_vip_prata",
    "ouro": "licenca_vip_ouro",
    "diamante": "licenca_vip_diamante",
}

TIER_KIT_SUFFIX_RE = re.compile(r"_(gama|gamma|beta|alfa)$", re.I)
TIER_SUFFIX_TO_LICENSE = {
    "gama": "licenca_gamma",
    "gamma": "licenca_gamma",
    "beta": "licenca_beta",
    "alfa": "licenca_alfa",
}

# Grupos que não têm item de licença no catálogo — não aplicar 10%
SKIP_PERMISSION_GROUPS = frozenset({"Admins", "Staff", "VIPDoacao", ""})

MARKUP = 1.5
MAJOR_STRUCT_COUNT = 5  # transmitter, soultraps, rig, generator, replicator

REPLICATOR_BP = (
    "/Game/Mods/StructuresPlusMod/Crafting/replicator/"
    "PrimalItemStructure_Replicatorplus.PrimalItemStructure_replicatorplus"
)


def _replicator_kit_item() -> dict:
    return {
        "Blueprint": REPLICATOR_BP,
        "Quantity": 1,
        "Quality": 0,
        "ForceBlueprint": False,
    }


def _ensure_replicator_in_vip_kits(kits: dict) -> None:
    """Garante Replicador S+ em todos os kits VIP (Bronze/Prata/Ouro/Diamante)."""
    entry = _replicator_kit_item()
    for kit_id in KIT_TO_LICENSE:
        kit = kits.get(kit_id)
        if not isinstance(kit, dict):
            continue
        items = kit.setdefault("Items", [])
        if not isinstance(items, list):
            continue
        if any("replicator" in str(i.get("Blueprint", "")).lower() for i in items if isinstance(i, dict)):
            continue
        insert_at = len(items)
        for idx, raw in enumerate(items):
            if not isinstance(raw, dict):
                continue
            bp = str(raw.get("Blueprint") or "").lower()
            if "generatortek" in bp or "generator_tek" in bp:
                insert_at = idx + 1
                break
        items.insert(insert_at, entry)


POINT_PACKAGES = [
    {"id": "p500", "label": "500 Âmbares", "points": 500, "price_brl": 5.0},
    {"id": "p1200", "label": "1.200 Âmbares", "points": 1200, "price_brl": 10.0},
    {"id": "p3000", "label": "3.000 Âmbares", "points": 3000, "price_brl": 20.0},
    {"id": "p8000", "label": "8.000 Âmbares", "points": 8000, "price_brl": 45.0},
    {
        "id": "p8250",
        "label": "8.250 Âmbares — Kit VIP Ouro",
        "points": 8250,
        "price_brl": 75.0,
        "note": "Suficiente para Licença VIP Ouro (7.500) + Kit Ouro (750). Apenas Âmbar — VIP Diamante não incluído.",
    },
]


def bundle_item_price(kit_price: int) -> int:
    return max(1, math.ceil(kit_price / MAJOR_STRUCT_COUNT * MARKUP))


def license_entry(spec: dict) -> dict:
    return {
        "Type": "license",
        "Category": "Licenças VIP",
        "Name": spec["name"],
        "Price": spec["price"],
        "Description": spec["description"],
        "LicenseGrant": {
            "Group": spec["group"],
            "Days": 30,
            "Redeemable": True,
        },
    }


def _fmt_amber(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _parse_permissions(raw: object) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        parts = [str(p).strip() for p in raw]
    else:
        parts = [p.strip() for p in str(raw).split(",")]
    return [p for p in parts if p]


def _license_meta(items: dict, license_key: str) -> dict | None:
    entry = items.get(license_key)
    if not isinstance(entry, dict):
        return None
    price = int(entry.get("Price") or 0)
    if price <= 0:
        return None
    grant = entry.get("LicenseGrant") or {}
    group = str(grant.get("Group") or "").strip()
    name = str(entry.get("Name") or license_key).strip()
    label = name.replace("Licença ", "").strip() or group or license_key
    return {"license_key": license_key, "price": price, "group": group, "label": label}


def _build_group_license_index(items: dict) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for key, entry in items.items():
        meta = _license_meta(items, str(key))
        if meta and meta["group"]:
            index[meta["group"]] = meta
    return index


def _kit_base_label(kit: dict, kit_id: str) -> str:
    desc = str(kit.get("Description") or kit_id).strip()
    if " — " in desc:
        desc = desc.split(" — ", 1)[0].strip()
    # Descrições legadas "Kit VIP X — ..." → manter nome curto
    if desc.lower().startswith("kit vip "):
        return desc
    return desc or kit_id


def _resolve_kit_license(kit_id: str, kit: dict, items: dict, by_group: dict[str, dict]) -> dict | None:
    """Determina qual licença governa o preço do kit."""
    if kit_id in KIT_TO_LICENSE:
        return _license_meta(items, KIT_TO_LICENSE[kit_id])

    vip = kit.get("VipLicense")
    if isinstance(vip, dict):
        tier = str(vip.get("Tier") or "").strip()
        if tier and tier in by_group:
            return by_group[tier]

    m = TIER_KIT_SUFFIX_RE.search(str(kit_id))
    if m:
        lic_key = TIER_SUFFIX_TO_LICENSE.get(m.group(1).lower())
        if lic_key:
            meta = _license_meta(items, lic_key)
            if meta:
                return meta

    for group in _parse_permissions(kit.get("Permissions")):
        if group in SKIP_PERMISSION_GROUPS:
            continue
        if group in by_group:
            return by_group[group]

    return None


def _kit_description(kit_id: str, kit: dict, kit_price: int, label: str) -> str:
    base = _kit_base_label(kit, kit_id)
    if kit_id in KIT_TO_LICENSE or base.lower().startswith("kit vip"):
        return (
            f"Kit VIP {label.replace('VIP ', '')} — {_fmt_amber(kit_price)} Âmbar (10% da licença). "
            f"Requer Licença {label}."
        )
    return (
        f"{base} — {_fmt_amber(kit_price)} Âmbar (10% da licença). "
        f"Requer Licença {label}."
    )


def _sanitize_placeholder_prices(kits: dict) -> list[str]:
    cleared: list[str] = []
    for kit_id, kit in kits.items():
        if not isinstance(kit, dict):
            continue
        price = int(kit.get("Price") or 0)
        if price >= PLACEHOLDER_PRICE_MIN or price == 1:
            # 1 e 99M são placeholders comuns; será recalculado se houver licença
            kit["Price"] = 0
            cleared.append(f"{kit_id}(was {price})")
    return cleared


def _apply_all_permission_kit_pricing(kits: dict, items: dict) -> list[str]:
    """Todos os kits com Permissions ou mapeamento explícito → 10% da licença."""
    by_group = _build_group_license_index(items)
    updated: list[str] = []

    for kit_id, kit in kits.items():
        if not isinstance(kit, dict):
            continue

        perms = _parse_permissions(kit.get("Permissions"))
        has_perms = any(p for p in perms if p not in SKIP_PERMISSION_GROUPS)
        is_mapped = kit_id in KIT_TO_LICENSE or TIER_KIT_SUFFIX_RE.search(str(kit_id))
        has_vip = isinstance(kit.get("VipLicense"), dict)

        if not (has_perms or is_mapped or has_vip):
            continue

        meta = _resolve_kit_license(kit_id, kit, items, by_group)
        if not meta:
            continue

        kit_price = meta["price"] // 10
        group = meta["group"]
        label = meta["label"]

        kit["Price"] = kit_price
        if group and group not in SKIP_PERMISSION_GROUPS:
            kit["Permissions"] = f"Admins,{group}"
        kit["Description"] = _kit_description(kit_id, kit, kit_price, label)
        updated.append(f"{kit_id}={kit_price}({group})")

    return updated


def apply(config_path: Path) -> tuple[list[str], list[str]]:
    data = json.loads(config_path.read_text(encoding="utf-8"))
    items = data.setdefault("Items", {})
    kits = data.setdefault("Kits", {})

    for key, spec in VIP_LICENSES.items():
        items[key] = license_entry(spec)

    cleared = _sanitize_placeholder_prices(kits)
    kit_updates = _apply_all_permission_kit_pricing(kits, items)

    # Standalone premium structures
    if "struct_tekforge" in items:
        items["struct_tekforge"]["Price"] = 50000
        items["struct_tekforge"]["Category"] = items["struct_tekforge"].get("Category") or "Ferramentas"
    if "struct_tekreplicator" in items:
        items["struct_tekreplicator"]["Price"] = 52500
        items["struct_tekreplicator"]["Category"] = items["struct_tekreplicator"].get("Category") or "Ferramentas"
        rep_items = items["struct_tekreplicator"].get("Items") or []
        if rep_items and isinstance(rep_items[0], dict):
            rep_items[0]["Blueprint"] = REPLICATOR_BP

    bronze_kit = VIP_LICENSES["licenca_vip_bronze"]["price"] // 10
    indiv_price = bundle_item_price(bronze_kit)

    vip_individuals = {
        "struct_transmitter": {
            "Type": "item",
            "Category": "Ferramentas",
            "Price": indiv_price,
            "Permissions": "Admins,VIPBronze",
            "Description": f"Transmissor S+ (1x) — {indiv_price:,} Âmbar; kit VIP Bronze é melhor custo-benefício".replace(",", "."),
            "Items": [
                {
                    "Blueprint": "/Game/Mods/StructuresPlusMod/Misc/Transmitter/PrimalItemStructure_TransmitterPlus.PrimalItemStructure_TransmitterPlus",
                    "Quantity": 1,
                    "Quality": 0,
                    "ForceBlueprint": False,
                }
            ],
        },
        "struct_generatortek": {
            "Type": "item",
            "Category": "Ferramentas",
            "Price": indiv_price,
            "Permissions": "Admins,VIPBronze",
            "Description": f"Gerador Tek S+ (1x) — {indiv_price:,} Âmbar; kit VIP Bronze é melhor custo-benefício".replace(",", "."),
            "Items": [
                {
                    "Blueprint": "/Game/Mods/StructuresPlusMod/Misc/GeneratorTek/PrimalItemStructure_GeneratorTek.PrimalItemStructure_GeneratorTek",
                    "Quantity": 1,
                    "Quality": 0,
                    "ForceBlueprint": False,
                }
            ],
        },
        "item_soultraps_20": {
            "Type": "item",
            "Category": "Ferramentas",
            "Price": indiv_price,
            "Permissions": "Admins,VIPBronze",
            "Description": f"Soul Traps DinoStorage (20x) — {indiv_price:,} Âmbar; kit VIP Bronze é melhor custo-benefício".replace(",", "."),
            "Items": [
                {
                    "Blueprint": "/Game/Mods/DinoStorage2/SoulTraps_DS.SoulTraps_DS",
                    "Quantity": 20,
                    "Quality": 0,
                    "ForceBlueprint": False,
                }
            ],
        },
        "struct_tekreplicator_vip": {
            "Type": "item",
            "Category": "Ferramentas",
            "Name": "Replicador S+",
            "Price": indiv_price,
            "Permissions": "Admins,VIPBronze",
            "Description": f"Replicador S+ VIP (1x) — {indiv_price:,} Âmbar; kit VIP Bronze é melhor custo-benefício. Avulso premium: struct_tekreplicator (52.500).".replace(",", "."),
            "Items": [_replicator_kit_item()],
        },
    }
    for key, entry in vip_individuals.items():
        items[key] = entry

    _ensure_replicator_in_vip_kits(kits)

    if "stryder_rig" in items:
        items["stryder_rig"]["Price"] = indiv_price
        items["stryder_rig"]["Permissions"] = "Admins,VIPBronze"
        items["stryder_rig"]["Category"] = items["stryder_rig"].get("Category") or "Ferramentas"
        items["stryder_rig"]["Description"] = (
            f"Swappable Stryder Rig (1x) — {indiv_price:,} Âmbar; kit VIP Bronze é melhor custo-benefício"
        ).replace(",", ".")

    data["PointPackages"] = POINT_PACKAGES

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
