"""Arquivos de Steam ID em ShooterGame/Saved/ (admin, whitelist, etc.)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, List, Optional

ALLOWED_CHEATER_STEAM_IDS_FILE = "AllowedCheaterSteamIDs.txt"


def allowed_cheater_steam_ids_path(install_dir: str) -> Path:
    """Caminho oficial: ``<install_dir>/ShooterGame/Saved/AllowedCheaterSteamIDs.txt``."""
    return Path(install_dir) / "ShooterGame" / "Saved" / ALLOWED_CHEATER_STEAM_IDS_FILE


def write_allowed_cheater_steam_ids(install_dir: str, admin_ids: List[str]) -> Path:
    """Grava IDs de admin (um por linha). Cria ``ShooterGame/Saved`` se necessário."""
    if not install_dir:
        raise ValueError("install_dir vazio")
    path = allowed_cheater_steam_ids_path(install_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    ids = [s.strip() for s in admin_ids if s and str(s).strip()]
    path.write_text(("\n".join(ids) + "\n") if ids else "", encoding="utf-8")
    return path


def write_allowed_cheater_steam_ids_safe(
    install_dir: str,
    admin_ids: List[str],
    *,
    server_name: str = "",
    on_warning: Optional[Callable[[str], None]] = None,
) -> bool:
    if not install_dir or not os.path.isdir(install_dir):
        return False
    try:
        write_allowed_cheater_steam_ids(install_dir, admin_ids)
        return True
    except Exception as exc:
        label = server_name or "servidor"
        msg = f"[{label}] Não foi possível gravar {ALLOWED_CHEATER_STEAM_IDS_FILE}: {exc}"
        if on_warning:
            on_warning(msg)
        return False
