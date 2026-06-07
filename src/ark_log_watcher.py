"""
Monitor de log do ARK: Survival Evolved durante a inicialização do servidor.

Detecta marcadores de pronto/WAN no ShooterGame.log e promove o status
do servidor de STARTING para RUNNING via callbacks do ServerManager.
"""
from __future__ import annotations

import time
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .rcon_client import RconClient
from .server_config import (
    SERVER_STATUS_STARTING,
    SERVER_STATUS_RUNNING,
    SERVER_STATUS_CRASHED,
)

if TYPE_CHECKING:
    from .server_manager import ServerManager


# Linhas de log do ARK SE que indicam que o servidor terminou de inicializar
# NOTA: Estes marcadores aparecem no ShooterGame.log, não no console do ArkAPI.
# O ArkAPI carrega plugins em ~60s mas o mundo leva 10-15 min para carregar.
ARK_READY_MARKERS = (
    "Full Startup",              # "Full Startup: X.XX seconds" — marcador definitivo
    "server has been listed online",
    "GameMode BeginPlay",
    "Beacon has completed",
    "LogWorld: Bringing World",
    "World loaded",
    "All levels loaded",
)

# Marcadores que indicam INÍCIO do carregamento (não pronto ainda — apenas log)
ARK_LOADING_MARKERS = (
    "[API][info] Loaded all plugins",  # ArkAPI: plugins carregados, mundo ainda não
    "Initialized hooks",               # ArkAPI: hooks inicializados
    "API was successfully loaded",     # ArkAPI: API pronta
    "BeginPlay",
    "Networking initialized",
    "Game Engine Initialized",
    "Set New", "Set Summer", "Set Fear", "Set Winter",
    "Set Turkey", "Set Easter", "Set Love", "Set Anniversary",
)

# Linha que indica registro bem-sucedido no Steam (acessível WAN)
ARK_STEAM_MARKERS = (
    "OnCreateLobbyComplete",
    "Steam lobby created",
    "OnlineLobbyID",
    "bLANMatch=false",
    "STEAM: Search result",
)


def _find_ark_log_candidates(exe_path: Path) -> list:
    """Retorna caminhos candidatos para ShooterGame.log."""
    candidates: list = []
    try:
        candidates.append(exe_path.parents[2] / "Saved" / "Logs" / "ShooterGame.log")
    except Exception:
        pass
    try:
        candidates.append(exe_path.parent / "ShooterGame" / "Saved" / "Logs" / "ShooterGame.log")
    except Exception:
        pass
    return candidates


def _ark_read_log_lines(sm, server_id: str, inst, log_file: Optional[Path],
                        last_size: int, found_ready: bool):
    """Lê novas linhas do log e detecta marcadores de pronto/WAN. Retorna (last_size, found_ready)."""
    if not (log_file and log_file.exists()):
        return last_size, found_ready
    try:
        size = log_file.stat().st_size
        if size < last_size:
            last_size = 0
        if size > last_size:
            with open(log_file, "r", encoding="utf-8", errors="replace") as fh:
                fh.seek(last_size)
                new_lines = fh.read()
            last_size = size
            for line in new_lines.splitlines():
                if not line.strip():
                    continue
                inst.push_log(line)
                sm._emit_log(server_id, line, "debug")
                if not found_ready and inst.status == SERVER_STATUS_STARTING:
                    if any(m.lower() in line.lower() for m in ARK_LOADING_MARKERS):
                        sm._emit_log(server_id,
                            "[ARKLAND] Engine/ArkAPI inicializados — aguardando carregamento do mundo...",
                            "info")
                    if any(m.lower() in line.lower() for m in ARK_READY_MARKERS):
                        found_ready = True
                        sm._set_status(server_id, SERVER_STATUS_RUNNING)
                        sm._emit_log(server_id, "Servidor inicializado e aceitando conexões.", "info")
                        _mode = "LAN" if sm._is_lan_only(inst.config) else "WAN"
                        inst.online_mode = _mode
                        sm._on_visibility_change(server_id, _mode)
                if inst.status == SERVER_STATUS_RUNNING and inst.online_mode != "WAN":
                    if any(m.lower() in line.lower() for m in ARK_STEAM_MARKERS):
                        inst.online_mode = "WAN"
                        sm._on_visibility_change(server_id, "WAN")
                        sm._emit_log(server_id, "Servidor visível publicamente (WAN/Steam).", "info")
    except Exception:
        pass
    return last_size, found_ready


def _ark_rcon_probe(sm, server_id: str, inst, start: float, last_check: float,
                    first_check: float, check_every: float):
    """Sonda RCON como fallback se marcadores de log não detectados. Retorna (found_ready, last_check)."""
    elapsed = time.monotonic() - start
    since_last = time.monotonic() - last_check
    cfg = inst.config
    if not (elapsed >= first_check and since_last >= check_every and cfg.rcon_enabled and cfg.rcon_password):
        return False, last_check
    last_check = time.monotonic()
    try:
        _rcon = RconClient("127.0.0.1", cfg.rcon_port, cfg.rcon_password)
        _rcon.connect()
        _rcon.disconnect()
        sm._set_status(server_id, SERVER_STATUS_RUNNING)
        elapsed_min = int((time.monotonic() - start) / 60)
        sm._emit_log(server_id,
            f"Servidor marcado como rodando via RCON (fallback após {elapsed_min} min — "
            f"marcadores de log não detectados; mundo pode estar carregando).", "warning")
        _mode = "LAN" if sm._is_lan_only(inst.config) else "WAN"
        inst.online_mode = _mode
        sm._on_visibility_change(server_id, _mode)
        return True, last_check
    except Exception:
        return False, last_check


def _ark_timeout_promote(sm, server_id: str, proc, start: float,
                         found_ready: bool, timeout: float) -> bool:
    """Promove STARTING→RUNNING por timeout. Retorna True para sair do loop."""
    if found_ready or (time.monotonic() - start) < timeout:
        return False
    inst2 = sm._instances.get(server_id)
    if inst2 and inst2.status == SERVER_STATUS_STARTING and proc.poll() is None:
        sm._set_status(server_id, SERVER_STATUS_RUNNING)
        _mode = "LAN" if sm._is_lan_only(inst2.config) else "WAN"
        inst2.online_mode = _mode
        sm._on_visibility_change(server_id, _mode)
        sm._emit_log(server_id,
            f"Timeout de {int(timeout) // 60} min atingido — servidor considerado RODANDO "
            f"(processo ativo, sem marcadores de log detectados).", "warning")
    return True


def watch_ark_log(sm: "ServerManager", server_id: str,
                  proc: subprocess.Popen, exe_path: Path) -> None:
    """Monitora ShooterGame.log; fallback RCON e timeout de 45 min."""
    _STARTING_TIMEOUT = 45 * 60
    _POLL_INTERVAL    = 3
    _RCON_FIRST_CHECK = 10 * 60
    _RCON_CHECK_EVERY = 60
    candidates = _find_ark_log_candidates(exe_path)
    log_file: Optional[Path] = next((c for c in candidates if c.exists()), None)
    start = time.monotonic()
    last_size = 0
    found_ready = False
    last_rcon_check = start
    if log_file:
        try: last_size = log_file.stat().st_size
        except Exception: pass
    else:
        sm._emit_log(server_id, "Arquivo de log do ARK não encontrado ainda. Aguardando...", "debug")
    while True:
        inst = sm._instances.get(server_id)
        if not inst or inst.status not in (SERVER_STATUS_STARTING,):
            break
        if proc.poll() is not None:
            if inst.status == SERVER_STATUS_STARTING:
                sm._set_status(server_id, SERVER_STATUS_CRASHED)
                sm._emit_log(server_id,
                    f"Processo encerrou antes de inicializar (código {proc.returncode}).", "error")
                cfg2 = inst.config
                if cfg2.install_dir:
                    sm._emit_crash_details(server_id, cfg2.install_dir, kind="launch_fail")
            break
        if log_file is None:
            for cand in candidates:
                if cand.exists():
                    log_file = cand
                    sm._emit_log(server_id, f"Log detectado: {log_file}", "debug")
                    break
        last_size, found_ready = _ark_read_log_lines(sm, server_id, inst, log_file, last_size, found_ready)
        if not found_ready and inst.status == SERVER_STATUS_STARTING:
            found_ready, last_rcon_check = _ark_rcon_probe(
                sm, server_id, inst, start, last_rcon_check, _RCON_FIRST_CHECK, _RCON_CHECK_EVERY)
        if _ark_timeout_promote(sm, server_id, proc, start, found_ready, _STARTING_TIMEOUT):
            break
        time.sleep(_POLL_INTERVAL)
    if log_file:
        tail_ark_log(sm, server_id, proc, log_file, last_size)


def tail_ark_log(
    sm: "ServerManager",
    server_id: str,
    proc: subprocess.Popen,
    log_file: Path,
    offset: int,
) -> None:
    """Continua lendo o arquivo de log do ARK após o servidor estar RODANDO."""
    _POLL_INTERVAL = 3
    last_size = offset
    while True:
        inst = sm._instances.get(server_id)
        if not inst or inst.status not in (SERVER_STATUS_RUNNING,):
            break
        if proc.poll() is not None:
            break
        try:
            if log_file.exists():
                size = log_file.stat().st_size
                if size < last_size:
                    last_size = 0  # arquivo rotacionado/truncado
                if size > last_size:
                    with open(log_file, "r", encoding="utf-8", errors="replace") as fh:
                        fh.seek(last_size)
                        new_lines = fh.read()
                    last_size = size
                    for line in new_lines.splitlines():
                        if not line.strip():
                            continue
                        inst.push_log(line)
                        sm._emit_log(server_id, line, "debug")
                        if inst.online_mode != "WAN":
                            if any(m.lower() in line.lower() for m in ARK_STEAM_MARKERS):
                                inst.online_mode = "WAN"
                                sm._on_visibility_change(server_id, "WAN")
                                sm._emit_log(server_id, "Servidor visível publicamente (WAN/Steam).", "info")
        except Exception:
            pass
        time.sleep(_POLL_INTERVAL)
