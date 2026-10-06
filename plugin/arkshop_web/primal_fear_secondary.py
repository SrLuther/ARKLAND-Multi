"""Referência secundária do Primal Fear. Não altera o piso R + B×Q.

A faixa sai do nome, do prefixo ou da classe já escrita na ficha.
O índice é M ÷ 5 (Alpha = 1). A referência é a raiz da família vanilla
vezes esse índice, com teto de 600000. Sem família, sem M ou sem faixa,
a referência fica vazia. Spawn, tier numérico de chefe e mecânicas
(toxicidade, corrupção, ascensão) não entram na conta.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

_FICHA_PATH = Path(__file__).resolve().parent / "static" / "primal_fear_ficha.json"
_BP_RE = re.compile(r"Blueprint'([^']+)'", re.I)

# M do General Info. Buffoon, Elder e Primal (não Tek) não têm M fixo.
# Celestial/Demonic e Chaos/Spirit usam o meio da faixa do documento.
_BANDS: dict[str, tuple[str, float | None]] = {
    "toxic": ("Toxic", 3),
    "alpha": ("Alpha", 5),
    "elemental_basic": ("Elemental Basic", 7.5),
    "apex": ("Apex", 10),
    "elemental_advanced": ("Elemental Advanced", 14),
    "omega": ("Omega", 13),
    "fabled": ("Fabled", 16),
    "black_omega": ("Black Omega", 16),
    "celestial": ("Celestial", 27.5),
    "demonic": ("Demonic", 27.5),
    "chaos": ("Chaos", 40),
    "spirit": ("Spirit", 40),
    "buffoon": ("Buffoon", None),
    "elder": ("Elder", None),
    "primal_tek": ("Primal Tek", 12),
    "primal": ("Primal", None),
}

# Pastas de mod, a mais específica primeiro. Não inventa criatura.
_PATH_MODS: tuple[tuple[str, str], ...] = (
    ("primal_fear_noxious_creatures", "Noxious Creatures"),
    ("primal_fear_bosses", "Primal Fear Boss Expansion"),
    ("primal_fear_scorched_earth", "Primal Fear Scorched Earth Expansion"),
    ("primal_fear_scorched", "Primal Fear Scorched Earth Expansion"),
    ("primal_fear_extinction", "Primal Fear Extinction Expansion"),
    ("primal_fear_aberration", "Primal Fear Aberration Expansion"),
    ("primal_fear_genesis", "Primal Fear Genesis Expansion"),
    ("primal_fear_fey", "Primal Fear Fey Expansion"),
    ("primal_fear_dodo", "Primal Fear Dodo Expansion"),
    ("primal_fear_unofficial_extras", "Primal Fear | Unofficial Extras"),
    ("primal_fear_unofficial", "Primal Fear | Unofficial Extras"),
    ("unofficial_extras", "Primal Fear | Unofficial Extras"),
    ("primal_fear", "Primal Fear"),
)

TRACKED_MODS: tuple[str, ...] = (
    "Noxious Creatures",
    "Primal Fear",
    "Primal Fear Scorched Earth Expansion",
    "Primal Fear Extinction Expansion",
    "Primal Fear Aberration Expansion",
    "Primal Fear Genesis Expansion",
    "Primal Fear Fey Expansion",
    "Primal Fear Boss Expansion",
    "Primal Fear Dodo Expansion",
    "Primal Fear | Unofficial Extras",
)

_GROUP_BAND: dict[str, str] = {
    "alpha": "alpha",
    "alfa": "alpha",
    "toxic": "toxic",
    "toxico": "toxic",
    "apex": "apex",
    "fabled": "fabled",
    "elder": "elder",
    "anciao": "elder",
    "buffoon": "buffoon",
    "elementals": "elemental",
    "elemental": "elemental",
    "elementais": "elemental",
    "elemental basic": "elemental_basic",
    "elemental basico": "elemental_basic",
    "elemental advanced": "elemental_advanced",
    "elemental avancado": "elemental_advanced",
    "demonic": "demonic",
    "demoniaco": "demonic",
    "celestial": "celestial",
    "chaos": "chaos",
    "caos": "chaos",
    "spirit": "spirit",
    "espirito": "spirit",
    "omega": "omega",
    "black omega": "black_omega",
    "omega negro": "black_omega",
    "primal tek": "primal_tek",
    "primal": "primal",
}

_NAME_BANDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("celestial", ("celestial",)),
    ("demonic", ("demonic", "demoniaco")),
    ("chaos", ("chaos", "caos")),
    ("spirit", ("spirit", "espirito")),
    ("buffoon", ("buffoon",)),
    ("elder", ("elder", "anciao")),
    ("fabled", ("fabled",)),
    ("apex", ("apex",)),
    ("omega", ("omega",)),
    ("alpha", ("alpha", "alfa")),
    ("toxic", ("toxic", "toxico")),
)

_FOLDER_NOISE: tuple[str, ...] = (
    "primalfearnoxiouscreatures",
    "primalfearbosses",
    "primalfearscorchedearth",
    "primalfearextinction",
    "primalfearaberration",
    "primalfeargenesis",
    "primalfearfey",
    "primalfeardodo",
    "primalfearunofficialextras",
    "primalfearunofficial",
    "primalfear",
)

_ROSTER: dict[str, Any] | None = None


def _fold(text: str) -> str:
    folded = (text or "").strip().lower()
    for src, dst in (
        ("á", "a"),
        ("à", "a"),
        ("ã", "a"),
        ("â", "a"),
        ("é", "e"),
        ("ê", "e"),
        ("í", "i"),
        ("ó", "o"),
        ("ô", "o"),
        ("õ", "o"),
        ("ú", "u"),
        ("ç", "c"),
    ):
        folded = folded.replace(src, dst)
    return folded


def _flat(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _fold(text))


def _norm_bp(bp: str | None) -> str:
    text = (bp or "").strip()
    if not text:
        return ""
    found = _BP_RE.search(text)
    if found:
        text = found.group(1)
    text = text.strip().strip("'\"")
    if " " in text:
        head, tail = text.rsplit(" ", 1)
        head_l = head.lower()
        if "blueprint" in head_l or head_l.endswith("class"):
            text = tail
    text = text.lower()
    if "." in text:
        pkg, cls = text.rsplit(".", 1)
        if cls.endswith("_c") and len(cls) > 2:
            text = f"{pkg}.{cls[:-2]}"
    return text


def _stem(value: str | None) -> str:
    norm = _norm_bp(value) if value and ("/" in value or "blueprint" in value.lower()) else _fold(value or "")
    short = norm.rsplit("/", 1)[-1].split(".")[0]
    for suffix in ("_character_bp_child", "_character_bp", "_c"):
        if short.endswith(suffix) and len(short) > len(suffix):
            short = short[: -len(suffix)]
            break
    return short.strip("_")


def mod_from_blueprint(bp: str | None) -> str | None:
    """Mod de origem pela pasta do blueprint. Pastas mais longas ganham."""
    norm = _norm_bp(bp)
    found = re.search(r"/mods/([^/]+)", norm)
    if not found:
        return None
    folder = found.group(1)
    for key, label in _PATH_MODS:
        if folder == key:
            return label
    return None


def _group_band(group: str) -> str:
    return _GROUP_BAND.get(_fold(group), "")


def _strip_folder_noise(flat: str) -> str:
    cleaned = flat
    for noise in _FOLDER_NOISE:
        cleaned = cleaned.replace(noise, "")
    return cleaned


def detect_primal_fear_band(signals: list[str], group: str = "") -> str | None:
    """Faixa PF. Não trata corrupção, ascensão nem a pasta do mod como faixa."""
    flat = _strip_folder_noise(_flat(" ".join(part for part in signals if part)))
    group_key = _group_band(group)
    if group_key == "primal_tek" or "primaltek" in flat or "bionic" in flat:
        return "primal_tek"
    if group_key == "black_omega" or "blackomega" in flat:
        return "black_omega"
    elemental = group_key in {"elemental", "elemental_basic", "elemental_advanced"} or "elemental" in flat
    light_dark = bool(re.search(r"(light|dark)", flat))
    if group_key == "elemental_advanced" or (elemental and ("elementaladvanced" in flat or light_dark)):
        return "elemental_advanced"
    if group_key in {"elemental", "elemental_basic"} or "elementalbasic" in flat or (elemental and "elemental" in flat):
        return "elemental_basic"
    scan = flat.replace("blackomega", "").replace("fallendemonics", "").replace("fallendemonic", "")
    for band, tokens in _NAME_BANDS:
        if group_key == band or any(token in scan for token in tokens):
            return band
    if group_key == "primal" or "primal" in flat.replace("primaltek", ""):
        return "primal"
    return None


def _band_payload(band: str | None, family_root: int | None, cap: int) -> tuple[str | None, int | float | None, int | None]:
    if not band or band not in _BANDS:
        return None, None, None
    label, multiplier = _BANDS[band]
    if multiplier is None:
        return label, None, None
    index_dec = (Decimal(str(multiplier)) / Decimal(5)).quantize(Decimal("0.1"))
    index: int | float = int(index_dec) if index_dec == index_dec.to_integral_value() else float(index_dec)
    if family_root is None:
        return label, index, None
    raw = (Decimal(int(family_root)) * index_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return label, index, min(int(raw), int(cap))


def _note(band: str | None, flat: str) -> str | None:
    parts: list[str] = []
    if band in {"buffoon", "elder", "primal"}:
        parts.append("Sem multiplicador fixo.")
    if "corrupt" in flat:
        parts.append("Corrupção não entra na referência.")
    if "ascend" in flat:
        parts.append("Ascensão não entra na referência.")
    return " ".join(parts) or None


def _empty_fields() -> dict[str, Any]:
    return {
        "pf_band": None,
        "pf_index": None,
        "pf_reference": None,
        "pf_mod": None,
        "pf_note": None,
    }


def _extract_bp(text: str) -> str:
    found = _BP_RE.search(text or "")
    return found.group(1) if found else ""


def _creature(mod: str, name: str, group: str, blueprint: str, entity: str, tag: str) -> dict[str, str]:
    return {
        "mod": mod,
        "name": name.strip(),
        "group": group.strip(),
        "blueprint": blueprint.strip(),
        "entity": entity.strip(),
        "tag": tag.strip(),
    }


def _remember(bucket: dict[str, Any], creature: dict[str, str]) -> None:
    if not creature["name"] and not creature["blueprint"] and not creature["entity"]:
        return
    bucket["creatures"].append(creature)
    bucket["counts"][creature["mod"]] = bucket["counts"].get(creature["mod"], 0) + 1
    norm = _norm_bp(creature["blueprint"])
    if norm:
        bucket["by_blueprint"].setdefault(norm, creature)
    for token in (
        _stem(creature["blueprint"]),
        _stem(creature["entity"]),
        _stem(creature["tag"]),
    ):
        if len(token) >= 4:
            bucket["by_token"].setdefault(token, creature)


def _parse_dino_sheet(sheet: dict[str, Any], bucket: dict[str, Any]) -> None:
    for group in sheet.get("groups") or []:
        title = str(group.get("title") or "")
        for dino in group.get("dinos") or []:
            fields = {
                str(field.get("label") or ""): str(field.get("value") or "")
                for field in (dino.get("fields") or [])
                if isinstance(field, dict)
            }
            spawn = fields.get("Spawn") or fields.get("Spawn Code") or ""
            _remember(
                bucket,
                _creature(
                    "Primal Fear",
                    str(dino.get("name") or ""),
                    title,
                    _extract_bp(spawn),
                    fields.get("Entity ID") or "",
                    fields.get("Tag") or "",
                ),
            )


def _parse_noxious(sheet: dict[str, Any], bucket: dict[str, Any]) -> None:
    for block in sheet.get("blocks") or []:
        if block.get("type") != "table":
            continue
        for row in block.get("rows") or []:
            if not isinstance(row, list) or len(row) < 3:
                continue
            name = str(row[0] or "").strip()
            if _fold(name) in {"", "dino name", "tier"}:
                continue
            spawn = str(row[2] or "")
            blueprint = _extract_bp(spawn)
            if not blueprint:
                continue
            _remember(
                bucket,
                _creature("Noxious Creatures", name, "", blueprint, "", str(row[1] or "")),
            )


def _cell_entity(cells: list[str]) -> str:
    for cell in cells:
        low = cell.lower()
        if "blueprint" in low or "admincheat" in low or "spawn" in low:
            continue
        if "character_bp" in low or low.endswith("_c"):
            return cell
    return ""


def _cell_tag(cells: list[str]) -> str:
    for cell in cells:
        low = cell.lower()
        if "blueprint" in low or "admincheat" in low:
            continue
        if low.startswith("pfb") or low.startswith("pfnc") or low.startswith("pf"):
            return cell
    return ""


def _parse_boss(sheet: dict[str, Any], bucket: dict[str, Any]) -> None:
    section = ""
    for block in sheet.get("blocks") or []:
        kind = block.get("type")
        if kind == "h2":
            section = str(block.get("text") or "").strip()
            continue
        if kind != "table":
            continue
        for row in block.get("rows") or []:
            if not isinstance(row, list) or not row:
                continue
            cells = [str(cell or "").strip() for cell in row]
            name = cells[0]
            folded = _fold(name)
            if folded in {"", "dino name", "tier", "taming food"}:
                continue
            if folded == "vanilla":
                section = "Vanilla"
                continue
            blob = " ".join(cells)
            blueprint = _extract_bp(blob)
            entity = _cell_entity(cells)
            if not blueprint and not entity:
                continue
            _remember(
                bucket,
                _creature(
                    "Primal Fear Boss Expansion",
                    name,
                    section,
                    blueprint,
                    entity,
                    _cell_tag(cells),
                ),
            )


def _build_roster() -> dict[str, Any]:
    bucket: dict[str, Any] = {
        "creatures": [],
        "counts": {mod: 0 for mod in TRACKED_MODS},
        "by_blueprint": {},
        "by_token": {},
    }
    if not _FICHA_PATH.is_file():
        return bucket
    try:
        data = json.loads(_FICHA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return bucket
    sheets = {str(sheet.get("id") or ""): sheet for sheet in data.get("sheets") or [] if isinstance(sheet, dict)}
    if "dino-tags" in sheets:
        _parse_dino_sheet(sheets["dino-tags"], bucket)
    if "noxious-creatures" in sheets:
        _parse_noxious(sheets["noxious-creatures"], bucket)
    if "pf-boss-expansion" in sheets:
        _parse_boss(sheets["pf-boss-expansion"], bucket)
    return bucket


def primal_fear_roster() -> dict[str, Any]:
    """Criaturas lidas da ficha. Só leitura: não grava o JSON."""
    global _ROSTER
    if _ROSTER is None:
        _ROSTER = _build_roster()
    return _ROSTER


def primal_fear_roster_counts() -> dict[str, int]:
    counts = primal_fear_roster().get("counts") or {}
    return {mod: int(counts.get(mod) or 0) for mod in TRACKED_MODS}


def _catalog_blueprint(entry: dict[str, Any] | None) -> str:
    if not isinstance(entry, dict):
        return ""
    dinos = entry.get("Dinos") or []
    if dinos and isinstance(dinos[0], dict):
        return str(dinos[0].get("Blueprint") or "")
    return ""


def _match_roster(blueprint: str, item_id: str) -> dict[str, str] | None:
    roster = primal_fear_roster()
    norm = _norm_bp(blueprint)
    if norm and norm in roster["by_blueprint"]:
        return roster["by_blueprint"][norm]
    for token in (_stem(blueprint), _stem(item_id)):
        if len(token) >= 4 and token in roster["by_token"]:
            return roster["by_token"][token]
    return None


def _mod_from_identity(item_id: str, display_name: str) -> str | None:
    item = _fold(item_id).replace("-", "_")
    name = _fold(display_name)
    flat = _flat(f"{item_id} {display_name}")
    if "noxious" in name or "noxious" in item or flat.startswith("pfnc") or item.startswith("pfn_"):
        return "Noxious Creatures"
    if flat.startswith("pfb") or item.startswith("pfb_") or "boss expansion" in name:
        return "Primal Fear Boss Expansion"
    if item.startswith("pf_") or name.startswith("pf ") or name.startswith("pf_") or "primal fear" in name:
        return "Primal Fear"
    return None


def primal_fear_secondary_fields(
    *,
    item_id: str,
    entry: dict[str, Any] | None,
    display_name: str,
    family_root: int | None,
    cap: int,
) -> dict[str, Any]:
    """Faixa, índice, referência e mod. Não mexe em R, B nem no piso."""
    blueprint = _catalog_blueprint(entry)
    matched = _match_roster(blueprint, item_id)
    mod = mod_from_blueprint(blueprint)
    if not mod and matched:
        mod = matched.get("mod") or None
    if not mod:
        mod = _mod_from_identity(item_id, display_name)
    if not mod:
        return _empty_fields()
    group = matched.get("group") if matched else ""
    signals = [
        display_name,
        item_id,
        blueprint,
        (matched or {}).get("name") or "",
        (matched or {}).get("entity") or "",
        (matched or {}).get("tag") or "",
        group or "",
    ]
    band = detect_primal_fear_band(signals, group or "")
    label, index, reference = _band_payload(band, family_root, cap)
    return {
        "pf_band": label,
        "pf_index": index,
        "pf_reference": reference,
        "pf_mod": mod,
        "pf_note": _note(band, _flat(" ".join(signals))),
    }
