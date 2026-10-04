"""
Gerenciamento de saves nativos do ARK em ShooterGame/Saved/{alt_save_directory_name}.

Classifica, lista, carrega, faz backup manual e exclui arquivos .ark/.bak
do diretório savegame — sem copiar para pastas externas.
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

from .asm_mod_utils import map_cli_name
from .asm_server_config import (
    ASM_STATUS_CRASHED,
    ASM_STATUS_RUNNING,
    ASM_STATUS_STARTING,
    ASM_STATUS_STOPPED,
    ASM_STATUS_STOPPING,
    ASM_STATUS_UPDATING,
    AsmServerConfig,
    is_config_editable,
)

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp

_DATED_BACKUP_RE = re.compile(
    r"^(.+)_(\d{2})\.(\d{2})\.(\d{4})_(\d{2})\.(\d{2})\.(\d{2})\.ark$",
    re.IGNORECASE,
)

_STATUS_LABELS = {
    ASM_STATUS_STOPPED: "parado",
    ASM_STATUS_STARTING: "iniciando",
    ASM_STATUS_RUNNING: "em execução",
    ASM_STATUS_STOPPING: "parando",
    ASM_STATUS_CRASHED: "travado",
    ASM_STATUS_UPDATING: "atualizando",
}


class SaveFileKind(str, Enum):
    ACTIVE = "active"
    DATED_BACKUP = "dated_backup"
    ANTI_CORRUPTION = "anti_corruption"
    NEW_LAUNCH = "new_launch"
    OTHER = "other"


_KIND_LABELS = {
    SaveFileKind.ACTIVE: "Save ativo",
    SaveFileKind.DATED_BACKUP: "Backup datado",
    SaveFileKind.ANTI_CORRUPTION: "Anti Corruption",
    SaveFileKind.NEW_LAUNCH: "New Launch",
    SaveFileKind.OTHER: "Outro",
}


@dataclass
class SaveFileEntry:
    path: Path
    name: str
    kind: SaveFileKind
    size_bytes: int
    modified: Optional[datetime] = None
    parsed_date: Optional[datetime] = None

    @property
    def kind_label(self) -> str:
        return _KIND_LABELS.get(self.kind, self.kind.value)

    @property
    def display_date(self) -> Optional[datetime]:
        return self.parsed_date or self.modified


@dataclass
class SaveInventory:
    server_id: str
    server_name: str
    savegame_dir: Path
    map_basename: str
    active_filename: str
    entries: List[SaveFileEntry] = field(default_factory=list)
    dir_exists: bool = False
    error: str = ""
    source_dirs: List[Path] = field(default_factory=list)


def savegame_dir(srv: AsmServerConfig) -> Path:
    """Pasta que o servidor usa ao iniciar: ShooterGame/Saved/{AltSaveDirectoryName}."""
    sub = (srv.alt_save_directory_name or "").strip() or "savegame"
    return Path(srv.install_dir) / "ShooterGame" / "Saved" / sub


def _saved_root(srv: AsmServerConfig) -> Path:
    return Path(srv.install_dir) / "ShooterGame" / "Saved"


def _dir_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def candidate_save_dirs(srv: AsmServerConfig) -> List[Path]:
    """Pastas onde o ARK pode ter deixado o mundo deste mapa.

    A configurada (AltSaveDirectoryName, padrão savegame) vem primeiro.
    SavedArks (dedicado) e SavedArksLocal (local) entram se forem outras pastas —
    o painel antigo só olhava savegame e a lista ficava vazia.
    """
    configured = savegame_dir(srv)
    ordered = [
        configured,
        _saved_root(srv) / "SavedArks",
        _saved_root(srv) / "SavedArksLocal",
    ]
    out: List[Path] = []
    seen: set[str] = set()
    for path in ordered:
        key = _dir_key(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def is_world_save_filename(name: str) -> bool:
    """True para mundo .ark/.bak. Perfis e tribos não contam como save do mapa."""
    lower = (name or "").lower()
    if lower.endswith((
        ".arkprofile",
        ".arktribe",
        ".arktributetribe",
        ".profilebak",
        ".tribebak",
    )):
        return False
    return lower.endswith(".ark") or lower.endswith(".bak")


def map_save_basename(srv: AsmServerConfig) -> str:
    """Nome base do save (.ark) derivado de server_map."""
    return map_cli_name(srv.server_map, srv.install_dir or "")


def active_save_path(srv: AsmServerConfig) -> Path:
    """Caminho completo do save ativo ({mapa}.ark)."""
    return savegame_dir(srv) / f"{map_save_basename(srv)}.ark"


def parse_dated_backup_filename(name: str) -> Optional[datetime]:
    """Extrai data/hora de ``Map_DD.MM.YYYY_HH.MM.SS.ark``."""
    m = _DATED_BACKUP_RE.match(name)
    if not m:
        return None
    try:
        _map, dd, mm, yyyy, hh, mi, ss = m.groups()
        return datetime(
            int(yyyy), int(mm), int(dd),
            int(hh), int(mi), int(ss),
        )
    except ValueError:
        return None


def classify_save_files(
    directory: Path,
    map_basename: str,
    *,
    mark_active: bool = True,
) -> List[SaveFileEntry]:
    """Classifica arquivos de mundo .ark/.bak. Perfis (.arkprofile) ficam de fora.

    ``mark_active`` só na pasta configurada do servidor — um ``Mapa.ark`` em
    SavedArks continua carregável em vez de ser tratado como o save ativo.
    O nome do mapa não esconde outros .ark: se o basename não bater, o arquivo
    entra como «Outro» e ainda pode ser carregado.
    """
    if not directory.is_dir():
        return []

    active_name = f"{map_basename}.ark"
    anti_name = f"{map_basename}_AntiCorruptionBackup.bak"
    new_launch_name = f"{map_basename}_NewLaunchBackup.bak"
    entries: List[SaveFileEntry] = []

    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        name = path.name
        if not is_world_save_filename(name):
            continue

        try:
            stat = path.stat()
            size = stat.st_size
            modified = datetime.fromtimestamp(stat.st_mtime)
        except OSError:
            size = 0
            modified = None

        lower_name = name.lower()
        if mark_active and lower_name == active_name.lower():
            kind = SaveFileKind.ACTIVE
            parsed = None
        elif lower_name == anti_name.lower():
            kind = SaveFileKind.ANTI_CORRUPTION
            parsed = None
        elif lower_name == new_launch_name.lower():
            kind = SaveFileKind.NEW_LAUNCH
            parsed = None
        elif parse_dated_backup_filename(name) is not None:
            kind = SaveFileKind.DATED_BACKUP
            parsed = parse_dated_backup_filename(name)
        else:
            kind = SaveFileKind.OTHER
            parsed = None

        entries.append(SaveFileEntry(
            path=path,
            name=name,
            kind=kind,
            size_bytes=size,
            modified=modified,
            parsed_date=parsed,
        ))

    def _sort_key(e: SaveFileEntry) -> tuple:
        kind_order = {
            SaveFileKind.ACTIVE: 0,
            SaveFileKind.DATED_BACKUP: 1,
            SaveFileKind.ANTI_CORRUPTION: 2,
            SaveFileKind.NEW_LAUNCH: 3,
            SaveFileKind.OTHER: 4,
        }
        dt = e.display_date or datetime.min
        return (kind_order.get(e.kind, 9), -dt.timestamp(), e.name.lower())

    entries.sort(key=_sort_key)
    return entries


def format_size(size_bytes: int) -> str:
    """Tamanho legível (ex.: 47,2 MB)."""
    total = float(max(0, size_bytes))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if total < 1024:
            if unit == "B":
                return f"{int(total)} {unit}"
            return f"{total:.1f} {unit}"
        total /= 1024
    return f"{total:.1f} PB"


def format_datetime(dt: Optional[datetime]) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%d/%m/%Y %H:%M:%S")


def backup_timestamp(dt: Optional[datetime] = None) -> str:
    """Padrão ARK: DD.MM.YYYY_HH.MM.SS."""
    dt = dt or datetime.now()
    return dt.strftime("%d.%m.%Y_%H.%M.%S")


def list_server_saves(srv: AsmServerConfig) -> SaveInventory:
    """Inventário de saves do servidor.

    Lista a pasta configurada e, se o mundo estiver em SavedArks ou
    SavedArksLocal, esses arquivos também. O save ativo continua sendo
    ``{mapa}.ark`` na pasta configurada (é para lá que «Carregar» copia).
    """
    sg_dir = savegame_dir(srv)
    basename = map_save_basename(srv)
    inv = SaveInventory(
        server_id=srv.id,
        server_name=srv.name,
        savegame_dir=sg_dir,
        map_basename=basename,
        active_filename=f"{basename}.ark",
    )
    configured_key = _dir_key(sg_dir)
    any_dir = False
    entries: List[SaveFileEntry] = []
    found: List[Path] = []
    for directory in candidate_save_dirs(srv):
        if not directory.exists():
            continue
        if not directory.is_dir():
            continue
        any_dir = True
        mark_active = _dir_key(directory) == configured_key
        batch = classify_save_files(directory, basename, mark_active=mark_active)
        if batch:
            found.append(directory)
            entries.extend(batch)

    if not any_dir:
        inv.dir_exists = False
        inv.error = (
            "Pasta de saves não encontrada. "
            "Procurei a pasta configurada, SavedArks e SavedArksLocal."
        )
        return inv

    def _sort_key(e: SaveFileEntry) -> tuple:
        kind_order = {
            SaveFileKind.ACTIVE: 0,
            SaveFileKind.DATED_BACKUP: 1,
            SaveFileKind.ANTI_CORRUPTION: 2,
            SaveFileKind.NEW_LAUNCH: 3,
            SaveFileKind.OTHER: 4,
        }
        dt = e.display_date or datetime.min
        return (kind_order.get(e.kind, 9), -dt.timestamp(), e.name.lower())

    entries.sort(key=_sort_key)
    inv.dir_exists = True
    inv.entries = entries
    inv.source_dirs = found
    return inv


def can_load_save(app: "ARKServerManagerApp", server_id: str) -> Tuple[bool, str]:
    """True apenas se o servidor estiver parado ou travado (crashed)."""
    status = app.asm_server_manager.get_status(server_id)
    if is_config_editable(status):
        return True, ""
    label = _STATUS_LABELS.get(status, status)
    return (
        False,
        f"O servidor precisa estar desligado para carregar um save. "
        f"Status atual: {label}. Pare o servidor manualmente antes de continuar.",
    )


def _safety_backup_active(srv: AsmServerConfig) -> Optional[Path]:
    """Copia o save ativo para backup datado antes de substituir."""
    active = active_save_path(srv)
    if not active.is_file():
        return None
    sg_dir = savegame_dir(srv)
    basename = map_save_basename(srv)
    ts = backup_timestamp()
    dest = sg_dir / f"{basename}_{ts}.ark"
    shutil.copy2(str(active), str(dest))
    return dest


def load_save(srv: AsmServerConfig, source_path: Path) -> Path:
    """
    Restaura *source_path* como save ativo ({mapa}.ark).

    Faz backup de segurança do ativo atual (se existir) e usa arquivo temporário
    para troca atômica quando possível.
    Retorna o caminho do save ativo após a operação.
    """
    source = Path(source_path)
    if not source.is_file():
        raise FileNotFoundError(f"Arquivo de origem não encontrado: {source}")

    active = active_save_path(srv)
    sg_dir = savegame_dir(srv)
    sg_dir.mkdir(parents=True, exist_ok=True)
    if not sg_dir.is_dir():
        raise FileNotFoundError(f"Pasta de saves não encontrada: {sg_dir}")

    if source.resolve() == active.resolve():
        raise ValueError("O arquivo selecionado já é o save ativo.")

    safety = _safety_backup_active(srv)
    tmp = sg_dir / f"{map_save_basename(srv)}.ark.tmp"
    try:
        shutil.copy2(str(source), str(tmp))
        os.replace(str(tmp), str(active))
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise
    return active


def create_manual_backup(srv: AsmServerConfig, when: Optional[datetime] = None) -> Path:
    """Copia o save ativo para backup datado manual."""
    active = active_save_path(srv)
    if not active.is_file():
        raise FileNotFoundError(
            f"Save ativo não encontrado: {active.name}. "
            "Inicie o servidor ao menos uma vez ou verifique o mapa configurado."
        )
    sg_dir = savegame_dir(srv)
    basename = map_save_basename(srv)
    dest = sg_dir / f"{basename}_{backup_timestamp(when)}.ark"
    if dest.exists():
        raise FileExistsError(f"Já existe um backup com este nome: {dest.name}")
    shutil.copy2(str(active), str(dest))
    return dest


def delete_save_file(path: Path, *, allow_active: bool = False) -> None:
    """Remove um arquivo de save. Por padrão bloqueia exclusão do save ativo."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {p}")
    name = p.name
    parent = p.parent
    if name.endswith(".ark") and not _DATED_BACKUP_RE.match(name):
        if not allow_active:
            raise ValueError("Não é permitido excluir o save ativo por aqui.")
    p.unlink()
    if not parent.exists():
        return
