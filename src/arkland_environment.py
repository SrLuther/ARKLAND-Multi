"""Ambiente padronizado ARKLAND SERVER — pastas de instalação, cluster, backup, etc."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .config_manager import AppConfig, ConfigManager

ARKLAND_SERVER_DIR_NAME = "ARKLAND SERVER"

# Disco dedicado de backups (override: env ARKLAND_BACKUP_ROOT).
BACKUP_ROOT_ENV = "ARKLAND_BACKUP_ROOT"
DEFAULT_BACKUP_ROOT = Path(r"D:\Backups")

_DIR_README: dict[str, str] = {
    "MAPAS": "Instalações dos servidores ARK (um subdiretório por mapa/servidor).",
    "CLUSTER": "Dados compartilhados de viagem cross-ARK entre mapas do cluster.",
    "BACKUP": "Backups gerenciados pelo ARKLAND (servidores, saves, banco, cloud, .ini).",
    "CACHE": "Cache de atualizações e arquivos temporários.",
    "LOGS": "Logs do gerenciador e diagnósticos.",
    "STEAMCMD": "SteamCMD para instalar/atualizar servidores e mods.",
    "WEBSTORE": "Dados da loja web (modo Host).",
    "CustomShop": "Catálogo partilhado catalog.json (Items/Kits) + configs locais por mapa.",
    "MARIADB": "MariaDB portable (binários e dados).",
}


def resolve_backup_root() -> Path:
    """Raiz dedicada de backups. Default ``D:\\Backups``; override via ``ARKLAND_BACKUP_ROOT``."""
    raw = (os.environ.get(BACKUP_ROOT_ENV) or "").strip()
    return Path(raw) if raw else DEFAULT_BACKUP_ROOT


def ensure_backup_tree(root: Optional[Path] = None) -> Path:
    """Garante a árvore padrão sob a raiz de backups (cria on first use)."""
    base = root or resolve_backup_root()
    for sub in ("servers", "saves", "database", "cloud", ".ini"):
        try:
            (base / sub).mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    return base

_TZ_BR = timezone(timedelta(hours=-3))


@dataclass
class EnvironmentPaths:
    root: Path

    @property
    def maps(self) -> Path:
        return self.root / "MAPAS"

    @property
    def cluster(self) -> Path:
        return self.root / "CLUSTER"

    @property
    def backup(self) -> Path:
        """Disco dedicado de backups (não fica sob ARKLAND SERVER/)."""
        return resolve_backup_root()

    @property
    def backup_servers(self) -> Path:
        return self.backup / "servers"

    @property
    def backup_saves(self) -> Path:
        return self.backup / "saves"

    @property
    def backup_database(self) -> Path:
        return self.backup / "database"

    @property
    def backup_cloud(self) -> Path:
        return self.backup / "cloud"

    @property
    def backup_ini(self) -> Path:
        return self.backup / ".ini"

    @property
    def cache(self) -> Path:
        return self.root / "CACHE"

    @property
    def cache_updates(self) -> Path:
        return self.cache / "updates"

    @property
    def logs(self) -> Path:
        return self.root / "LOGS"

    @property
    def logs_manager(self) -> Path:
        return self.logs / "manager"

    @property
    def steamcmd(self) -> Path:
        return self.root / "STEAMCMD"

    @property
    def steamcmd_exe(self) -> Path:
        return self.steamcmd / "steamcmd.exe"

    @property
    def webstore(self) -> Path:
        return self.root / "WEBSTORE"

    @property
    def customshop_dir(self) -> Path:
        return self.root / "CustomShop"

    @property
    def customshop_master(self) -> Path:
        """Catálogo partilhado canónico (Items/Kits/…)."""
        return self.customshop_dir / "catalog.json"

    @property
    def customshop_master_legacy(self) -> Path:
        """Mestre legado monolítico (pré Fase 1)."""
        return self.customshop_dir / "configs" / "config.json"

    @property
    def mariadb(self) -> Path:
        return self.root / "MARIADB"

    @property
    def mariadb_data(self) -> Path:
        return self.mariadb / "data"

    def backup_directories(self) -> list[Path]:
        """Pastas no disco dedicado ``D:\\Backups`` (ou ``ARKLAND_BACKUP_ROOT``)."""
        return [
            self.backup_servers,
            self.backup_saves,
            self.backup_database,
            self.backup_cloud,
            self.backup_ini,
        ]

    def all_directories(self) -> list[Path]:
        return [
            self.maps,
            self.cluster,
            *self.backup_directories(),
            self.cache_updates,
            self.logs_manager,
            self.logs / "app",
            self.steamcmd,
            self.webstore,
            self.customshop_dir,
            self.customshop_master_legacy.parent,
            self.mariadb,
            self.mariadb_data,
        ]

    def _dir_label(self, d: Path) -> str:
        try:
            return str(d.relative_to(self.root)).replace("\\", "/")
        except ValueError:
            return str(d)

    def preview_tree(self) -> str:
        r = str(self.root)
        b = str(self.backup)
        lines = [
            f"{r}/",
            "├── MAPAS/",
            "├── CLUSTER/",
            "├── CACHE/updates/",
            "├── LOGS/manager/",
            "├── STEAMCMD/",
            "├── WEBSTORE/",
            "├── CustomShop/catalog.json  (catálogo partilhado)",
            "└── MARIADB/data/",
            "",
            f"{b}/   (disco dedicado — env {BACKUP_ROOT_ENV})",
            "├── servers/",
            "├── saves/",
            "├── database/",
            "├── cloud/",
            "└── .ini/",
        ]
        return "\n".join(lines)


@dataclass
class CreateEnvironmentResult:
    paths: EnvironmentPaths
    created: list[str] = field(default_factory=list)
    existing: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


def environment_root_from_parent(parent: Path | str) -> Path:
    parent = Path(parent)
    if parent.name.strip() == ARKLAND_SERVER_DIR_NAME:
        return parent
    return parent / ARKLAND_SERVER_DIR_NAME


def _config_file_path() -> Path:
    return Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager" / "config.json"


def try_load_environment_paths() -> Optional[EnvironmentPaths]:
    """Lê config.json do APPDATA e retorna paths se o ambiente estiver ativo."""
    try:
        cfg_path = _config_file_path()
        if not cfg_path.is_file():
            return None
        with open(cfg_path, encoding="utf-8") as fh:
            data = json.load(fh)
        env = data.get("environment") or {}
        if not env.get("enabled"):
            return None
        root = (env.get("root_path") or "").strip()
        if not root:
            return None
        return EnvironmentPaths(root=Path(root))
    except Exception:
        return None


def resolve_environment(cfg: "AppConfig") -> Optional[EnvironmentPaths]:
    env = getattr(cfg, "environment", None)
    if env is None or not getattr(env, "enabled", False):
        return None
    root = (getattr(env, "root_path", "") or "").strip()
    if not root:
        return None
    return EnvironmentPaths(root=Path(root))


def validate_environment(root: Path | str) -> list[str]:
    """Retorna caminhos relativos das pastas obrigatórias ausentes."""
    paths = EnvironmentPaths(root=Path(root))
    missing: list[str] = []
    for d in paths.all_directories():
        if not d.is_dir():
            missing.append(paths._dir_label(d))
    return missing


def _write_readme(folder: Path, title: str, description: str) -> None:
    readme = folder / "README.txt"
    if readme.exists():
        return
    try:
        readme.write_text(
            f"{title}\n{'=' * len(title)}\n\n{description}\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def _touch_readmes(paths: EnvironmentPaths) -> None:
    top_readmes = {
        paths.maps: ("MAPAS", _DIR_README["MAPAS"]),
        paths.cluster: ("CLUSTER", _DIR_README["CLUSTER"]),
        paths.backup: ("BACKUP", _DIR_README["BACKUP"]),
        paths.cache: ("CACHE", _DIR_README["CACHE"]),
        paths.logs: ("LOGS", _DIR_README["LOGS"]),
        paths.steamcmd: ("STEAMCMD", _DIR_README["STEAMCMD"]),
        paths.webstore: ("WEBSTORE", _DIR_README["WEBSTORE"]),
        paths.customshop_master.parent.parent: ("CustomShop", _DIR_README["CustomShop"]),
        paths.mariadb: ("MARIADB", _DIR_README["MARIADB"]),
    }
    for folder, (title, desc) in top_readmes.items():
        _write_readme(folder, title, desc)


def create_environment(
    parent: Path | str,
    *,
    write_readmes: bool = True,
) -> CreateEnvironmentResult:
    """Cria a árvore ARKLAND SERVER de forma idempotente (+ disco dedicado de backups)."""
    root = environment_root_from_parent(parent)
    paths = EnvironmentPaths(root=root)
    result = CreateEnvironmentResult(paths=paths)

    for d in paths.all_directories():
        rel = paths._dir_label(d)
        if d.is_dir():
            result.existing.append(rel)
            continue
        try:
            d.mkdir(parents=True, exist_ok=True)
            result.created.append(rel)
        except OSError:
            result.failed.append(rel)

    if write_readmes:
        _touch_readmes(paths)

    return result


def apply_paths_to_config(cfg: "AppConfig", paths: EnvironmentPaths) -> None:
    """Preenche campos globais com os caminhos do ambiente."""
    env = cfg.environment
    env.enabled = True
    env.root_path = str(paths.root)
    if not env.created_at:
        env.created_at = datetime.now(tz=_TZ_BR).strftime("%Y-%m-%d %H:%M:%S")

    cfg.default_install_dir = str(paths.maps)
    cfg.steamcmd_path = str(paths.steamcmd_exe)
    # Respeita pasta custom já definida pelo utilizador; só preenche o default vazio.
    if not (cfg.backup.backup_dir or "").strip():
        cfg.backup.backup_dir = str(paths.backup_servers)
    if not (cfg.db_backup.backup_dir or "").strip():
        cfg.db_backup.backup_dir = str(paths.backup_database)
    cfg.auto_update.cache_dir = str(paths.cache_updates)


def apply_cluster_dir_to_profiles(config_manager: "ConfigManager", paths: EnvironmentPaths) -> int:
    """Define cluster_dir no perfil principal se vazio. Retorna quantos perfis atualizados."""
    updated = 0
    clusters = config_manager.clusters
    if not clusters:
        return 0

    def _pick_target():
        for prof in clusters:
            if (prof.name or "").strip().upper() == "ARKLAND":
                return prof
        return clusters[0]

    prof = _pick_target()
    if (prof.cluster_dir or "").strip():
        return 0
    prof.cluster_dir = str(paths.cluster)
    if prof.mode not in ("local", "network"):
        prof.mode = "local"
    config_manager.update_cluster(prof)
    updated = 1
    return updated


def apply_cloud_backup_local_path(paths: EnvironmentPaths) -> bool:
    """Sugere ``D:\\Backups\\cloud`` se credenciais cloud local estiverem sem local_path."""
    creds_file = (
        Path(os.environ.get("APPDATA", Path.home()))
        / "ARKLAND-ServerManager"
        / "cloud_credentials.json"
    )
    if not creds_file.is_file():
        return False
    try:
        with open(creds_file, encoding="utf-8") as fh:
            creds = json.load(fh)
    except Exception:
        return False
    if creds.get("provider") != "local":
        return False
    if (creds.get("local_path") or "").strip():
        return False
    creds["local_path"] = str(paths.backup_cloud)
    try:
        with open(creds_file, "w", encoding="utf-8") as fh:
            json.dump(creds, fh, indent=2, ensure_ascii=False)
        return True
    except OSError:
        return False


def sanitize_map_folder_name(name: str) -> str:
    """Nome seguro para subpasta em MAPAS/."""
    raw = (name or "").strip()
    raw = re.sub(r"[_]+", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    if not raw:
        return "Servidor"
    cleaned = re.sub(r'[<>:"/\\|?*]', "", raw)
    cleaned = cleaned.strip(" .")
    return cleaned or "Servidor"


def suggest_map_install_dir(paths: EnvironmentPaths, map_name: str) -> str:
    folder = sanitize_map_folder_name(map_name)
    return str(paths.maps / folder)


def suggest_next_server_dir(
    paths: EnvironmentPaths,
    *,
    existing_count: int = 0,
    occupied_paths: Optional[List[str]] = None,
) -> str:
    """Próxima pasta livre em MAPAS/ (Servidor 01, 02, …)."""
    occupied = {Path(p).resolve() for p in (occupied_paths or []) if p}
    n = max(1, existing_count + 1)
    while True:
        candidate = paths.maps / f"Servidor {n:02d}"
        if not candidate.exists() and candidate.resolve() not in occupied:
            return str(candidate)
        n += 1
        if n > 999:
            return str(paths.maps / f"Servidor {n}")


def default_backups_servers_root() -> Path:
    """Padrão: ``D:\\Backups\\servers`` (override via ``ARKLAND_BACKUP_ROOT``)."""
    return resolve_backup_root() / "servers"


def default_backups_saves_root() -> Path:
    """Padrão: ``D:\\Backups\\saves``."""
    return resolve_backup_root() / "saves"


def default_db_backup_dir() -> Path:
    """Padrão: ``D:\\Backups\\database``."""
    return resolve_backup_root() / "database"


def default_ini_backup_root() -> Path:
    """Padrão: ``D:\\Backups\\.ini`` (Eventos Sazonais / BUFFs)."""
    return resolve_backup_root() / ".ini"


def default_cloud_backup_dir() -> Path:
    """Padrão: ``D:\\Backups\\cloud``."""
    return resolve_backup_root() / "cloud"


def default_steamcmd_dir() -> Path:
    paths = try_load_environment_paths()
    if paths:
        return paths.steamcmd
    return Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager" / "steamcmd"


def default_manager_log_dir() -> Path:
    paths = try_load_environment_paths()
    if paths:
        return paths.logs_manager
    return Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager" / "logs"


def default_webstore_dir() -> Path:
    paths = try_load_environment_paths()
    if paths:
        return paths.webstore
    return Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager" / "arkshop_web"


def default_mariadb_dir() -> Path:
    paths = try_load_environment_paths()
    if paths:
        return paths.mariadb
    return Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager" / "mariadb"


def default_mariadb_data_dir() -> Path:
    paths = try_load_environment_paths()
    if paths:
        return paths.mariadb_data
    return Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager" / "mariadb_data"
