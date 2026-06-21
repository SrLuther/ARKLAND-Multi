"""Economia do Mercado de Dinos — espécies, multiplicadores e cálculo de valor sugerido."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STAT_KEYS: tuple[str, ...] = (
    "health",
    "stamina",
    "oxygen",
    "food",
    "weight",
    "melee",
    "speed",
)

# Mapeamento metadata cryopod / UI → stat_key
STAT_ALIASES: dict[str, str] = {
    "health": "health",
    "hp": "health",
    "stamina": "stamina",
    "oxygen": "oxygen",
    "food": "food",
    "weight": "weight",
    "melee": "melee",
    "melee_damage": "melee",
    "damage": "melee",
    "speed": "speed",
}

def _defaults_file_path() -> Path:
    """Dev: plugin/arkshop_web/data/… — PyInstaller: _MEIPASS/data/…"""
    if getattr(sys, "frozen", False):
        bundled = Path(sys._MEIPASS) / "data" / "market_species_defaults.json"  # type: ignore[attr-defined]
        if bundled.is_file():
            return bundled
    return Path(__file__).resolve().parent / "data" / "market_species_defaults.json"


_DEFAULTS_FILE = _defaults_file_path()


@dataclass
class StatMultiplier:
    stat_key: str
    multiplier: int
    enabled: bool = True
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "stat_key": self.stat_key,
            "multiplier": self.multiplier,
            "enabled": self.enabled,
            "label": self.label,
        }


@dataclass
class SpeciesEconomy:
    species_key: str
    display_name: str
    root_value: int
    catalog_item_id: str = ""
    blueprint_path: str = ""
    reference_level: int = 1
    tier: str = "B"
    breeding_difficulty: str = ""
    breeding_notes: str = ""
    status: str = "PRE_REGISTERED"
    multipliers: dict[str, StatMultiplier] = field(default_factory=dict)

    def to_dict(self, *, include_multipliers: bool = True) -> dict[str, Any]:
        out: dict[str, Any] = {
            "species_key": self.species_key,
            "display_name": self.display_name,
            "root_value": self.root_value,
            "catalog_item_id": self.catalog_item_id,
            "blueprint_path": self.blueprint_path,
            "reference_level": self.reference_level,
            "tier": self.tier,
            "breeding_difficulty": self.breeding_difficulty,
            "breeding_notes": self.breeding_notes,
            "status": self.status,
        }
        if include_multipliers:
            out["multipliers"] = {
                k: v.to_dict() for k, v in sorted(self.multipliers.items())
            }
        return out


def load_defaults_file() -> dict[str, Any]:
    if not _DEFAULTS_FILE.is_file():
        return {"species": [], "global_stat_labels": {}}
    return json.loads(_DEFAULTS_FILE.read_text(encoding="utf-8"))


def load_default_species_map() -> dict[str, dict[str, Any]]:
    data = load_defaults_file()
    return {s["species_key"]: s for s in data.get("species", [])}


def normalize_blueprint(bp: str | None) -> str:
    bp = (bp or "").strip()
    if bp.startswith("Blueprint'") and bp.endswith("'"):
        bp = bp[10:-1]
    return bp.lower()


def build_catalog_economy_map() -> dict[str, dict[str, Any]]:
    """catalog_item_id → definição econômica canônica (grupo rex, giga, …)."""
    out: dict[str, dict[str, Any]] = {}
    for sk, defn in load_default_species_map().items():
        out[sk] = defn
        ref = defn.get("reference_catalog_item_id") or defn.get("catalog_item_id")
        if ref:
            out[str(ref)] = defn
        for cid in defn.get("catalog_item_ids") or []:
            out[str(cid)] = defn
        for alias in defn.get("catalog_aliases") or []:
            if isinstance(alias, str):
                out[alias] = defn
            elif isinstance(alias, dict) and alias.get("catalog_item_id"):
                out[str(alias["catalog_item_id"])] = defn
    return out


def _catalog_item_blueprint(entry: dict[str, Any]) -> str:
    dino = (entry.get("Dinos") or [{}])[0]
    return str(dino.get("Blueprint") or "")


def iter_economy_groups(
    catalog: dict[str, Any],
) -> list[tuple[str, dict[str, Any], list[tuple[str, dict[str, Any]]]]]:
    """Agrupa itens Type:dino do catálogo por species_key econômico."""
    catalog_map = build_catalog_economy_map()
    grouped: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for item_id, entry in iter_catalog_dinos(catalog):
        defn = catalog_map.get(item_id)
        group_key = str((defn or {}).get("species_key") or item_id)
        grouped.setdefault(group_key, []).append((item_id, entry))
    out: list[tuple[str, dict[str, Any], list[tuple[str, dict[str, Any]]]]] = []
    defaults_map = load_default_species_map()
    for group_key, items in grouped.items():
        defn = defaults_map.get(group_key, {})
        out.append((group_key, defn, items))
    out.sort(key=lambda g: -max(int(e[1].get("Price") or 0) for e in g[2]))
    return out


def expand_aliases_from_defaults(
    defn: dict[str, Any],
    aliases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Anexa blueprint_path e blueprint_aliases do JSON às variantes de loja."""
    seen: set[str] = {
        str(a.get("blueprint_norm") or "")
        for a in aliases
        if a.get("blueprint_norm")
    }
    out = list(aliases)
    primary = str(defn.get("blueprint_path") or "").strip()
    if primary:
        nb = normalize_blueprint(primary)
        if nb and nb not in seen:
            seen.add(nb)
            out.append(
                {
                    "blueprint_path": primary,
                    "blueprint_norm": nb,
                    "variant_label": str(defn.get("display_name") or "") or None,
                }
            )
    for raw in defn.get("blueprint_aliases") or []:
        if isinstance(raw, str):
            bp = raw
            label = ""
        elif isinstance(raw, dict):
            bp = str(raw.get("blueprint_path") or "")
            label = str(raw.get("variant_label") or "")
        else:
            continue
        nb = normalize_blueprint(bp)
        if not nb or nb in seen:
            continue
        seen.add(nb)
        out.append(
            {
                "blueprint_path": bp,
                "blueprint_norm": nb,
                "variant_label": label or None,
            }
        )
    return out


def merge_species_from_defaults(
    defn: dict[str, Any],
    *,
    status: str = "PRE_REGISTERED",
) -> tuple[SpeciesEconomy, list[dict[str, Any]]]:
    """Espécie só de referência (sem item na loja) — usa root_value do JSON."""
    group_key = str(defn["species_key"])
    species = SpeciesEconomy(
        species_key=group_key,
        catalog_item_id=str(
            defn.get("reference_catalog_item_id") or defn.get("catalog_item_id") or ""
        ),
        display_name=str(defn.get("display_name") or group_key),
        blueprint_path=str(defn.get("blueprint_path") or ""),
        reference_level=1,
        root_value=int(defn.get("root_value") or 0),
        tier=str(defn.get("tier") or "B"),
        breeding_difficulty=str(defn.get("breeding_difficulty") or ""),
        breeding_notes=str(defn.get("breeding_notes") or ""),
        status=status,
        multipliers=build_multipliers_from_defaults(group_key),
    )
    aliases = expand_aliases_from_defaults(defn, [])
    return species, aliases


def merge_economy_group(
    group_key: str,
    catalog_items: list[tuple[str, dict[str, Any]]],
    *,
    defaults: dict[str, Any] | None = None,
    catalog: dict[str, Any] | None = None,
    status: str = "PRE_REGISTERED",
) -> tuple[SpeciesEconomy, list[dict[str, Any]]]:
    """Retorna espécie canônica + aliases (variantes de loja/blueprint)."""
    defaults = defaults or load_default_species_map().get(group_key, {})
    ref_id = str(
        defaults.get("reference_catalog_item_id")
        or defaults.get("catalog_item_id")
        or catalog_items[0][0]
    )
    ref_entry = dict(catalog_items[0][1])
    for cid, entry in catalog_items:
        if cid == ref_id:
            ref_entry = entry
            break

    dino = (ref_entry.get("Dinos") or [{}])[0]
    display_name = str(defaults.get("display_name") or group_key)
    species = SpeciesEconomy(
        species_key=group_key,
        catalog_item_id=ref_id,
        display_name=display_name,
        blueprint_path=str(dino.get("Blueprint") or ""),
        reference_level=int(dino.get("Level") or 1),
        root_value=int(ref_entry.get("Price") or 0),
        tier=str(defaults.get("tier") or "B"),
        breeding_difficulty=str(defaults.get("breeding_difficulty") or ""),
        breeding_notes=str(defaults.get("breeding_notes") or ""),
        status=status,
        multipliers=build_multipliers_from_defaults(group_key),
    )

    aliases: list[dict[str, Any]] = []
    for item_id, entry in catalog_items:
        bp = _catalog_item_blueprint(entry)
        label = str(entry.get("Name") or entry.get("Description") or item_id)
        if catalog is not None:
            label = shop_catalog_display_name(catalog, item_id) or label
        bp_norm = normalize_blueprint(bp) or f"catalog:{item_id}"
        aliases.append(
            {
                "catalog_item_id": item_id,
                "blueprint_path": bp,
                "blueprint_norm": bp_norm,
                "variant_label": label,
            }
        )
    aliases = expand_aliases_from_defaults(defaults, aliases)
    return species, aliases


def stat_labels() -> dict[str, str]:
    data = load_defaults_file()
    labels = data.get("global_stat_labels") or {}
    defaults = {
        "health": "Vida",
        "melee": "Dano",
        "weight": "Peso",
        "stamina": "Estamina",
        "oxygen": "Oxigênio",
        "food": "Comida",
        "speed": "Velocidade",
    }
    return {**defaults, **labels}


def normalize_stat_points(raw: dict[str, Any]) -> dict[str, int]:
    """Converte stats_max do metadata em pontos por stat_key."""
    points: dict[str, int] = {k: 0 for k in STAT_KEYS}
    if not raw:
        return points
    for key, val in raw.items():
        sk = STAT_ALIASES.get(str(key).lower(), str(key).lower())
        if sk not in points:
            continue
        if isinstance(val, dict):
            p = val.get("points", val.get("value", 0))
        else:
            p = val
        try:
            points[sk] = max(0, int(round(float(p))))
        except (TypeError, ValueError):
            continue
    return points


def build_multipliers_from_defaults(species_key: str) -> dict[str, StatMultiplier]:
    defaults = load_default_species_map().get(species_key, {})
    raw = defaults.get("multipliers") or {}
    labels = stat_labels()
    out: dict[str, StatMultiplier] = {}
    for sk in STAT_KEYS:
        mult = int(raw.get(sk, 0))
        out[sk] = StatMultiplier(
            stat_key=sk,
            multiplier=mult,
            enabled=mult > 0,
            label=labels.get(sk, sk),
        )
    return out


def merge_species_from_catalog_item(
    item_id: str,
    entry: dict[str, Any],
    *,
    defaults: dict[str, Any] | None = None,
    status: str = "PRE_REGISTERED",
) -> SpeciesEconomy:
    dino = (entry.get("Dinos") or [{}])[0]
    defaults = defaults or build_catalog_economy_map().get(item_id) or load_default_species_map().get(item_id, {})
    species_key = str(defaults.get("species_key") or item_id)
    return SpeciesEconomy(
        species_key=species_key,
        catalog_item_id=item_id,
        display_name=str(
            defaults.get("display_name")
            or entry.get("Name")
            or entry.get("Description")
            or item_id
        ),
        blueprint_path=str(dino.get("Blueprint") or ""),
        reference_level=int(dino.get("Level") or 1),
        root_value=int(entry.get("Price") or 0),
        tier=str(defaults.get("tier") or "B"),
        breeding_difficulty=str(defaults.get("breeding_difficulty") or ""),
        breeding_notes=str(defaults.get("breeding_notes") or ""),
        status=status,
        multipliers=build_multipliers_from_defaults(species_key),
    )


def iter_catalog_dinos(catalog: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    items = catalog.get("Items") or catalog.get("ShopItems") or {}
    out: list[tuple[str, dict[str, Any]]] = []
    for item_id, entry in items.items():
        if str(entry.get("Type") or "").lower() != "dino":
            continue
        out.append((item_id, entry))
    out.sort(key=lambda x: -int(x[1].get("Price") or 0))
    return out


def shop_catalog_display_name(catalog: dict[str, Any], catalog_item_id: str | None) -> str:
    """Nome do item na loja (config.json) — não altera a loja, só referência para o admin."""
    item_id = (catalog_item_id or "").strip()
    if not item_id:
        return ""
    items = catalog.get("Items") or catalog.get("ShopItems") or {}
    entry = items.get(item_id)
    if not entry:
        return item_id
    return str(entry.get("Name") or entry.get("Description") or item_id)


def calculate_suggested_value(
    species: SpeciesEconomy,
    stat_points: dict[str, int],
) -> tuple[int, list[dict[str, Any]]]:
    """Retorna (valor_total, breakdown) conforme §5.7 do projeto."""
    breakdown: list[dict[str, Any]] = [
        {
            "kind": "root",
            "label": f"Valor Raiz ({species.display_name})",
            "stat_key": None,
            "points": None,
            "multiplier": None,
            "subtotal": species.root_value,
        }
    ]
    total = species.root_value
    labels = stat_labels()
    for sk in STAT_KEYS:
        sm = species.multipliers.get(sk)
        if not sm or not sm.enabled or sm.multiplier <= 0:
            continue
        pts = int(stat_points.get(sk, 0))
        if pts <= 0:
            continue
        sub = pts * sm.multiplier
        total += sub
        breakdown.append(
            {
                "kind": "stat",
                "label": labels.get(sk, sk),
                "stat_key": sk,
                "points": pts,
                "multiplier": sm.multiplier,
                "subtotal": sub,
            }
        )
    breakdown.append(
        {
            "kind": "total",
            "label": "Valor Sugerido Total",
            "stat_key": None,
            "points": None,
            "multiplier": None,
            "subtotal": total,
        }
    )
    return total, breakdown


def format_breakdown_text(breakdown: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for row in breakdown:
        if row["kind"] == "root":
            lines.append(f"{row['label']}: {row['subtotal']:,}".replace(",", "."))
        elif row["kind"] == "stat":
            lines.append(
                f"{row['label']}: {row['points']} pts × {row['multiplier']} = "
                f"{row['subtotal']:,}".replace(",", ".")
            )
        elif row["kind"] == "total":
            lines.append(f"── Total: {row['subtotal']:,} Âmbar".replace(",", "."))
    return lines
