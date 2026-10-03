"""Nível e gênero de dinos no catálogo da Web Store (sem trava L1/L200).

Antes (≤ 1.10.x) a loja tratava só dois níveis (abas «Dinos» = L1 e «Dinos 200» = L200).
Agora o nível é um inteiro livre (1..``dino_level_max()``) e o gênero é normalizado em
``male`` | ``female`` | ``pair`` | ``random``.

Este módulo é **puro** (sem Flask/DB) para ser reutilizado por:
  - ``catalog_enrich`` (campos extras em ``/api/catalog``);
  - ``app.py`` (validação ao salvar catálogo, auditoria, entrega admin);
  - ``tools/migrate_dinos_unified.py`` / ``tools/generate_dino_level_variants.py``.

Fonte de verdade do nível para **entrega no jogo** = ``Dinos[i].Level`` (plugin CustomShop).
Leitura é tolerante a catálogos antigos: infere o nível de ``Category`` («Dinos 200»),
``dino_level``/``Level`` no item, nome, descrição e id («LVL 200», «L200», ``_200``).
"""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Any, Iterable

# ── Limites ──────────────────────────────────────────────────────────────────
DINO_LEVEL_MIN = 1
#: Teto padrão para **cadastro** (configurável: env ``ARKSHOP_DINO_LEVEL_MAX``).
DEFAULT_DINO_LEVEL_MAX = 500
#: Teto de **leitura** (nunca esconder itens antigos): alinhado ao plugin (kSpawnExactMaxTotalLevel).
HARD_DINO_LEVEL_MAX = 5000
#: Nível assumido quando o catálogo não traz nenhuma pista (compat. com UI antiga).
DEFAULT_UNSPECIFIED_LEVEL = 1

GENDER_MALE = "male"
GENDER_FEMALE = "female"
GENDER_PAIR = "pair"
GENDER_RANDOM = "random"
GENDERS = (GENDER_MALE, GENDER_FEMALE, GENDER_PAIR, GENDER_RANDOM)

GENDER_LABELS_PT: dict[str, str] = {
    GENDER_MALE: "Macho",
    GENDER_FEMALE: "Fêmea",
    GENDER_PAIR: "Casal",
    GENDER_RANDOM: "Aleatório",
}

#: Abas legadas da loja que apontavam para «Dinos 200».
LEGACY_DINOS200_TABS = frozenset({
    "dinos200", "dinos_200", "dinos-200", "dinos 200", "dino200", "dino_200", "dino-200",
})
LEGACY_DINOS200_LEVEL = 200


def dino_level_max(settings: dict[str, Any] | None = None) -> int:
    """Teto configurável do nível de cadastro (settings ``shop_dino_level_max`` > env > 500)."""
    raw: Any = None
    if isinstance(settings, dict):
        raw = settings.get("shop_dino_level_max")
    if raw in (None, "", 0, "0"):
        raw = os.environ.get("ARKSHOP_DINO_LEVEL_MAX")
    try:
        n = int(str(raw).strip()) if raw not in (None, "") else DEFAULT_DINO_LEVEL_MAX
    except (TypeError, ValueError):
        n = DEFAULT_DINO_LEVEL_MAX
    if n < DINO_LEVEL_MIN:
        n = DEFAULT_DINO_LEVEL_MAX
    return min(n, HARD_DINO_LEVEL_MAX)


# ── Nível ────────────────────────────────────────────────────────────────────
def parse_dino_level(raw: Any, *, max_level: int | None = None) -> int | None:
    """Converte para nível válido (inteiro 1..max) ou ``None`` se inválido.

    Aceita ``int``, ``"200"``, ``200.0``. Rejeita 0, negativos, ``bool``, texto
    («abc»), frações («1.5») e valores acima do teto.
    """
    if raw is None or isinstance(raw, bool):
        return None
    cap = int(max_level) if max_level is not None else HARD_DINO_LEVEL_MAX
    value: int
    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, float):
        if raw != raw or raw in (float("inf"), float("-inf")) or raw != int(raw):
            return None
        value = int(raw)
    else:
        s = str(raw).strip()
        if not re.fullmatch(r"[+-]?\d{1,6}", s):
            return None
        value = int(s)
    if value < DINO_LEVEL_MIN or value > cap:
        return None
    return value


def _fold(text: Any) -> str:
    s = unicodedata.normalize("NFD", str(text or ""))
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn").lower()


_LEVEL_WORD_RE = re.compile(
    r"(?<![a-z0-9])(?:nivel|level|lvl|lv|nv)\.?\s*[:#=-]?\s*(\d{1,4})(?![0-9])"
)
_LEVEL_L_RE = re.compile(r"(?<![a-z0-9])l(\d{1,4})(?![a-z0-9])")
_LEVEL_SUFFIX_RE = re.compile(r"_(\d{1,4})$")
_LEVEL_CATEGORY_RE = re.compile(r"(?<![a-z0-9])dinos?[\s_-]*l?(\d{1,4})(?![0-9])")


def infer_level_from_text(text: Any, *, allow_suffix: bool = False) -> int | None:
    """Infere o nível de textos como «LVL 200», «Nível 150», «L200», ``rex_l200``.

    ``allow_suffix`` aceita ``_200`` no fim de ids (não usar em descrições livres).
    """
    s = _fold(text)
    if not s:
        return None
    for rx in (_LEVEL_WORD_RE, _LEVEL_L_RE):
        m = rx.search(s)
        if m:
            lvl = parse_dino_level(m.group(1), max_level=HARD_DINO_LEVEL_MAX)
            if lvl is not None:
                return lvl
    if allow_suffix:
        m = _LEVEL_SUFFIX_RE.search(s.strip())
        if m:
            lvl = parse_dino_level(m.group(1), max_level=HARD_DINO_LEVEL_MAX)
            if lvl is not None:
                return lvl
    return None


def infer_level_from_category(category: Any) -> int | None:
    """«Dinos 200» / «dinos_200» / «Dinos L200» → 200; «Dinos» → ``None``."""
    s = _fold(category)
    if not s:
        return None
    m = _LEVEL_CATEGORY_RE.search(s)
    if m:
        return parse_dino_level(m.group(1), max_level=HARD_DINO_LEVEL_MAX)
    return None


def _dinos_list(entry: dict[str, Any]) -> list[dict[str, Any]]:
    raw = entry.get("Dinos") if isinstance(entry, dict) else None
    if not isinstance(raw, list):
        return []
    return [d for d in raw if isinstance(d, dict)]


def entry_dino_level_info(entry: dict[str, Any], key: str = "") -> tuple[int, str]:
    """Nível primário do item/kit + origem (``dinos`` | ``field`` | ``category`` | ``text`` | ``default``)."""
    if not isinstance(entry, dict):
        return DEFAULT_UNSPECIFIED_LEVEL, "default"
    dinos = _dinos_list(entry)
    if dinos:
        lvl = parse_dino_level(dinos[0].get("Level", dinos[0].get("level")),
                               max_level=HARD_DINO_LEVEL_MAX)
        if lvl is not None:
            return lvl, "dinos"
    for field in ("dino_level", "DinoLevel", "Level", "level"):
        if field in entry:
            lvl = parse_dino_level(entry.get(field), max_level=HARD_DINO_LEVEL_MAX)
            if lvl is not None:
                return lvl, "field"
    lvl = infer_level_from_category(entry.get("Category") or entry.get("category")
                                    or entry.get("display_category"))
    if lvl is not None:
        return lvl, "category"
    lvl = infer_level_from_text(key, allow_suffix=True)
    if lvl is None:
        for field in ("Name", "name", "Description", "description"):
            lvl = infer_level_from_text(entry.get(field))
            if lvl is not None:
                break
    if lvl is not None:
        return lvl, "text"
    return DEFAULT_UNSPECIFIED_LEVEL, "default"


def entry_dino_level(entry: dict[str, Any], key: str = "") -> int:
    return entry_dino_level_info(entry, key)[0]


def entry_dino_levels(entry: dict[str, Any], key: str = "") -> list[int]:
    """Todos os níveis distintos (ordenados) dos ``Dinos[]``; fallback = nível primário."""
    levels: set[int] = set()
    for d in _dinos_list(entry):
        lvl = parse_dino_level(d.get("Level", d.get("level")), max_level=HARD_DINO_LEVEL_MAX)
        if lvl is not None:
            levels.add(lvl)
    if not levels:
        levels.add(entry_dino_level(entry, key))
    return sorted(levels)


# ── Gênero ───────────────────────────────────────────────────────────────────
_GENDER_FEMALE_RE = re.compile(r"(?<![a-z0-9])(?:femeas?|females?|fem)(?![a-z0-9])|♀")
_GENDER_MALE_RE = re.compile(r"(?<![a-z0-9])(?:machos?|males?|masc)(?![a-z0-9])|♂")
_GENDER_PAIR_RE = re.compile(r"(?<![a-z0-9])(?:casal|casais|couple|pair|par)(?![a-z0-9])")

_EXPLICIT_FEMALE = {"female", "femea", "fem", "f", "2", "♀", "femeas", "females"}
_EXPLICIT_MALE = {"male", "macho", "masc", "m", "1", "♂", "machos", "males"}
_EXPLICIT_RANDOM = {"random", "aleatorio", "any", "none", "no", "n/a", "na", "3", "neutral",
                    "neutro", "", "?"}
_EXPLICIT_PAIR = {"pair", "casal", "couple", "both", "ambos"}


def normalize_gender(raw: Any) -> str | None:
    """Normaliza um valor **explícito** de gênero.

    Devolve ``male|female|pair|random`` ou ``None`` se o valor não for reconhecido
    (ex.: texto inesperado) — ``None``/vazio explícito → ``random``.
    """
    if raw is None:
        return GENDER_RANDOM
    s = _fold(raw).strip()
    if s in _EXPLICIT_FEMALE:
        return GENDER_FEMALE
    if s in _EXPLICIT_MALE:
        return GENDER_MALE
    if s in _EXPLICIT_PAIR:
        return GENDER_PAIR
    if s in _EXPLICIT_RANDOM:
        return GENDER_RANDOM
    return None


def infer_gender_from_text(*texts: Any) -> str | None:
    """Infere gênero de nome/descrição/id («FEMEA», «MACHO», «FEM», «MALE», «Casal»)."""
    folded = " ".join(_fold(t) for t in texts if t)
    if not folded.strip():
        return None
    female = bool(_GENDER_FEMALE_RE.search(folded))
    male = bool(_GENDER_MALE_RE.search(folded))
    if female and male:
        return GENDER_PAIR
    if female:
        return GENDER_FEMALE
    if male:
        return GENDER_MALE
    if _GENDER_PAIR_RE.search(folded):
        return GENDER_PAIR
    return None


def entry_dino_gender_info(entry: dict[str, Any], key: str = "") -> tuple[str, str]:
    """Gênero do item/kit + origem (``explicit`` | ``inferred`` | ``default``)."""
    if not isinstance(entry, dict):
        return GENDER_RANDOM, "default"
    dinos = _dinos_list(entry)
    explicit: list[str] = []
    for d in dinos:
        raw = d.get("Gender", d.get("gender"))
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            continue
        g = normalize_gender(raw)
        if g in (GENDER_MALE, GENDER_FEMALE, GENDER_PAIR):
            explicit.append(g)
    if explicit:
        distinct = set(explicit)
        if len(distinct) > 1 or GENDER_PAIR in distinct:
            return GENDER_PAIR, "explicit"
        only = next(iter(distinct))
        if len(explicit) == len(dinos):
            return only, "explicit"
        return GENDER_RANDOM, "explicit"  # só parte dos dinos tem gênero definido
    top = entry.get("Gender", entry.get("gender", entry.get("dino_gender")))
    if top is not None and str(top).strip():
        g = normalize_gender(top)
        if g in (GENDER_MALE, GENDER_FEMALE, GENDER_PAIR):
            return g, "explicit"
    inferred = infer_gender_from_text(
        key,
        entry.get("Name") or entry.get("name"),
        entry.get("Description") or entry.get("description"),
    )
    if inferred:
        return inferred, "inferred"
    return GENDER_RANDOM, "default"


def entry_dino_gender(entry: dict[str, Any], key: str = "") -> str:
    return entry_dino_gender_info(entry, key)[0]


def gender_label(gender: str | None) -> str:
    return GENDER_LABELS_PT.get(str(gender or GENDER_RANDOM), GENDER_LABELS_PT[GENDER_RANDOM])


# ── Metadados para o card / API ──────────────────────────────────────────────
def is_dino_entry(entry: dict[str, Any]) -> bool:
    if not isinstance(entry, dict):
        return False
    if str(entry.get("Type") or entry.get("type") or "").lower() == "dino":
        return True
    return bool(_dinos_list(entry))


def dino_card_meta(entry: dict[str, Any], key: str = "") -> dict[str, Any]:
    """Campos extras ``dino_*`` para ``/api/catalog`` (itens tipo dino e kits com ``Dinos[]``)."""
    level, level_src = entry_dino_level_info(entry, key)
    gender, gender_src = entry_dino_gender_info(entry, key)
    levels = entry_dino_levels(entry, key)
    meta: dict[str, Any] = {
        "dino_level": level,
        "dino_level_source": level_src,
        "dino_gender": gender,
        "dino_gender_label": gender_label(gender),
        "dino_gender_source": gender_src,
        "dino_count": max(1, len(_dinos_list(entry))),
    }
    if len(levels) > 1:
        meta["dino_levels"] = levels
    return meta


def collect_level_options(entries: Iterable[dict[str, Any]]) -> list[dict[str, int]]:
    """Lista dinâmica ``[{level, count}]`` (ordem crescente) a partir de itens dino."""
    counts: dict[int, int] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        lvl = entry.get("dino_level")
        lvl = parse_dino_level(lvl, max_level=HARD_DINO_LEVEL_MAX) or entry_dino_level(entry)
        counts[lvl] = counts.get(lvl, 0) + 1
    return [{"level": lvl, "count": counts[lvl]} for lvl in sorted(counts)]


def legacy_tab_redirect(tab: Any) -> tuple[str, int | None]:
    """Mapeia aba antiga → (aba nova, filtro de nível). ``dinos200`` → ``("dinos", 200)``."""
    t = str(tab or "").strip().lower()
    if t in LEGACY_DINOS200_TABS:
        return "dinos", LEGACY_DINOS200_LEVEL
    return t, None


# ── Variantes por nível (geração de catálogo) ────────────────────────────────
_LEVEL_ID_SUFFIX_RE = re.compile(r"_l\d{1,4}$", re.IGNORECASE)
_LEVEL_PHRASE_RE = re.compile(r"(?i)\b(n[ií]vel|nivel|level|lvl)\s*\d{1,4}\b")


def base_item_id(item_id: str) -> str:
    """``rex_femea_l200`` → ``rex_femea`` (remove sufixo ``_l<N>``)."""
    return _LEVEL_ID_SUFFIX_RE.sub("", str(item_id or "").strip())


def level_variant_id(base_id: str, level: int) -> str:
    """ID da variante de nível: nível 1 mantém o id base; demais → ``<base>_l<N>``."""
    lvl = parse_dino_level(level, max_level=HARD_DINO_LEVEL_MAX)
    if lvl is None:
        raise ValueError(f"Nível inválido: {level!r}")
    base = base_item_id(base_id)
    return base if lvl == 1 else f"{base}_l{lvl}"


def retitle_for_level(text: str, level: int) -> str:
    """Troca «Nível 1» por «Nível N» (ou acrescenta) na descrição/nome da variante."""
    s = str(text or "").strip()
    if not s:
        return s
    if _LEVEL_PHRASE_RE.search(s):
        return _LEVEL_PHRASE_RE.sub(lambda m: f"{m.group(1)} {int(level)}", s, count=1)
    return f"{s} Nível {int(level)}"


def interpolate_level_price(
    p1: int,
    p_ref: int,
    level: int,
    *,
    ref_level: int = 200,
    round_to: int = 100,
) -> int:
    """Preço linear entre (nível 1, ``p1``) e (``ref_level``, ``p_ref``).

    Extrapola linearmente acima de ``ref_level``; nunca menor que ``p1`` (+1 se nível > 1).
    Arredonda para ``round_to`` (padrão 100 Âmbares).
    """
    p1 = max(0, int(p1))
    p_ref = max(0, int(p_ref))
    lvl = max(1, int(level))
    if lvl == 1 or ref_level <= 1:
        return p1
    slope = (p_ref - p1) / float(ref_level - 1)
    raw = p1 + slope * (lvl - 1)
    step = max(1, int(round_to))
    out = int(round(raw / step) * step)
    return max(out, p1 + 1)


# ── Validação / migração de catálogo ─────────────────────────────────────────
_CATALOG_ITEM_KEYS = ("Items", "ShopItems")


def _catalog_items(catalog: dict[str, Any]) -> dict[str, Any]:
    for k in _CATALOG_ITEM_KEYS:
        v = catalog.get(k)
        if isinstance(v, dict):
            return v
    return {}


def _iter_entries_with_dinos(catalog: dict[str, Any]) -> Iterable[tuple[str, str, dict[str, Any]]]:
    for key, entry in _catalog_items(catalog).items():
        if isinstance(entry, dict):
            yield "Items", str(key), entry
    kits = catalog.get("Kits")
    if isinstance(kits, dict):
        for key, entry in kits.items():
            if isinstance(entry, dict) and isinstance(entry.get("Dinos"), list):
                yield "Kits", str(key), entry


def validate_catalog_dino_levels(
    catalog: dict[str, Any],
    *,
    max_level: int | None = None,
) -> list[dict[str, Any]]:
    """Erros de ``Dinos[].Level`` informado mas inválido (0, negativo, texto, > teto).

    ``Level`` ausente/``null`` é aceito (será inferido). Devolve ``[]`` se tudo OK.
    """
    cap = int(max_level) if max_level is not None else dino_level_max()
    errors: list[dict[str, Any]] = []
    if not isinstance(catalog, dict):
        return errors
    for section, key, entry in _iter_entries_with_dinos(catalog):
        raw_dinos = entry.get("Dinos")
        if not isinstance(raw_dinos, list):
            continue
        for idx, d in enumerate(raw_dinos):
            if not isinstance(d, dict) or "Level" not in d:
                continue
            raw = d.get("Level")
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                continue
            if parse_dino_level(raw, max_level=cap) is None:
                errors.append({
                    "section": section,
                    "item_id": key,
                    "dino_index": idx,
                    "value": raw,
                    "error": f"Nível inválido em «{key}» (Dino {idx + 1}): "
                             f"use um inteiro entre {DINO_LEVEL_MIN} e {cap}.",
                })
    return errors


def migrate_catalog_dinos(
    catalog: dict[str, Any],
    *,
    write_inferred_gender: bool = False,
) -> dict[str, Any]:
    """Migra catálogos antigos para o modelo unificado (idempotente, in-place).

    - ``Dinos[].Level`` ausente/ inválido → nível inferido (categoria/id/nome) e gravado;
    - ``Level`` já válido **nunca** é alterado;
    - ``Category`` «Dinos 200» (e variantes) em itens dino → «Dinos»;
    - ``write_inferred_gender=True`` grava ``Gender`` inferido do id/nome nos ``Dinos[]``
      sem gênero (⚠ muda a entrega de aleatório → fixo; por isso é opt-in).

    Devolve relatório ``{changed_items, level_filled, category_fixed, gender_filled, items}``.
    """
    report: dict[str, Any] = {
        "changed_items": 0, "level_filled": 0, "category_fixed": 0,
        "gender_filled": 0, "unresolved_level": [],
    }
    if not isinstance(catalog, dict):
        return report
    for section, key, entry in _iter_entries_with_dinos(catalog):
        is_dino_item = section == "Items" and str(entry.get("Type") or "").lower() == "dino"
        dinos = entry.get("Dinos")
        if not is_dino_item and not (section == "Kits" and isinstance(dinos, list)):
            continue
        changed = False
        if is_dino_item:
            cat = entry.get("Category")
            if isinstance(cat, str) and cat.strip() and infer_level_from_category(cat) is not None:
                entry["Category"] = "Dinos"
                report["category_fixed"] += 1
                changed = True
        if isinstance(dinos, list):
            # Pista de nível sem olhar Dinos[] (categoria/campo/id/nome).
            shell = {k: v for k, v in entry.items() if k != "Dinos"}
            fallback_level, src = entry_dino_level_info(shell, key)
            for d in dinos:
                if not isinstance(d, dict):
                    continue
                if "Level" not in d or d.get("Level") in (None, ""):
                    # Level ausente → grava inferido; Level inválido explícito NÃO é reescrito
                    if src == "default":
                        if key not in report["unresolved_level"]:
                            report["unresolved_level"].append(key)
                    else:
                        d["Level"] = fallback_level
                        report["level_filled"] += 1
                        changed = True
                if write_inferred_gender and not str(d.get("Gender") or "").strip():
                    inferred = infer_gender_from_text(
                        key, entry.get("Name"), entry.get("Description"))
                    if inferred in (GENDER_MALE, GENDER_FEMALE):
                        d["Gender"] = inferred
                        report["gender_filled"] += 1
                        changed = True
        if changed:
            report["changed_items"] += 1
    return report
