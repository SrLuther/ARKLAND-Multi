"""Backup e restauração de GameUserSettings.ini / Game.ini para Eventos Sazonais."""
from __future__ import annotations

import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

from .ark_ini import get_ini_path

_TZ_BRASILIA = timezone(timedelta(hours=-3))
_INI_FILES = ("GameUserSettings.ini", "Game.ini")


def now_brasilia() -> datetime:
    return datetime.now(tz=_TZ_BRASILIA).replace(tzinfo=None)


def resolve_ini_backup_root() -> Path:
    """Raiz dos backups .ini: ``ARKLAND SERVER/BACKUP/.ini``."""
    try:
        from .arkland_environment import try_load_environment_paths

        paths = try_load_environment_paths()
        if paths is not None:
            return paths.backup / ".ini"
    except Exception:
        pass
    return Path(r"C:\ARKLAND SERVER\BACKUP\.ini")


def server_folder_name(cfg: object) -> str:
    install = (getattr(cfg, "install_dir", "") or "").strip()
    if install:
        name = Path(install).name.strip()
        if name:
            return name
    name = (getattr(cfg, "name", "") or "").strip()
    return name or "servidor"


def backup_dir_for(cfg: object) -> Path:
    return resolve_ini_backup_root() / server_folder_name(cfg)


def backup_ini_files(cfg: object, label: str = "") -> Optional[str]:
    """
    Copia GUS + Game.ini para ``BACKUP/.ini/{server_folder}/{timestamp}.zip``.
    Retorna o caminho do zip ou None se install_dir ausente.
    """
    install_dir = (getattr(cfg, "install_dir", "") or "").strip()
    if not install_dir:
        return None

    dest_dir = backup_dir_for(cfg)
    dest_dir.mkdir(parents=True, exist_ok=True)

    ts = now_brasilia().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (label or "").strip())
    zip_name = f"{ts}_{safe}.zip" if safe else f"{ts}.zip"
    zip_path = dest_dir / zip_name

    written = False
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in _INI_FILES:
            src = get_ini_path(install_dir, fname)
            if src.exists():
                zf.write(src, fname)
                written = True

    if not written:
        try:
            zip_path.unlink(missing_ok=True)
        except Exception:
            pass
        return None
    return str(zip_path)


def list_ini_backups(cfg: object) -> List[Path]:
    """Lista zips de backup do servidor, do mais recente ao mais antigo."""
    folder = backup_dir_for(cfg)
    if not folder.is_dir():
        return []
    zips = list(folder.glob("*.zip"))
    zips.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return zips


def latest_ini_backup(cfg: object) -> Optional[Path]:
    items = list_ini_backups(cfg)
    return items[0] if items else None


def restore_ini_from_backup(cfg: object, backup_path: str) -> bool:
    """Restaura INIs do zip ou pasta legada para os caminhos originais do servidor."""
    install_dir = (getattr(cfg, "install_dir", "") or "").strip()
    if not install_dir:
        return False

    bp = Path(backup_path)
    if not bp.exists():
        return False

    if bp.is_dir():
        for fname in _INI_FILES:
            src = bp / fname
            if src.is_file():
                dst = get_ini_path(install_dir, fname)
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(src.read_bytes())
        return True

    if bp.suffix.lower() != ".zip":
        return False

    with zipfile.ZipFile(bp, "r") as zf:
        names = set(zf.namelist())
        for fname in _INI_FILES:
            if fname not in names:
                continue
            dst = get_ini_path(install_dir, fname)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(zf.read(fname))
    return True
