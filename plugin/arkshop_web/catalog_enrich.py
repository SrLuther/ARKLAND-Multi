"""Enriquecimento do catálogo público da Web Store (thumbnails, busca, metadados)."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from ark_species_registry import lookup_species, tier_icon_url
from resource_icon_registry import resolve_resource_icon

CATEGORY_ICONS: dict[str, str] = {
    "ferramentas": "/catalog/tool.svg",
    "armaduras": "/catalog/armor.svg",
    "armas": "/catalog/weapon.svg",
    "recursos": "/catalog/consumable.svg",
    "consumiveis": "/catalog/consumable.svg",
    "selas": "/catalog/structure.svg",
    "estruturas": "/catalog/structure.svg",
    "structures": "/catalog/structure.svg",
    "blueprints": "/catalog/item.svg",
    "blueprint": "/catalog/item.svg",
    "veiculos": "/catalog/structure.svg",
    "licencas": "/catalog/license.svg",
    "vip": "/catalog/license.svg",
    "geral": "/catalog/item.svg",
    "mods": "/catalog/item.svg",
    "comercio": "/catalog/item.svg",
}

DEFAULT_ITEM_ICON = "/catalog/item.svg"
KIT_ICON = "/catalog/kit.svg"
LICENSE_ICON = "/catalog/license.svg"

BLUEPRINT_FRIENDLY_NAMES: dict[str, str] = {
    "replicatorplus": "Replicador S+",
    "replicator_plus": "Replicador S+",
    "transmitterplus": "Transmissor S+",
    "generatortek": "Gerador Tek S+",
    "soultraps_ds": "Soul Traps (DinoStorage)",
    "rigchanger": "Swappable Stryder Rig",
}


def _norm_cat(text: str) -> str:
    return (
        unicodedata.normalize("NFD", text or "")
        .encode("ascii", "ignore")
        .decode()
        .lower()
        .strip()
    )


def _infer_category_from_content(entry: dict[str, Any], key: str) -> str:
    """Inferência quando Category não está definida no config."""
    itype = str(entry.get("Type") or entry.get("type") or "item").lower()
    text = (
        f"{entry.get('Name') or ''} {entry.get('Description') or ''} {key} "
        f"{_extract_blueprint(entry)}"
    ).lower()
    if itype == "blueprint" or entry.get("ForceBlueprint"):
        return "Blueprints"
    if re.search(r"saddle|sela|saddles", text):
        return "Selas"
    if re.search(
        r"structure|estrutura|foundation|wall|ceiling|door|gate|pillar|beam|"
        r"ramp|ladder|trap|turret|vault|bed|forge|smithy|fabricator|replicator|"
        r"transmitter|generator|tek\s",
        text,
    ):
        return "Estruturas"
    if re.search(r"vehicle|veiculo|mejo|motorcycle|car|boat|raft|submarine|glider", text):
        return "Veículos"
    if re.search(r"weapon|arma|rifle|pistol|sword|bow|cannon|launcher|shotgun|sniper", text):
        return "Armas"
    if re.search(r"armor|armadura|helmet|chest|gloves|boots|pants|shield|gauntlet|mask", text):
        return "Armaduras"
    if re.search(
        r"consumable|food|water|berry|meat|brew|narcotic|resource|recurso|element|"
        r"metal|hide|fiber|chitin|polymer|crystal|pearl|ingot|paste|oil|gunpowder|"
        r"sparkpowder|cement|charcoal|flint|stone|wood|thatch",
        text,
    ):
        return "Recursos"
    if re.search(r"tool|pick|hatchet|sickle|whip|fishing|ferramenta|chainsaw", text):
        return "Ferramentas"
    return "Geral"


def _resolve_display_category(entry: dict[str, Any], key: str) -> str:
    explicit = str(entry.get("Category") or entry.get("category") or "").strip()
    if explicit:
        return explicit
    itype = str(entry.get("Type") or entry.get("type") or "item").lower()
    text = f"{entry.get('Name') or ''} {entry.get('Description') or ''} {key}"
    if itype == "command" and re.search(r"licen[cç]a|license", text, re.I):
        return "Licenças"
    if itype == "dino":
        return "Dinos"
    if itype in ("license", "licenca"):
        return "Licenças"
    return _infer_category_from_content(entry, key)


def _extract_blueprint(entry: dict[str, Any]) -> str:
    dinos = entry.get("Dinos") or []
    if dinos and isinstance(dinos[0], dict):
        bp = str(dinos[0].get("Blueprint") or "").strip()
        if bp:
            return bp
    for field in ("Blueprint", "blueprint", "ItemBlueprint"):
        val = entry.get(field)
        if val:
            return str(val).strip()
    items = entry.get("Items") or []
    if items and isinstance(items[0], dict):
        bp = str(items[0].get("Blueprint") or "").strip()
        if bp:
            return bp
    return ""


def _category_icon_url(category: str, item_type: str) -> str:
    cat = _norm_cat(category)
    itype = item_type.lower()
    if itype in ("license", "licenca") or cat == "licencas":
        return LICENSE_ICON
    return CATEGORY_ICONS.get(cat, DEFAULT_ITEM_ICON)


def _kit_price_tier(price: int) -> str:
    if price >= 20000:
        return "S+"
    if price >= 10000:
        return "S"
    if price >= 5000:
        return "A"
    if price >= 2000:
        return "B"
    return "C"


def _is_license_entry(entry: dict[str, Any], key: str) -> bool:
    cat = _norm_cat(_resolve_display_category(entry, key))
    if cat == "licencas":
        return True
    itype = str(entry.get("Type") or entry.get("type") or "").lower()
    if itype in ("license", "licenca"):
        return True
    text = f"{entry.get('Name') or ''} {entry.get('Description') or ''}"
    return itype == "command" and bool(re.search(r"licen[cç]a|license", text, re.I))


def _license_meta(entry: dict[str, Any]) -> tuple[int | None, str | None]:
    grant = entry.get("LicenseGrant")
    if not isinstance(grant, dict):
        return None, None
    days = grant.get("Days")
    group = grant.get("Group")
    days_out = int(days) if days is not None else None
    group_out = str(group).strip() if group else None
    return days_out, group_out


def _build_search_text(*parts: str | None) -> str:
    return " ".join(p.strip() for p in parts if p and str(p).strip()).lower()


def enrich_shop_item(key: str, entry: dict[str, Any]) -> dict[str, Any]:
    """Campos extras para /api/catalog (não altera o config original)."""
    if not isinstance(entry, dict):
        return {}

    itype = str(entry.get("Type") or entry.get("type") or "item").lower()
    display_category = _resolve_display_category(entry, key)
    name = str(
        entry.get("Name")
        or entry.get("name")
        or entry.get("Description")
        or entry.get("description")
        or key
    ).strip()
    desc = str(entry.get("Description") or entry.get("description") or "").strip()
    blueprint = _extract_blueprint(entry)

    thumbnail_url = DEFAULT_ITEM_ICON
    tier: str | None = None
    species_key: str | None = None

    if itype == "dino" or (blueprint and "character_bp" in blueprint.lower()):
        lookup = lookup_species(blueprint=blueprint or None, name_hint=name or key)
        if lookup:
            thumbnail_url = str(lookup.get("image_url") or tier_icon_url(lookup.get("tier")))
            tier = str(lookup.get("tier") or "B")
            species_key = lookup.get("species_key")
        else:
            tier = "B"
            thumbnail_url = tier_icon_url(tier)
    elif _is_license_entry(entry, key):
        thumbnail_url = LICENSE_ICON
    else:
        resource_icon = resolve_resource_icon(key, blueprint=blueprint or None)
        thumbnail_url = resource_icon or _category_icon_url(display_category, itype)

    license_days, license_group = _license_meta(entry)
    search_text = _build_search_text(
        key,
        name,
        desc,
        display_category,
        blueprint,
        itype,
        species_key,
        license_group,
        str(license_days) if license_days is not None else None,
    )

    out: dict[str, Any] = {
        "display_category": display_category,
        "thumbnail_url": thumbnail_url,
        "search_text": search_text,
    }
    if tier:
        out["tier"] = tier
    if species_key:
        out["species_key"] = species_key
    if blueprint:
        out["blueprint"] = blueprint
    if license_days is not None:
        out["license_days"] = license_days
    if license_group:
        out["license_group"] = license_group
    return out


def _kit_item_label(item: dict[str, Any]) -> str:
    for field in ("Description", "Name", "description", "name"):
        val = str(item.get(field) or "").strip()
        if val:
            return val
    bp = str(item.get("Blueprint") or "").strip()
    if bp:
        token = bp.rsplit("/", 1)[-1].split(".")[0]
        norm = token.lower().replace("primalitem", "").replace("primalitemstructure_", "").replace("_", "")
        for key, label in BLUEPRINT_FRIENDLY_NAMES.items():
            if key.replace("_", "") in norm:
                return label
        return token.replace("PrimalItem", "").replace("_", " ").strip() or bp
    return "Item"


def enrich_kit(key: str, entry: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(entry, dict):
        return {}

    desc = str(entry.get("Description") or entry.get("description") or key).strip()
    price = int(entry.get("Price") or entry.get("price") or 0)
    raw_items = entry.get("Items") or []
    kit_contents: list[dict[str, Any]] = []
    if isinstance(raw_items, list):
        for raw in raw_items[:80]:
            if not isinstance(raw, dict):
                continue
            kit_contents.append({
                "label": _kit_item_label(raw),
                "blueprint": str(raw.get("Blueprint") or "").strip(),
                "amount": int(raw.get("Amount") or raw.get("Quantity") or 1),
            })

    item_count = len(raw_items) if isinstance(raw_items, list) else 0
    tier = _kit_price_tier(price)
    thumbnail_url = tier_icon_url(tier)

    search_text = _build_search_text(
        key,
        desc,
        "kit",
        str(item_count),
        " ".join(c["label"] for c in kit_contents[:12]),
    )

    return {
        "display_category": "Kit",
        "thumbnail_url": thumbnail_url,
        "search_text": search_text,
        "item_count": item_count,
        "kit_contents": kit_contents,
        "tier": tier,
    }


def enrich_catalog_payload(
    items: dict[str, Any],
    kits: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Mescla metadados enriquecidos em cópias rasas dos mapas de catálogo."""
    enriched_items: dict[str, Any] = {}
    for key, entry in (items or {}).items():
        if isinstance(entry, dict):
            enriched_items[key] = {**entry, **enrich_shop_item(str(key), entry)}
        else:
            enriched_items[key] = entry

    enriched_kits: dict[str, Any] = {}
    for key, entry in (kits or {}).items():
        if isinstance(entry, dict):
            enriched_kits[key] = {**entry, **enrich_kit(str(key), entry)}
        else:
            enriched_kits[key] = entry

    return enriched_items, enriched_kits
