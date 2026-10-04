"""Tabela fixa da progressão que concede 200 níveis ao jogador.

Os números não são calculados: vêm de ``src/data/nivel200.txt``, cópia do
formato que o Game.ini deve receber (rampa, teto de XP e engramas).
"""
from __future__ import annotations

import re
from functools import cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "data" / "nivel200.txt"

# Perfil dos mapas: nível base 199. 200 cobre o mesmo padrão se o campo for ajustado.
LEVEL_200_BASE_LEVELS = frozenset({199, 200})

_RAMP_ENTRY_RE = re.compile(
    r"ExperiencePointsForLevel\[(\d+)\]\s*=\s*(\d+)",
    re.IGNORECASE,
)


def is_level_200_base(base_level: int) -> bool:
    """True quando o nível base do perfil é a progressão de 200 níveis."""
    try:
        return int(base_level or 0) in LEVEL_200_BASE_LEVELS
    except (TypeError, ValueError):
        return False


@cache
def preset_text() -> str:
    return _DATA_PATH.read_text(encoding="utf-8")


@cache
def load_level_200_preset() -> tuple[int, tuple[int, ...], tuple[int, ...]]:
    """Retorna (OverrideMaxExperiencePointsPlayer, limiares da rampa, engramas)."""
    override = 0
    ramp: dict[int, int] = {}
    engrams: list[int] = []
    for raw in preset_text().splitlines():
        line = raw.strip()
        if not line or line.startswith((";", "#", "[")):
            continue
        low = line.lower()
        if low.startswith("overridemaxexperiencepointsplayer="):
            override = int(line.split("=", 1)[1].strip())
        elif low.startswith("levelexperiencerampoverrides="):
            for idx, xp in _RAMP_ENTRY_RE.findall(line):
                ramp[int(idx)] = int(xp)
        elif low.startswith("overrideplayerlevelengrampoints="):
            engrams.append(int(line.split("=", 1)[1].strip()))
    if override <= 0 or not ramp or not engrams:
        raise RuntimeError(f"Tabela de 200 níveis incompleta: {_DATA_PATH}")
    max_index = max(ramp)
    missing = [i for i in range(max_index + 1) if i not in ramp]
    if missing:
        raise RuntimeError(
            f"Rampa de 200 níveis com índices faltando: {missing[:8]}"
        )
    values = tuple(ramp[i] for i in range(max_index + 1))
    return override, values, tuple(engrams)


def level_200_override_max_xp() -> int:
    return load_level_200_preset()[0]


def level_200_ramp_values() -> list[int]:
    return list(load_level_200_preset()[1])


def level_200_engram_points() -> list[int]:
    return list(load_level_200_preset()[2])


def level_200_relevant_ini_lines() -> list[str]:
    """Bloco do Game.ini na mesma ordem do arquivo de referência."""
    override, ramp, engrams = load_level_200_preset()
    parts = ",".join(
        f"ExperiencePointsForLevel[{i}]={xp}" for i, xp in enumerate(ramp)
    )
    lines = [
        f"OverrideMaxExperiencePointsPlayer={override}",
        f"LevelExperienceRampOverrides=({parts})",
    ]
    lines.extend(f"OverridePlayerLevelEngramPoints={pts}" for pts in engrams)
    return lines
