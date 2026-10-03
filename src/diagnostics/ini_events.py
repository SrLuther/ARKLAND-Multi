"""Decorators de diagnóstico para ``write_ini`` / ``read_ini`` (asm_ini_manager).

Registram, a cada chamada: servidor, caminho do Game.ini, nº de linhas de rampa de nível
no arquivo, ``player_level_progressions_enabled``, ``override_max_xp_player`` e duração.
Falhas viram traceback no log (e a exceção original continua sendo lançada).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Dict

from .events import CAT_INI, diag_call
from .servers import read_text_any

_RAMP_LINE = re.compile(r"^\s*LevelExperienceRampOverrides\s*=", re.IGNORECASE | re.MULTILINE)


def _cfg_arg(args: tuple, kwargs: dict) -> Any:
    if args:
        return args[0]
    return kwargs.get("cfg")


def ini_summary(cfg: Any) -> Dict[str, Any]:
    """Resumo seguro (sem senhas) do estado de nível/INI de ``cfg``."""
    info: Dict[str, Any] = {
        "server": getattr(cfg, "name", None) or getattr(cfg, "session_name", None),
        "progressions_enabled": getattr(cfg, "player_level_progressions_enabled", None),
        "cfg_ramp_entries": getattr(cfg, "player_ramp_entry_count", None),
        "override_max_xp_player": getattr(cfg, "override_max_xp_player", None),
    }
    install = getattr(cfg, "install_dir", "") or ""
    if install:
        game = Path(install) / "ShooterGame" / "Saved" / "Config" / "WindowsServer" / "Game.ini"
        info["game_ini"] = str(game)
        try:
            if game.is_file():
                text = read_text_any(game, max_bytes=16 * 1024 * 1024)
                info["game_ini_ramp_lines"] = len(_RAMP_LINE.findall(text))
                info["game_ini_bytes"] = game.stat().st_size
            else:
                info["game_ini_exists"] = False
        except OSError as exc:
            info["game_ini_error"] = str(exc)
    return info


def _summ(args: tuple, kwargs: dict, _result: Any) -> Dict[str, Any]:
    return ini_summary(_cfg_arg(args, kwargs))


def traced_write_ini(fn: Callable[..., Any]) -> Callable[..., Any]:
    return diag_call(CAT_INI, "write_ini", _summ)(fn)


def traced_read_ini(fn: Callable[..., Any]) -> Callable[..., Any]:
    return diag_call(CAT_INI, "read_ini", _summ)(fn)
