"""
Gerenciador de backups automáticos de saves e configurações de servidor ARK.

Estrutura de armazenamento (ZIP):
  %APPDATA%/ARKLAND-ServerManager/backups/servers/{server_id}/{YYYYMMDD_HHMMSS}.zip
      config/              ← GameUserSettings.ini, Game.ini (WindowsServer/) — opcional
      saves/{pasta}/       ← ShooterGame/Saved/{AltSaveDirectoryName}/ (prioridade)
      saves/SavedArks/     ← legado, se existir separadamente
"""
from __future__ import annotations

import os
import shutil
import threading
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, TYPE_CHECKING

from .arkland_environment import default_backups_servers_root

if TYPE_CHECKING:
    from .server_config import ServerConfig
    from .config_manager import BackupConfig
    from .asm_engine.asm_server_config import AsmServerConfig

_DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager"


def saved_root(install_dir: str) -> Path:
    return Path(install_dir) / "ShooterGame" / "Saved"


def resolve_save_source_dirs(srv: "ServerConfig") -> list[Path]:
    """Pastas de save a incluir — respeita ?AltSaveDirectoryName= (ex.: savegame)."""
    base = saved_root(srv.install_dir)
    alt = (getattr(srv, "alt_save_directory_name", "") or "").strip() or "savegame"
    candidates: list[Path] = []
    seen: set[Path] = set()

    alt_path = base / alt
    if alt_path not in seen:
        candidates.append(alt_path)
        seen.add(alt_path)

    legacy = base / "SavedArks"
    if legacy not in seen:
        candidates.append(legacy)
        seen.add(legacy)

    existing = [p for p in candidates if p.is_dir() and any(p.rglob("*"))]
    if existing:
        return existing
    return [alt_path]


def _zip_saves_prefix(save_dir: Path, saved_base: Path) -> str:
    rel = save_dir.relative_to(saved_base)
    return f"saves/{rel.as_posix()}"


def _is_legacy_flat_saves(members: list[str]) -> bool:
    rels = [
        Path(m).relative_to("saves")
        for m in members
        if m.startswith("saves/") and not m.endswith("/")
    ]
    return bool(rels) and all(len(r.parts) == 1 for r in rels)


def _format_size(size_bytes: int | float) -> str:
    """Formata bytes para exibição legível (B, KB, MB, GB)."""
    n = float(max(0, size_bytes))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(n)} {unit}"
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _zip_backup_sizes(path: Path) -> tuple[int, int]:
    """Retorna (comprimido_bytes, original_bytes) de um snapshot ZIP."""
    compressed = path.stat().st_size if path.is_file() else 0
    uncompressed = 0
    if path.is_file() and path.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(path, "r") as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    uncompressed += max(0, info.file_size)
        except Exception:
            pass
    if uncompressed <= 0:
        uncompressed = compressed
    return compressed, uncompressed


def asm_server_to_backup_target(asm_srv: "AsmServerConfig", global_bk: "BackupConfig") -> "ServerConfig":
    """Converte servidor TEK + config global em ServerConfig para backup."""
    from .server_config import ServerConfig

    keep = global_bk.max_backup_count if global_bk.limit_backup_count else 0
    return ServerConfig(
        id=asm_srv.id,
        name=asm_srv.session_name or asm_srv.name,
        install_dir=asm_srv.install_dir,
        alt_save_directory_name=getattr(asm_srv, "alt_save_directory_name", "") or "savegame",
        backup_dir=global_bk.backup_dir,
        backup_include_saves=global_bk.include_savegames,
        backup_include_config=global_bk.include_config,
        backup_keep_count=keep,
    )


class BackupEntry:
    """Representa um único snapshot de backup (ZIP ou diretório legado)."""

    def __init__(self, path: Path) -> None:
        self.path = path

        if path.is_file() and path.suffix == ".zip":
            # ── Novo formato: arquivo ZIP comprimido ──────────────────────────
            self.is_zip       = True
            self.timestamp    = path.stem
            with zipfile.ZipFile(path, "r") as zf:
                names = zf.namelist()
                self.has_config = any(n.startswith("config/") for n in names)
                self.has_saves  = any(n.startswith("saves/")  for n in names)
            compressed_b, uncompressed_b = _zip_backup_sizes(path)
            self.size_bytes          = compressed_b
            self.uncompressed_bytes  = uncompressed_b
            self.size_mb             = round(compressed_b / (1024 ** 2), 2)
            self.uncompressed_mb     = round(uncompressed_b / (1024 ** 2), 2)
        else:
            # ── Legado: diretório ─────────────────────────────────────────────
            self.is_zip          = False
            self.timestamp       = path.name
            self.has_saves       = (path / "saves").exists()
            self.has_config      = (path / "config").exists()
            total                = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            self.size_bytes      = total
            self.uncompressed_bytes = total
            self.size_mb         = round(total / (1024 * 1024), 2)
            self.uncompressed_mb = self.size_mb

        try:
            self.dt = datetime.strptime(self.timestamp, "%Y%m%d_%H%M%S")
        except ValueError:
            self.dt = datetime.fromtimestamp(path.stat().st_mtime)

    @property
    def label(self) -> str:
        parts: List[str] = []
        if self.has_config:
            parts.append("Config")
        if self.has_saves:
            parts.append("Saves")
        tag = " + ".join(parts) if parts else "Vazio"
        if self.is_zip and self.uncompressed_bytes > 0 and self.uncompressed_bytes != self.size_bytes:
            size_str = (
                f"{_format_size(self.size_bytes)}  "
                f"(original: {_format_size(self.uncompressed_bytes)})"
            )
        else:
            size_str = _format_size(self.size_bytes)
        return f"{self.dt.strftime('%d/%m/%Y %H:%M:%S')}  [{tag}]  {size_str}"


class BackupManager:
    """Gerencia backups manuais e automáticos por servidor."""

    def __init__(
        self,
        get_servers: Callable[[], List["ServerConfig"]],
        on_log: Optional[Callable[[str, str], None]] = None,
        discord_notifier: Optional[object] = None,
    ) -> None:
        self._get_servers  = get_servers
        self._on_log       = on_log or (lambda m, lvl: None)
        self._discord_notifier = discord_notifier
        self._backups_root = default_backups_servers_root()
        self._timers: Dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    # ── Caminho do diretório de backups ───────────────────────────────────────

    def backup_dir(self, srv: "ServerConfig") -> Path:
        if srv.backup_dir:
            return Path(srv.backup_dir) / srv.id
        return self._backups_root / srv.id

    # ── Realizar backup ───────────────────────────────────────────────────────

    def do_backup(self, srv: "ServerConfig") -> Optional[str]:
        """Faz backup dos arquivos selecionados em ZIP comprimido. Retorna caminho do .zip ou None."""
        if not srv.install_dir:
            self._on_log(f"[Backup] {srv.name}: diretório de instalação não configurado.", "warning")
            return None

        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        bdir     = self.backup_dir(srv)
        bdir.mkdir(parents=True, exist_ok=True)
        zip_path = bdir / f"{ts}.zip"

        added = False
        uncompressed_bytes = 0
        save_files = 0
        config_files = 0

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
                if srv.backup_include_saves:
                    sbase = saved_root(srv.install_dir)
                    save_dirs = resolve_save_source_dirs(srv)
                    for saves_src in save_dirs:
                        if not saves_src.is_dir():
                            self._on_log(
                                f"[Backup] {srv.name}: pasta de saves não encontrada ({saves_src}).",
                                "warning",
                            )
                            continue
                        prefix = _zip_saves_prefix(saves_src, sbase)
                        found_here = 0
                        for f in sorted(saves_src.rglob("*")):
                            if f.is_file():
                                arc = f"{prefix}/{f.relative_to(saves_src).as_posix()}"
                                zf.write(f, arc)
                                uncompressed_bytes += f.stat().st_size
                                found_here += 1
                                added = True
                        save_files += found_here
                        if found_here:
                            self._on_log(
                                f"[Backup] {srv.name}: {found_here} arquivo(s) de save em {saves_src.name}/",
                                "info",
                            )

                if srv.backup_include_config:
                    cfg_src = Path(srv.install_dir) / "ShooterGame" / "Saved" / "Config" / "WindowsServer"
                    if cfg_src.exists():
                        for f in sorted(cfg_src.rglob("*")):
                            if f.is_file():
                                zf.write(f, "config/" + f.relative_to(cfg_src).as_posix())
                                uncompressed_bytes += f.stat().st_size
                                config_files += 1
                                added = True
                    else:
                        self._on_log(f"[Backup] {srv.name}: pasta de config não encontrada ({cfg_src}).", "warning")
        except Exception as exc:
            self._on_log(f"[Backup] {srv.name}: erro ao criar ZIP — {exc}", "error")
            try:
                zip_path.unlink(missing_ok=True)
            except Exception:
                pass
            return None

        if not added:
            try:
                zip_path.unlink(missing_ok=True)
            except Exception:
                pass
            if srv.backup_include_saves and save_files == 0:
                self._on_log(
                    f"[Backup] {srv.name}: nenhum arquivo de save encontrado — "
                    f"verifique AltSaveDirectoryName e se o servidor já salvou ao menos uma vez.",
                    "error",
                )
            return None

        compressed_bytes = zip_path.stat().st_size
        parts = []
        if save_files:
            parts.append(f"{save_files} save(s)")
        if config_files:
            parts.append(f"{config_files} config")
        content_tag = " + ".join(parts) if parts else "vazio"
        self._on_log(
            f"[Backup] {srv.name}: snapshot salvo → {zip_path.name}  "
            f"[{content_tag}]  "
            f"({_format_size(compressed_bytes)} comprimido / "
            f"{_format_size(uncompressed_bytes)} original)",
            "info",
        )
        self._prune(srv)
        if self._discord_notifier:
            detail = (
                f"Snapshot: `{zip_path.name}`\n"
                f"Conteúdo: **{content_tag}**\n"
                f"Tamanho: {_format_size(compressed_bytes)} "
                f"(original: {_format_size(uncompressed_bytes)})"
            )
            self._discord_notifier.notify_backup(srv.name, detail=detail)  # type: ignore[union-attr]
        return str(zip_path)

    def _prune(self, srv: "ServerConfig") -> None:
        """Remove os backups mais antigos excedendo o limite de retenção."""
        keep = max(0, srv.backup_keep_count)
        if keep <= 0:
            return
        bdir = self.backup_dir(srv)
        if not bdir.exists():
            return
        all_items = sorted(
            [i for i in bdir.iterdir() if (i.is_file() and i.suffix == ".zip") or i.is_dir()],
            key=lambda i: i.stem if i.suffix == ".zip" else i.name,
        )
        for old in all_items[:-keep]:
            try:
                if old.is_file():
                    old.unlink()
                else:
                    shutil.rmtree(old)
                self._on_log(f"[Backup] Snapshot antigo removido: {old.name}", "debug")
            except Exception as exc:
                self._on_log(f"[Backup] Erro ao remover {old.name}: {exc}", "warning")

    def backup_all_servers(
        self,
        servers: List["AsmServerConfig"],
        global_bk: "BackupConfig",
    ) -> List[str]:
        """Executa backup ZIP de todos os servidores com install_dir configurado."""
        created: List[str] = []
        active = [s for s in servers if (s.install_dir or "").strip()]
        if not active:
            self._on_log("[Backup] Nenhum servidor com pasta de instalação para backup.", "warning")
            return created
        self._on_log(f"[Backup] Iniciando backup global de {len(active)} servidor(es)...", "info")
        for asm_srv in active:
            target = asm_server_to_backup_target(asm_srv, global_bk)
            path = self.do_backup(target)
            if path:
                created.append(path)
        self._on_log(f"[Backup] Backup global concluído ({len(created)}/{len(active)}).", "info")
        return created

    # ── Restaurar backup ──────────────────────────────────────────────────────

    def restore_backup(self, srv: "ServerConfig", backup_path: str) -> bool:
        """Restaura um snapshot (ZIP ou diretório legado) para o install_dir do servidor."""
        bp = Path(backup_path)
        if not bp.exists():
            self._on_log(f"[Backup] Snapshot não encontrado: {backup_path}", "error")
            return False
        if not srv.install_dir:
            self._on_log(f"[Backup] {srv.name}: diretório de instalação não configurado.", "error")
            return False

        if bp.is_file() and bp.suffix == ".zip":
            return self._restore_from_zip(srv, bp)
        return self._restore_from_dir(srv, bp)

    def _restore_from_zip(self, srv: "ServerConfig", zip_path: Path) -> bool:
        """Restaura a partir de um arquivo ZIP comprimido."""
        base      = Path(srv.install_dir) / "ShooterGame" / "Saved"
        cfg_dst   = base / "Config" / "WindowsServer"
        restored  = False
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                has_config = any(n.startswith("config/") for n in names)
                save_members = [n for n in names if n.startswith("saves/") and not n.endswith("/")]
                has_saves = bool(save_members)
                legacy_flat = _is_legacy_flat_saves(names)

                if has_config:
                    cfg_dst.mkdir(parents=True, exist_ok=True)
                    for member in (n for n in names if n.startswith("config/") and not n.endswith("/")):
                        dest = cfg_dst / Path(member).relative_to("config")
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as src, open(dest, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                    restored = True

                if has_saves:
                    for member in save_members:
                        rel = Path(member).relative_to("saves")
                        if legacy_flat and len(rel.parts) == 1:
                            dest = base / "SavedArks" / rel
                        else:
                            dest = base / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as src, open(dest, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                    restored = True
        except Exception as exc:
            self._on_log(f"[Backup] {srv.name}: erro ao restaurar ZIP — {exc}", "error")
            return False

        if restored:
            self._on_log(f"[Backup] {srv.name}: restaurado do snapshot {zip_path.name}.", "info")
        return restored

    def _restore_from_dir(self, srv: "ServerConfig", bp: Path) -> bool:
        """Restaura a partir de um diretório (formato legado)."""
        base      = Path(srv.install_dir) / "ShooterGame" / "Saved"
        cfg_dst   = base / "Config" / "WindowsServer"
        saves_dst = base / "SavedArks"
        restored  = False

        cfg_src = bp / "config"
        if cfg_src.exists():
            cfg_dst.mkdir(parents=True, exist_ok=True)
            for f in cfg_src.iterdir():
                if f.is_file():
                    shutil.copy2(str(f), str(cfg_dst / f.name))
            restored = True

        saves_src = bp / "saves"
        if saves_src.exists():
            if saves_dst.exists():
                shutil.rmtree(saves_dst)
            shutil.copytree(str(saves_src), str(saves_dst))
            restored = True

        if restored:
            self._on_log(f"[Backup] {srv.name}: restaurado do snapshot {bp.name}.", "info")
        return restored

    # ── Listar backups ────────────────────────────────────────────────────────

    def list_backups(self, srv: "ServerConfig") -> List[BackupEntry]:
        bdir = self.backup_dir(srv)
        if not bdir.exists():
            return []
        entries: List[BackupEntry] = []
        for item in sorted(bdir.iterdir(), reverse=True):
            if (item.is_file() and item.suffix == ".zip") or item.is_dir():
                try:
                    entries.append(BackupEntry(item))
                except Exception:
                    pass
        return entries

    # ── Deletar backup ────────────────────────────────────────────────────────

    def delete_backup(self, backup_path: str) -> bool:
        bp = Path(backup_path)
        try:
            if bp.is_file():
                bp.unlink()
            elif bp.is_dir():
                shutil.rmtree(bp)
            return True
        except Exception as exc:
            self._on_log(f"[Backup] Erro ao deletar snapshot: {exc}", "error")
            return False

    # ── Agendamento automático ────────────────────────────────────────────────

    def start_auto_backup(self, srv: "ServerConfig") -> None:
        """Agenda o próximo auto-backup para este servidor."""
        self.stop_auto_backup(srv.id)
        if not srv.backup_enabled or srv.backup_interval_hours <= 0:
            return

        interval_s = srv.backup_interval_hours * 3600

        def _run() -> None:
            current = self._find_server(srv.id)
            if not current or not current.backup_enabled:
                return
            self._on_log(f"[Backup] Auto-backup iniciado: {current.name}.", "info")
            self.do_backup(current)
            # Reagenda para o próximo ciclo
            self.start_auto_backup(current)

        with self._lock:
            t = threading.Timer(interval_s, _run)
            t.daemon = True
            t.start()
            self._timers[srv.id] = t

    def stop_auto_backup(self, server_id: str) -> None:
        """Cancela o timer de auto-backup."""
        with self._lock:
            t = self._timers.pop(server_id, None)
        if t:
            t.cancel()

    def restart_all(self, servers: List["ServerConfig"]) -> None:
        """Reinicia todos os timers (usar ao carregar configurações)."""
        for srv in servers:
            self.stop_auto_backup(srv.id)
            if srv.backup_enabled:
                self.start_auto_backup(srv)

    def shutdown(self) -> None:
        """Para todos os timers ativos."""
        for srv_id in list(self._timers):
            self.stop_auto_backup(srv_id)

    # ── Utilitários internos ──────────────────────────────────────────────────

    def _find_server(self, server_id: str) -> Optional["ServerConfig"]:
        for s in self._get_servers():
            if s.id == server_id:
                return s
        return None
