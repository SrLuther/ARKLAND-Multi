"""Registro de espécies ARK para categorização automática do Comércio P2P.

Lógica de tiers (justa, baseada em utilidade meta ARK):
- S+: apex boss/tek breeders (Giga, Indominus, Astrocetus)
- S:  apex PvP / wyverns / striders premium
- A:  meta breeding PvE (Rex, Carcha, Spino, Quetz)
- B:  gatherers e utilidade (Ankylo, Doed, Argy, Stego)
- C:  entrada / passivos / montarias básicas

root_value (Âmbar nível 1) deriva do tier quando não há preço de loja.
Fontes: market_species_defaults.json + lista vanilla curada + ark_species_registry.json
(overlay de mods — ex.: Abyss com tiers S+ apex abissal 12–13k, S combat 8–9k, recursos C 200–800).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from market_economy import (
    build_multipliers_from_defaults,
    load_defaults_file,
    normalize_blueprint,
)

_DATA_DIR = Path(__file__).resolve().parent / "data"
_REGISTRY_PATH = _DATA_DIR / "ark_species_registry.json"

TIER_ROOT_VALUES: dict[str, int] = {
    "S+": 12000,
    "S": 8000,
    "A": 5000,
    "B": 2500,
    "C": 800,
}

# Silhuetas genéricas ARKLAND — servidas de static/species/ (sem dependência externa).
TIER_ICON_URLS: dict[str, str] = {
    "S+": "/species/tier-s-plus.svg",
    "S": "/species/tier-s.svg",
    "A": "/species/tier-a.svg",
    "B": "/species/tier-b.svg",
    "C": "/species/tier-c.svg",
}

# (species_key, display_name_pt, class_token, tier, role, root_value)
# class_token = parte antes de _Character_BP no blueprint ARK
VANILLA_CURATED: tuple[tuple[str, str, str, str, str, int], ...] = (
    ("ankylo", "Anquilossauro", "ankylo", "B", "farm", 2000),
    ("doed", "Doedicurus", "doed", "B", "farm", 2200),
    ("beaver", "Castoroides", "beaver", "B", "farm", 1800),
    ("mammoth", "Mamute", "mammoth", "B", "farm", 2500),
    ("paracer", "Paraceratherium", "paracer", "B", "utility", 2000),
    ("bronto", "Brontossauro", "sauropod", "C", "utility", 1200),
    ("stego", "Stegossauro", "stego", "B", "utility", 2200),
    ("trike", "Triceratops", "trike", "C", "utility", 900),
    ("para", "Parasaurolophus", "para", "C", "utility", 600),
    ("iguanodon", "Iguanodonte", "iguanodon", "C", "utility", 700),
    ("carbonemys", "Carbonemys", "turtle", "C", "utility", 500),
    ("ptera", "Pteranodonte", "ptera", "C", "transport", 800),
    ("argent", "Argentavis", "argent", "B", "transport", 2800),
    ("quetz", "Quetzalcoatlus", "quetz", "A", "transport", 5500),
    ("tapejara", "Tapejara", "tapejara", "B", "transport", 3200),
    ("pelagornis", "Pelagornis", "pelagornis", "C", "transport", 1000),
    ("griffin", "Grifo", "griffin", "A", "transport", 4800),
    ("wyvern", "Wyvern", "wyvern", "S", "pvp", 9000),
    ("rockdrake", "Rock Drake", "drake", "S", "pvp", 8500),
    ("basilisk", "Basilisco", "basilisk", "A", "pvp", 5000),
    ("megalodon", "Megalodon", "megalodon", "B", "pvp", 2500),
    ("mosasaurus", "Mosasauro", "mosasaurus", "A", "pvp", 5500),
    ("plesiosaur", "Plesiossauro", "plesiosaur", "B", "utility", 2800),
    ("tuso", "Tusoteuthis", "tuso", "A", "pvp", 5200),
    ("dunkle", "Dunkleosteus", "dunkle", "B", "pvp", 3000),
    ("allo", "Allosaurus", "allo", "A", "pvp", 4500),
    ("carno", "Carnotauro", "carno", "B", "pvp", 2800),
    ("spino", "Espinosaur", "spino", "A", "pvp", 5500),
    ("baryonyx", "Baryonyx", "baryonyx", "B", "pvp", 3200),
    ("theriz", "Therizinosaur", "theriz", "A", "pvp", 5000),
    ("yuty", "Yutyrannus", "yuty", "A", "pvp", 5200),
    ("deinonychus", "Deinonychus", "deinonychus", "A", "pvp", 4800),
    ("raptor", "Raptor", "raptor", "C", "pvp", 900),
    ("sabertooth", "Smilodonte", "sabertooth", "B", "pvp", 2200),
    ("direwolf", "Lobo Gigante", "wolf", "B", "pvp", 2000),
    ("thyla", "Thylacoleo", "thyla", "B", "pvp", 2800),
    ("megatherium", "Megatherium", "megatherium", "B", "farm", 2500),
    ("daeodon", "Daeodon", "daeodon", "B", "utility", 3000),
    ("achatina", "Achatina", "snail", "C", "farm", 400),
    ("dodo", "Dodo", "dodo", "C", "utility", 300),
    ("gallimimus", "Gallimimus", "galli", "C", "transport", 500),
    ("lystrosaurus", "Lystrossauro", "lystro", "C", "utility", 300),
    ("phiomia", "Phiomia", "phiomia", "C", "utility", 400),
    ("pulmonoscorpius", "Escorpião", "scorpion", "C", "pvp", 600),
    ("mantis", "Louva-a-deus", "mantis", "B", "pvp", 2200),
    ("kairuku", "Kairuku", "kairuku", "C", "utility", 400),
    ("diplodocus", "Diplodocus", "diplo", "C", "utility", 800),
    ("gigant", "Giganotossauro", "gigant", "S+", "boss", 15000),
    ("megalosaurus", "Megalossauro", "megalosaurus", "A", "pvp", 4500),
    ("maewing", "Maewing", "lawnmower", "A", "utility", 4500),
    ("desmodus", "Desmodus", "desmodus", "A", "transport", 5000),
    ("fjordhawk", "Fjordhawk", "fjordhawk", "B", "utility", 2800),
    ("andrewsarchus", "Andrewsarchus", "andrewsarchus", "B", "pvp", 3200),
    ("sinomacrops", "Sinomacrops", "sinomacrops", "C", "utility", 800),
    ("amargasaurus", "Amargassauro", "amargasaurus", "B", "utility", 2800),
    ("dinopithecus", "Dinopithecus", "dinopithecus", "B", "pvp", 3000),
    ("fenrir", "Fenrir", "fenrir", "S", "boss", 10000),
    ("rhynio", "Rhinognatha", "rhyniognatha", "A", "pvp", 5200),
    ("owl", "Coruja das Neves", "owl", "A", "utility", 4800),
    ("gasbags", "Gasbags", "gasbags", "B", "utility", 2800),
    ("velonasaur", "Velonasaur", "velonasaur", "A", "pvp", 4800),
    ("gacha", "Gacha", "gacha", "B", "farm", 2500),
    ("managarmr", "Managarmr", "icejumper", "S", "pvp", 9000),
    ("ferox", "Ferox", "shapeshifter", "A", "pvp", 5000),
    ("bloodstalker", "Bloodstalker", "bogspider", "B", "utility", 2500),
    ("astrocetus", "Astrocetus", "spacewhale", "S", "transport", 10000),
    ("megachelon", "Megachelon", "megachelon", "A", "utility", 5000),
    ("tropeognathus", "Tropeognathus", "tropeognathus", "A", "transport", 5200),
    ("crystalwyvern", "Wyvern de Cristal", "crystalwyvern", "S", "pvp", 9000),
    ("magmasaur", "Magmasaur", "cherchedragon", "A", "pvp", 5200),
    ("xenomorph", "Reaper", "xenomorph", "S", "pvp", 8500),
    ("tekstrider", "Tek Strider", "tekstrider", "S", "utility", 9000),
    ("compy", "Compy", "compy", "C", "utility", 200),
    ("dimorph", "Dimorphodon", "dimorph", "C", "pvp", 400),
    ("otter", "Lontra", "otter", "C", "utility", 500),
    ("jerboa", "Gerboa", "jerboa", "C", "utility", 300),
    ("equus", "Equus", "equus", "C", "transport", 600),
    ("procoptodon", "Procoptodon", "kangaroo", "B", "transport", 2200),
    ("purlovia", "Purlovia", "purlovia", "B", "pvp", 2200),
    ("basilosaurus", "Basilossauro", "basilosaurus", "B", "utility", 3000),
    ("titanboa", "Titanoboa", "titanboa", "C", "pvp", 600),
    ("sarco", "Sarcosuchus", "sarco", "B", "pvp", 2200),
    ("kaprosuchus", "Kaprosuchus", "kaprosuchus", "B", "pvp", 2500),
    ("castoroides", "Castoroides", "beaver", "B", "farm", 1800),
    ("doedicurus", "Doedicurus", "doed", "B", "farm", 2200),
    ("lionfishlion", "Lionfish Lion", "lionfishlion", "S", "pvp", 9000),
    ("bionicgigant", "Giga Bionic", "bionicgigant", "S", "boss", 14000),
    ("bionicrex", "Rex Bionic", "bionicrex", "A", "pvp", 5500),
    ("volcanorex", "Rex Vulcão", "volcanorex", "A", "pvp", 5200),
)

_BP_CLASS_RE = re.compile(
    r"^(?:blueprintgeneratedclass\s+)?(.+)$",
    re.IGNORECASE,
)
_STRIP_SUFFIX_RE = re.compile(
    r"(_character_bp(?:_c)?(?:_\d+)?|_bp_c(?:_\d+)?|_c_\d+)$",
    re.IGNORECASE,
)
_TRAILING_NUM_RE = re.compile(r"_\d+$")
_GENDER_SUFFIX_RE = re.compile(r"[\s♂♀]+$")


def extract_class_token(raw: str | None) -> str:
    """Extrai token de classe a partir de blueprint, GetFullName ou name_map cru."""
    text = (raw or "").strip()
    if not text:
        return ""
    text = _GENDER_SUFFIX_RE.sub("", text)
    m = _BP_CLASS_RE.match(text)
    if m:
        text = m.group(1).strip()
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    text = text.lower()
    text = _STRIP_SUFFIX_RE.sub("", text)
    text = _TRAILING_NUM_RE.sub("", text)
    text = re.sub(r"_character$", "", text)
    return text.strip("_")


def normalize_blueprint_extended(bp: str | None) -> str:
    """``normalize_blueprint`` + remove sufixos numéricos de instância."""
    base = normalize_blueprint(bp)
    if not base:
        return extract_class_token(bp)
    if "." in base:
        pkg, cls = base.rsplit(".", 1)
        cls = _STRIP_SUFFIX_RE.sub("", cls)
        cls = _TRAILING_NUM_RE.sub("", cls)
        return f"{pkg}.{cls}" if cls else base
    return _TRAILING_NUM_RE.sub("", base)


def tier_icon_url(tier: str | None) -> str:
    """URL do placeholder SVG por tier (fallback quando não há imagem da espécie)."""
    key = (tier or "B").strip().upper()
    if key == "S+":
        return TIER_ICON_URLS["S+"]
    return TIER_ICON_URLS.get(key, TIER_ICON_URLS["B"])


def _image_from_entry(entry: dict[str, Any]) -> str | None:
    """Resolve image_url ou icon_path de uma entrada do registro."""
    url = str(entry.get("image_url") or "").strip()
    if url:
        return url
    icon = str(entry.get("icon_path") or "").strip()
    if not icon:
        return None
    if icon.startswith(("http://", "https://", "/")):
        return icon
    return f"/species/{icon.lstrip('/')}"


def resolve_species_image(entry: dict[str, Any] | None, *, tier: str | None = None) -> str:
    """URL servível para thumbnail: imagem da espécie ou silhueta do tier."""
    if entry:
        custom = _image_from_entry(entry)
        if custom:
            return custom
        tier = tier or str(entry.get("tier") or "B")
    return tier_icon_url(tier)


@lru_cache(maxsize=1)
def load_registry_overlay_raw() -> list[dict[str, Any]]:
    """Entradas exclusivas de data/ark_species_registry.json (overlay de mods)."""
    if not _REGISTRY_PATH.is_file():
        return []
    try:
        with _REGISTRY_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        return [e for e in (data.get("species") or []) if isinstance(e, dict) and e.get("species_key")]
    except Exception:
        return []


def get_registry_entry(species_key: str | None) -> dict[str, Any] | None:
    """Entrada completa do registro por species_key."""
    sk = (species_key or "").strip().lower()
    if not sk:
        return None
    for entry in load_registry().get("species") or []:
        if str(entry.get("species_key") or "").lower() == sk:
            return entry
    return None


def is_raw_blueprint_label(text: str | None) -> bool:
    """Detecta rótulos crus do jogo (ex.: Ankylo_Character_BP_C_257)."""
    t = (text or "").strip()
    if not t:
        return False
    low = t.lower()
    return (
        "_character_bp" in low
        or "_bp_c" in low
        or low.startswith("blueprint")
        or ("/game/" in low and "character" in low)
    )


def _entry_from_defaults(defn: dict[str, Any]) -> dict[str, Any]:
    sk = str(defn.get("species_key") or "")
    tier = str(defn.get("tier") or "B")
    paths: list[str] = []
    tokens: set[str] = set()
    bp = str(defn.get("blueprint_path") or "").strip()
    if bp:
        paths.append(bp)
        tokens.add(extract_class_token(bp))
    for alias in defn.get("blueprint_aliases") or []:
        abp = alias.get("blueprint_path") if isinstance(alias, dict) else alias
        if abp:
            paths.append(str(abp))
            tokens.add(extract_class_token(str(abp)))
    tokens.add(sk.split("_")[0].lower())
    out: dict[str, Any] = {
        "species_key": sk,
        "display_name": defn.get("display_name") or sk,
        "tier": tier,
        "role": defn.get("breeding_notes", "")[:32] or "utility",
        "root_value": int(defn.get("root_value") or TIER_ROOT_VALUES.get(tier, 2500)),
        "blueprint_paths": paths,
        "class_tokens": sorted(tokens),
        "source": "market_defaults",
        "confidence": "high",
    }
    for img_key in ("image_url", "icon_path"):
        if defn.get(img_key):
            out[img_key] = defn[img_key]
    return out


def _merged_species_list() -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}

    for defn in load_defaults_file().get("species") or []:
        sk = str(defn.get("species_key") or "")
        if sk:
            by_key[sk] = _entry_from_defaults(defn)

    for sk, dn, token, tier, role, rv in VANILLA_CURATED:
        if sk in by_key:
            existing = by_key[sk]
            tokens = set(existing.get("class_tokens") or [])
            tokens.add(token)
            existing["class_tokens"] = sorted(tokens)
            continue
        by_key[sk] = {
            "species_key": sk,
            "display_name": dn,
            "tier": tier,
            "role": role,
            "root_value": rv,
            "blueprint_paths": [],
            "class_tokens": [token],
            "source": "vanilla_curated",
            "confidence": "high",
        }

    if _REGISTRY_PATH.is_file():
        try:
            with _REGISTRY_PATH.open(encoding="utf-8") as f:
                overlay = json.load(f)
            for entry in overlay.get("species") or []:
                sk = str(entry.get("species_key") or "")
                if sk:
                    by_key[sk] = {**by_key.get(sk, {}), **entry, "source": entry.get("source", "registry_json")}
        except Exception:
            pass

    return list(by_key.values())


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    species = _merged_species_list()
    return {
        "version": "1.1.0",
        "species_count": len(species),
        "tier_base_values": TIER_ROOT_VALUES,
        "tier_icon_urls": TIER_ICON_URLS,
        "species": species,
    }


def _build_indexes() -> tuple[dict[str, dict], dict[str, dict]]:
    by_bp: dict[str, dict] = {}
    by_token: dict[str, dict] = {}
    for entry in load_registry().get("species") or []:
        sk = str(entry.get("species_key") or "")
        if not sk:
            continue
        for bp in entry.get("blueprint_paths") or []:
            nb = normalize_blueprint_extended(str(bp))
            if nb:
                by_bp[nb] = entry
        for token in entry.get("class_tokens") or []:
            tok = str(token).strip().lower()
            if tok and tok not in by_token:
                by_token[tok] = entry
        by_token.setdefault(sk.split("_")[0].lower(), entry)
    return by_bp, by_token


@lru_cache(maxsize=1)
def _indexes() -> tuple[dict[str, dict], dict[str, dict]]:
    return _build_indexes()


def lookup_species(
    *,
    blueprint: str | None = None,
    species_key: str | None = None,
    name_hint: str | None = None,
) -> dict[str, Any] | None:
    """Busca espécie no registro. Retorna dict com confidence high|medium|low."""
    by_bp, by_token = _indexes()
    candidates: list[tuple[str, dict]] = []

    if species_key:
        sk = species_key.strip().lower()
        for entry in load_registry().get("species") or []:
            if str(entry.get("species_key") or "").lower() == sk:
                candidates.append(("high", entry))
                break

    if blueprint:
        nb = normalize_blueprint_extended(blueprint)
        if nb in by_bp:
            candidates.append(("high", by_bp[nb]))
        token = extract_class_token(blueprint)
        if token in by_token:
            conf = "high" if nb in by_bp else "medium"
            candidates.append((conf, by_token[token]))

    for hint in (name_hint, blueprint):
        if not hint:
            continue
        token = extract_class_token(hint)
        if token in by_token:
            candidates.append(("medium", by_token[token]))
        elif is_raw_blueprint_label(hint) and len(token) >= 4:
            for tok, entry in by_token.items():
                if len(tok) >= 4 and (token.startswith(tok) or tok.startswith(token)):
                    candidates.append(("low", entry))
                    break

    if not candidates:
        return None

    conf_order = {"high": 3, "medium": 2, "low": 1}
    conf, entry = max(candidates, key=lambda c: conf_order.get(c[0], 0))
    tier = str(entry.get("tier") or "B")
    root = int(entry.get("root_value") or TIER_ROOT_VALUES.get(tier, 2500))
    return {
        "species_key": entry.get("species_key"),
        "display_name": entry.get("display_name"),
        "tier": tier,
        "role": entry.get("role") or "utility",
        "root_value": root,
        "confidence": conf,
        "is_new_species": entry.get("source") == "vanilla_curated",
        "registry_source": entry.get("source"),
        "blueprint_paths": entry.get("blueprint_paths") or [],
        "image_url": resolve_species_image(entry, tier=tier),
    }


def registry_stats() -> dict[str, Any]:
    data = load_registry()
    return {
        "registry_version": data.get("version"),
        "species_count": len(data.get("species") or []),
        "tier_base_values": data.get("tier_base_values") or TIER_ROOT_VALUES,
    }


def suggestion_to_public(suggestion: dict[str, Any] | None) -> dict[str, Any] | None:
    if not suggestion:
        return None
    tier = suggestion.get("tier")
    image_url = suggestion.get("image_url")
    if not image_url and suggestion.get("species_key"):
        reg = get_registry_entry(str(suggestion.get("species_key")))
        image_url = resolve_species_image(reg, tier=tier)
    elif not image_url:
        image_url = tier_icon_url(tier)
    return {
        "species_key": suggestion.get("species_key"),
        "display_name": suggestion.get("display_name"),
        "tier": tier,
        "role": suggestion.get("role"),
        "root_value": suggestion.get("root_value"),
        "confidence": suggestion.get("confidence"),
        "is_new_species": bool(suggestion.get("is_new_species")),
        "needs_review": suggestion.get("confidence") == "low",
        "image_url": image_url,
    }


def ensure_pre_registered_species(db: Any, suggestion: dict[str, Any], *, blueprint: str) -> Any:
    """Cria espécie PRE_REGISTERED + alias se ainda não existir no banco."""
    from datetime import datetime, timezone

    from app import MarketSpecies, MarketSpeciesAlias, MarketSpeciesStatMultiplier

    sk = str(suggestion.get("species_key") or "").strip()
    if not sk:
        raise ValueError("species_key obrigatório na sugestão")

    row = db.query(MarketSpecies).filter(MarketSpecies.species_key == sk).first()
    now = datetime.now(timezone.utc)
    bp_path = blueprint or (suggestion.get("blueprint_paths") or [""])[0]
    bp_norm = normalize_blueprint_extended(bp_path)

    if row is None:
        mults = build_multipliers_from_defaults(sk)
        default_mult = next((m.multiplier for m in mults.values() if m.enabled), 100)
        row = MarketSpecies(
            species_key=sk,
            catalog_item_id=None,
            display_name=str(suggestion.get("display_name") or sk),
            blueprint_path=bp_path or None,
            reference_level=1,
            root_value=int(suggestion.get("root_value") or TIER_ROOT_VALUES.get("B", 2500)),
            tier=str(suggestion.get("tier") or "B"),
            breeding_difficulty="",
            breeding_notes=str(suggestion.get("role") or ""),
            status="PRE_REGISTERED",
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.flush()
        added_mult = False
        for stat_key, sm in mults.items():
            if sm.multiplier > 0:
                db.add(
                    MarketSpeciesStatMultiplier(
                        species_id=row.id,
                        stat_key=stat_key,
                        multiplier=sm.multiplier,
                        enabled=sm.enabled,
                    )
                )
                added_mult = True
        if not added_mult and default_mult:
            db.add(
                MarketSpeciesStatMultiplier(
                    species_id=row.id,
                    stat_key="melee",
                    multiplier=default_mult,
                    enabled=True,
                )
            )

    if bp_norm:
        alias = (
            db.query(MarketSpeciesAlias)
            .filter(MarketSpeciesAlias.blueprint_norm == bp_norm)
            .first()
        )
        if alias is None:
            db.add(
                MarketSpeciesAlias(
                    species_id=row.id,
                    blueprint_path=bp_path,
                    blueprint_norm=bp_norm,
                    variant_label=None,
                )
            )
        elif alias.species_id != row.id:
            alias.species_id = row.id

    db.flush()
    return row
