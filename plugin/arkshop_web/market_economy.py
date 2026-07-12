"""Economia do Mercado de Dinos — espécies, multiplicadores e cálculo de valor sugerido."""
from __future__ import annotations

import json
import shutil
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

def _bundled_defaults_path() -> Path:
    """Template empacotado — somente leitura no .exe (PyInstaller _MEIPASS)."""
    if getattr(sys, "frozen", False):
        bundled = Path(sys._MEIPASS) / "data" / "market_species_defaults.json"  # type: ignore[attr-defined]
        if bundled.is_file():
            return bundled
    return Path(__file__).resolve().parent / "data" / "market_species_defaults.json"


def _writable_data_dir() -> Path:
    """Diretório gravável para JSON de economia (paridade com settings.json da Web Store)."""
    try:
        from src.shop_integration import webstore_data_dir

        base = webstore_data_dir()
    except ImportError:
        base = Path(__file__).resolve().parent
    data = base / "data"
    data.mkdir(parents=True, exist_ok=True)
    return data


def _writable_defaults_path() -> Path:
    return _writable_data_dir() / "market_species_defaults.json"


def _ensure_defaults_file() -> Path:
    """Garante cópia gravável — no .exe o bundle _MEIPASS não aceita PATCH admin."""
    path = _writable_defaults_path()
    if path.is_file():
        return path
    bundled = _bundled_defaults_path()
    if bundled.is_file() and bundled.resolve() != path.resolve():
        shutil.copy2(bundled, path)
    elif not path.is_file():
        path.write_text(
            json.dumps({"species": [], "global_stat_labels": {}}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
    return path


# Tests podem monkeypatchar este path; produção usa _ensure_defaults_file().
_DEFAULTS_FILE: Path | None = None


def _defaults_file_path() -> Path:
    global _DEFAULTS_FILE
    if _DEFAULTS_FILE is None:
        _DEFAULTS_FILE = _ensure_defaults_file()
    return _DEFAULTS_FILE


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
    pricing_mode: str = "floor_quality"
    premium_budget: int = 0
    dino_role: str = "ataque"
    prestige_rank: int = 50
    commerce_channel: str = "market_p2p"

    def to_dict(self, *, include_multipliers: bool = True) -> dict[str, Any]:
        mode = (self.pricing_mode or "floor_quality").strip().lower()
        market_cap = load_market_absolute_max()
        bonus = (
            int(self.premium_budget)
            if mode == "floor_quality"
            else max(0, size_cap_for_class(self.size_class) - self.root_value)
        )
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
            "premium_budget": int(self.premium_budget),
            "dino_role": self.dino_role,
            "prestige_rank": int(self.prestige_rank),
            "commerce_channel": self.commerce_channel,
            "size_cap": market_cap if mode == "floor_quality" else size_cap_for_class(self.size_class),
            "bonus_space": bonus,
        }
        if include_multipliers:
            out["multipliers"] = {
                k: v.to_dict() for k, v in sorted(self.multipliers.items())
            }
        return out


def load_defaults_file() -> dict[str, Any]:
    path = _defaults_file_path()
    if not path.is_file():
        return {"species": [], "global_stat_labels": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def load_size_caps() -> dict[str, int]:
    raw = load_defaults_file().get("_size_caps") or {}
    return {
        "large": int(raw.get("large", 300_000)),
        "medium": int(raw.get("medium", 250_000)),
        "small": int(raw.get("small", 100_000)),
    }


_DEFAULT_TIER_MULTIPLIERS: dict[str, float] = {
    "S+": 12.0,
    "S": 10.0,
    "A": 10.0,
    "B": 8.0,
    "C": 6.0,
}


def load_price_ceiling_config() -> dict[str, Any]:
    """Configuração do teto máximo de preço de anúncio (multiplicador sobre valor sugerido)."""
    raw = load_defaults_file().get("_price_ceiling") or {}
    tier_raw = raw.get("tier_multipliers") or {}
    tier_multipliers: dict[str, float] = dict(_DEFAULT_TIER_MULTIPLIERS)
    for tier, mult in tier_raw.items():
        try:
            tier_multipliers[str(tier).strip().upper()] = max(1.0, float(mult))
        except (TypeError, ValueError):
            continue
    try:
        global_mult = max(1.0, float(raw.get("global_multiplier", 10)))
    except (TypeError, ValueError):
        global_mult = 10.0
    try:
        absolute_max = int(raw.get("absolute_max", 500_000))
    except (TypeError, ValueError):
        absolute_max = 500_000
    return {
        "enabled": bool(raw.get("enabled", True)),
        "global_multiplier": global_mult,
        "tier_multipliers": tier_multipliers,
        "absolute_max": max(0, absolute_max),
    }


def calculate_listing_price_ceiling(
    suggested_value: int,
    *,
    tier: str | None = None,
    size_class: str | None = None,
) -> int:
    """Teto de preço de anúncio: min(sugerido × mult tier, teto porte, absolute_max)."""
    suggested = max(0, int(suggested_value or 0))
    cfg = load_price_ceiling_config()
    if not cfg["enabled"] or suggested <= 0:
        return max(suggested, int(cfg.get("absolute_max") or 0))

    tier_key = str(tier or "B").strip().upper()
    mult = float(cfg["tier_multipliers"].get(tier_key, cfg["global_multiplier"]))
    ceiling = int(suggested * mult)
    porte_cap = size_cap_for_class(size_class or "medium")
    ceiling = min(ceiling, porte_cap)
    abs_max = int(cfg.get("absolute_max") or 0)
    if abs_max > 0:
        ceiling = min(ceiling, abs_max)
    return max(suggested, ceiling)


def format_price_ceiling_error(
    price: int,
    suggested: int,
    ceiling: int,
    *,
    tier: str | None = None,
) -> str:
    """Mensagem PT-BR para preço acima do teto."""
    tier_txt = f" (tier {tier})" if tier else ""
    return (
        f"Preço máximo permitido: {ceiling:,} Âmbar{tier_txt} "
        f"(sugerido {suggested:,} Âmbar; você informou {price:,} Âmbar)"
    ).replace(",", ".")


def load_pts_reference() -> int:
    try:
        return max(1, int(load_defaults_file().get("_pts_reference") or 254))
    except (TypeError, ValueError):
        return 254


def _ladder_file_path() -> Path:
    if getattr(sys, "frozen", False):
        bundled = Path(sys._MEIPASS) / "data" / "species_root_ladder.json"  # type: ignore[attr-defined]
        if bundled.is_file():
            return bundled
    return Path(__file__).resolve().parent / "data" / "species_root_ladder.json"


def load_species_root_ladder() -> dict[str, Any]:
    path = _ladder_file_path()
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_floor_quality_config() -> dict[str, Any]:
    raw = load_defaults_file().get("_floor_quality") or {}
    ladder = load_species_root_ladder()
    try:
        gamma = float(raw.get("gamma", ladder.get("gamma", 0.82)))
    except (TypeError, ValueError):
        gamma = 0.82
    return {
        "enabled": bool(raw.get("enabled", True)),
        "gamma": max(0.1, min(1.0, gamma)),
        "market_absolute_max": load_market_absolute_max(),
        "encomenda_absolute_max": load_encomenda_absolute_max(),
        "encomenda_alpha": float(raw.get("encomenda_alpha", ladder.get("encomenda_alpha", 0.25))),
        "encomenda_beta": float(raw.get("encomenda_beta", ladder.get("encomenda_beta", 0.35))),
        "role_stat_weights": load_role_stat_weights(),
    }


def load_market_absolute_max() -> int:
    raw = load_defaults_file().get("_floor_quality") or {}
    ladder = load_species_root_ladder()
    try:
        return max(1, int(raw.get("market_absolute_max", ladder.get("market_absolute_max", 150_000))))
    except (TypeError, ValueError):
        return 150_000


def load_encomenda_absolute_max() -> int:
    raw = load_defaults_file().get("_floor_quality") or {}
    ladder = load_species_root_ladder()
    try:
        return max(1, int(raw.get("encomenda_absolute_max", ladder.get("encomenda_absolute_max", 275_000))))
    except (TypeError, ValueError):
        return 275_000


def load_role_stat_weights() -> dict[str, dict[str, float]]:
    raw = load_defaults_file().get("_role_stat_weights") or {}
    ladder = load_species_root_ladder()
    defaults = dict(ladder.get("role_stat_weights") or {})
    out: dict[str, dict[str, float]] = {}
    roles = set(defaults) | set(raw)
    for role in roles:
        base = dict(defaults.get(role) or {})
        role_raw = raw.get(role) or {}
        weights: dict[str, float] = {}
        for sk in ECONOMY_STAT_KEYS + ("food",):
            try:
                weights[sk] = float(role_raw.get(sk, base.get(sk, 0.0)))
            except (TypeError, ValueError):
                weights[sk] = float(base.get(sk, 0.0))
        total = sum(weights.values()) or 1.0
        out[str(role)] = {sk: weights[sk] / total for sk in weights}
    return out


def blueprint_short_key(bp: str | None) -> str:
    bp = normalize_blueprint(bp)
    if not bp:
        return ""
    return bp.rsplit("/", 1)[-1].split(".")[0]


def resolve_species_by_blueprint(blueprint: str | None) -> dict[str, Any] | None:
    """Lookup espécie canônica por blueprint_path normalizado."""
    bp_norm = normalize_blueprint(blueprint)
    if not bp_norm:
        return None
    for sk, defn in load_default_species_map().items():
        paths = [str(defn.get("blueprint_path") or "")]
        for alias in defn.get("blueprint_aliases") or []:
            if isinstance(alias, dict):
                paths.append(str(alias.get("blueprint_path") or ""))
            elif isinstance(alias, str):
                paths.append(alias)
        for path in paths:
            if normalize_blueprint(path) == bp_norm:
                return defn
    ladder = load_species_root_ladder()
    override = (ladder.get("blueprint_overrides") or {}).get(blueprint_short_key(blueprint))
    if override and override.get("species_key"):
        return load_default_species_map().get(str(override["species_key"]))
    return None


def calculate_quality_index(
    stat_points: dict[str, int],
    *,
    dino_role: str,
    gamma: float | None = None,
) -> tuple[float, list[dict[str, Any]]]:
    """Índice Q ∈ [0, 1] agregando stats breedáveis com retornos decrescentes."""
    cfg = load_floor_quality_config()
    g = float(gamma if gamma is not None else cfg["gamma"])
    weights = cfg["role_stat_weights"].get(str(dino_role or "ataque")) or cfg["role_stat_weights"].get(
        "ataque", {}
    )
    pts_ref = load_pts_reference()
    labels = stat_labels()
    parts: list[dict[str, Any]] = []
    weighted_sum = 0.0
    weight_total = 0.0
    for sk in ECONOMY_STAT_KEYS:
        w = float(weights.get(sk, 0.0))
        if w <= 0:
            continue
        pts = min(pts_ref, max(0, int(stat_points.get(sk, 0))))
        q_s = (pts / pts_ref) ** g if pts_ref else 0.0
        weighted_sum += w * q_s
        weight_total += w
        parts.append(
            {
                "stat_key": sk,
                "label": labels.get(sk, sk),
                "points": pts,
                "q_stat": round(q_s, 4),
                "weight_pct": round(w * 100, 1),
            }
        )
    q = weighted_sum / weight_total if weight_total else 0.0
    return min(1.0, max(0.0, q)), parts


def calculate_encomenda_value(
    species: SpeciesEconomy,
    market_value: int,
    *,
    color_component: int = 0,
) -> int:
    """Valor de encomenda com taxas de serviço e teto global."""
    cfg = load_floor_quality_config()
    r = int(species.root_value)
    alpha = float(cfg["encomenda_alpha"])
    beta = float(cfg["encomenda_beta"])
    base_surcharge = round(r * alpha)
    service_premium = round((market_value + color_component) * beta)
    total = market_value + color_component + base_surcharge + service_premium
    floor = max(market_value, r)
    cap = load_encomenda_absolute_max()
    return max(floor, min(total, cap))


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
        "pricing_mode": str(defn.get("pricing_mode") or "floor_quality"),
        "premium_budget": int(defn.get("premium_budget") or 0),
        "dino_role": str(defn.get("dino_role") or "ataque"),
        "prestige_rank": int(defn.get("prestige_rank") or 50),
        "commerce_channel": str(defn.get("commerce_channel") or "market_p2p"),
    }


def apply_economy_meta(species: "SpeciesEconomy") -> "SpeciesEconomy":
    meta = species_economy_meta_from_defaults(species.species_key)
    species.diet_class = meta["diet_class"]
    species.size_class = meta["size_class"]
    species.economy_stats = meta["economy_stats"]
    species.pricing_mode = meta["pricing_mode"]
    species.premium_budget = int(meta["premium_budget"])
    species.dino_role = meta["dino_role"]
    species.prestige_rank = int(meta["prestige_rank"])
    species.commerce_channel = meta["commerce_channel"]
    return species


def save_defaults_file(data: dict[str, Any]) -> None:
    path = _defaults_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
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
    if "price_ceiling" in updates:
        pc = updates["price_ceiling"] or {}
        existing = dict(data.get("_price_ceiling") or {})
        if "enabled" in pc:
            existing["enabled"] = bool(pc["enabled"])
        if "global_multiplier" in pc:
            existing["global_multiplier"] = max(1.0, float(pc["global_multiplier"]))
        if "absolute_max" in pc:
            existing["absolute_max"] = max(0, int(pc["absolute_max"]))
        if "tier_multipliers" in pc and isinstance(pc["tier_multipliers"], dict):
            tier_map = dict(existing.get("tier_multipliers") or {})
            for tier, mult in pc["tier_multipliers"].items():
                tier_map[str(tier).strip().upper()] = max(1.0, float(mult))
            existing["tier_multipliers"] = tier_map
        data["_price_ceiling"] = existing
    if "floor_quality" in updates:
        fq = updates["floor_quality"] or {}
        existing_fq = dict(data.get("_floor_quality") or {})
        for key in (
            "enabled",
            "gamma",
            "market_absolute_max",
            "encomenda_absolute_max",
            "encomenda_alpha",
            "encomenda_beta",
        ):
            if key in fq:
                existing_fq[key] = fq[key]
        data["_floor_quality"] = existing_fq
    if "role_stat_weights" in updates and isinstance(updates["role_stat_weights"], dict):
        data["_role_stat_weights"] = updates["role_stat_weights"]
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
    if "dino_role" in updates:
        target["dino_role"] = str(updates["dino_role"])
    if "premium_budget" in updates:
        target["premium_budget"] = int(updates["premium_budget"])
    if "prestige_rank" in updates:
        target["prestige_rank"] = int(updates["prestige_rank"])
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
                "premium_budget": int(defn.get("premium_budget") or 0),
                "dino_role": defn.get("dino_role") or "ataque",
                "prestige_rank": int(defn.get("prestige_rank") or 50),
                "commerce_channel": defn.get("commerce_channel") or "market_p2p",
                **meta,
                "size_cap": load_market_absolute_max()
                if (meta.get("pricing_mode") or "floor_quality") == "floor_quality"
                else size_cap_for_class(meta["size_class"]),
                "bonus_space": int(defn.get("premium_budget") or 0)
                if (meta.get("pricing_mode") or "floor_quality") == "floor_quality"
                else max(
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
    encomenda = calculate_encomenda_value(species, total)
    return {
        "species_key": species_key,
        "computed_base_value": total,
        "encomenda_value": encomenda,
        "calculation_breakdown": breakdown,
        "species": species.to_dict(include_multipliers=False),
        "stat_points": points,
    }


def load_economy_global_config() -> dict[str, Any]:
    fq = load_floor_quality_config()
    return {
        "floor_quality": fq,
        "market_absolute_max": fq["market_absolute_max"],
        "encomenda_absolute_max": fq["encomenda_absolute_max"],
        "size_caps": load_size_caps(),
        "pts_reference": load_pts_reference(),
        "stat_weights": load_stat_weights(),
        "role_stat_weights": fq["role_stat_weights"],
        "tier_legend": load_tier_legend(),
        "price_ceiling": load_price_ceiling_config(),
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


def build_blueprint_economy_map() -> dict[str, dict[str, Any]]:
    """blueprint_norm → definição econômica canônica."""
    out: dict[str, dict[str, Any]] = {}
    for sk, defn in load_default_species_map().items():
        paths = [str(defn.get("blueprint_path") or "")]
        for alias in defn.get("blueprint_aliases") or []:
            if isinstance(alias, dict):
                paths.append(str(alias.get("blueprint_path") or ""))
            elif isinstance(alias, str):
                paths.append(alias)
        for path in paths:
            nb = normalize_blueprint(path)
            if nb:
                out[nb] = defn
    return out


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


# L200 = 40% do valor de mercado full-254 (Q=1). Aprovado Jul/2026 (opção A).
# V254 = min(R + B, market_absolute_max); P200 = round(0.40 × V254).
L200_OF_V254_RATIO: float = 0.40
L200_ID_SUFFIX: str = "_l200"
# Kits breeding pack10: 25% off vs preço unitário L1 (paga 75% do retail).
BREEDING_KIT_PAY_RATIO: float = 0.75


def is_catalog_dino_level1(entry: dict[str, Any]) -> bool:
    """True se Type:dino e primeiro Dinos[].Level == 1 (referência de piso)."""
    if str(entry.get("Type") or "").lower() != "dino":
        return False
    dino = (entry.get("Dinos") or [{}])[0]
    return int(dino.get("Level") or 1) == 1


def is_catalog_dino_level200(entry: dict[str, Any]) -> bool:
    """True se Type:dino e primeiro Dinos[].Level == 200."""
    if str(entry.get("Type") or "").lower() != "dino":
        return False
    dino = (entry.get("Dinos") or [{}])[0]
    return int(dino.get("Level") or 0) == 200


def catalog_dino_level(entry: dict[str, Any]) -> int:
    dino = (entry.get("Dinos") or [{}])[0]
    return int(dino.get("Level") or 1)


def l200_shop_id(l1_item_id: str) -> str:
    """ID de loja para o par L200 (`rex_femea` → `rex_femea_l200`)."""
    base = str(l1_item_id or "").strip()
    if base.endswith(L200_ID_SUFFIX):
        return base
    return f"{base}{L200_ID_SUFFIX}"


def compute_v254(
    root_value: int,
    premium_budget: int,
    market_absolute_max: int | None = None,
) -> int:
    """Valor de mercado full-254 (Q=1): ``min(R + B, market_absolute_max)``."""
    cap = (
        int(market_absolute_max)
        if market_absolute_max is not None
        else int(load_market_absolute_max())
    )
    r = max(0, int(root_value))
    b = max(0, int(premium_budget))
    return min(r + b, max(1, cap))


def compute_l200_price(
    p1: int,
    root_value: int,
    premium_budget: int,
    *,
    market_absolute_max: int | None = None,
    ratio: float = L200_OF_V254_RATIO,
) -> int | None:
    """Preço L200 a partir de R+B (valor full-254) e do L1.

    Fórmula aprovada (Jul/2026): ``P200 = round(ratio × V254)`` com
    ``V254 = min(R + B, market_absolute_max)`` e ``ratio`` default ``0.40``.
    Devolve ``None`` (skip / não listar) quando ``P200 <= P1``.
    """
    p1_i = int(p1)
    if p1_i < 0:
        return None
    v254 = compute_v254(root_value, premium_budget, market_absolute_max)
    if v254 <= 0:
        return None
    p200 = int(round(float(ratio) * float(v254)))
    if p200 <= p1_i:
        return None
    return p200


def resolve_species_root_value(l1_item_id: str, entry: dict[str, Any] | None = None) -> int | None:
    """R = root_value da espécie em market_species_defaults (opção A)."""
    catalog_map = build_catalog_economy_map()
    defn = catalog_map.get(str(l1_item_id))
    if defn is not None and defn.get("root_value") is not None:
        return int(defn.get("root_value") or 0)
    if entry is not None:
        # fallback fraco: Price L1 (só se defaults em falta)
        price = entry.get("Price")
        if price is not None:
            return int(price)
    return None


def resolve_species_premium_budget(
    l1_item_id: str, entry: dict[str, Any] | None = None
) -> int | None:
    """B = premium_budget da espécie em market_species_defaults."""
    _ = entry  # API simétrica a resolve_species_root_value; B só vem dos defaults
    catalog_map = build_catalog_economy_map()
    defn = catalog_map.get(str(l1_item_id))
    if defn is None:
        return None
    if defn.get("premium_budget") is not None:
        return max(0, int(defn.get("premium_budget") or 0))
    return 0


def sync_catalog_l1_prices_from_root(catalog: dict[str, Any]) -> dict[str, Any]:
    """Opção A: ``Items[L1].Price = root_value`` para cada dino ligado aos defaults."""
    catalog_map = build_catalog_economy_map()
    changed: list[dict[str, Any]] = []
    unchanged: list[str] = []
    skipped: list[dict[str, Any]] = []
    for l1_id, entry in iter_catalog_dinos(catalog, level1_only=True):
        defn = catalog_map.get(str(l1_id))
        if defn is None or defn.get("root_value") is None:
            skipped.append({"l1_id": l1_id, "reason": "missing_root_value"})
            continue
        root = int(defn.get("root_value") or 0)
        old = int(entry.get("Price") or 0)
        if old == root:
            unchanged.append(l1_id)
            continue
        entry["Price"] = root
        changed.append({"l1_id": l1_id, "old_price": old, "new_price": root})
    return {
        "ok": True,
        "changed": changed,
        "unchanged": unchanged,
        "skipped": skipped,
        "changed_count": len(changed),
        "unchanged_count": len(unchanged),
        "skipped_count": len(skipped),
    }


def is_breeding_pack_kit(kit_id: str, kit: dict[str, Any]) -> bool:
    """Kits pack10 de breeding (25% off vs L1 unitário) — não licenças alfa/beta/gamma."""
    kid = str(kit_id or "")
    if kid in {"kit_alfa", "kit_beta", "kit_gamma", "recursos", "starter", "starter2"}:
        return False
    if kid.endswith("_pack10"):
        return True
    desc = str(kit.get("Description") or "")
    return "25% off" in desc.lower()


def sync_breeding_kit_prices(catalog: dict[str, Any]) -> dict[str, Any]:
    """Recalcula preço dos kits breeding: ``round(n × P1 × 0.75)``."""
    items = catalog.get("Items") or catalog.get("ShopItems") or {}
    bp_to_l1: dict[str, tuple[str, int]] = {}
    for l1_id, entry in iter_catalog_dinos(catalog, level1_only=True):
        bp = normalize_blueprint(_catalog_item_blueprint(entry))
        if not bp:
            continue
        # Preferir o primeiro L1 visto; preços iguais após sync root
        bp_to_l1.setdefault(bp, (l1_id, int(entry.get("Price") or 0)))

    kits = catalog.get("Kits") or {}
    changed: list[dict[str, Any]] = []
    unchanged: list[str] = []
    skipped: list[dict[str, Any]] = []
    for kit_id, kit in list(kits.items()):
        if not isinstance(kit, dict) or not is_breeding_pack_kit(kit_id, kit):
            continue
        dinos = kit.get("Dinos") or []
        if not dinos:
            skipped.append({"kit_id": kit_id, "reason": "no_dinos"})
            continue
        bp = normalize_blueprint(str((dinos[0] or {}).get("Blueprint") or ""))
        if not bp or bp not in bp_to_l1:
            skipped.append({"kit_id": kit_id, "reason": "no_l1_match", "blueprint": bp})
            continue
        l1_id, p1 = bp_to_l1[bp]
        n = len(dinos)
        new_price = int(round(float(n) * float(p1) * float(BREEDING_KIT_PAY_RATIO)))
        old = int(kit.get("Price") or 0)
        if old == new_price:
            unchanged.append(kit_id)
            continue
        kit["Price"] = new_price
        changed.append(
            {
                "kit_id": kit_id,
                "l1_id": l1_id,
                "n": n,
                "p1": p1,
                "old_price": old,
                "new_price": new_price,
            }
        )
    return {
        "ok": True,
        "changed": changed,
        "unchanged": unchanged,
        "skipped": skipped,
        "changed_count": len(changed),
        "unchanged_count": len(unchanged),
        "skipped_count": len(skipped),
    }


def iter_catalog_dinos(
    catalog: dict[str, Any],
    *,
    level1_only: bool = False,
    level200_only: bool = False,
) -> list[tuple[str, dict[str, Any]]]:
    items = catalog.get("Items") or catalog.get("ShopItems") or {}
    out: list[tuple[str, dict[str, Any]]] = []
    for item_id, entry in items.items():
        if str(entry.get("Type") or "").lower() != "dino":
            continue
        if level1_only and not is_catalog_dino_level1(entry):
            continue
        if level200_only and not is_catalog_dino_level200(entry):
            continue
        out.append((item_id, entry))
    out.sort(key=lambda x: -int(x[1].get("Price") or 0))
    return out


def iter_economy_groups(
    catalog: dict[str, Any],
    *,
    level1_only: bool = False,
) -> list[tuple[str, dict[str, Any], list[tuple[str, dict[str, Any]]]]]:
    """Agrupa itens Type:dino do catálogo por species_key econômico."""
    catalog_map = build_catalog_economy_map()
    grouped: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for item_id, entry in iter_catalog_dinos(catalog, level1_only=level1_only):
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


def _calculate_floor_quality(
    species: SpeciesEconomy,
    stat_points: dict[str, int],
    *,
    root: int,
) -> tuple[int, list[dict[str, Any]]]:
    """Piso R + orçamento B × índice Q — cap mercado global."""
    cfg = load_floor_quality_config()
    market_cap = int(cfg["market_absolute_max"])
    budget = int(species.premium_budget or 0)
    q, q_parts = calculate_quality_index(
        stat_points, dino_role=species.dino_role, gamma=cfg["gamma"]
    )
    premium = int(round(budget * q))
    total = min(root + premium, market_cap)
    breakdown: list[dict[str, Any]] = [
        {
            "kind": "root",
            "label": f"Piso L1 ({species.display_name})",
            "stat_key": None,
            "points": None,
            "multiplier": None,
            "subtotal": root,
            "pricing_mode": "floor_quality",
        },
        {
            "kind": "quality",
            "label": f"Índice Q ({species.dino_role})",
            "stat_key": None,
            "points": None,
            "multiplier": None,
            "subtotal": premium,
            "q_index": round(q, 4),
            "premium_budget": budget,
        },
    ]
    for part in q_parts:
        breakdown.append(
            {
                "kind": "stat",
                "label": part["label"],
                "stat_key": part["stat_key"],
                "points": part["points"],
                "multiplier": part["q_stat"],
                "weight_pct": part["weight_pct"],
                "subtotal": 0,
            }
        )
    if root + premium > market_cap:
        breakdown.append(
            {
                "kind": "cap",
                "label": f"Teto mercado ({market_cap:,} Âmbar)".replace(",", "."),
                "stat_key": None,
                "points": None,
                "multiplier": None,
                "subtotal": market_cap - (root + premium),
            }
        )
    total = max(root, total)
    breakdown.append(
        {
            "kind": "total",
            "label": "Valor sugerido total",
            "stat_key": None,
            "points": None,
            "multiplier": None,
            "subtotal": total,
            "market_cap": market_cap,
        }
    )
    return total, breakdown


def calculate_suggested_value(
    species: SpeciesEconomy,
    stat_points: dict[str, int],
) -> tuple[int, list[dict[str, Any]]]:
    """Valor sugerido — floor_quality (padrão), proporcional, custom ou legado."""
    mode_override = (species.pricing_mode or "").strip().lower()
    apply_economy_meta(species)
    if mode_override in ("legacy", "legacy_multipliers", "custom", "proportional", "floor_quality"):
        species.pricing_mode = mode_override
    root = int(species.root_value)
    mode = (species.pricing_mode or "floor_quality").strip().lower()
    if mode == "floor_quality":
        return _calculate_floor_quality(species, stat_points, root=root)
    cap = size_cap_for_class(species.size_class)
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


# ── Sync catálogo loja → market_species_defaults ──────────────────────────────

_DEFAULT_ECONOMY_STATS = {
    "health": {"enabled": True},
    "melee": {"enabled": True},
    "weight": {"enabled": True},
    "stamina": {"enabled": True},
    "speed": {"enabled": True},
}

# Variantes de loja que partilham o mesmo species_key econômico.
_CATALOG_SPECIES_GROUPS: dict[str, str] = {
    "meraxes_femea": "meraxes",
    "meraxes_scorched_femea": "meraxes",
    "meraxes_rockwell_femea": "meraxes",
    "meraxes_snow_femea": "meraxes",
    "tekstrider_femea": "tekstrider",
}


def _species_key_from_catalog_item_id(item_id: str) -> str:
    grouped = _CATALOG_SPECIES_GROUPS.get(item_id)
    if grouped:
        return grouped
    key = str(item_id or "").strip()
    if key.endswith("_femea"):
        key = key[: -len("_femea")]
    return key or item_id


def _infer_mod_source_from_blueprint(blueprint: str) -> str:
    inner = (blueprint or "").strip().lower()
    if "/game/mods/meraxes/" in inner:
        return "meraxes"
    if "/game/mods/funny_creatures/" in inner:
        return "brighamia"
    if "/game/mods/" in inner:
        parts = inner.split("/game/mods/", 1)[1].split("/")
        if parts and parts[0]:
            return parts[0].replace(" ", "_").lower()
    return "vanilla"


def _load_root_ladder() -> dict[str, Any]:
    path = _writable_data_dir() / "species_root_ladder.json"
    if not path.is_file():
        bundled = Path(__file__).resolve().parent / "data" / "species_root_ladder.json"
        path = bundled if bundled.is_file() else path
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _infer_tier_role_budget(price: int, species_key: str) -> dict[str, Any]:
    """Infere tier/role/premium_budget a partir do Price L1 e da ladder."""
    ladder = _load_root_ladder()
    anchors = ladder.get("anchors") or {}
    targets = ladder.get("mercado_254_targets") or {}
    anchor = anchors.get(species_key) or {}

    role = str(anchor.get("dino_role") or "").strip()
    tier = str(anchor.get("tier") or "").strip()
    prestige = int(anchor.get("prestige_rank") or 0)
    commerce = str(anchor.get("commerce_channel") or "market_p2p").strip() or "market_p2p"

    if not role or not tier:
        # Heurística por preço de loja (L1).
        if price >= 30000:
            role, tier, prestige = role or "boss", tier or "S+", prestige or 85
        elif price >= 15000:
            role, tier, prestige = role or "ataque", tier or "S", prestige or 70
        elif price >= 8000:
            role, tier, prestige = role or "ataque", tier or "A", prestige or 58
        elif price >= 4000:
            role, tier, prestige = role or "ataque", tier or "B", prestige or 48
        elif price >= 1500:
            role, tier, prestige = role or "utilitario", tier or "B", prestige or 40
        else:
            role, tier, prestige = role or "utilitario", tier or "C", prestige or 28

    role_targets = targets.get(role) or targets.get("ataque") or {}
    market_254 = int(role_targets.get(tier) or role_targets.get("A") or 75000)
    root = int(anchor.get("R") or price or 0)
    premium_budget = max(0, market_254 - root)

    breeding = {"S+": "extremo", "S": "muito alto", "A": "alto", "B": "moderado"}.get(
        tier, "basico"
    )
    return {
        "dino_role": role,
        "tier": tier,
        "prestige_rank": prestige or 50,
        "commerce_channel": commerce,
        "root_value": root,
        "premium_budget": premium_budget,
        "breeding_difficulty": breeding,
        "size_class": "large" if price >= 8000 else "medium",
    }


def _display_name_from_catalog_entry(item_id: str, entry: dict[str, Any]) -> str:
    raw = str(entry.get("Name") or entry.get("Description") or item_id).strip()
    # Remove tags de mod entre parênteses no fim primeiro.
    if raw.endswith(")") and "(" in raw:
        raw = raw[: raw.rfind("(")].strip()
    for suffix in (
        " Fêmea Nível 1",
        " Femea Nivel 1",
        " Nível 1",
        " Nivel 1",
        " Level 1",
    ):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)].strip()
    return raw or item_id


def find_catalog_dinos_missing_from_defaults(
    catalog: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """Itens Type:dino L1 da loja sem entrada nos defaults (por id ou blueprint)."""
    defaults = load_defaults_file()
    species = defaults.get("species") or []
    known_ids: set[str] = set()
    known_keys: set[str] = set()
    known_bps: set[str] = set()
    for s in species:
        sk = str(s.get("species_key") or "").strip()
        if sk:
            known_keys.add(sk)
        for cid in (
            [s.get("catalog_item_id"), s.get("reference_catalog_item_id")]
            + list(s.get("catalog_item_ids") or [])
        ):
            if cid:
                known_ids.add(str(cid))
        bp = normalize_blueprint(str(s.get("blueprint_path") or ""))
        if bp:
            known_bps.add(bp)
        for alias in s.get("blueprint_aliases") or []:
            path = alias if isinstance(alias, str) else (alias or {}).get("blueprint_path")
            nb = normalize_blueprint(str(path or ""))
            if nb:
                known_bps.add(nb)

    missing: list[tuple[str, dict[str, Any]]] = []
    for item_id, entry in iter_catalog_dinos(catalog, level1_only=True):
        bp = _catalog_item_blueprint(entry)
        nb = normalize_blueprint(bp)
        sk = _species_key_from_catalog_item_id(item_id)
        if item_id in known_ids or sk in known_keys or (nb and nb in known_bps):
            continue
        missing.append((item_id, entry))
    return missing


def build_defaults_stub_from_catalog_item(
    item_id: str,
    entry: dict[str, Any],
    *,
    siblings: list[tuple[str, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Cria entrada de market_species_defaults a partir de um item Type:dino da loja."""
    siblings = siblings or [(item_id, entry)]
    species_key = _species_key_from_catalog_item_id(item_id)
    primary_id, primary_entry = siblings[0]
    for cid, ent in siblings:
        if cid == item_id or _species_key_from_catalog_item_id(cid) == species_key:
            # Preferir o item "base" (sem variante no nome) como referência.
            if cid == f"{species_key}_femea" or cid == species_key:
                primary_id, primary_entry = cid, ent
                break

    bp = _catalog_item_blueprint(primary_entry)
    price = int(primary_entry.get("Price") or 0)
    meta = _infer_tier_role_budget(price, species_key)
    mod = _infer_mod_source_from_blueprint(bp)
    catalog_ids = [cid for cid, _ in siblings]
    aliases: list[dict[str, str]] = []
    for cid, ent in siblings:
        if cid == primary_id:
            continue
        abp = _catalog_item_blueprint(ent)
        if not abp:
            continue
        aliases.append(
            {
                "blueprint_path": abp,
                "variant_label": _display_name_from_catalog_entry(cid, ent),
            }
        )

    return {
        "species_key": species_key,
        "display_name": _display_name_from_catalog_entry(primary_id, primary_entry),
        "blueprint_path": bp,
        "catalog_item_id": primary_id,
        "reference_catalog_item_id": primary_id,
        "catalog_item_ids": catalog_ids,
        "root_value": int(meta["root_value"]),
        "premium_budget": int(meta["premium_budget"]),
        "tier": meta["tier"],
        "dino_role": meta["dino_role"],
        "prestige_rank": int(meta["prestige_rank"]),
        "commerce_channel": meta["commerce_channel"],
        "pricing_mode": "floor_quality",
        "diet_class": "carnivore",
        "size_class": meta["size_class"],
        "breeding_difficulty": meta["breeding_difficulty"],
        "breeding_notes": f"Auto-sync catálogo loja ({primary_id})",
        "mod_source": mod,
        "economy_stats": dict(_DEFAULT_ECONOMY_STATS),
        "blueprint_aliases": aliases,
    }


def ensure_catalog_species_in_defaults(
    catalog: dict[str, Any] | None = None,
    *,
    write: bool = True,
) -> dict[str, Any]:
    """Garante que todos os Type:dino L1 da loja existam em market_species_defaults.

    Não inventa blueprints — só usa o BP do config.json. Agrupa variantes conhecidas
    (ex.: Meraxes) no mesmo species_key.
    """
    if catalog is None:
        try:
            from app import _read_shop_config

            catalog = _read_shop_config()
        except Exception as exc:
            return {"ok": False, "error": str(exc), "added": 0, "species_keys": []}

    missing = find_catalog_dinos_missing_from_defaults(catalog)
    if not missing:
        return {"ok": True, "added": 0, "species_keys": [], "message": "defaults já cobrem o catálogo"}

    # Agrupar variantes (meraxes_*) antes de criar stubs.
    groups: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for item_id, entry in missing:
        sk = _species_key_from_catalog_item_id(item_id)
        groups.setdefault(sk, []).append((item_id, entry))

    data = load_defaults_file()
    species_list: list[dict[str, Any]] = list(data.get("species") or [])
    existing_keys = {str(s.get("species_key") or "") for s in species_list}
    added_keys: list[str] = []

    # Atualizar _mod_sources se necessário.
    mod_sources = dict(data.get("_mod_sources") or {})
    if "meraxes" not in mod_sources:
        mod_sources["meraxes"] = "BigAL's Meraxes Collection"
    data["_mod_sources"] = mod_sources

    for sk, items in sorted(groups.items()):
        if sk in existing_keys:
            # Espécie já existe — anexar catalog_item_ids em falta.
            for s in species_list:
                if str(s.get("species_key")) != sk:
                    continue
                ids = list(s.get("catalog_item_ids") or [])
                for cid, ent in items:
                    if cid not in ids:
                        ids.append(cid)
                    abp = _catalog_item_blueprint(ent)
                    if abp and normalize_blueprint(abp) != normalize_blueprint(
                        str(s.get("blueprint_path") or "")
                    ):
                        aliases = list(s.get("blueprint_aliases") or [])
                        aliases.append(
                            {
                                "blueprint_path": abp,
                                "variant_label": _display_name_from_catalog_entry(cid, ent),
                            }
                        )
                        s["blueprint_aliases"] = aliases
                s["catalog_item_ids"] = ids
                added_keys.append(sk)
                break
            continue
        stub = build_defaults_stub_from_catalog_item(items[0][0], items[0][1], siblings=items)
        species_list.append(stub)
        existing_keys.add(sk)
        added_keys.append(sk)

    species_list.sort(key=lambda s: str(s.get("display_name") or s.get("species_key") or "").lower())
    data["species"] = species_list
    if write:
        save_defaults_file(data)

    return {
        "ok": True,
        "added": len(added_keys),
        "species_keys": added_keys,
        "missing_catalog_items": [cid for cid, _ in missing],
    }
