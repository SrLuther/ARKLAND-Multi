"""Manutenção do catálogo no sync TEK — placeholders, tiers licenciados, purge de entradas obsoletas."""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

PLACEHOLDER_PRICE_MIN = 1_000_000

# Grupos Permissions.dll descontinuados no cluster (prefixo no JSON legado).
_REMOVED_GROUP_PREFIX = "VIP"

TIER_KIT_SUFFIX_RE = re.compile(r"_(gama|gamma|beta|alfa)$", re.I)
TIER_SUFFIX_TO_LICENSE = {
    "gama": "licenca_gamma",
    "gamma": "licenca_gamma",
    "beta": "licenca_beta",
    "alfa": "licenca_alfa",
}

SKIP_PERMISSION_GROUPS = frozenset({"Admins", "Staff", ""})

REPLICATOR_BP = (
    "/Game/Mods/StructuresPlusMod/Crafting/replicator/"
    "PrimalItemStructure_Replicatorplus.PrimalItemStructure_replicatorplus"
)

POINT_PACKAGES = [
    {"id": "p10000", "label": "10.000 Âmbares", "points": 10000, "price_brl": 5.0, "note": "Primeiro passo — ideal para conhecer a loja"},
    {"id": "p20500", "label": "20.500 Âmbares", "points": 20500, "price_brl": 10.0, "note": "+2,5% bônus vs pacote inicial"},
    {"id": "p42000", "label": "42.000 Âmbares", "points": 42000, "price_brl": 20.0, "note": "+5% bônus — dobro com vantagem"},
    {"id": "p75000", "label": "75.000 Âmbares", "points": 75000, "price_brl": 35.0, "note": "Melhor custo-benefício entre R$ 20 e R$ 50"},
    {"id": "p110000", "label": "110.000 Âmbares", "points": 110000, "price_brl": 50.0, "note": "Pacote popular — equilíbrio ideal"},
    {"id": "p170000", "label": "170.000 Âmbares", "points": 170000, "price_brl": 75.0, "note": "+13% bônus vs pacote de R$ 50"},
    {"id": "p230000", "label": "230.000 Âmbares", "points": 230000, "price_brl": 100.0, "note": "Impulsione seu progresso no cluster"},
    {"id": "p625000", "label": "625.000 Âmbares", "points": 625000, "price_brl": 250.0, "note": "+25% bônus — apoio premium ao servidor"},
    {"id": "p1300000", "label": "1.300.000 Âmbares", "points": 1300000, "price_brl": 500.0, "note": "Melhor valor por Âmbar acima de R$ 250"},
    {"id": "p2700000", "label": "2.700.000 Âmbares", "points": 2700000, "price_brl": 1000.0, "note": "+35% bônus — máximo incentivo ARKLAND"},
]


def _parse_permissions(raw: object) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        parts = [str(p).strip() for p in raw]
    else:
        parts = [p.strip() for p in str(raw).split(",")]
    return [p for p in parts if p]


def _is_removed_group(name: str) -> bool:
    return bool(name) and name.upper().startswith(_REMOVED_GROUP_PREFIX)


def _is_retired_item(item_id: str, item: dict[str, Any]) -> bool:
    key = item_id.lower()
    if key.startswith("licenca_vip") or "_vip" in key:
        return True
    grant = item.get("LicenseGrant") or {}
    return _is_removed_group(str(grant.get("Group") or ""))


def _is_retired_kit(kit_id: str, kit: dict[str, Any]) -> bool:
    if kit_id.lower().startswith("vip"):
        return True
    if isinstance(kit.get("VipLicense"), dict):
        return True
    return any(_is_removed_group(p) for p in _parse_permissions(kit.get("Permissions")))


def _purge_retired_entries(data: dict[str, Any]) -> list[str]:
    """Remove itens/kits obsoletos ainda presentes em config.json legado."""
    removed: list[str] = []
    items: dict[str, Any] = data.setdefault("Items", {})
    kits: dict[str, Any] = data.setdefault("Kits", {})

    for key in list(items.keys()):
        entry = items.get(key)
        if isinstance(entry, dict) and _is_retired_item(str(key), entry):
            del items[key]
            removed.append(f"item:{key}")

    for key in list(kits.keys()):
        entry = kits.get(key)
        if isinstance(entry, dict) and _is_retired_kit(str(key), entry):
            del kits[key]
            removed.append(f"kit:{key}")

    return removed


def normalize_timed_points_reward_groups(data: dict[str, Any]) -> list[str]:
    """Remove grupos VIP obsoletos e normaliza aliases Mod/MOD → Moderacao em TimedPointsReward."""
    return _purge_timed_points_groups(data)


def _purge_timed_points_groups(data: dict[str, Any]) -> list[str]:
    """Remove grupos VIP obsoletos e normaliza aliases do cargo MOD em TimedPointsReward."""
    timed = data.get("TimedPointsReward")
    if not isinstance(timed, dict):
        return []
    groups = timed.get("Groups")
    if not isinstance(groups, dict):
        return []
    notes: list[str] = []
    mod_aliases = frozenset({"Mod", "MOD"})
    for key in list(groups.keys()):
        name = str(key).strip()
        if _is_removed_group(name):
            del groups[key]
            notes.append(f"timed:{name}")
        elif name in mod_aliases:
            entry = groups.pop(key)
            if "Moderacao" not in groups:
                groups["Moderacao"] = entry
            notes.append(f"timed:{name}->Moderacao")
    return notes


def _fmt_amber(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _license_meta(items: dict[str, Any], license_key: str) -> dict[str, Any] | None:
    entry = items.get(license_key)
    if not isinstance(entry, dict):
        return None
    price = int(entry.get("Price") or 0)
    if price <= 0:
        return None
    grant = entry.get("LicenseGrant") or {}
    group = str(grant.get("Group") or "").strip()
    if _is_removed_group(group):
        return None
    name = str(entry.get("Name") or license_key).strip()
    label = name.replace("Licença ", "").strip() or group or license_key
    return {"license_key": license_key, "price": price, "group": group, "label": label}


def _build_group_license_index(items: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for key, entry in items.items():
        meta = _license_meta(items, str(key))
        if meta and meta["group"]:
            index[meta["group"]] = meta
    return index


def _kit_base_label(kit: dict[str, Any], kit_id: str) -> str:
    desc = str(kit.get("Description") or kit_id).strip()
    if " — " in desc:
        desc = desc.split(" — ", 1)[0].strip()
    return desc or kit_id


def _resolve_kit_license(
    kit_id: str,
    kit: dict[str, Any],
    items: dict[str, Any],
    by_group: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    m = TIER_KIT_SUFFIX_RE.search(str(kit_id))
    if m:
        lic_key = TIER_SUFFIX_TO_LICENSE.get(m.group(1).lower())
        if lic_key:
            meta = _license_meta(items, lic_key)
            if meta:
                return meta

    for group in _parse_permissions(kit.get("Permissions")):
        if group in SKIP_PERMISSION_GROUPS or _is_removed_group(group):
            continue
        if group in by_group:
            return by_group[group]

    return None


SIMPLE_LICENSE_KIT_IDS = frozenset({"kit_gamma", "kit_beta", "kit_alfa"})


def _short_kit_title(kit_id: str, kit: dict[str, Any], label: str) -> str:
    """Título curto para UI — sem preço, % de licença ou marketing."""
    kid = str(kit_id)
    if kid in SIMPLE_LICENSE_KIT_IDS:
        return f"KIT {label.upper()}"
    if kid.startswith("kit_itensalfa_armas_"):
        tier = kid[len("kit_itensalfa_armas_") :].replace("_", " ").upper()
        return f"KIT ARMAS {tier}"
    if kid.startswith("kit_itensalfa_ferramentas_"):
        tier = kid[len("kit_itensalfa_ferramentas_") :].replace("_", " ").upper()
        return f"KIT FERRAMENTAS {tier}"
    if kid.startswith("kit_itensalfa_"):
        tier = kid[len("kit_itensalfa_") :].replace("_", " ").upper()
        return f"KIT ITENSALFA {tier}"
    base = _kit_base_label(kit, kid)
    # Evita reintroduzir poluição se Description já veio suja
    if any(m in base.lower() for m in ("âmbar", "ambar", "licen", "50%", "/ 30")):
        return f"KIT {label.upper()}"
    return base


def _kit_description(kit_id: str, kit: dict[str, Any], kit_price: int, label: str) -> str:
    # kit_price mantido na assinatura por compatibilidade — NÃO entra no título.
    return _short_kit_title(kit_id, kit, label)


def _sanitize_placeholder_prices(kits: dict[str, Any]) -> list[str]:
    cleared: list[str] = []
    for kit_id, kit in kits.items():
        if not isinstance(kit, dict):
            continue
        if _is_retired_kit(str(kit_id), kit):
            continue
        price = int(kit.get("Price") or 0)
        if price >= PLACEHOLDER_PRICE_MIN or price == 1:
            kit["Price"] = 0
            cleared.append(f"{kit_id}(was {price})")
    return cleared


def _apply_tier_kit_pricing(kits: dict[str, Any], items: dict[str, Any]) -> list[str]:
    by_group = _build_group_license_index(items)
    updated: list[str] = []

    for kit_id, kit in kits.items():
        if not isinstance(kit, dict):
            continue
        if _is_retired_kit(str(kit_id), kit):
            continue

        perms = _parse_permissions(kit.get("Permissions"))
        has_perms = any(
            p for p in perms if p not in SKIP_PERMISSION_GROUPS and not _is_removed_group(p)
        )
        is_tier = bool(TIER_KIT_SUFFIX_RE.search(str(kit_id)))

        if not (has_perms or is_tier):
            continue

        meta = _resolve_kit_license(kit_id, kit, items, by_group)
        if not meta:
            continue

        kit_price = meta["price"] // 2
        group = meta["group"]
        label = meta["label"]

        kit["Price"] = kit_price
        if group and group not in SKIP_PERMISSION_GROUPS and not _is_removed_group(group):
            # Mantém Admins + tier atual + próximo (se já existia N+1); senão Admins,group
            existing_perms = _parse_permissions(kit.get("Permissions"))
            next_tiers = [p for p in existing_perms if p not in SKIP_PERMISSION_GROUPS and p != group]
            if next_tiers:
                kit["Permissions"] = "Admins," + ",".join([group] + next_tiers[:1])
            else:
                kit["Permissions"] = f"Admins,{group}"
        title = _short_kit_title(kit_id, kit, label)
        kit["Name"] = title
        kit["Description"] = title
        kit["KitDescription"] = title
        updated.append(f"{kit_id}={kit_price}({group})")

    return updated


def apply_catalog_sync(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Sanitiza catálogo no sync TEK. Modifica *data* in-place."""
    purged = _purge_retired_entries(data)
    purged.extend(_purge_timed_points_groups(data))
    items = data.setdefault("Items", {})
    kits = data.setdefault("Kits", {})

    cleared = _sanitize_placeholder_prices(kits)
    cleared = [*(f"removed:{s}" for s in purged), *cleared]
    kit_updates = _apply_tier_kit_pricing(kits, items)

    if "struct_tekforge" in items:
        items["struct_tekforge"]["Price"] = 50000
        items["struct_tekforge"]["Category"] = items["struct_tekforge"].get("Category") or "Ferramentas"
    if "struct_tekreplicator" in items:
        items["struct_tekreplicator"]["Price"] = 15000
        items["struct_tekreplicator"]["Category"] = items["struct_tekreplicator"].get("Category") or "Ferramentas"
        rep_items = items["struct_tekreplicator"].get("Items") or []
        if rep_items and isinstance(rep_items[0], dict):
            rep_items[0]["Blueprint"] = REPLICATOR_BP

    data["PointPackages"] = deepcopy(POINT_PACKAGES)
    return cleared, kit_updates


def catalog_has_placeholder_kit_prices(data: dict[str, Any]) -> bool:
    """True se algum kit ativo ainda tem preço placeholder (≥1M ou 1)."""
    kits = data.get("Kits") or {}
    for kit_id, kit in kits.items():
        if not isinstance(kit, dict):
            continue
        if _is_retired_kit(str(kit_id), kit):
            continue
        price = int(kit.get("Price") or 0)
        if price >= PLACEHOLDER_PRICE_MIN or price == 1:
            return True
    return False
