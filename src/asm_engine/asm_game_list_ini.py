"""Listas agregadas do Game.ini (chaves repetidas — Fase 4 TEK)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..ark_ini_spawn import (
    _parse_dino_class_multiplier,
    _serialize_dino_class_multiplier,
)

if TYPE_CHECKING:
    from .asm_server_config import AsmServerConfig

_GAME_MODE_SECTION = "/Script/ShooterGame.ShooterGameMode"

# Prefixos de chaves que podem repetir na mesma seção (case-insensitive).
REPEATED_KEY_PREFIXES: tuple[str, ...] = (
    "harvestresourceitemamountclassmultipliers",
    "dinoclassresistancemultipliers",
    "dinoclassdamagemultipliers",
    "tameddinoclassresistancemultipliers",
    "tameddinoclassdamagemultipliers",
    "dinospawnweightmultipliers",
    "preventdinotameclassnames",
    "configoverrideitemcraftingcosts",
    "configoverrideitemmaxquantity",
    "configaddnpcspawnentriescontainer",
    "configsubtractnpcspawnentriescontainer",
    "configoverridenpcspawnentriescontainer",
    "configoverridesupplycrateitems",
    "overrideplayerlevelengrampoints",
)

_STRIP_RE = re.compile(
    r"^(?:"
    + "|".join(re.escape(p) for p in REPEATED_KEY_PREFIXES)
    + r")\s*=.*$",
    re.IGNORECASE | re.MULTILINE,
)

_REPEATED_KEY_SET = frozenset(REPEATED_KEY_PREFIXES)


def is_repeated_game_ini_key(key: str) -> bool:
    """True para chaves que o ARK permite repetir na mesma seção (patch pós-escrita)."""
    return key.lower() in _REPEATED_KEY_SET


def _read_text(path: Path) -> str:
    for enc in ("utf-16", "utf-8-sig", "utf-8", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def parse_spawn_weight(value: str) -> dict | None:
    text = value.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    m_tag = re.search(r'DinoNameTag\s*=\s*"?([^",)]+)"?', text, re.I)
    if not m_tag:
        return None
    m_w = re.search(r"SpawnWeightMultiplier\s*=\s*([\d.]+)", text, re.I)
    m_ov = re.search(r"OverrideSpawnLimitPercentage\s*=\s*(\w+)", text, re.I)
    m_lim = re.search(r"SpawnLimitPercentage\s*=\s*([\d.]+)", text, re.I)
    try:
        weight = float(m_w.group(1)) if m_w else 1.0
    except ValueError:
        weight = 1.0
    try:
        limit = float(m_lim.group(1)) if m_lim else 1.0
    except ValueError:
        limit = 1.0
    override = m_ov.group(1).strip().lower() in ("true", "1") if m_ov else False
    return {
        "dino_name_tag": m_tag.group(1).strip(),
        "spawn_weight_multiplier": weight,
        "override_spawn_limit_percentage": override,
        "spawn_limit_percentage": limit,
    }


def serialize_spawn_weight(entry: dict) -> str:
    tag = entry.get("dino_name_tag", "")
    weight = entry.get("spawn_weight_multiplier", 1.0)
    override = bool(entry.get("override_spawn_limit_percentage", False))
    limit = entry.get("spawn_limit_percentage", 1.0)
    return (
        f'(DinoNameTag="{tag}",SpawnWeightMultiplier={weight},'
        f"OverrideSpawnLimitPercentage={str(override).lower()},"
        f"SpawnLimitPercentage={limit})"
    )


def parse_prevent_tame(value: str) -> str | None:
    v = value.strip().strip('"')
    return v or None


def serialize_prevent_tame(class_name: str) -> str:
    return f'"{class_name}"'


def _lines_from_raw_text(raw: str) -> list[str]:
    lines: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith(";") or s.startswith("#"):
            continue
        if s.startswith("[") and s.endswith("]"):
            continue
        if "=" in s:
            lines.append(s)
    return lines


def build_repeated_game_lines(cfg: "AsmServerConfig") -> list[str]:
    """Gera linhas Game.ini com chaves repetidas a partir do cfg."""
    lines: list[str] = []

    for entry in cfg.harvest_resource_multipliers:
        lines.append(
            "HarvestResourceItemAmountClassMultipliers="
            + _serialize_dino_class_multiplier(entry)
        )
    for entry in cfg.dino_class_resistance_multipliers:
        lines.append(
            "DinoClassResistanceMultipliers=" + _serialize_dino_class_multiplier(entry)
        )
    for entry in cfg.dino_class_damage_multipliers:
        lines.append(
            "DinoClassDamageMultipliers=" + _serialize_dino_class_multiplier(entry)
        )
    for entry in cfg.tamed_dino_class_resistance_multipliers:
        lines.append(
            "TamedDinoClassResistanceMultipliers="
            + _serialize_dino_class_multiplier(entry)
        )
    for entry in cfg.tamed_dino_class_damage_multipliers:
        lines.append(
            "TamedDinoClassDamageMultipliers="
            + _serialize_dino_class_multiplier(entry)
        )
    for entry in cfg.dino_spawn_weight_multipliers:
        lines.append(
            "DinoSpawnWeightMultipliers=" + serialize_spawn_weight(entry)
        )
    for name in cfg.prevent_dino_tame_class_names:
        n = (name or "").strip()
        if n:
            lines.append(
                f"PreventDinoTameClassNames={serialize_prevent_tame(n)}"
            )

    for raw in (
        cfg.crafting_overrides_raw,
        cfg.stack_size_overrides_raw,
        cfg.npc_spawn_overrides_raw,
        cfg.supply_crate_overrides_raw,
        cfg.custom_game_ini_raw,
    ):
        lines.extend(_lines_from_raw_text(raw))

    from ..player_engram_points import build_engram_points_ini_lines

    lines.extend(build_engram_points_ini_lines(cfg))

    return lines


def populate_lists_from_game_ini(cfg: "AsmServerConfig", game_path: Path) -> None:
    """Lê listas agregadas de um Game.ini (texto bruto)."""
    if not game_path.exists():
        return
    try:
        text = _read_text(game_path)
    except OSError:
        return

    cfg.harvest_resource_multipliers = []
    cfg.dino_class_resistance_multipliers = []
    cfg.dino_class_damage_multipliers = []
    cfg.tamed_dino_class_resistance_multipliers = []
    cfg.tamed_dino_class_damage_multipliers = []
    cfg.dino_spawn_weight_multipliers = []
    cfg.prevent_dino_tame_class_names = []

    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(";") or s.startswith("#"):
            continue
        ll = s.lower()
        val = s.split("=", 1)[1] if "=" in s else ""

        if ll.startswith("harvestresourceitemamountclassmultipliers="):
            e = _parse_dino_class_multiplier(val)
            if e:
                cfg.harvest_resource_multipliers.append(e)
        elif ll.startswith("dinoclassresistancemultipliers="):
            e = _parse_dino_class_multiplier(val)
            if e:
                cfg.dino_class_resistance_multipliers.append(e)
        elif ll.startswith("dinoclassdamagemultipliers="):
            e = _parse_dino_class_multiplier(val)
            if e:
                cfg.dino_class_damage_multipliers.append(e)
        elif ll.startswith("tameddinoclassresistancemultipliers="):
            e = _parse_dino_class_multiplier(val)
            if e:
                cfg.tamed_dino_class_resistance_multipliers.append(e)
        elif ll.startswith("tameddinoclassdamagemultipliers="):
            e = _parse_dino_class_multiplier(val)
            if e:
                cfg.tamed_dino_class_damage_multipliers.append(e)
        elif ll.startswith("dinospawnweightmultipliers="):
            e = parse_spawn_weight(val)
            if e:
                cfg.dino_spawn_weight_multipliers.append(e)
        elif ll.startswith("preventdinotameclassnames="):
            n = parse_prevent_tame(val)
            if n:
                cfg.prevent_dino_tame_class_names.append(n)


def patch_game_ini_repeated_lines(path: Path, new_lines: list[str]) -> None:
    """Remove chaves repetidas antigas e anexa novas linhas ao final do Game.ini."""
    if not path.exists():
        return
    try:
        text = _read_text(path)
    except OSError:
        return

    text = _STRIP_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    if not new_lines:
        path.write_bytes(b"\xff\xfe" + text.encode("utf-16-le"))
        return

    section_header = f"[{_GAME_MODE_SECTION}]"
    block = [ln + "\r\n" for ln in new_lines]

    if section_header.lower() not in text.lower():
        if not text.endswith("\r\n"):
            text += "\r\n"
        text += f"{section_header}\r\n" + "".join(block)
    else:
        if not text.endswith("\r\n"):
            text += "\r\n"
        text += "".join(block)

    path.write_bytes(b"\xff\xfe" + text.encode("utf-16-le"))
