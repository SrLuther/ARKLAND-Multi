"""Tabela fixa da progressão que concede 200 níveis ao jogador.

Os números não são calculados: vêm de ``src/data/nivel200.txt``, cópia do
formato que o Game.ini deve receber (rampa, teto de XP e engramas).

No executável PyInstaller o arquivo vai em ``_MEIPASS/src/data``. Se faltar,
``level_200_preset_error`` devolve a mensagem do botão e a tela continua.
"""
from __future__ import annotations

import re
import sys
from functools import cache
from pathlib import Path

_PRESET_FILENAME = "nivel200.txt"

# Perfil dos mapas: nível base 199. 200 cobre o mesmo padrão se o campo for ajustado.
LEVEL_200_BASE_LEVELS = frozenset({199, 200})
LEVEL_200_PROFILE_BASE = 199

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


def level_200_shortcut_base(current: int) -> int:
    """Base que emite o bloco nivel200. Mantém 199 ou 200; senão usa 199."""
    try:
        value = int(current or 0)
    except (TypeError, ValueError):
        return LEVEL_200_PROFILE_BASE
    if value in LEVEL_200_BASE_LEVELS:
        return value
    return LEVEL_200_PROFILE_BASE


def apply_level_200_shortcut(cfg: object) -> int:
    """Liga a progressão customizada e fixa a base do preset.

    Não escreve Game.ini. A curva dos outros níveis permanece nos campos da curva.
    """
    try:
        current = int(getattr(cfg, "player_base_level", 0) or 0)
    except (TypeError, ValueError):
        current = 0
    base = level_200_shortcut_base(current)
    if hasattr(cfg, "player_base_level"):
        cfg.player_base_level = base
    else:
        setattr(cfg, "player_base_level", base)
    if hasattr(cfg, "player_level_progressions_enabled"):
        cfg.player_level_progressions_enabled = True
    else:
        setattr(cfg, "player_level_progressions_enabled", True)
    return base


def level_200_preset_path() -> Path:
    """Caminho de ``nivel200.txt`` no código-fonte ou no bundle frozen.

    Desenvolvimento: ao lado deste módulo (``src/data``).
    Executável: ``sys._MEIPASS/src/data`` (entrada ``datas`` do spec).
    """
    bundled_rel = Path("src") / "data" / _PRESET_FILENAME
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / bundled_rel
    return Path(__file__).resolve().parent / "data" / _PRESET_FILENAME


def level_200_preset_error() -> str | None:
    """Mensagem para o botão do preset, ou None quando a tabela abre."""
    path = level_200_preset_path()
    try:
        if not path.is_file():
            return (
                "Preset nível 200 indisponível: não foi possível abrir "
                f"«{path}»."
            )
        load_level_200_preset()
    except OSError as exc:
        return f"Preset nível 200 indisponível: {exc}"
    except RuntimeError as exc:
        return f"Preset nível 200 indisponível: {exc}"
    return None


@cache
def preset_text() -> str:
    path = level_200_preset_path()
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FileNotFoundError(
            f"Preset nível 200 não encontrado: {path}"
        ) from exc


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
        raise RuntimeError(
            f"Tabela de 200 níveis incompleta: {level_200_preset_path()}"
        )
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
