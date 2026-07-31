"""Código público padronizado para dinos gerados via catálogo.

Formato: ``{tipo}{variante}{género}{seq}`` — ex. ``R21347``
  - 1 caractere  → família/espécie base (R=Rex, G=Giga, …)
  - 1 dígito     → variante/linha (1=vanilla, 2=abissal, …)
  - 1 dígito     → género (1=macho, 2=fêmea, 3=sem género)
  - 3 dígitos    → sequência única dentro do prefixo tipo+variante+género

A letra da família é única no catálogo. A-Z é reservada a mnemónicos
conhecidos; o restante usa um alfabeto estendido documentado (a-z, 0-9,
Latin-1, grego, cirílico) para caber todas as espécies.
"""
from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Variante (2.º caractere — dígito)
# ---------------------------------------------------------------------------
VARIANT_VANILLA = 1
VARIANT_ABYSS = 2
VARIANT_ABERRANT = 3
VARIANT_BIONIC = 4
VARIANT_SB = 5
VARIANT_BRIGHAMIA = 6
VARIANT_ROCKWELL = 7
VARIANT_SCORCHED = 8
VARIANT_OTHER = 9

VARIANT_LABELS: dict[int, str] = {
    VARIANT_VANILLA: "vanilla",
    VARIANT_ABYSS: "abyss",
    VARIANT_ABERRANT: "aberrant",
    VARIANT_BIONIC: "bionic",
    VARIANT_SB: "sb",
    VARIANT_BRIGHAMIA: "brighamia",
    VARIANT_ROCKWELL: "rockwell",
    VARIANT_SCORCHED: "scorched/snow",
    VARIANT_OTHER: "other",
}

# ---------------------------------------------------------------------------
# Género (3.º caractere — dígito)
# ---------------------------------------------------------------------------
GENDER_MALE = 1
GENDER_FEMALE = 2
GENDER_NONE = 3

# ---------------------------------------------------------------------------
# Família → letra (mnemónicos A-Z; restantes preenchidos do alfabeto estendido)
# ---------------------------------------------------------------------------
# Aliases de chave de catálogo → família canónica (partilham a mesma letra).
_FAMILY_ALIASES: dict[str, str] = {
    "ankylo": "ankylosaurus",
    "stego": "stegosaurus",
    "theriz": "therizinosaur",
    "thyla": "thylacoleo",
    "yuty": "yutyrannus",
    "gigant": "giga",
    "acro": "acrocanto",
}

# Preferência mnemónica (atribuída primeiro se a família existir / for pedida).
_MNEMONIC_LETTER: dict[str, str] = {
    "rex": "R",
    "giga": "G",
    "carcha": "C",
    "spinosaur": "S",
    "wyvern_fire": "W",
    "argentavis": "A",
    "therizinosaur": "T",
    "quetzal": "Q",
    "managarmr": "M",
    "deinonychus": "D",
    "raptor": "P",
    "allosaurus": "L",
    "baryonyx": "B",
    "carnotaurus": "K",
    "mosasaurus": "O",
    "megalodon": "E",
    "yutyrannus": "Y",
    "thylacoleo": "H",
    "ankylosaurus": "N",
    "stegosaurus": "U",
    "triceratops": "V",
    "parasaur": "X",
    "dilophosaur": "F",
    "equus": "Z",
    "indominus": "I",
    "indoraptor": "J",
}

# Alfabeto estendido (1 caractere por família). Ordem estável = códigos estáveis.
_TYPE_CHARSET: str = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789"
    "ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞ"
    "ßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ"
    "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"
    "αβγδεζηθικλμνξοπρστυφχψω"
    "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЫЭЮЯ"
)

_letter_cache: dict[str, str] = {}
_used_letters: set[str] = set()
_known_families: set[str] = set()

_FEMEA_RE = re.compile(r"_femea$", re.I)
_MACHO_RE = re.compile(r"_macho$", re.I)
_L200_RE = re.compile(r"_l200$", re.I)
_PACK10_RE = re.compile(r"_pack10$", re.I)


def normalize_species_key(raw: str) -> str:
    """Remove sufixos de kit/nível; mantém chave de espécie do catálogo."""
    s = str(raw or "").strip()
    s = _PACK10_RE.sub("", s)
    s = _L200_RE.sub("", s)
    return s


def parse_species_key(species_key: str) -> tuple[str, int]:
    """Devolve (família_canónica, dígito_variante) a partir da species_key."""
    k = normalize_species_key(species_key)
    k = _FEMEA_RE.sub("", k)
    k = _MACHO_RE.sub("", k)

    variant = VARIANT_VANILLA
    if k.startswith("abyss_"):
        variant = VARIANT_ABYSS
        k = k[6:]
        if k.endswith("_abyssal"):
            k = k[: -len("_abyssal")]
    elif k.startswith("aberrant_"):
        variant = VARIANT_ABERRANT
        k = k[9:]
    elif k.startswith("sb_"):
        variant = VARIANT_SB
        k = k[3:]
    elif k.startswith("brighamia_"):
        variant = VARIANT_BRIGHAMIA
        k = k[10:]
    elif k.startswith("bionic"):
        variant = VARIANT_BIONIC
        k = k[6:].lstrip("_")
    else:
        for suf, var in (
            ("_aberrant", VARIANT_ABERRANT),
            ("_rockwell", VARIANT_ROCKWELL),
            ("_scorched", VARIANT_SCORCHED),
            ("_snow", VARIANT_SCORCHED),
            ("_abyssal", VARIANT_ABYSS),
        ):
            if k.endswith(suf):
                variant = var
                k = k[: -len(suf)]
                break

    family = _FAMILY_ALIASES.get(k, k) or "unknown"
    return family, variant


def gender_digit_from_value(raw: Any) -> int:
    """Mapeia Gender do catálogo / payload → dígito 1/2/3."""
    if raw is None:
        return GENDER_NONE
    s = str(raw).strip().lower()
    if not s:
        return GENDER_NONE
    if s in ("male", "macho", "m", "1"):
        return GENDER_MALE
    if s in ("female", "femea", "fêmea", "f", "2"):
        return GENDER_FEMALE
    if s in ("none", "no", "n/a", "na", "3", "neutral", "neutro"):
        return GENDER_NONE
    return GENDER_NONE


def gender_digit_from_item_id(item_id: str) -> int | None:
    """Infere género pelo sufixo do item_id; None se não houver pista."""
    s = normalize_species_key(item_id)
    if _FEMEA_RE.search(s):
        return GENDER_FEMALE
    if _MACHO_RE.search(s):
        return GENDER_MALE
    return None


def resolve_gender_digit(
    *,
    payload_gender: Any = None,
    item_id: str = "",
    catalog_entry: dict[str, Any] | None = None,
) -> int:
    """Prioridade: payload → campo Gender do item → Dinos[0].Gender → sufixo → 3."""
    if payload_gender is not None and str(payload_gender).strip() != "":
        return gender_digit_from_value(payload_gender)
    if isinstance(catalog_entry, dict):
        if "Gender" in catalog_entry or "gender" in catalog_entry:
            return gender_digit_from_value(
                catalog_entry.get("Gender", catalog_entry.get("gender"))
            )
        dinos = catalog_entry.get("Dinos")
        if isinstance(dinos, list) and dinos and isinstance(dinos[0], dict):
            g0 = dinos[0].get("Gender", dinos[0].get("gender"))
            if g0 is not None and str(g0).strip() != "":
                return gender_digit_from_value(g0)
    inferred = gender_digit_from_item_id(item_id)
    if inferred is not None:
        return inferred
    return GENDER_NONE


def _assign_letter(family: str) -> str:
    """Atribui letra de forma append-only (nunca reshuffle de famílias já mapeadas)."""
    if family in _letter_cache:
        return _letter_cache[family]
    # 1) mnemónico se livre
    mnemonic = _MNEMONIC_LETTER.get(family)
    if mnemonic and mnemonic not in _used_letters:
        _letter_cache[family] = mnemonic
        _used_letters.add(mnemonic)
        return mnemonic
    # 2) primeira letra A-Z se livre
    hint = family[:1].upper() if family else ""
    if "A" <= hint <= "Z" and hint not in _used_letters:
        _letter_cache[family] = hint
        _used_letters.add(hint)
        return hint
    # 3) próximo do alfabeto estendido
    for ch in _TYPE_CHARSET:
        if ch not in _used_letters:
            _letter_cache[family] = ch
            _used_letters.add(ch)
            return ch
    _letter_cache[family] = "?"
    return "?"


def reset_letter_state_for_tests() -> None:
    """Limpa cache de letras (apenas testes)."""
    _letter_cache.clear()
    _used_letters.clear()
    _known_families.clear()


def register_known_families(families: list[str] | set[str]) -> None:
    """Regista famílias conhecidas em ordem estável (sorted) e atribui letras."""
    pending = sorted({str(f).strip() for f in families if str(f or "").strip()})
    for fam in pending:
        _known_families.add(fam)
    # Atribui primeiro todas as mnemónicas (ordem do dict), depois o resto sorted
    for fam, _ch in _MNEMONIC_LETTER.items():
        if fam in _known_families:
            _assign_letter(fam)
    for fam in pending:
        _assign_letter(fam)


def family_letter(family: str) -> str:
    """Letra estável da família (regista a família se ainda for desconhecida)."""
    fam = str(family or "unknown").strip() or "unknown"
    _known_families.add(fam)
    return _assign_letter(fam)


def code_prefix(family: str, variant: int, gender: int) -> str:
    return f"{family_letter(family)}{int(variant)}{int(gender)}"


def format_public_code(prefix: str, sequence: int) -> str:
    """Monta o código; se sequence > 999, usa mais dígitos (colisão rara)."""
    seq = max(0, int(sequence))
    if seq <= 999:
        return f"{prefix}{seq:03d}"
    return f"{prefix}{seq}"


def build_public_code(
    *,
    species_key: str,
    gender_digit: int,
    sequence: int,
) -> str:
    family, variant = parse_species_key(species_key)
    return format_public_code(code_prefix(family, variant, gender_digit), sequence)


def seed_families_from_catalog(catalog: dict[str, Any] | None) -> None:
    """Extrai famílias de Items do catálogo CustomShop e regista-as."""
    if not isinstance(catalog, dict):
        return
    items = catalog.get("Items") or catalog.get("ShopItems") or {}
    if not isinstance(items, dict):
        return
    families: set[str] = set()
    for key, entry in items.items():
        if not isinstance(entry, dict):
            continue
        if str(entry.get("Type") or "").lower() != "dino":
            continue
        fam, _ = parse_species_key(str(key))
        families.add(fam)
    register_known_families(families)


def lookup_catalog_entry(
    catalog: dict[str, Any] | None,
    item_id: str,
) -> dict[str, Any] | None:
    """Resolve entrada do item (tenta L1 se L200 não tiver Gender)."""
    if not isinstance(catalog, dict):
        return None
    items = catalog.get("Items") or catalog.get("ShopItems") or {}
    if not isinstance(items, dict):
        return None
    iid = str(item_id or "").strip()
    if not iid:
        return None
    entry = items.get(iid)
    if isinstance(entry, dict):
        return entry
    base = normalize_species_key(iid)
    entry = items.get(base)
    return entry if isinstance(entry, dict) else None
