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

# Stats que entram na economia proporcional (oxigênio/comida ficam de fora)
ECONOMY_STAT_KEYS: tuple[str, ...] = (
    "health",
    "melee",
    "weight",
    "stamina",
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
    diet_class: str = "carnivore"
    size_class: str = "medium"
    economy_stats: dict[str, Any] = field(default_factory=dict)
    pricing_mode: str = "proportional"

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
            "diet_class": self.diet_class,
            "size_class": self.size_class,
            "economy_stats": self.economy_stats,
            "pricing_mode": self.pricing_mode,
            "size_cap": size_cap_for_class(self.size_class),
            "bonus_space": max(0, size_cap_for_class(self.size_class) - self.root_value),
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


def load_size_caps() -> dict[str, int]:
    raw = load_defaults_file().get("_size_caps") or {}
    return {
        "large": int(raw.get("large", 300_000)),
        "medium": int(raw.get("medium", 250_000)),
        "small": int(raw.get("small", 100_000)),
    }


def load_pts_reference() -> int:
    try:
        return max(1, int(load_defaults_file().get("_pts_reference") or 254))
    except (TypeError, ValueError):
        return 254


def load_stat_weights() -> dict[str, dict[str, float]]:
    raw = load_defaults_file().get("_stat_weights") or {}
    defaults: dict[str, dict[str, float]] = {
        "carnivore": {"health": 0.55, "melee": 0.45, "weight": 0.0, "stamina": 0.0, "speed": 0.0},
        "herbivore": {"health": 0.35, "melee": 0.0, "weight": 0.40, "stamina": 0.25, "speed": 0.0},
        "omnivore": {"health": 0.30, "melee": 0.25, "weight": 0.30, "stamina": 0.15, "speed": 0.0},
    }
    out: dict[str, dict[str, float]] = {}
    for diet, base in defaults.items():
        diet_raw = raw.get(diet) or {}
        out[diet] = {
            sk: float(diet_raw.get(sk, base.get(sk, 0.0))) for sk in ECONOMY_STAT_KEYS
        }
    return out


def size_cap_for_class(size_class: str) -> int:
    caps = load_size_caps()
    return int(caps.get(str(size_class or "medium").lower(), caps["medium"]))


def _parse_economy_stat_entry(val: Any) -> tuple[bool, float | None]:
    if isinstance(val, bool):
        return val, None
    if isinstance(val, dict):
        enabled = bool(val.get("enabled", False))
        wo = val.get("weight_override")
        try:
            override = float(wo) if wo is not None else None
        except (TypeError, ValueError):
            override = None
        return enabled, override
    return False, None


def species_economy_meta_from_defaults(species_key: str) -> dict[str, Any]:
    defn = load_default_species_map().get(species_key, {})
    raw_stats = defn.get("economy_stats") or {}
    economy_stats: dict[str, dict[str, Any]] = {}
    for sk in ECONOMY_STAT_KEYS:
        enabled, override = _parse_economy_stat_entry(raw_stats.get(sk))
        entry: dict[str, Any] = {"enabled": enabled}
        if override is not None:
            entry["weight_override"] = override
        raw_entry = raw_stats.get(sk)
        if isinstance(raw_entry, dict) and raw_entry.get("rate_per_point") is not None:
            try:
                entry["rate_per_point"] = float(raw_entry["rate_per_point"])
            except (TypeError, ValueError):
                pass
        economy_stats[sk] = entry
    if not any(v.get("enabled") for v in economy_stats.values()):
        for sk in ECONOMY_STAT_KEYS:
            mult = int((defn.get("multipliers") or {}).get(sk, 0))
            economy_stats[sk] = {"enabled": mult > 0}
    return {
        "diet_class": str(defn.get("diet_class") or "carnivore"),
        "size_class": str(defn.get("size_class") or "medium"),
        "economy_stats": economy_stats,
        "pricing_mode": str(defn.get("pricing_mode") or "proportional"),
    }


def apply_economy_meta(species: "SpeciesEconomy") -> "SpeciesEconomy":
    meta = species_economy_meta_from_defaults(species.species_key)
    species.diet_class = meta["diet_class"]
    species.size_class = meta["size_class"]
    species.economy_stats = meta["economy_stats"]
    species.pricing_mode = meta["pricing_mode"]
    return species


def save_defaults_file(data: dict[str, Any]) -> None:
    _DEFAULTS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def patch_economy_global_config(updates: dict[str, Any]) -> dict[str, Any]:
    data = load_defaults_file()
    if "size_caps" in updates:
        data["_size_caps"] = {
            k: int(v) for k, v in (updates["size_caps"] or {}).items()
        }
    if "pts_reference" in updates:
        data["_pts_reference"] = int(updates["pts_reference"])
    if "stat_weights" in updates:
        raw = updates["stat_weights"] or {}
        out: dict[str, dict[str, float]] = {}
        for diet, weights in raw.items():
            out[str(diet)] = {
                sk: float((weights or {}).get(sk, 0.0)) for sk in ECONOMY_STAT_KEYS
            }
        data["_stat_weights"] = out
    save_defaults_file(data)
    return load_economy_global_config()


def patch_species_economy_meta(species_key: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    data = load_defaults_file()
    species_list = data.get("species") or []
    target: dict[str, Any] | None = None
    for sp in species_list:
        if str(sp.get("species_key")) == species_key:
            target = sp
            break
    if target is None:
        return None
    if "diet_class" in updates:
        target["diet_class"] = str(updates["diet_class"])
    if "size_class" in updates:
        target["size_class"] = str(updates["size_class"])
    if "pricing_mode" in updates:
        target["pricing_mode"] = str(updates["pricing_mode"])
    if "economy_stats" in updates and isinstance(updates["economy_stats"], dict):
        existing = dict(target.get("economy_stats") or {})
        for sk, val in updates["economy_stats"].items():
            if sk not in ECONOMY_STAT_KEYS:
                continue
            prev = existing.get(sk)
            if isinstance(val, bool):
                entry = dict(prev) if isinstance(prev, dict) else {}
                entry["enabled"] = val
                existing[sk] = entry
            elif isinstance(val, dict):
                entry = dict(prev) if isinstance(prev, dict) else {}
                entry.update(val)
                existing[sk] = entry
        target["economy_stats"] = existing
    save_defaults_file(data)
    return target


def list_species_economy_meta() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sk, defn in sorted(load_default_species_map().items()):
        meta = species_economy_meta_from_defaults(sk)
        out.append(
            {
                "species_key": sk,
                "display_name": defn.get("display_name") or sk,
                "tier": defn.get("tier") or "B",
                "root_value": int(defn.get("root_value") or 0),
                **meta,
                "size_cap": size_cap_for_class(meta["size_class"]),
                "bonus_space": max(
                    0,
                    size_cap_for_class(meta["size_class"])
                    - int(defn.get("root_value") or 0),
                ),
            }
        )
    return out


def simulate_economy(
    species_key: str,
    stat_points: dict[str, Any],
    *,
    root_value: int | None = None,
) -> dict[str, Any] | None:
    defn = load_default_species_map().get(species_key)
    if not defn:
        return None
    entry = {
        "Type": "dino",
        "Price": root_value if root_value is not None else int(defn.get("root_value") or 0),
        "Dinos": [{"Blueprint": defn.get("blueprint_path") or "", "Level": 1}],
    }
    ref_id = str(defn.get("catalog_item_id") or defn.get("reference_catalog_item_id") or species_key)
    species = merge_species_from_catalog_item(ref_id, entry, defaults=defn)
    if root_value is not None:
        species.root_value = int(root_value)
    points = normalize_stat_points(stat_points)
    total, breakdown = calculate_suggested_value(species, points)
    return {
        "species_key": species_key,
        "computed_base_value": total,
        "calculation_breakdown": breakdown,
        "species": species.to_dict(include_multipliers=False),
        "stat_points": points,
    }


def load_economy_global_config() -> dict[str, Any]:
    return {
        "size_caps": load_size_caps(),
        "pts_reference": load_pts_reference(),
        "stat_weights": load_stat_weights(),
        "tier_legend": load_tier_legend(),
    }


def load_tier_legend() -> dict[str, str]:
    """Rótulos de tier (S+, S, A, B, C) para exibição na tabela do Comércio."""
    raw = load_defaults_file().get("_tier_legend") or {}
    order = ("S+", "S", "A", "B", "C")
    out: dict[str, str] = {}
    for key in order:
        label = raw.get(key)
        if label:
            out[key] = str(label)
    for key, label in raw.items():
        if key not in out and label:
            out[str(key)] = str(label)
    return out


def load_default_species_map() -> dict[str, dict[str, Any]]:
    data = load_defaults_file()
    return {s["species_key"]: s for s in data.get("species", [])}


def normalize_blueprint(bp: str | None) -> str:
    bp = (bp or "").strip()
    if not bp:
        return ""
    if bp.startswith("Blueprint'") and bp.endswith("'"):
        bp = bp[10:-1]
    # GetFullName do ArkApi: "BlueprintGeneratedClass /Game/.../Foo.Bar_C"
    if " " in bp:
        head, tail = bp.rsplit(" ", 1)
        head_l = head.lower()
        if head_l.endswith("class") or "blueprint" in head_l:
            bp = tail
    bp = bp.lower()
    if "." in bp:
        pkg, cls = bp.rsplit(".", 1)
        if cls.endswith("_c") and len(cls) > 2:
            bp = f"{pkg}.{cls[:-2]}"
    return bp


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


def merge_species_from_registry_entry(
    entry: dict[str, Any],
    *,
    status: str = "PRE_REGISTERED",
) -> tuple[SpeciesEconomy, list[dict[str, Any]]]:
    """Espécie do overlay ark_species_registry.json (mods — ex.: Abyss)."""
    from ark_species_registry import TIER_ROOT_VALUES, normalize_blueprint_extended

    group_key = str(entry.get("species_key") or "").strip()
    if not group_key:
        raise ValueError("species_key obrigatório no registro overlay")
    paths = [str(p).strip() for p in (entry.get("blueprint_paths") or []) if str(p).strip()]
    bp = paths[0] if paths else ""
    tier = str(entry.get("tier") or "B")
    root = int(entry.get("root_value") or TIER_ROOT_VALUES.get(tier, 2500))
    mod = str(entry.get("mod") or "").strip()
    role = str(entry.get("role") or "utility")
    notes = f"{mod}: {role}".strip(": ") if mod else role
    species = SpeciesEconomy(
        species_key=group_key,
        catalog_item_id=str(entry.get("catalog_item_id") or group_key),
        display_name=str(entry.get("display_name") or group_key),
        blueprint_path=bp,
        reference_level=1,
        root_value=root,
        tier=tier,
        breeding_difficulty="",
        breeding_notes=notes,
        status=status,
        multipliers=build_multipliers_from_defaults(group_key),
    )
    aliases: list[dict[str, Any]] = []
    cid = str(entry.get("catalog_item_id") or "").strip() or None
    label = str(entry.get("display_name") or group_key)
    for path in paths:
        bp_norm = normalize_blueprint(path) or normalize_blueprint_extended(path)
        if not bp_norm:
            continue
        aliases.append(
            {
                "catalog_item_id": cid if path == bp else None,
                "blueprint_path": path,
                "blueprint_norm": bp_norm,
                "variant_label": label,
            }
        )
    if not aliases and bp:
        bp_norm = normalize_blueprint(bp) or normalize_blueprint_extended(bp)
        if bp_norm:
            aliases.append(
                {
                    "catalog_item_id": cid,
                    "blueprint_path": bp,
                    "blueprint_norm": bp_norm,
                    "variant_label": label,
                }
            )
    apply_economy_meta(species)
    return species, aliases


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
    apply_economy_meta(species)
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
    apply_economy_meta(species)
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
    """Converte stats_max do metadata em pontos por stat_key.

    Usa ``points_base`` (wild+mut, Spyglass X) quando disponível; senão ``points``.
    Valores brutos ``value`` da cryopod nunca são pontos.
    """
    points: dict[str, int] = {k: 0 for k in STAT_KEYS}
    if not raw:
        return points
    for key, val in raw.items():
        sk = STAT_ALIASES.get(str(key).lower(), str(key).lower())
        if sk not in points:
            continue
        if isinstance(val, dict):
            if val.get("points_base") is not None:
                p = val["points_base"]
            elif val.get("points") is not None:
                p = val["points"]
            else:
                continue
        else:
            p = val
        try:
            points[sk] = max(0, int(round(float(p))))
        except (TypeError, ValueError):
            continue
    return points


def suggested_value_cap() -> int:
    """Legado — preferir ``size_cap_for_class`` por espécie."""
    import os

    try:
        return max(0, int(os.environ.get("MARKET_SUGGESTED_VALUE_CAP", "300000")))
    except ValueError:
        return 300_000


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
    species = SpeciesEconomy(
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
    apply_economy_meta(species)
    return species


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


def _calculate_legacy_multipliers(
    species: SpeciesEconomy,
    stat_points: dict[str, int],
    *,
    root: int,
    cap: int,
) -> tuple[int, list[dict[str, Any]]]:
    """Modo legado: root + pts × multiplicador (exceção por espécie)."""
    labels = stat_labels()
    breakdown: list[dict[str, Any]] = [
        {
            "kind": "root",
            "label": f"Valor base ({species.display_name})",
            "stat_key": None,
            "points": None,
            "multiplier": None,
            "subtotal": root,
            "pricing_mode": "legacy_multipliers",
        },
        {
            "kind": "mode",
            "label": "Modo legado (pts × mult.)",
            "stat_key": None,
            "points": None,
            "multiplier": None,
            "subtotal": 0,
        },
    ]
    total = root
    for sk in STAT_KEYS:
        sm = species.multipliers.get(sk)
        if not sm or not sm.enabled or sm.multiplier <= 0:
            continue
        entry = species.economy_stats.get(sk) or {}
        if isinstance(entry, dict) and entry.get("enabled") is False:
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
    if cap > 0 and total > cap:
        breakdown.append(
            {
                "kind": "cap",
                "label": f"Teto porte {species.size_class} ({cap:,} Âmbar)".replace(",", "."),
                "stat_key": None,
                "points": None,
                "multiplier": None,
                "subtotal": cap - total,
            }
        )
        total = cap
    total = max(root, total)
    breakdown.append(
        {
            "kind": "total",
            "label": "Valor sugerido total",
            "stat_key": None,
            "points": None,
            "multiplier": None,
            "subtotal": total,
            "size_cap": cap,
        }
    )
    return total, breakdown


def _calculate_proportional(
    species: SpeciesEconomy,
    stat_points: dict[str, int],
    *,
    root: int,
    cap: int,
) -> tuple[int, list[dict[str, Any]]]:
    """Modelo padrão: root + fatias do espaço bônus."""
    pts_ref = load_pts_reference()
    espaco_bonus = max(0, cap - root)
    labels = stat_labels()

    breakdown: list[dict[str, Any]] = [
        {
            "kind": "root",
            "label": f"Valor base ({species.display_name})",
            "stat_key": None,
            "points": None,
            "multiplier": None,
            "subtotal": root,
        }
    ]
    if espaco_bonus > 0:
        breakdown.append(
            {
                "kind": "bonus_space",
                "label": f"Espaço bônus (teto {cap:,} − base)".replace(",", "."),
                "stat_key": None,
                "points": None,
                "multiplier": None,
                "subtotal": espaco_bonus,
                "size_cap": cap,
            }
        )

    enabled: list[str] = []
    weight_overrides: dict[str, float] = {}
    for sk in ECONOMY_STAT_KEYS:
        entry = species.economy_stats.get(sk) or {}
        if isinstance(entry, dict) and entry.get("enabled"):
            enabled.append(sk)
            wo = entry.get("weight_override")
            if wo is not None:
                try:
                    weight_overrides[sk] = float(wo)
                except (TypeError, ValueError):
                    pass

    if not enabled or espaco_bonus <= 0:
        total = root
        breakdown.append(
            {
                "kind": "total",
                "label": "Valor sugerido total",
                "stat_key": None,
                "points": None,
                "multiplier": None,
                "subtotal": total,
                "size_cap": cap,
            }
        )
        return total, breakdown

    diet_weights = load_stat_weights().get(species.diet_class, load_stat_weights()["carnivore"])
    pesos_raw: dict[str, float] = {}
    for sk in enabled:
        if sk in weight_overrides:
            pesos_raw[sk] = weight_overrides[sk]
        else:
            pesos_raw[sk] = float(diet_weights.get(sk, 0.0))
    peso_total = sum(pesos_raw.values())
    if peso_total <= 0:
        total = root
        breakdown.append(
            {
                "kind": "total",
                "label": "Valor sugerido total",
                "stat_key": None,
                "points": None,
                "multiplier": None,
                "subtotal": total,
                "size_cap": cap,
            }
        )
        return total, breakdown

    bonus_sum = 0.0
    for sk in enabled:
        peso_eff = pesos_raw[sk] / peso_total
        pts = min(pts_ref, max(0, int(stat_points.get(sk, 0))))
        fatia = espaco_bonus * peso_eff * (pts / pts_ref)
        bonus_sum += fatia
        rate = int(round(espaco_bonus * peso_eff / pts_ref)) if pts_ref else 0
        sub = int(round(fatia))
        breakdown.append(
            {
                "kind": "stat",
                "label": labels.get(sk, sk),
                "stat_key": sk,
                "points": pts,
                "multiplier": rate,
                "weight_pct": round(peso_eff * 100, 1),
                "subtotal": sub,
            }
        )

    total = int(round(root + bonus_sum))
    if total > cap:
        breakdown.append(
            {
                "kind": "cap",
                "label": f"Teto porte {species.size_class} ({cap:,} Âmbar)".replace(",", "."),
                "stat_key": None,
                "points": None,
                "multiplier": None,
                "subtotal": cap - total,
            }
        )
        total = cap
    total = max(root, total)

    breakdown.append(
        {
            "kind": "total",
            "label": "Valor sugerido total",
            "stat_key": None,
            "points": None,
            "multiplier": None,
            "subtotal": total,
            "size_cap": cap,
        }
    )
    return total, breakdown


def _calculate_custom_rates(
    species: SpeciesEconomy,
    stat_points: dict[str, int],
    *,
    root: int,
    cap: int,
) -> tuple[int, list[dict[str, Any]]]:
    """Modo custom: root + pts × rate_per_point por stat (clamp teto)."""
    pts_ref = load_pts_reference()
    labels = stat_labels()
    breakdown: list[dict[str, Any]] = [
        {
            "kind": "root",
            "label": f"Valor base ({species.display_name})",
            "stat_key": None,
            "points": None,
            "multiplier": None,
            "subtotal": root,
            "pricing_mode": "custom",
        },
        {
            "kind": "mode",
            "label": "Modo custom (pts × taxa por stat)",
            "stat_key": None,
            "points": None,
            "multiplier": None,
            "subtotal": 0,
        },
    ]
    total = root
    for sk in ECONOMY_STAT_KEYS:
        entry = species.economy_stats.get(sk) or {}
        if not (isinstance(entry, dict) and entry.get("enabled")):
            continue
        rate_raw = entry.get("rate_per_point")
        if rate_raw is None:
            continue
        try:
            rate = float(rate_raw)
        except (TypeError, ValueError):
            continue
        if rate <= 0:
            continue
        pts = min(pts_ref, max(0, int(stat_points.get(sk, 0))))
        if pts <= 0:
            continue
        sub = int(round(pts * rate))
        total += sub
        breakdown.append(
            {
                "kind": "stat",
                "label": labels.get(sk, sk),
                "stat_key": sk,
                "points": pts,
                "multiplier": int(round(rate)),
                "subtotal": sub,
            }
        )
    if cap > 0 and total > cap:
        breakdown.append(
            {
                "kind": "cap",
                "label": f"Teto porte {species.size_class} ({cap:,} Âmbar)".replace(",", "."),
                "stat_key": None,
                "points": None,
                "multiplier": None,
                "subtotal": cap - total,
            }
        )
        total = cap
    total = max(root, total)
    breakdown.append(
        {
            "kind": "total",
            "label": "Valor sugerido total",
            "stat_key": None,
            "points": None,
            "multiplier": None,
            "subtotal": total,
            "size_cap": cap,
        }
    )
    return total, breakdown


def calculate_suggested_value(
    species: SpeciesEconomy,
    stat_points: dict[str, int],
) -> tuple[int, list[dict[str, Any]]]:
    """Valor sugerido — proporcional (padrão), custom ou legado por espécie."""
    mode_override = (species.pricing_mode or "").strip().lower()
    apply_economy_meta(species)
    if mode_override in ("legacy", "legacy_multipliers", "custom"):
        species.pricing_mode = mode_override
    root = int(species.root_value)
    cap = size_cap_for_class(species.size_class)
    mode = (species.pricing_mode or "proportional").strip().lower()
    if mode == "custom":
        return _calculate_custom_rates(species, stat_points, root=root, cap=cap)
    if mode in ("legacy", "legacy_multipliers"):
        return _calculate_legacy_multipliers(species, stat_points, root=root, cap=cap)
    return _calculate_proportional(species, stat_points, root=root, cap=cap)


def format_breakdown_text(breakdown: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for row in breakdown:
        kind = row.get("kind")
        if kind == "root":
            lines.append(f"{row['label']}: {row['subtotal']:,}".replace(",", "."))
        elif kind == "bonus_space":
            lines.append(f"{row['label']}: {row['subtotal']:,}".replace(",", "."))
        elif kind == "stat":
            lines.append(
                f"{row['label']}: {row['points']} pts × {row['multiplier']} = "
                f"{row['subtotal']:,}".replace(",", ".")
            )
        elif kind == "cap":
            lines.append(f"{row['label']}")
        elif kind == "total":
            lines.append(f"── Total: {row['subtotal']:,} Âmbar".replace(",", "."))
    return lines
