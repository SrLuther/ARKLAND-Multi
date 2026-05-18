"""
Gerenciador de backups automáticos de saves e configurações de servidor ARK.

Estrutura de armazenamento:
  %APPDATA%/ARKLAND-ServerManager/backups/servers/{server_id}/{YYYYMMDD_HHMMSS}/
      config/   ← GameUserSettings.ini, Game.ini (WindowsServer/)
      saves/    ← SavedArks/
"""
from __future__ import annotations

import os
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .server_config import ServerConfig

_DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager"


class BackupEntry:
    """Representa um único snapshot de backup."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.timestamp = path.name
        try:
            self.dt = datetime.strptime(self.timestamp, "%Y%m%d_%H%M%S")
        except ValueError:
            self.dt = datetime.fromtimestamp(path.stat().st_mtime)

        self.has_saves  = (path / "saves").exists()
        self.has_config = (path / "config").exists()

        total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        self.size_mb = round(total / (1024 * 1024), 1)

    @property
    def label(self) -> str:
        parts: List[str] = []
        if self.has_config:
            parts.append("Config")
        if self.has_saves:
            parts.append("Saves")
        tag = " + ".join(parts) if parts else "Vazio"
        return f"{self.dt.strftime('%d/%m/%Y %H:%M:%S')}  [{tag}]  {self.size_mb} MB"


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
        self._backups_root = _DATA_DIR / "backups" / "servers"
        self._timers: Dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    # ── Caminho do diretório de backups ───────────────────────────────────────

    def backup_dir(self, srv: "ServerConfig") -> Path:
        if srv.backup_dir:
            return Path(srv.backup_dir) / srv.id
        return self._backups_root / srv.id

    # ── Realizar backup ───────────────────────────────────────────────────────

    def do_backup(self, srv: "ServerConfig") -> Optional[str]:
        """Faz backup dos arquivos selecionados. Retorna caminho do snapshot ou None."""
        if not srv.install_dir:
            self._on_log(f"[Backup] {srv.name}: diretório de instalação não configurado.", "warning")
            return None

        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        bdir = self.backup_dir(srv) / ts
        bdir.mkdir(parents=True, exist_ok=True)

        copied = False

        if srv.backup_include_config:
            cfg_src = Path(srv.install_dir) / "ShooterGame" / "Saved" / "Config" / "WindowsServer"
            if cfg_src.exists():
                shutil.copytree(str(cfg_src), str(bdir / "config"))
                copied = True
            else:
                self._on_log(f"[Backup] {srv.name}: pasta de config não encontrada ({cfg_src}).", "warning")

        if srv.backup_include_saves:
            saves_src = Path(srv.install_dir) / "ShooterGame" / "Saved" / "SavedArks"
            if saves_src.exists():
                shutil.copytree(str(saves_src), str(bdir / "saves"))
                copied = True
            else:
                self._on_log(f"[Backup] {srv.name}: pasta de saves não encontrada ({saves_src}).", "warning")

        if copied:
            self._on_log(f"[Backup] {srv.name}: snapshot salvo → {bdir.name}", "info")
            self._prune(srv)
            if self._discord_notifier:
                entry = BackupEntry(bdir)
                detail = f"Snapshot: `{bdir.name}`\nTamanho: {entry.size_mb} MB"
                self._discord_notifier.notify_backup(srv.name, detail=detail)  # type: ignore[union-attr]
            return str(bdir)

        # Nada foi copiado — remove a pasta vazia
        try:
            bdir.rmdir()
        except Exception:
            pass
        return None

    def _prune(self, srv: "ServerConfig") -> None:
        """Remove os backups mais antigos excedendo o limite de retenção."""
        bdir = self.backup_dir(srv)
        if not bdir.exists():
            return
        entries = sorted(
            [d for d in bdir.iterdir() if d.is_dir()],
            key=lambda d: d.name,
        )
        keep = max(1, srv.backup_keep_count)
        for old in entries[:-keep]:
            try:
                shutil.rmtree(old)
                self._on_log(f"[Backup] Snapshot antigo removido: {old.name}", "debug")
            except Exception as exc:
                self._on_log(f"[Backup] Erro ao remover {old.name}: {exc}", "warning")

    # ── Restaurar backup ──────────────────────────────────────────────────────

    def restore_backup(self, srv: "ServerConfig", backup_path: str) -> bool:
        """Restaura um snapshot para o install_dir do servidor."""
        bp = Path(backup_path)
        if not bp.exists():
            self._on_log(f"[Backup] Snapshot não encontrado: {backup_path}", "error")
            return False
        if not srv.install_dir:
            self._on_log(f"[Backup] {srv.name}: diretório de instalação não configurado.", "error")
            return False

        base       = Path(srv.install_dir) / "ShooterGame" / "Saved"
        cfg_dst    = base / "Config" / "WindowsServer"
        saves_dst  = base / "SavedArks"
        restored   = False

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
        for d in sorted(bdir.iterdir(), reverse=True):
            if d.is_dir():
                try:
                    entries.append(BackupEntry(d))
                except Exception:
                    pass
        return entries

    # ── Deletar backup ────────────────────────────────────────────────────────

    def delete_backup(self, backup_path: str) -> bool:
        bp = Path(backup_path)
        try:
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
