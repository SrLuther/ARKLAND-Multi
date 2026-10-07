"""Economia do Mercado de Dinos — espécies, multiplicadores e cálculo de valor sugerido."""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
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

# Markup fixo sobre o subtotal da encomenda (após α/β, antes do teto).
ENCOMENDA_PRICE_MARKUP: float = 0.05

# Teto da tabela Economia (floor_quality). O teto antigo dessa tabela era 150000.
ECONOMY_TABLE_CAP: int = 600_000

# Afixos de variante tirados ao achar a família vanilla. Ordem: prefixo mais longo primeiro.
_VARIANT_PREFIXES: tuple[str, ...] = ("aby_", "pf_", "vn_", "ab_", "x_")
_VARIANT_SUFFIXES: tuple[str, ...] = ("_aberrante", "_aberrant", "_fabled", "_alpha")
_VARIANT_SEGMENTS: frozenset[str] = frozenset({"alpha", "fabled", "aberrante", "aberrant"})
_GENDER_KEY_SUFFIXES: tuple[str, ...] = ("_femea", "_macho", "_female", "_male")

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
    try:
        mtime = path.stat().st_mtime
        path_key = str(path.resolve())
    except OSError:
        mtime = -1.0
        path_key = str(path)
    cache = getattr(load_defaults_file, "_cache", None)
    if (
        isinstance(cache, dict)
        and cache.get("path") == path_key
        and cache.get("mtime") == mtime
        and isinstance(cache.get("data"), dict)
    ):
        return cache["data"]
    data = json.loads(path.read_text(encoding="utf-8"))
    load_defaults_file._cache = {"path": path_key, "mtime": mtime, "data": data}  # type: ignore[attr-defined]
    return data


def invalidate_defaults_cache() -> None:
    load_defaults_file._cache = None  # type: ignore[attr-defined]
    try:
        _bundled_species_map.cache_clear()
    except Exception:
        pass


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
    """Valor de encomenda com taxas de serviço, markup +5% e teto global."""
    cfg = load_floor_quality_config()
    r = int(species.root_value)
    alpha = float(cfg["encomenda_alpha"])
    beta = float(cfg["encomenda_beta"])
    base_surcharge = round(r * alpha)
    service_premium = round((market_value + color_component) * beta)
    subtotal = market_value + color_component + base_surcharge + service_premium
    markup = round(subtotal * ENCOMENDA_PRICE_MARKUP)
    total = subtotal + markup
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


def _pick_positive_int(*candidates: Any) -> int | None:
    for raw in candidates:
        if raw is None:
            continue
        try:
            val = int(raw)
        except (TypeError, ValueError):
            continue
        if val > 0:
            return val
    return None


def _merge_species_defn(*sources: dict[str, Any]) -> dict[str, Any]:
    """Mescla definições (esquerda → direita sobrescreve); B/floor_quality do bundle prevalece se o vivo for legado."""
    merged: dict[str, Any] = {}
    for src in sources:
        if not src:
            continue
        for key, val in src.items():
            if val in (None, "", [], {}):
                continue
            if key == "premium_budget":
                picked = _pick_positive_int(merged.get("premium_budget"), val)
                if picked is not None:
                    merged["premium_budget"] = picked
                else:
                    try:
                        merged["premium_budget"] = int(val)
                    except (TypeError, ValueError):
                        pass
                continue
            merged[key] = val
    return merged


def _prefer_bundled_floor_quality(merged: dict[str, Any], bundled: dict[str, Any]) -> dict[str, Any]:
    """Cópia WEBSTORE legada (proportional, sem B) não deve anular floor_quality do repo."""
    if not bundled:
        return merged
    b_bundled = int(bundled.get("premium_budget") or 0)
    if b_bundled <= 0:
        return merged
    out = dict(merged)
    b_now = int(out.get("premium_budget") or 0)
    if b_now <= 0:
        out["premium_budget"] = b_bundled
        b_now = b_bundled
    mode = str(out.get("pricing_mode") or "").strip().lower()
    # Legado: proportional sem orçamento próprio → restaurar floor_quality do bundle.
    if mode == "proportional":
        for field in ("pricing_mode", "dino_role", "prestige_rank", "commerce_channel"):
            if bundled.get(field) is not None:
                out[field] = bundled[field]
        out["premium_budget"] = max(b_bundled, b_now)
    return out


def _defn_by_blueprint_in_maps(
    blueprint: str | None,
    *maps: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    bp_norm = normalize_blueprint(blueprint)
    if not bp_norm:
        return {}
    for species_map in maps:
        if not species_map:
            continue
        for defn in species_map.values():
            paths = [str(defn.get("blueprint_path") or "")]
            for alias in defn.get("blueprint_aliases") or []:
                if isinstance(alias, dict):
                    paths.append(str(alias.get("blueprint_path") or ""))
                elif isinstance(alias, str):
                    paths.append(alias)
            for path in paths:
                if normalize_blueprint(path) == bp_norm:
                    return dict(defn)
    return {}


def _resolve_species_defaults_defn(
    species_key: str,
    *,
    blueprint_path: str | None = None,
) -> dict[str, Any]:
    """Resolve defaults com canonicalização + bundle + blueprint.

    Sem isto, espécie no DB com key fora do JSON fica B=0 em floor_quality
    e a cotação da encomenda cola no piso R mesmo com stats 254.
    """
    raw_key = str(species_key or "").strip()
    keys: list[str] = []
    if raw_key:
        keys.append(raw_key)
        try:
            canon = canonicalize_species_key(raw_key)
        except Exception:
            canon = ""
        if canon and canon not in keys:
            keys.append(canon)

    live_map = load_default_species_map()
    try:
        bundled = _bundled_species_map()
    except Exception:
        bundled = {}

    best: dict[str, Any] = {}
    best_bundled: dict[str, Any] = {}
    for key in keys:
        bdef = bundled.get(key) or {}
        ldef = live_map.get(key) or {}
        candidate = _prefer_bundled_floor_quality(_merge_species_defn(bdef, ldef), bdef)
        if not candidate:
            continue
        if int(candidate.get("premium_budget") or 0) > int(best.get("premium_budget") or 0):
            best = candidate
            best_bundled = bdef
        elif not best:
            best = candidate
            best_bundled = bdef

    if int(best.get("premium_budget") or 0) <= 0 and blueprint_path:
        by_bp = _defn_by_blueprint_in_maps(blueprint_path, bundled, live_map)
        if by_bp:
            bp_key = str(by_bp.get("species_key") or "").strip()
            bdef = (bundled.get(bp_key) or {}) if bp_key else {}
            ldef = (live_map.get(bp_key) or {}) if bp_key else {}
            # by_bp pode já ser a def bundled completa
            candidate = _prefer_bundled_floor_quality(
                _merge_species_defn(bdef or by_bp, ldef, by_bp),
                bdef or by_bp,
            )
            if int(candidate.get("premium_budget") or 0) > int(best.get("premium_budget") or 0):
                best = candidate
            elif not best:
                best = candidate

    if best and best_bundled:
        best = _prefer_bundled_floor_quality(best, best_bundled)
    return best


def species_economy_meta_from_defaults(
    species_key: str,
    *,
    blueprint_path: str | None = None,
) -> dict[str, Any]:
    defn = _resolve_species_defaults_defn(species_key, blueprint_path=blueprint_path)
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
    meta = species_economy_meta_from_defaults(
        species.species_key,
        blueprint_path=getattr(species, "blueprint_path", None) or None,
    )
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
    invalidate_defaults_cache()


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


def _catalog_items_dict(catalog: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(catalog, dict):
        return {}
    items = catalog.get("Items") or catalog.get("ShopItems") or {}
    return items if isinstance(items, dict) else {}


def _l1_shop_price(
    defn: dict[str, Any],
    items: list[tuple[str, dict[str, Any]]],
    species_key: str,
) -> int | None:
    """Price do item Type:dino nível 1. Sem L1, não há piso — não usar o preço L200."""
    l1 = [(iid, entry) for iid, entry in items if is_catalog_dino_level1(entry)]
    if not l1:
        return None
    by_id = {iid: entry for iid, entry in l1}
    preferred = [
        str(defn.get("reference_catalog_item_id") or ""),
        str(defn.get("catalog_item_id") or ""),
        species_key,
        f"{species_key}_femea" if species_key else "",
    ]
    for rid in preferred:
        if rid and rid in by_id:
            return int(by_id[rid].get("Price") or 0)
    _iid, entry = sorted(l1, key=lambda pair: pair[0])[0]
    return int(entry.get("Price") or 0)


def _resolved_listing_defn(live: dict[str, Any], bundled: dict[str, Any]) -> dict[str, Any]:
    """Une a cópia gravável com o JSON do repo.

    Cache antigo (modo proportional, sem B) não zera o prêmio floor_quality.
    """
    live = live or {}
    bundled = bundled or {}
    if not live and not bundled:
        return {}
    merged = _prefer_bundled_floor_quality(_merge_species_defn(bundled, live), bundled)
    legacy = (
        str(live.get("pricing_mode") or "").strip().lower() == "proportional"
        and int(live.get("premium_budget") or 0) <= 0
    )
    if bundled and (not live or legacy):
        for field in (
            "tier",
            "blueprint_path",
            "catalog_item_id",
            "reference_catalog_item_id",
            "catalog_item_ids",
            "blueprint_aliases",
            "catalog_aliases",
            "species_key",
        ):
            bundled_val = bundled.get(field)
            if bundled_val not in (None, "", [], {}):
                merged[field] = bundled_val
    return merged


def _merged_economy_species_map() -> dict[str, dict[str, Any]]:
    bundled = _bundled_species_map()
    live = load_default_species_map()
    out: dict[str, dict[str, Any]] = {}
    for key in set(bundled) | set(live):
        resolved = _resolved_listing_defn(live.get(key) or {}, bundled.get(key) or {})
        sk = str(resolved.get("species_key") or key).strip()
        if sk:
            out[sk] = resolved
    return out


def _index_economy_defs(
    species_map: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_bp: dict[str, dict[str, Any]] = {}
    for sk, defn in species_map.items():
        if not isinstance(defn, dict):
            continue
        by_id[str(sk)] = defn
        ids: list[Any] = [
            defn.get("catalog_item_id"),
            defn.get("reference_catalog_item_id"),
            *(defn.get("catalog_item_ids") or []),
        ]
        for alias in defn.get("catalog_aliases") or []:
            if isinstance(alias, str):
                ids.append(alias)
            elif isinstance(alias, dict) and alias.get("catalog_item_id"):
                ids.append(alias["catalog_item_id"])
        for cid in ids:
            if cid:
                by_id[str(cid)] = defn
        paths = [str(defn.get("blueprint_path") or "")]
        for alias in defn.get("blueprint_aliases") or []:
            if isinstance(alias, str):
                paths.append(alias)
            elif isinstance(alias, dict):
                paths.append(str(alias.get("blueprint_path") or ""))
        for path in paths:
            nb = normalize_blueprint(path)
            if nb and nb not in by_bp:
                by_bp[nb] = defn
    return by_id, by_bp


def _group_catalog_dinos_for_economy(
    catalog: dict[str, Any],
) -> list[tuple[str, dict[str, Any], list[tuple[str, dict[str, Any]]]]]:
    """Agrupa Type:dino do catálogo da loja por species_key.

    Item id conhecido nos defaults ganha do blueprint. Espécie que só existe
    em market_species_defaults não entra.
    """
    species_map = _merged_economy_species_map()
    by_id, by_bp = _index_economy_defs(species_map)
    grouped: dict[str, dict[str, Any]] = {}
    for item_id, entry in iter_catalog_dinos(catalog, level1_only=False):
        defn = by_id.get(item_id)
        if not defn:
            nb = normalize_blueprint(_catalog_item_blueprint(entry))
            defn = by_bp.get(nb) if nb else None
        if defn and defn.get("species_key"):
            raw_key = str(defn.get("species_key") or "")
        else:
            raw_key = _species_key_from_catalog_item_id(item_id)
            defn = species_map.get(raw_key) or {}
        group_key = str(raw_key or item_id).strip()
        if not group_key:
            continue
        bucket = grouped.get(group_key)
        if bucket is None:
            bucket = {"defn": defn if isinstance(defn, dict) else {}, "items": []}
            grouped[group_key] = bucket
        elif not bucket["defn"] and defn:
            bucket["defn"] = defn
        bucket["items"].append((item_id, entry))
    return [(key, bucket["defn"] or {}, bucket["items"]) for key, bucket in grouped.items()]


def _economy_row_from_catalog_group(
    species_key: str,
    defn: dict[str, Any],
    items: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    """Legado do agrupamento por espécie (preço L1). A tabela usa a linha do catálogo."""
    defn = defn or {}
    has_defaults = bool(defn.get("species_key"))
    meta = (
        species_economy_meta_from_defaults(str(defn.get("species_key") or species_key))
        if has_defaults
        else {
            "diet_class": "",
            "size_class": "",
            "economy_stats": {},
            "pricing_mode": "floor_quality",
            "premium_budget": 0,
            "dino_role": "",
            "prestige_rank": 0,
            "commerce_channel": "market_p2p",
        }
    )
    mode = str(defn.get("pricing_mode") or meta.get("pricing_mode") or "floor_quality")
    # B é o prêmio do defaults. Não recalcular como teto − R (isso colava B em 150k − cache).
    premium = int(defn.get("premium_budget") or 0) if has_defaults else 0
    root_value = _l1_shop_price(defn, items, species_key)
    if mode == "floor_quality":
        size_cap = load_market_absolute_max()
        bonus_space = premium
    else:
        size_class = str(meta.get("size_class") or defn.get("size_class") or "medium")
        size_cap = size_cap_for_class(size_class)
        bonus_space = max(0, size_cap - int(root_value or 0))
    display = clean_species_display_name(str(defn.get("display_name") or ""))
    if not display:
        for _iid, entry in items:
            display = clean_species_display_name(str(entry.get("Name") or ""))
            if display:
                break
    if not display:
        display = species_key
    return {
        "species_key": species_key,
        "display_name": display,
        "tier": (defn.get("tier") if has_defaults else None) or "—",
        "root_value": root_value,
        "premium_budget": premium,
        "dino_role": str(defn.get("dino_role") or "") if has_defaults else "",
        "prestige_rank": int(defn.get("prestige_rank") or meta.get("prestige_rank") or 0),
        "commerce_channel": str(
            defn.get("commerce_channel") or meta.get("commerce_channel") or "market_p2p"
        ),
        "diet_class": meta.get("diet_class") or "",
        "size_class": meta.get("size_class") or "",
        "economy_stats": meta.get("economy_stats") or {},
        "pricing_mode": mode,
        "size_cap": size_cap,
        "bonus_space": bonus_space,
    }


def economy_line_level(entry: dict[str, Any] | None) -> int:
    """Nível da linha do catálogo. Ausente, inválido ou zero conta como 1."""
    dino: dict[str, Any] = {}
    if isinstance(entry, dict):
        dinos = entry.get("Dinos") or []
        if dinos and isinstance(dinos[0], dict):
            dino = dinos[0]
    raw = dino.get("Level")
    if raw is None or raw == "":
        return 1
    try:
        level = int(raw)
    except (TypeError, ValueError):
        return 1
    return level if level > 0 else 1


def economy_line_root(price: int, level: int) -> int:
    """R = preço daquela linha dividido pelo nível dela."""
    lvl = int(level or 0)
    if lvl <= 0:
        lvl = 1
    return max(0, int(price)) // lvl


def strip_economy_variant_key(raw: str | None) -> str:
    """Tira nível, gênero e afixos de variante para achar a família.

    Prefixos e sufixos: pf_, ab_, vn_, aby_, x_, alpha, fabled, aberrante.
    """
    key = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not key:
        return ""
    key = strip_level_key_suffix(key)
    for gender in _GENDER_KEY_SUFFIXES:
        if key.endswith(gender) and len(key) > len(gender):
            key = key[: -len(gender)]
            break
    changed = True
    while key and changed:
        changed = False
        for prefix in _VARIANT_PREFIXES:
            if key.startswith(prefix) and len(key) > len(prefix):
                key = key[len(prefix) :]
                changed = True
                break
        if changed:
            continue
        for suffix in _VARIANT_SUFFIXES:
            if key.endswith(suffix) and len(key) > len(suffix):
                key = key[: -len(suffix)]
                changed = True
                break
        if changed:
            continue
        parts = [part for part in key.split("_") if part]
        if len(parts) > 1 and any(part in _VARIANT_SEGMENTS for part in parts):
            key = "_".join(part for part in parts if part not in _VARIANT_SEGMENTS)
            changed = True
    return key.strip("_")


def _is_vanilla_family_defn(defn: dict[str, Any]) -> bool:
    source = str(defn.get("mod_source") or "").strip().lower()
    return source == "vanilla" or source.startswith("vanilla_")


def _vanilla_family_index(
    species_map: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for key, defn in species_map.items():
        if not isinstance(defn, dict) or not _is_vanilla_family_defn(defn):
            continue
        species_key = str(defn.get("species_key") or key).strip().lower()
        if species_key:
            out[species_key] = defn
    return out


def _match_vanilla_family(
    token: str,
    families: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Casa o token com a família vanilla. Abreviação única conta (ankylo = ankylosaurus)."""
    token = str(token or "").strip().lower()
    if not token or not families:
        return None
    if token in families:
        return families[token]
    alias = _SPECIES_KEY_ALIASES.get(token)
    if alias and alias in families:
        return families[alias]
    if len(token) >= 4:
        hits = [key for key in families if key.startswith(token)]
        if len(hits) == 1:
            return families[hits[0]]
    return None


def economy_quality_premium(
    role: str,
    tier: str,
    family_root: int,
    stored_premium: int,
) -> int:
    """B do piso de qualidade, pelo tier herdado.

    Usa o prêmio já gravado na família. Se ele for 0, B = alvo do tier − raiz
    da família (não o preço da linha, e não 0 só porque a variante perdeu o tier).
    """
    stored = max(0, int(stored_premium or 0))
    if stored > 0:
        return stored
    ladder = load_species_root_ladder()
    targets = (ladder.get("mercado_254_targets") or {}).get(str(role or "")) or {}
    try:
        target = int(targets.get(str(tier or "")) or 0)
    except (TypeError, ValueError):
        target = 0
    if target <= 0:
        return 0
    return max(0, target - max(0, int(family_root or 0)))


def _blueprint_creature_token(entry: dict[str, Any]) -> str:
    short = blueprint_short_key(_catalog_item_blueprint(entry))
    if short.endswith("_character_bp"):
        short = short[: -len("_character_bp")]
    return short


def _lookup_vanilla_family_for_line(
    item_id: str,
    species_key: str,
    entry: dict[str, Any],
    families: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    seen: set[str] = set()
    for raw in (item_id, species_key, _blueprint_creature_token(entry)):
        text = str(raw or "").strip().lower()
        if not text or text in seen:
            continue
        seen.add(text)
        stripped = strip_economy_variant_key(text)
        if not stripped:
            continue
        hit = _match_vanilla_family(stripped, families)
        if hit:
            return hit
    return None


def _resolve_catalog_dino_defn(
    item_id: str,
    entry: dict[str, Any],
    species_map: dict[str, dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    by_bp: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    defn = by_id.get(item_id)
    if not defn:
        blueprint = normalize_blueprint(_catalog_item_blueprint(entry))
        defn = by_bp.get(blueprint) if blueprint else None
    if defn and defn.get("species_key"):
        raw_key = str(defn.get("species_key") or "")
    else:
        raw_key = _species_key_from_catalog_item_id(item_id)
        mapped = species_map.get(raw_key)
        if mapped:
            defn = mapped
        elif not isinstance(defn, dict):
            defn = {}
    species_key = str(raw_key or item_id).strip() or item_id
    return species_key, defn if isinstance(defn, dict) else {}


def _economy_line_display(
    entry: dict[str, Any],
    source: dict[str, Any],
    fallback: str,
) -> str:
    raw = str(entry.get("Name") or "").strip()
    if raw.endswith(")") and "(" in raw:
        raw = raw[: raw.rfind("(")].strip()
    if raw:
        return raw
    display = clean_species_display_name(str(source.get("display_name") or ""))
    return display or fallback


def _economy_row_from_catalog_line(
    item_id: str,
    entry: dict[str, Any],
    species_key: str,
    defn: dict[str, Any],
    families: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Uma linha do catálogo. R é o preço dela ÷ o nível dela. Não média, não só L1."""
    defn = defn or {}
    family = _lookup_vanilla_family_for_line(item_id, species_key, entry, families)
    source = family or defn
    has_source = bool(source.get("species_key"))
    if family:
        species_key = str(family.get("species_key") or species_key)
        role = str(family.get("dino_role") or "")
        tier = str(family.get("tier") or "") or "—"
        premium = economy_quality_premium(
            role,
            tier,
            int(family.get("root_value") or 0),
            int(family.get("premium_budget") or 0),
        )
    elif has_source:
        role = str(defn.get("dino_role") or "")
        tier = str(defn.get("tier") or "") or "—"
        premium = int(defn.get("premium_budget") or 0)
    else:
        role = ""
        tier = "—"
        premium = 0
    meta: dict[str, Any] = {}
    if has_source:
        meta = species_economy_meta_from_defaults(str(source.get("species_key") or species_key))
    level = economy_line_level(entry)
    shop_price = int(entry.get("Price") or 0)
    root_value = economy_line_root(shop_price, level)
    mode = str(source.get("pricing_mode") or meta.get("pricing_mode") or "floor_quality")
    if mode == "floor_quality":
        size_cap = ECONOMY_TABLE_CAP
        bonus_space = premium
    else:
        size_class = str(meta.get("size_class") or source.get("size_class") or "medium")
        size_cap = size_cap_for_class(size_class)
        bonus_space = max(0, size_cap - int(root_value or 0))
    display_name = _economy_line_display(entry, source, species_key)
    from primal_fear_secondary import primal_fear_secondary_fields

    family_root = int(family.get("root_value") or 0) if family else None
    family_name = (
        clean_species_display_name(str(family.get("display_name") or "")) or species_key
        if family
        else None
    )
    pf = primal_fear_secondary_fields(
        item_id=item_id,
        entry=entry,
        display_name=display_name,
        family_root=family_root,
        cap=ECONOMY_TABLE_CAP,
    )
    return {
        "species_key": species_key,
        "catalog_item_id": item_id,
        "reference_level": level,
        "shop_price": shop_price,
        "display_name": display_name,
        "tier": tier,
        "root_value": root_value,
        "premium_budget": premium,
        "dino_role": role,
        "prestige_rank": int(source.get("prestige_rank") or meta.get("prestige_rank") or 0),
        "commerce_channel": str(
            source.get("commerce_channel") or meta.get("commerce_channel") or "market_p2p"
        ),
        "diet_class": meta.get("diet_class") or "",
        "size_class": meta.get("size_class") or "",
        "economy_stats": meta.get("economy_stats") or {},
        "pricing_mode": mode,
        "size_cap": size_cap,
        "bonus_space": bonus_space,
        "pf_band": pf["pf_band"],
        "pf_index": pf["pf_index"],
        "pf_reference": pf["pf_reference"],
        "pf_mod": pf["pf_mod"],
        "pf_note": pf["pf_note"],
        "family_root": family_root,
        "family_name": family_name,
    }


def list_species_economy_meta(
    catalog: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Uma linha por Type:dino do catálogo da loja.

    R = Price daquela linha ÷ nível dela (nível ausente ou zero vale 1).
    Papel e tier de variante vêm da família vanilla, sem prefixo de mod.
    B é o prêmio floor_quality desse tier. Cap da tabela = 600000.
    Espécie que só existe em market_species_defaults não entra.
    Criatura sem família vanilla mantém a classificação que já tem.
    A referência PF é outra coluna: raiz da família × (M ÷ 5), teto 600000.
    Ela não multiplica R nem B.
    """
    if not _catalog_items_dict(catalog):
        return []
    species_map = _merged_economy_species_map()
    by_id, by_bp = _index_economy_defs(species_map)
    families = _vanilla_family_index(species_map)
    out = [
        _economy_row_from_catalog_line(item_id, entry, species_key, defn, families)
        for item_id, entry in iter_catalog_dinos(catalog)
        for species_key, defn in (_resolve_catalog_dino_defn(item_id, entry, species_map, by_id, by_bp),)
    ]
    out.sort(
        key=lambda row: (
            str(row.get("display_name") or "").casefold(),
            row["species_key"],
            str(row.get("catalog_item_id") or ""),
        )
    )
    return out


def attach_economy_db_status(
    species: list[dict[str, Any]],
    db_rows: dict[str, Any],
) -> list[dict[str, Any]]:
    """Grava o selo de status do MySQL sem substituir R nem B.

    O root_value antigo da tabela MarketSpecies não é o piso da loja, e
    recalcular B como cap − root inventava prêmio (ex.: 147.000).
    """
    for sp in species:
        row = db_rows.get(str(sp.get("species_key") or ""))
        if row is None:
            continue
        status = getattr(row, "status", None)
        if status is None and isinstance(row, dict):
            status = row.get("status")
        if status:
            sp["db_status"] = str(status)
    return species


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
    from primal_fear_secondary import primal_fear_base_ladder

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
        "pf_base": primal_fear_base_ladder(cap=ECONOMY_TABLE_CAP),
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
# Kits breeding pack10: 40% off vs preço unitário L1 (paga 60% do retail).
BREEDING_KIT_PAY_RATIO: float = 0.60


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
    """Kits pack10 de breeding (40% off / paga 60% vs L1 unitário) — não licenças alfa/beta/gamma."""
    kid = str(kit_id or "")
    if kid in {"kit_alfa", "kit_beta", "kit_gamma", "recursos", "starter", "starter2"}:
        return False
    if kid.endswith("_pack10"):
        return True
    desc = str(kit.get("Description") or "")
    dl = desc.lower()
    return "kit 10" in dl or "25% off" in dl or "40% off" in dl


def sync_breeding_kit_prices(catalog: dict[str, Any]) -> dict[str, Any]:
    """Recalcula preço dos kits breeding: ``round(n × P1 × 0.60)``."""
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
    """Agrupa itens Type:dino do catálogo por species_key econômico canônico."""
    catalog_map = build_catalog_economy_map()
    grouped: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for item_id, entry in iter_catalog_dinos(catalog, level1_only=level1_only):
        defn = catalog_map.get(item_id)
        raw_key = str((defn or {}).get("species_key") or item_id)
        group_key = canonicalize_species_key(raw_key) or raw_key
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

# Tokens/ids legados → species_key canônico dos defaults (ex.: class name ARK).
_SPECIES_KEY_ALIASES: dict[str, str] = {
    "lionfishlion": "lionfish",
    "shadowmane": "lionfish",
    "ankylo": "ankylosaurus",
    "argent": "argentavis",
}

# Sufixos de nível no id do catálogo (astrodelphis_1, sb_manticore_200, rex_l200).
_LEVEL_KEY_SUFFIXES: tuple[str, ...] = (L200_ID_SUFFIX, "_200", "_1")

# Qualquer nível (não só 200): «Rex Nível 50», «Rex Level 225»…
_LEVEL_SUFFIX_RE = re.compile(
    r"\s*(?:[Nn][ií]vel|Nivel|Level)\s*\d{1,4}\b",
    re.IGNORECASE,
)
# Sufixo de id gerado por tools/generate_dino_level_variants.py (`rex_l50`, `rex_femea_l225`).
_GENERIC_LEVEL_ID_RE = re.compile(r"_l\d{1,4}$", re.IGNORECASE)
_DISPLAY_LEVEL_SUFFIXES = (
    " Fêmea Nível 200",
    " Femea Nivel 200",
    " Fêmea Nível 1",
    " Femea Nivel 1",
    " Nível 200",
    " Nivel 200",
    " Level 200",
    " Nível 1",
    " Nivel 1",
    " Level 1",
)


def strip_level_key_suffix(species_key: str | None) -> str:
    """Remove sufixos de nível (_1, _200, _l200) e _femea do id de catálogo."""
    key = str(species_key or "").strip()
    if not key:
        return ""
    for suffix in _LEVEL_KEY_SUFFIXES:
        if key.endswith(suffix) and len(key) > len(suffix):
            key = key[: -len(suffix)]
            break
    else:
        stripped = _GENERIC_LEVEL_ID_RE.sub("", key)
        if stripped and stripped != key:
            key = stripped
    if key.endswith("_femea"):
        key = key[: -len("_femea")]
    return key


def clean_species_display_name(raw: str | None) -> str:
    """Remove tags de mod e sufixos «Nível 1/200» do nome de catálogo/loja."""
    text = str(raw or "").strip()
    if not text:
        return ""
    if text.endswith(")") and "(" in text:
        text = text[: text.rfind("(")].strip()
    for suffix in _DISPLAY_LEVEL_SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
            break
    text = _LEVEL_SUFFIX_RE.sub("", text).strip(" -–—\t")
    return text.strip()


def canonicalize_species_key(species_key: str | None) -> str:
    """Normaliza species_key / catalog id legado para a chave econômica canônica."""
    key = str(species_key or "").strip()
    if not key:
        return ""
    grouped = _CATALOG_SPECIES_GROUPS.get(key)
    if grouped:
        return grouped
    low = key.lower()
    if low in _SPECIES_KEY_ALIASES:
        return _SPECIES_KEY_ALIASES[low]
    key = strip_level_key_suffix(key)
    low = key.lower()
    if low in _SPECIES_KEY_ALIASES:
        return _SPECIES_KEY_ALIASES[low]
    defaults = load_default_species_map()
    if key in defaults:
        return key
    try:
        cem = build_catalog_economy_map()
        hit = cem.get(key) or cem.get(low)
        if hit and hit.get("species_key"):
            return str(hit["species_key"])
    except Exception:
        pass
    return key


def _looks_like_raw_species_label(
    label: str | None,
    species_key: str | None = None,
    *,
    also_reject: tuple[str, ...] | list[str] | None = None,
) -> bool:
    """True se o rótulo parece id técnico (sb_manticore_200) ou blueprint cru."""
    text = str(label or "").strip()
    if not text:
        return True
    try:
        from ark_species_registry import is_raw_blueprint_label

        if is_raw_blueprint_label(text):
            return True
    except Exception:
        pass
    low = text.lower()
    for candidate in (species_key, *(also_reject or ())):
        c = str(candidate or "").strip().lower()
        if c and low == c:
            return True
    # snake_case / ids de catálogo
    if " " not in text and "_" in text and text.isascii() and text == text.lower():
        return True
    # token compacto só minúsculas (ex.: «lionfish» devolvido como Name falho)
    if " " not in text and text.isascii() and text == text.lower() and text.isalnum():
        return True
    return False


@lru_cache(maxsize=1)
def _bundled_species_map() -> dict[str, dict[str, Any]]:
    """Mapa do JSON empacotado no repo — fallback quando a cópia gravável está desatualizada."""
    path = _bundled_defaults_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {
            str(s["species_key"]): s
            for s in (data.get("species") or [])
            if s.get("species_key")
        }
    except Exception:
        return {}


def _species_defn_for_display(species_key: str) -> dict[str, Any]:
    """Preferência: defaults graváveis → bundle do repo."""
    key = str(species_key or "").strip()
    if not key:
        return {}
    live = load_default_species_map().get(key) or {}
    if str(live.get("display_name") or "").strip():
        return live
    bundled = _bundled_species_map().get(key) or {}
    if bundled:
        # Mescla: mantém overrides vivos, preenche nome/ids do bundle
        merged = dict(bundled)
        merged.update({k: v for k, v in live.items() if v not in (None, "", [], {})})
        if not str(merged.get("display_name") or "").strip():
            merged["display_name"] = bundled.get("display_name")
        return merged
    return live


def friendly_species_display_name(
    species_key: str | None,
    *,
    fallback: str | None = None,
    catalog: dict[str, Any] | None = None,
) -> str:
    """Nome amigável para UI: defaults/catálogo primeiro; sem ids crus nem «Nível 200»."""
    sk = str(species_key or "").strip()
    canon = canonicalize_species_key(sk) if sk else ""
    defn = _species_defn_for_display(canon) or _species_defn_for_display(sk)
    reject_ids = tuple(
        x
        for x in (sk, canon, *(str(c) for c in (defn.get("catalog_item_ids") or []) if c))
        if x
    )
    from_defaults = clean_species_display_name(str(defn.get("display_name") or ""))
    if from_defaults and not _looks_like_raw_species_label(
        from_defaults, sk, also_reject=reject_ids
    ):
        return from_defaults

    catalog_ids: list[str] = []
    for cid in (
        defn.get("reference_catalog_item_id"),
        defn.get("catalog_item_id"),
        *(defn.get("catalog_item_ids") or []),
        f"{canon}_femea" if canon else "",
        f"{sk}_femea" if sk else "",
        sk,
        canon,
    ):
        c = str(cid or "").strip()
        if c and c not in catalog_ids:
            catalog_ids.append(c)

    shop = catalog
    if shop is None and catalog_ids:
        try:
            from app import _read_shop_config

            shop = _read_shop_config()
        except Exception:
            shop = None
    if shop:
        for cid in catalog_ids:
            label = shop_catalog_display_name(shop, cid)
            # shop_catalog_display_name devolve o próprio id quando o item não existe
            if not label or label.strip() == cid:
                continue
            cleaned = clean_species_display_name(label)
            if cleaned and not _looks_like_raw_species_label(
                cleaned, sk, also_reject=reject_ids
            ):
                return cleaned

    for candidate in (fallback, from_defaults):
        cleaned = clean_species_display_name(str(candidate or ""))
        if cleaned and not _looks_like_raw_species_label(
            cleaned, sk, also_reject=reject_ids
        ):
            return cleaned

    if from_defaults:
        return from_defaults
    cleaned_fb = clean_species_display_name(fallback)
    if cleaned_fb and not _looks_like_raw_species_label(cleaned_fb, sk, also_reject=reject_ids):
        return cleaned_fb
    return canon or sk


def _species_key_from_catalog_item_id(item_id: str) -> str:
    grouped = _CATALOG_SPECIES_GROUPS.get(item_id)
    if grouped:
        return grouped
    key = str(item_id or "").strip()
    low = key.lower()
    if low in _SPECIES_KEY_ALIASES:
        return _SPECIES_KEY_ALIASES[low]
    key = strip_level_key_suffix(key)
    low = key.lower()
    if low in _SPECIES_KEY_ALIASES:
        return _SPECIES_KEY_ALIASES[low]
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
    return clean_species_display_name(raw) or item_id


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


# ── Precificação travada do catálogo ─────────────────────────────────────────
# Preço de catálogo = 10.000 × (raiz da família ÷ 18.000) × índice.
# O nível não multiplica. Noxious usa o índice da Toxic. Fey usa o de Celestial/Demonic.
# Tek Strider, sem família e sem índice não recebem preço automático.

CATALOG_PRICE_ORIGIN: int = 10_000
REX_ROOT_RULER: int = 18_000
LOCKED_PTS_REFERENCE: int = 254
LOCKED_GAMMA: Decimal = Decimal("0.82")
LOCKED_ATTACK_WEIGHTS: dict[str, Decimal] = {
    "health": Decimal("0.35"),
    "melee": Decimal("0.45"),
    "weight": Decimal("0.10"),
    "stamina": Decimal("0.10"),
}
LOCKED_ENCOMENDA_ALPHA: Decimal = Decimal("0.25")
LOCKED_ENCOMENDA_BETA: Decimal = Decimal("0.35")
LOCKED_ENCOMENDA_MARKUP: Decimal = Decimal("1.05")
MEGALOSAURUS_P2P_BUDGET: int = 66_000

# Índices travados. Não são M ÷ 5.
_LOCKED_TIER_INDEX: dict[str, tuple[str, Decimal]] = {
    "vanilla": ("Vanilla", Decimal("0.75")),
    "toxic": ("Toxic", Decimal("2.25")),
    "noxious": ("Noxious", Decimal("2.25")),
    "alpha": ("Alpha", Decimal("3.75")),
    "elemental_basic": ("Elemental Basic", Decimal("5.625")),
    "apex": ("Apex", Decimal("7.5")),
    "elemental_advanced": ("Elemental Advanced", Decimal("10.5")),
    "fabled": ("Fabled", Decimal("12")),
    "omega": ("Omega", Decimal("9.75")),
    "celestial": ("Celestial", Decimal("20.625")),
    "demonic": ("Demonic", Decimal("20.625")),
    "fey": ("Fey", Decimal("20.625")),
    "chaos": ("Chaos", Decimal("30")),
    "spirit": ("Spirit", Decimal("30")),
    "primal_tek": ("Primal Tek", Decimal("9")),
}

# Segmentos tirados do nome para achar a família. Não são, sozinhos, um índice.
_FAMILY_DROP_TOKENS: frozenset[str] = frozenset({
    "pf", "ab", "vn", "aby", "x",
    "alpha", "alfa", "fabled", "apex", "toxic", "toxico", "noxious",
    "elemental", "omega", "celestial", "demonic", "demoniaco",
    "chaos", "caos", "spirit", "espirito", "fey",
    "aberrante", "aberrant", "aberration",
    "elder", "anciao", "malin", "buffoon",
    "corrupted", "corrupt", "miscellaneous",
    "primal", "tek", "bionic",
    "basic", "basico", "advanced", "avancado",
    "light", "dark", "luz", "trevas",
    "fire", "fogo", "ice", "gelo", "electric", "eletrico", "caustic", "caustico",
    "black", "negro",
    "shop", "femea", "macho", "female", "male",
})

_BOSS_TOKENS: frozenset[str] = frozenset({
    "boss", "bosses", "miniboss", "minibosses",
    "emperor", "empress", "guardian", "guardians",
    "colossus", "pikkon", "origins", "gods", "creators",
})

_UNPRICED_TIER_REASONS: tuple[tuple[str, str], ...] = (
    ("elder", "Elder não tem índice. Sem preço automático."),
    ("anciao", "Elder não tem índice. Sem preço automático."),
    ("malin", "Malin não tem índice. Sem preço automático."),
    ("buffoon", "Buffoon não tem índice. Sem preço automático."),
    ("corrupted", "Corrupted não tem índice. Sem preço automático."),
    ("corrupt", "Corrupted não tem índice. Sem preço automático."),
    ("miscellaneous", "Miscellaneous não tem índice. Sem preço automático."),
)

PROTECTED_CATALOG_BACKUP_NAMES: frozenset[str] = frozenset({
    "catalog.json.bak-antes-itens-pf",
    "catalog.json.bak-antes-ajuste-precos",
})

_FOLD_CHARS = str.maketrans({
    "á": "a", "à": "a", "ã": "a", "â": "a",
    "é": "e", "ê": "e",
    "í": "i",
    "ó": "o", "ô": "o", "õ": "o",
    "ú": "u",
    "ç": "c",
})


def _pricing_fold(text: str | None) -> str:
    return (text or "").strip().lower().translate(_FOLD_CHARS)


def _pricing_tokens(*parts: str | None) -> list[str]:
    tokens: list[str] = []
    for part in parts:
        tokens.extend(re.findall(r"[a-z0-9]+", _pricing_fold(part)))
    return tokens


def format_pt_int(value: int) -> str:
    return f"{int(value):,}".replace(",", ".")


def format_pt_decimal(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." not in text:
        return text
    whole, frac = text.split(".", 1)
    return f"{whole},{frac}"


def locked_round_half_up(value: Decimal) -> int:
    """Inteiro mais próximo. Empate no meio sobe (half up)."""
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def locked_catalog_price(family_root: int, index: Decimal) -> int:
    """10.000 × (raiz ÷ 18.000) × índice, em inteiro half up."""
    raw = (Decimal(CATALOG_PRICE_ORIGIN) * Decimal(int(family_root)) * index) / Decimal(REX_ROOT_RULER)
    return locked_round_half_up(raw)


def coefficient_label(family_root: int) -> str:
    """Rótulo do coeficiente. Se a divisão não fecha curto, mostra a fração."""
    root = int(family_root)
    coef = Decimal(root) / Decimal(REX_ROOT_RULER)
    short = coef.quantize(Decimal("0.0001"))
    if short == coef:
        return format_pt_decimal(coef)
    return f"{format_pt_int(root)} ÷ {format_pt_int(REX_ROOT_RULER)}"


def locked_attack_quality(stat_points: dict[str, int] | None) -> Decimal:
    """Q do papel ataque. Média ponderada de (pontos ÷ 254) ^ 0,82, limitada a 1."""
    points = stat_points or {}
    ref = Decimal(LOCKED_PTS_REFERENCE)
    weighted = Decimal(0)
    weight_total = Decimal(0)
    for key, weight in LOCKED_ATTACK_WEIGHTS.items():
        try:
            pts = Decimal(int(points.get(key) or 0))
        except (TypeError, ValueError):
            pts = Decimal(0)
        if pts < 0:
            pts = Decimal(0)
        weighted += weight * ((pts / ref) ** LOCKED_GAMMA)
        weight_total += weight
    if weight_total <= 0:
        return Decimal(0)
    quality = weighted / weight_total
    if quality > 1:
        return Decimal(1)
    if quality < 0:
        return Decimal(0)
    return quality


def locked_p2p_price(catalog_price: int, budget: int, stat_points: dict[str, int] | None) -> int:
    """P2P = preço de catálogo + arredondamento(B × Q). O nível não entra."""
    quality = locked_attack_quality(stat_points)
    addon = locked_round_half_up(Decimal(int(budget)) * quality)
    return int(catalog_price) + addon


def locked_color_amount(
    catalog_price: int,
    *,
    mode: str = "none",
    regions: int = 0,
) -> Decimal:
    """Fração do catálogo. none = 0. uniform = 8%. regions = 5% + 2% por região."""
    catalog = Decimal(int(catalog_price))
    kind = str(mode or "none").strip().lower()
    if kind == "uniform":
        return catalog * Decimal("0.08")
    if kind == "regions":
        count = max(0, int(regions))
        return catalog * (Decimal("0.05") + Decimal("0.02") * Decimal(count))
    return Decimal(0)


def locked_encomenda_price(
    catalog_price: int,
    p2p_price: int,
    *,
    color_mode: str = "none",
    regions: int = 0,
) -> int:
    """(P2P + cores + catálogo × 0,25 + (P2P + cores) × 0,35) × 1,05.

    Sem teto. Com catálogo positivo, fica acima do P2P dos mesmos status.
    """
    catalog = Decimal(int(catalog_price))
    p2p = Decimal(int(p2p_price))
    colors = locked_color_amount(catalog_price, mode=color_mode, regions=regions)
    total = (p2p + colors + catalog * LOCKED_ENCOMENDA_ALPHA + (p2p + colors) * LOCKED_ENCOMENDA_BETA) * LOCKED_ENCOMENDA_MARKUP
    return locked_round_half_up(total)


def locked_pricing_examples() -> dict[str, Any]:
    """Números de conferência. As raízes saem de market_species_defaults.json."""
    species = load_default_species_map()
    rex_root = int(species["rex"]["root_value"])
    giga_root = int(species["giga"]["root_value"])
    mega_root = int(species["megalosaurus"]["root_value"])
    mega_budget = int(species["megalosaurus"]["premium_budget"])
    vanilla = _LOCKED_TIER_INDEX["vanilla"][1]
    alpha = _LOCKED_TIER_INDEX["alpha"][1]
    fey = _LOCKED_TIER_INDEX["fey"][1]
    full = {"health": LOCKED_PTS_REFERENCE, "melee": LOCKED_PTS_REFERENCE, "weight": LOCKED_PTS_REFERENCE, "stamina": LOCKED_PTS_REFERENCE}
    mega_catalog = locked_catalog_price(mega_root, fey)
    mega_p2p = locked_p2p_price(mega_catalog, mega_budget, full)
    return {
        "rex_root": rex_root,
        "giga_root": giga_root,
        "megalosaurus_root": mega_root,
        "megalosaurus_budget": mega_budget,
        "rex_vanilla": locked_catalog_price(rex_root, vanilla),
        "rex_alpha": locked_catalog_price(rex_root, alpha),
        "giga_vanilla": locked_catalog_price(giga_root, vanilla),
        "giga_alpha": locked_catalog_price(giga_root, alpha),
        "utility_root_800_alpha": locked_catalog_price(800, alpha),
        "megalosaurus_fey_catalog": mega_catalog,
        "megalosaurus_fey_p2p": mega_p2p,
        "megalosaurus_fey_encomenda": locked_encomenda_price(mega_catalog, mega_p2p),
        "noxious_index": format(_LOCKED_TIER_INDEX["noxious"][1], "f"),
        "toxic_index": format(_LOCKED_TIER_INDEX["toxic"][1], "f"),
        "fey_index": format(_LOCKED_TIER_INDEX["fey"][1], "f"),
        "celestial_index": format(_LOCKED_TIER_INDEX["celestial"][1], "f"),
        "demonic_index": format(_LOCKED_TIER_INDEX["demonic"][1], "f"),
    }


def _family_token(text: str | None) -> str:
    kept: list[str] = []
    for token in _pricing_tokens(text):
        if token in _FAMILY_DROP_TOKENS:
            continue
        if re.fullmatch(r"l?\d+", token):
            continue
        kept.append(token)
    return "_".join(kept)


def _locked_family_index() -> dict[str, dict[str, Any]]:
    """Famílias com raiz gravada. A chave é o species_key dos defaults."""
    out: dict[str, dict[str, Any]] = {}
    for key, defn in load_default_species_map().items():
        if not isinstance(defn, dict):
            continue
        try:
            root = int(defn.get("root_value") or 0)
        except (TypeError, ValueError):
            continue
        if root <= 0:
            continue
        species_key = str(defn.get("species_key") or key).strip().lower()
        if species_key:
            out[species_key] = defn
    return out


def _match_locked_family(token: str, families: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    token = str(token or "").strip().lower()
    if not token or not families:
        return None
    if token in families:
        return families[token]
    alias = _SPECIES_KEY_ALIASES.get(token)
    if alias and alias in families:
        return families[alias]
    if len(token) >= 4:
        hits = [key for key in families if key.startswith(token)]
        if len(hits) == 1:
            return families[hits[0]]
    return None


def _lookup_locked_family(
    item_id: str,
    entry: dict[str, Any],
    display_name: str,
    families: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    blueprint = _catalog_item_blueprint(entry)
    short = blueprint_short_key(blueprint)
    if short.endswith("_character_bp"):
        short = short[: -len("_character_bp")]
    for raw in (item_id, short, display_name):
        token = _family_token(raw)
        hit = _match_locked_family(token, families)
        if hit:
            return hit
    resolved = resolve_species_by_blueprint(blueprint)
    if isinstance(resolved, dict):
        try:
            root = int(resolved.get("root_value") or 0)
        except (TypeError, ValueError):
            root = 0
        if root > 0:
            stripped = _family_token(str(resolved.get("species_key") or ""))
            rematched = _match_locked_family(stripped, families) if stripped else None
            return rematched or resolved
    return None


def _detect_locked_tier(
    tokens: list[str],
    item_id: str,
    family_key: str = "",
) -> tuple[str | None, str | None, Decimal | None, str | None]:
    """Devolve (chave, rótulo, índice, motivo de bloqueio).

    Motivo preenchido significa sem preço automático.
    Palavra que já faz parte do nome da família (Rock Elemental) não vira tier.
    """
    token_set = set(tokens)
    flat = "".join(tokens)
    item_key = _pricing_fold(item_id)
    if "tekstrider" in token_set or "tekstrider" in flat or {"tek", "strider"} <= token_set:
        return None, None, None, "Tek Strider não é âncora e não recebe preço automático."
    if item_key.startswith("pfb_") or item_key.startswith("pfb ") or token_set & _BOSS_TOKENS:
        return None, None, None, "Chefe não domesticável. Sem preço automático."
    for token, reason in _UNPRICED_TIER_REASONS:
        if token in token_set:
            return None, None, None, reason
    if "blackomega" in flat or ({"black", "omega"} <= token_set):
        return None, None, None, "Black Omega não tem índice nesta tabela. Sem preço automático."
    if "primaltek" in flat or "bionic" in token_set or ({"primal", "tek"} <= token_set):
        label, index = _LOCKED_TIER_INDEX["primal_tek"]
        return "primal_tek", label, index, None
    if "primal" in token_set:
        return None, None, None, "Primal não tem índice. Sem preço automático."
    family_tokens = set(_pricing_tokens(family_key))
    tokens = [token for token in tokens if token not in family_tokens]
    token_set = set(tokens)
    flat = "".join(tokens)
    if "elemental" in token_set or "elemental" in flat:
        advanced = (
            "advanced" in token_set
            or "avancado" in token_set
            or "elementaladvanced" in flat
            or token_set & {"light", "dark", "luz", "trevas"}
        )
        key = "elemental_advanced" if advanced else "elemental_basic"
        label, index = _LOCKED_TIER_INDEX[key]
        return key, label, index, None
    ordered = (
        "fey",
        "celestial",
        "demonic",
        "chaos",
        "spirit",
        "omega",
        "fabled",
        "apex",
        "alpha",
        "noxious",
        "toxic",
    )
    aliases = {
        "demoniaco": "demonic",
        "caos": "chaos",
        "espirito": "spirit",
        "alfa": "alpha",
        "toxico": "toxic",
    }
    found: set[str] = set()
    for token in tokens:
        key = aliases.get(token, token)
        if key in ordered:
            found.add(key)
    for key in ordered:
        if key in found:
            label, index = _LOCKED_TIER_INDEX[key]
            return key, label, index, None
    label, index = _LOCKED_TIER_INDEX["vanilla"]
    return "vanilla", label, index, None


def _catalog_price_formula(family_root: int, index: Decimal, price: int) -> str:
    coef = coefficient_label(family_root)
    if "÷" in coef:
        coef_text = f"({coef})"
    else:
        coef_text = coef
    return (
        f"{format_pt_int(CATALOG_PRICE_ORIGIN)} × {coef_text} × {format_pt_decimal(index)}"
        f" = {format_pt_int(price)}"
    )


def locked_pricing_row(
    item_id: str,
    entry: dict[str, Any],
    families: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Uma criatura do catálogo, com o preço calculado ou o motivo de não calcular."""
    families = families if families is not None else _locked_family_index()
    display_name = _economy_line_display(entry, {}, item_id)
    blueprint = _catalog_item_blueprint(entry)
    short = blueprint_short_key(blueprint)
    tokens = _pricing_tokens(item_id, display_name, short)
    family = _lookup_locked_family(item_id, entry, display_name, families)
    family_key = str(family.get("species_key") or "").strip().lower() if family else ""
    family_name = ""
    family_root: int | None = None
    if family:
        family_name = clean_species_display_name(str(family.get("display_name") or "")) or family_key
        try:
            family_root = int(family.get("root_value") or 0)
        except (TypeError, ValueError):
            family_root = 0
        if family_root <= 0:
            family_root = None
            family = None
    tier_key, tier_label, index, block_reason = _detect_locked_tier(tokens, item_id, family_key)
    if family_key == "tekstrider":
        block_reason = "Tek Strider não é âncora e não recebe preço automático."
        tier_key, tier_label, index = None, None, None
    calculated: int | None = None
    formula = ""
    coef_label = ""
    if block_reason:
        calculated = None
    elif family is None or family_root is None:
        block_reason = "Sem família vanilla com raiz gravada. Sem preço automático."
    elif index is None:
        block_reason = block_reason or "Sem índice. Sem preço automático."
    else:
        calculated = locked_catalog_price(family_root, index)
        coef_label = coefficient_label(family_root)
        formula = _catalog_price_formula(family_root, index, calculated)
    try:
        current_price = int(entry.get("Price") or 0)
    except (TypeError, ValueError):
        current_price = 0
    return {
        "catalog_item_id": item_id,
        "display_name": display_name,
        "level": economy_line_level(entry),
        "family_key": family_key or None,
        "family_name": family_name or None,
        "family_root": family_root,
        "coefficient_label": coef_label or None,
        "tier_key": tier_key,
        "tier_label": tier_label,
        "index_label": format_pt_decimal(index) if index is not None else None,
        "calculated_price": calculated,
        "price_formula": formula or None,
        "current_price": current_price,
        "block_reason": block_reason,
        "can_apply_calculated": calculated is not None,
    }


def list_locked_catalog_pricing(catalog: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Todas as criaturas Type:dino do catálogo que a loja abre."""
    if not isinstance(catalog, dict) or not _catalog_items_dict(catalog):
        return []
    families = _locked_family_index()
    rows = [
        locked_pricing_row(item_id, entry, families)
        for item_id, entry in iter_catalog_dinos(catalog)
        if isinstance(entry, dict)
    ]
    rows.sort(
        key=lambda row: (
            str(row.get("display_name") or "").casefold(),
            str(row.get("catalog_item_id") or ""),
        )
    )
    return rows


def parse_manual_price(value: Any) -> tuple[int | None, str | None]:
    """Vazio vira None. Inteiro ≥ 0 é o preço manual. O resto é erro."""
    if value is None:
        return None, None
    if isinstance(value, bool):
        return None, "Ajuste manual precisa ser um inteiro maior ou igual a zero."
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return None, None
        if not text.isdigit():
            return None, "Ajuste manual precisa ser um inteiro maior ou igual a zero."
        return int(text), None
    if isinstance(value, int):
        if value < 0:
            return None, "Ajuste manual precisa ser um inteiro maior ou igual a zero."
        return value, None
    if isinstance(value, float) and value >= 0 and value.is_integer():
        return int(value), None
    return None, "Ajuste manual precisa ser um inteiro maior ou igual a zero."


def _price_to_write(row: dict[str, Any], manual: int | None) -> int | None:
    """Manual preenchido ganha do calculado. Sem os dois, não grava."""
    if manual is not None:
        return int(manual)
    if row.get("can_apply_calculated") and row.get("calculated_price") is not None:
        return int(row["calculated_price"])
    return None


def apply_locked_prices_to_catalog(
    catalog: dict[str, Any],
    *,
    item_ids: list[str],
    manuals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Grava só Items/ShopItems[id].Price das criaturas pedidas.

    Não mexe em Quantity, kits, itens nem nas outras chaves.
    """
    manuals = manuals or {}
    rows = {
        str(row["catalog_item_id"]): row
        for row in list_locked_catalog_pricing(catalog)
    }
    items = _catalog_items_dict(catalog)
    changed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    parsed_manuals: dict[str, int | None] = {}
    seen: set[str] = set()
    for raw_id in item_ids:
        item_id = str(raw_id or "").strip()
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        if item_id in manuals:
            manual, error = parse_manual_price(manuals[item_id])
            if error:
                errors.append({"catalog_item_id": item_id, "error": error})
                continue
            parsed_manuals[item_id] = manual
    if errors:
        return {"ok": False, "changed": [], "skipped": [], "errors": errors, "changed_count": 0}
    seen.clear()
    for raw_id in item_ids:
        item_id = str(raw_id or "").strip()
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        manual = parsed_manuals.get(item_id)
        row = rows.get(item_id)
        if row is None or item_id not in items or not isinstance(items.get(item_id), dict):
            skipped.append({"catalog_item_id": item_id, "reason": "Criatura não está no catálogo."})
            continue
        price = _price_to_write(row, manual)
        if price is None:
            skipped.append({
                "catalog_item_id": item_id,
                "reason": row.get("block_reason") or "Sem preço calculado e sem ajuste manual.",
            })
            continue
        entry = items[item_id]
        old = entry.get("Price")
        if old == price:
            skipped.append({"catalog_item_id": item_id, "reason": "Price já está nesse valor.", "price": price})
            continue
        entry["Price"] = price
        changed.append({
            "catalog_item_id": item_id,
            "old_price": old,
            "new_price": price,
            "source": "manual" if manual is not None else "calculado",
        })
    return {
        "ok": not errors,
        "changed": changed,
        "skipped": skipped,
        "errors": errors,
        "changed_count": len(changed),
    }


def _backup_name_is_protected(name: str) -> bool:
    lowered = name.lower()
    if name in PROTECTED_CATALOG_BACKUP_NAMES or lowered in PROTECTED_CATALOG_BACKUP_NAMES:
        return True
    return lowered.endswith("bak-antes-itens-pf") or lowered.endswith("bak-antes-ajuste-precos")


def backup_catalog_beside(path: Path) -> Path:
    """Cópia ao lado do catálogo. Não apaga e não sobrescreve backups antigos."""
    source = Path(path)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    number = 0
    while True:
        suffix = f".bak-precificacao-{stamp}" if number == 0 else f".bak-precificacao-{stamp}-{number}"
        dest = source.parent / f"{source.name}{suffix}"
        number += 1
        if _backup_name_is_protected(dest.name) or dest.exists():
            continue
        shutil.copy2(source, dest)
        return dest


def apply_locked_prices_at_path(
    path: Path,
    *,
    mode: str,
    catalog_item_id: str | None = None,
    manuals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Lê, altera Price e grava o mesmo arquivo. A massa faz cópia antes."""
    catalog_path = Path(path)
    if not catalog_path.is_file():
        return {"ok": False, "error": "Catálogo não encontrado no caminho que a loja já abre.", "changed": [], "skipped": []}
    kind = str(mode or "").strip().lower()
    if kind not in {"one", "bulk"}:
        return {"ok": False, "error": "Modo inválido. Use individual ou em massa.", "changed": [], "skipped": []}
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"Não foi possível ler o catálogo: {exc}", "changed": [], "skipped": []}
    if not isinstance(catalog, dict):
        return {"ok": False, "error": "O catálogo não é um objeto JSON.", "changed": [], "skipped": []}
    manuals = dict(manuals or {})
    if kind == "one":
        item_id = str(catalog_item_id or "").strip()
        if not item_id:
            return {"ok": False, "error": "Informe a criatura.", "changed": [], "skipped": []}
        item_ids = [item_id]
        if item_id not in manuals:
            manuals[item_id] = None
    else:
        item_ids = [item_id for item_id, _entry in iter_catalog_dinos(catalog)]
    result = apply_locked_prices_to_catalog(catalog, item_ids=item_ids, manuals=manuals)
    if not result.get("ok"):
        return {**result, "error": "Ajuste manual inválido.", "backup": None, "written": False}
    if not result["changed"]:
        return {**result, "backup": None, "written": False, "path": str(catalog_path)}
    backup_path: Path | None = None
    if kind == "bulk":
        backup_path = backup_catalog_beside(catalog_path)
    payload = json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"
    temporary = catalog_path.parent / f".{catalog_path.name}.precificacao-tmp-{os.getpid()}"
    try:
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, catalog_path)
    except OSError as exc:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass
        return {
            "ok": False,
            "error": f"Não foi possível gravar o catálogo: {exc}",
            "changed": [],
            "skipped": result["skipped"],
            "backup": str(backup_path) if backup_path else None,
            "written": False,
        }
    return {
        **result,
        "backup": str(backup_path) if backup_path else None,
        "written": True,
        "path": str(catalog_path),
    }
