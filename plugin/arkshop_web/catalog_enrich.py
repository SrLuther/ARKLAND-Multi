"""Enriquecimento do catálogo público da Web Store (thumbnails, busca, metadados)."""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

from ark_species_registry import lookup_species, tier_icon_url
from resource_icon_registry import resolve_resource_icon

_WEB_DIR = Path(__file__).resolve().parent
_ITENSALFA_DESC_CANDIDATES = (
    _WEB_DIR / "data" / "itensalfa_kit_descriptions.json",
    _WEB_DIR.parents[1] / "tools" / "itensalfa_kit_descriptions.json",
)

CATEGORY_ICONS: dict[str, str] = {
    "ferramentas": "/catalog/category-tools.webp",
    "armaduras": "/catalog/category-other.webp",
    "armas": "/catalog/category-weapons.webp",
    "recursos": "/catalog/category-resources.webp",
    "consumiveis": "/catalog/category-resources.webp",
    "selas": "/catalog/category-saddles.webp",
    "estruturas": "/catalog/category-other.webp",
    "structures": "/catalog/category-other.webp",
    "blueprints": "/catalog/category-other.webp",
    "blueprint": "/catalog/category-other.webp",
    "veiculos": "/catalog/category-other.webp",
    "licencas": "/catalog/license.svg",
    "vip": "/catalog/license.svg",
    "geral": "/catalog/category-other.webp",
    "mods": "/catalog/category-other.webp",
    "comercio": "/catalog/category-other.webp",
    "dinos": "/catalog/category-dinos.webp",
    "kits": "/catalog/category-kits.webp",
}

DEFAULT_ITEM_ICON = "/catalog/category-other.webp"
KIT_ICON = "/catalog/category-kits.webp"
DINO_FALLBACK_ICON = "/catalog/category-dinos.webp"
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
            # Dinos de mod fora do registro ainda podem ter ícone AI em generated/*.webp
            from ark_species_registry import _bundled_icon_for_species

            try:
                from market_economy import _species_key_from_catalog_item_id

                derived = _species_key_from_catalog_item_id(key) or key
            except Exception:
                derived = key
            candidates = [
                str(species_key or "").lower(),
                str(derived or "").lower(),
                str(key or "").lower(),
            ]
            bundled = None
            for cand in candidates:
                if not cand:
                    continue
                bundled = _bundled_icon_for_species(cand)
                if bundled:
                    species_key = cand
                    break
            tier = "B"
            thumbnail_url = bundled or DINO_FALLBACK_ICON
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
    if itype == "dino":
        dinos = entry.get("Dinos") or []
        if dinos and isinstance(dinos[0], dict):
            out["dino_level"] = int(dinos[0].get("Level") or 1)
        else:
            out["dino_level"] = 1
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


@lru_cache(maxsize=1)
def _load_itensalfa_kit_descriptions() -> dict[str, Any]:
    for path in _ITENSALFA_DESC_CANDIDATES:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("by_blueprint"), dict):
                return data
        except Exception:
            continue
    return {"by_blueprint": {}, "status_by_tier": {}}


def _lookup_itensalfa_meta(blueprint: str) -> dict[str, Any] | None:
    bp = (blueprint or "").strip()
    if not bp:
        return None
    by_bp = _load_itensalfa_kit_descriptions().get("by_blueprint") or {}
    meta = by_bp.get(bp)
    if isinstance(meta, dict):
        return meta
    # Fallback: caminho sem sufixo .ClassName duplicado
    if "." in bp:
        alt = bp.split(".")[0]
        for key, val in by_bp.items():
            if isinstance(val, dict) and (key == alt or key.startswith(alt + ".")):
                return val
    return None


def _components_meta_map(entry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Indexa ComponentsMeta do config por blueprint (ou índice numérico como str)."""
    raw = entry.get("ComponentsMeta") or entry.get("components_meta")
    out: dict[str, dict[str, Any]] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(v, dict):
                out[str(k).strip()] = v
        return out
    if isinstance(raw, list):
        for idx, v in enumerate(raw):
            if not isinstance(v, dict):
                continue
            bp = str(v.get("Blueprint") or v.get("blueprint") or "").strip()
            if bp:
                out[bp] = v
            out[str(idx)] = v
    return out


def _component_characteristics(
    raw: dict[str, Any],
    *,
    index: int,
    meta_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Características por componente: config > ComponentsMeta > planilha ItensAlfa."""
    bp = str(raw.get("Blueprint") or "").strip()
    extras: dict[str, Any] = {}

    sheet = _lookup_itensalfa_meta(bp) if bp else None
    if sheet:
        extras.update({
            "kind": sheet.get("kind"),
            "tier": sheet.get("tier"),
            "stats": sheet.get("stats") or {},
            "materials": sheet.get("materials") or [],
            "materials_text": sheet.get("materials_text") or "",
            "summary": sheet.get("summary") or "",
        })
        if sheet.get("name"):
            extras["name"] = sheet["name"]

    cfg_meta = meta_map.get(bp) or meta_map.get(str(index)) or {}
    if cfg_meta:
        for field in ("kind", "tier", "summary", "materials_text", "name", "characteristics"):
            val = cfg_meta.get(field) or cfg_meta.get(field.capitalize())
            if val:
                extras[field if field != "characteristics" else "characteristics"] = val
        if isinstance(cfg_meta.get("materials"), list):
            extras["materials"] = cfg_meta["materials"]
        if isinstance(cfg_meta.get("stats"), dict):
            extras["stats"] = cfg_meta["stats"]

    for field in ("Characteristics", "characteristics", "ItemDescription", "item_description"):
        val = str(raw.get(field) or "").strip()
        if val:
            extras["characteristics"] = val
            break

    manual_name = str(raw.get("Name") or raw.get("name") or "").strip()
    if manual_name:
        extras["name"] = manual_name

    if not extras.get("characteristics"):
        # Monta texto legível a partir de summary / materiais / stats
        parts: list[str] = []
        if extras.get("summary"):
            parts.append(str(extras["summary"]))
        elif extras.get("materials_text"):
            kind_pt = {
                "armor": "Armadura",
                "weapon": "Arma",
                "tool": "Ferramenta",
                "saddle": "Sela",
            }.get(str(extras.get("kind") or ""), "")
            tier = extras.get("tier") or ""
            head = " ".join(p for p in (kind_pt, tier) if p).strip()
            if head:
                parts.append(f"{head} · Craft: {extras['materials_text']}")
            else:
                parts.append(f"Craft: {extras['materials_text']}")
        if parts:
            extras["characteristics"] = parts[0]

    # Estrutura pronta mesmo sem dados (kits não-ItensAlfa)
    extras.setdefault("kind", None)
    extras.setdefault("tier", None)
    extras.setdefault("stats", {})
    extras.setdefault("materials", [])
    extras.setdefault("materials_text", "")
    extras.setdefault("summary", "")
    extras.setdefault("characteristics", "")
    return extras


def _kit_thumbnail_url(key: str, entry: dict[str, Any], tier: str) -> str:
    """Kits: ícone da espécie (se houver dino conhecido) → caixa ARKLAND → fallback."""
    dinos = entry.get("Dinos") or []
    if isinstance(dinos, list) and dinos:
        first = dinos[0] if isinstance(dinos[0], dict) else {}
        bp = str((first or {}).get("Blueprint") or "").strip()
        name_hint = str(
            entry.get("Description") or entry.get("Name") or key or ""
        ).strip()
        if bp:
            lookup = lookup_species(blueprint=bp, name_hint=name_hint)
            if lookup and lookup.get("image_url"):
                url = str(lookup["image_url"])
                # Evitar o próprio fallback genérico se a espécie não tem retrato
                if "category-dinos" not in url and "/species/tier-" not in url:
                    return url
                if lookup.get("image_url") and "generated" in url:
                    return url
            from ark_species_registry import _bundled_icon_for_species

            for cand in (
                str((lookup or {}).get("species_key") or ""),
                key.rsplit("_pack", 1)[0],
                key.rsplit("_femea", 1)[0],
            ):
                cand = str(cand or "").strip().lower()
                if not cand:
                    continue
                bundled = _bundled_icon_for_species(cand)
                if bundled:
                    return bundled
    # Pack key: astrodelphis_pack10 → astrodelphis
    stem = re.sub(r"_(pack\d+|femeas?|females?)$", "", key, flags=re.I)
    stem = re.sub(r"_pack\d+$", "", stem, flags=re.I)
    if stem and stem != key:
        from ark_species_registry import _bundled_icon_for_species

        bundled = _bundled_icon_for_species(stem.lower())
        if bundled:
            return bundled
    return KIT_ICON


def enrich_kit(key: str, entry: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(entry, dict):
        return {}

    desc = str(entry.get("Description") or entry.get("description") or key).strip()
    name = str(entry.get("Name") or entry.get("name") or "").strip()
    kit_description = str(
        entry.get("KitDescription")
        or entry.get("kit_description")
        or ""
    ).strip()
    price = int(entry.get("Price") or entry.get("price") or 0)
    raw_items = entry.get("Items") or []
    meta_map = _components_meta_map(entry)
    kit_contents: list[dict[str, Any]] = []
    if isinstance(raw_items, list):
        for idx, raw in enumerate(raw_items[:80]):
            if not isinstance(raw, dict):
                continue
            char = _component_characteristics(raw, index=idx, meta_map=meta_map)
            label = char.get("name") or _kit_item_label(raw)
            content: dict[str, Any] = {
                "label": label,
                "blueprint": str(raw.get("Blueprint") or "").strip(),
                "amount": int(raw.get("Amount") or raw.get("Quantity") or 1),
                "kind": char.get("kind"),
                "tier": char.get("tier"),
                "stats": char.get("stats") or {},
                "materials": char.get("materials") or [],
                "materials_text": char.get("materials_text") or "",
                "summary": char.get("summary") or "",
                "characteristics": char.get("characteristics") or "",
            }
            kit_contents.append(content)

    item_count = len(raw_items) if isinstance(raw_items, list) else 0
    tier = _kit_price_tier(price)
    thumbnail_url = _kit_thumbnail_url(key, entry, tier)

    counts: dict[str, int] = {"armor": 0, "weapon": 0, "tool": 0, "saddle": 0, "other": 0}
    for c in kit_contents:
        kind = str(c.get("kind") or "").lower()
        if kind in counts:
            counts[kind] += 1
        else:
            counts["other"] += 1

    # Stats representativos do tier (primeiro item de cada kind com stats)
    stats_by_kind: dict[str, dict[str, Any]] = {}
    for c in kit_contents:
        kind = str(c.get("kind") or "").lower()
        if not kind or kind in stats_by_kind:
            continue
        st = c.get("stats") if isinstance(c.get("stats"), dict) else {}
        if st:
            stats_by_kind[kind] = st

    # Fallback: status_by_tier da planilha ItensAlfa
    sheet = _load_itensalfa_kit_descriptions()
    status_by_tier = sheet.get("status_by_tier") or {}
    sheet_tier = next((c.get("tier") for c in kit_contents if c.get("tier")), None)
    if sheet_tier and isinstance(status_by_tier.get(sheet_tier), dict):
        st_tier = status_by_tier[sheet_tier]
        if "armor" not in stats_by_kind and st_tier.get("armor"):
            stats_by_kind["armor"] = {"armor": st_tier["armor"], "label": f"Armadura {st_tier['armor']}"}
        if "weapon" not in stats_by_kind and st_tier.get("weapon"):
            stats_by_kind["weapon"] = {"damage": st_tier["weapon"], "label": f"Dano {st_tier['weapon']}"}
        if "saddle" not in stats_by_kind and st_tier.get("saddle"):
            stats_by_kind["saddle"] = {
                "armor": st_tier["saddle"],
                "label": f"Armadura da sela {st_tier['saddle']}",
            }

    highlight_lines: list[str] = []
    if counts["armor"]:
        lab = (stats_by_kind.get("armor") or {}).get("label") or ""
        highlight_lines.append(
            f"{counts['armor']} armadura(s) TEK" + (f" · {lab}" if lab else "")
        )
    if counts["weapon"]:
        lab = (stats_by_kind.get("weapon") or {}).get("label") or ""
        highlight_lines.append(
            f"{counts['weapon']} arma(s)" + (f" · {lab}" if lab else "")
        )
    if counts["tool"]:
        highlight_lines.append(f"{counts['tool']} ferramenta(s)")
    if counts["saddle"]:
        lab = (stats_by_kind.get("saddle") or {}).get("label") or ""
        highlight_lines.append(
            f"{counts['saddle']} sela(s) TEK" + (f" · {lab}" if lab else "")
        )
    if counts["other"] and not any(counts[k] for k in ("armor", "weapon", "tool", "saddle")):
        highlight_lines.append(f"{counts['other']} item(ns)")

    # Auto-descrição só quando há classificação útil (ItensAlfa / kinds conhecidos)
    has_typed = any(counts[k] for k in ("armor", "weapon", "tool", "saddle"))
    if not kit_description and has_typed and highlight_lines:
        kit_description = (
            f"Inclui {item_count} itens: " + "; ".join(highlight_lines) + "."
        )

    kit_summary = {
        "counts": counts,
        "stats_by_kind": stats_by_kind,
        "highlights": highlight_lines,
        "sheet_tier": sheet_tier,
    }

    search_bits = [
        key,
        name,
        desc,
        kit_description,
        "kit",
        str(item_count),
        " ".join(highlight_lines),
        " ".join(c["label"] for c in kit_contents[:12]),
        " ".join(
            str(c.get("characteristics") or c.get("summary") or "")
            for c in kit_contents[:12]
        ),
    ]
    if counts["saddle"]:
        search_bits.append("selas saddle")
    search_text = _build_search_text(*search_bits)

    out: dict[str, Any] = {
        "display_category": "Kit",
        "thumbnail_url": thumbnail_url,
        "search_text": search_text,
        "item_count": item_count,
        "kit_contents": kit_contents,
        "kit_summary": kit_summary,
        "tier": tier,
        "kit_description": kit_description,
    }
    return out


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
