"""Backup e restauração de GameUserSettings.ini / Game.ini para Eventos Sazonais."""
from __future__ import annotations

import configparser
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


def read_active_event_from_gus(cfg: object) -> str:
    """Lê ``[ServerSettings]/ActiveEvent`` do GUS no disco (se existir)."""
    install_dir = (getattr(cfg, "install_dir", "") or "").strip()
    if not install_dir:
        return ""
    gus_path = get_ini_path(install_dir, "GameUserSettings.ini")
    if not gus_path.is_file():
        return ""

    parser = configparser.RawConfigParser()
    parser.optionxform = str  # type: ignore[assignment]
    for enc in ("utf-16", "utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(gus_path, "r", encoding=enc) as fh:
                parser.read_file(fh)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception:
            return ""

    if not parser.has_option("ServerSettings", "ActiveEvent"):
        return ""
    from .ui_constants import normalize_active_event

    return normalize_active_event(parser.get("ServerSettings", "ActiveEvent").strip())


def merge_active_event_into_gus(cfg: object, event_id: str) -> bool:
    """Grava ou remove ``ActiveEvent`` no GUS sem alterar o restante do arquivo."""
    install_dir = (getattr(cfg, "install_dir", "") or "").strip()
    if not install_dir:
        return False

    from .ui_constants import normalize_active_event

    event_id = normalize_active_event(event_id)
    gus_path = get_ini_path(install_dir, "GameUserSettings.ini")
    gus_path.parent.mkdir(parents=True, exist_ok=True)

    parser = configparser.RawConfigParser()
    parser.optionxform = str  # type: ignore[assignment]
    if gus_path.is_file():
        for enc in ("utf-16", "utf-8-sig", "utf-8", "latin-1"):
            try:
                with open(gus_path, "r", encoding=enc) as fh:
                    parser.read_file(fh)
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception:
                break

    if not parser.has_section("ServerSettings"):
        parser.add_section("ServerSettings")

    if event_id:
        parser.set("ServerSettings", "ActiveEvent", event_id)
    elif parser.has_option("ServerSettings", "ActiveEvent"):
        parser.remove_option("ServerSettings", "ActiveEvent")

    from .ark_ini_fields import ensure_gus_ark_skeleton, GUS_SECTION_ORDER

    ensure_gus_ark_skeleton(parser)
    from .asm_engine.asm_ini_manager import _render_ini_text

    tmp = gus_path.with_suffix(".tmp")
    text = _render_ini_text(parser, section_order=GUS_SECTION_ORDER)
    with open(tmp, "wb") as fh:
        fh.write(b"\xff\xfe")
        fh.write(text.encode("utf-16-le"))
    tmp.replace(gus_path)
    return True


def resolve_preserve_active_event(cfg: object) -> str:
    """Valor de ActiveEvent a preservar após restore de backup de buff."""
    from .ui_constants import normalize_active_event

    profile_val = normalize_active_event(getattr(cfg, "active_event", "") or "")
    if profile_val:
        return profile_val
    return read_active_event_from_gus(cfg)


def restore_ini_from_backup(
    cfg: object,
    backup_path: str,
    *,
    preserve_active_event: Optional[str] = None,
) -> bool:
    """Restaura INIs do zip ou pasta legada para os caminhos originais do servidor.

  Se ``preserve_active_event`` for omitido, usa ``cfg.active_event`` (perfil) ou o
  valor já presente no GUS — evita apagar Páscoa/Halloween definidos depois do backup.
    """
    install_dir = (getattr(cfg, "install_dir", "") or "").strip()
    if not install_dir:
        return False

    if preserve_active_event is None:
        preserved = resolve_preserve_active_event(cfg)
    else:
        from .ui_constants import normalize_active_event

        preserved = normalize_active_event(preserve_active_event)

    bp = Path(backup_path)
    if not bp.exists():
        return False

    restored = False
    if bp.is_dir():
        for fname in _INI_FILES:
            src = bp / fname
            if src.is_file():
                dst = get_ini_path(install_dir, fname)
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(src.read_bytes())
                restored = True
    elif bp.suffix.lower() == ".zip":
        with zipfile.ZipFile(bp, "r") as zf:
            names = set(zf.namelist())
            for fname in _INI_FILES:
                if fname not in names:
                    continue
                dst = get_ini_path(install_dir, fname)
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(zf.read(fname))
                restored = True

    if not restored:
        return False

    if preserved:
        merge_active_event_into_gus(cfg, preserved)
        if hasattr(cfg, "active_event"):
            cfg.active_event = preserved

    try:
        from .asm_engine.asm_server_config import AsmServerConfig
        from .asm_engine.asm_ini_manager import mirror_ini_to_user_config_folder

        if isinstance(cfg, AsmServerConfig):
            mirror_ini_to_user_config_folder(cfg)
    except Exception:
        pass
    return True
