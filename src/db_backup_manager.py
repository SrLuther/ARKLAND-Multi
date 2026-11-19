"""Backup e restauração compactados do MariaDB/MySQL (arkland_shop, ark_permission)."""
from __future__ import annotations

import shutil
import subprocess
import threading
import zipfile
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, List, Optional, TYPE_CHECKING

from .arkland_environment import default_db_backup_dir, shared_db_backup_dir

_RECENT_BACKUP_HOURS = 7
_DAILY_BACKUP_DAYS = 30

if TYPE_CHECKING:
    from .config_manager import DbBackupConfig


def _mariadb_bin_dir() -> Path:
    from .arkland_environment import default_mariadb_dir
    return default_mariadb_dir() / "bin"


@dataclass
class DbBackupEntry:
    path: Path
    timestamp: str
    size_mb: float
    databases: List[str]

    @property
    def label(self) -> str:
        try:
            dt = datetime.strptime(self.timestamp.removesuffix("_daily"), "%Y%m%d_%H%M%S")
            when = dt.strftime("%d/%m/%Y %H:%M:%S")
        except ValueError:
            when = self.timestamp
        dbs = ", ".join(self.databases) if self.databases else "?"
        cadence = "Diário · " if self.path.stem.endswith("_daily") else ""
        return f"{cadence}{when}  [{dbs}]  {self.size_mb} MB"


class DbBackupManager:
  """Cria/restaura dumps SQL compactados em ZIP (nível 9)."""

  def __init__(
      self,
      on_log: Optional[Callable[[str, str], None]] = None,
  ) -> None:
      self._on_log = on_log or (lambda _m, _l: None)
      self._lock = threading.Lock()
      self._running = False

  def backup_dir(self, cfg: "DbBackupConfig") -> Path:
      if getattr(cfg, "use_shared_backup_location", False):
          return shared_db_backup_dir(getattr(cfg, "shared_backup_root", ""))
      raw = (cfg.backup_dir or "").strip()
      return Path(raw) if raw else default_db_backup_dir()

  def list_backups(self, cfg: "DbBackupConfig") -> List[DbBackupEntry]:
      bdir = self.backup_dir(cfg)
      if not bdir.exists():
          return []
      out: List[DbBackupEntry] = []
      for item in sorted(bdir.glob("*.zip"), reverse=True):
          try:
              out.append(self._entry_from_zip(item))
          except Exception:
              pass
      return out

  def create_backup(
      self,
      cfg: "DbBackupConfig",
      *,
      host: str,
      port: int,
      user: str,
      password: str,
      scheduled: bool = False,
  ) -> Optional[str]:
      """Executa mysqldump dos bancos selecionados. Retorna caminho do .zip."""
      with self._lock:
          if self._running:
              self._on_log("[DB Backup] Já existe um backup em andamento.", "warning")
              return None
          self._running = True
      try:
          return self._create_backup_unlocked(
              cfg, host=host, port=port, user=user, password=password,
              scheduled=scheduled,
          )
      finally:
          with self._lock:
              self._running = False

  def restore_backup(
      self,
      backup_path: str,
      *,
      host: str,
      port: int,
      user: str,
      password: str,
  ) -> bool:
      """Restaura todos os .sql dentro do ZIP de backup."""
      zp = Path(backup_path)
      if not zp.is_file():
          self._on_log(f"[DB Backup] Arquivo não encontrado: {backup_path}", "error")
          return False
      mysql = self._resolve_mysql()
      if not mysql:
          self._on_log("[DB Backup] mysql.exe não encontrado (instale MariaDB portable).", "error")
          return False
      restored = 0
      try:
          with zipfile.ZipFile(zp, "r") as zf:
              sql_members = [n for n in zf.namelist() if n.endswith(".sql") and not n.endswith("/")]
              for member in sql_members:
                  db_name = Path(member).stem
                  self._on_log(f"[DB Backup] Restaurando {db_name}...", "info")
                  sql_bytes = zf.read(member)
                  ok = self._run_mysql_import(
                      mysql, host=host, port=port, user=user, password=password,
                      sql_data=sql_bytes,
                  )
                  if ok:
                      restored += 1
      except Exception as exc:
          self._on_log(f"[DB Backup] Erro ao restaurar: {exc}", "error")
          return False
      if restored:
          self._on_log(f"[DB Backup] Restauração concluída ({restored} banco(s)).", "info")
          return True
      self._on_log("[DB Backup] Nenhum banco restaurado.", "warning")
      return False

  def delete_backup(self, backup_path: str) -> bool:
      try:
          Path(backup_path).unlink(missing_ok=True)
          return True
      except Exception as exc:
          self._on_log(f"[DB Backup] Erro ao excluir: {exc}", "error")
          return False

  # ── Internos ──────────────────────────────────────────────────────────────

  def _create_backup_unlocked(
      self,
      cfg: "DbBackupConfig",
      *,
      host: str,
      port: int,
      user: str,
      password: str,
      scheduled: bool = False,
  ) -> Optional[str]:
      databases: List[str] = []
      if cfg.include_arkshop:
          databases.append("arkland_shop")
      if cfg.include_permissions:
          databases.append("ark_permission")
      if not databases:
          self._on_log("[DB Backup] Nenhum banco selecionado.", "warning")
          return None

      mysqldump = self._resolve_mysqldump()
      if not mysqldump:
          self._on_log("[DB Backup] mysqldump não encontrado (instale MariaDB portable).", "error")
          return None

      bdir = self.backup_dir(cfg)
      bdir.mkdir(parents=True, exist_ok=True)
      now = datetime.now()
      ts = now.strftime("%Y%m%d_%H%M%S")
      is_daily = scheduled and not any(bdir.glob(f"{now:%Y%m%d}_*_daily.zip"))
      zip_path = bdir / f"{ts}{'_daily' if is_daily else ''}.zip"
      temp_path = zip_path.with_name(zip_path.name + ".partial")
      added = 0

      try:
          with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
              for db in databases:
                  self._on_log(f"[DB Backup] Exportando {db}...", "info")
                  proc = subprocess.run(
                      [
                          str(mysqldump),
                          f"-h{host}",
                          f"-P{port}",
                          f"-u{user}",
                          f"-p{password}",
                          "--single-transaction",
                          "--routines",
                          "--triggers",
                          "--add-drop-database",
                          "--databases",
                          db,
                      ],
                      capture_output=True,
                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                  )
                  if proc.returncode != 0:
                      err = (proc.stderr or proc.stdout or b"").decode("utf-8", errors="replace")[:300]
                      self._on_log(f"[DB Backup] mysqldump falhou ({db}): {err}", "error")
                      continue
                  if proc.stdout:
                      zf.writestr(f"{db}.sql", proc.stdout)
                      added += 1
      except Exception as exc:
          self._on_log(f"[DB Backup] Erro ao criar ZIP: {exc}", "error")
          temp_path.unlink(missing_ok=True)
          zip_path.unlink(missing_ok=True)
          return None

      if added != len(databases):
          temp_path.unlink(missing_ok=True)
          zip_path.unlink(missing_ok=True)
          self._on_log(
              f"[DB Backup] Snapshot descartado: apenas {added}/{len(databases)} banco(s) foram exportados.",
              "error",
          )
          return None

      try:
          with zipfile.ZipFile(temp_path, "r") as verify_zip:
              bad_member = verify_zip.testzip()
              if bad_member:
                  raise zipfile.BadZipFile(f"CRC inválido: {bad_member}")
          os.replace(temp_path, zip_path)
      except Exception as exc:
          self._on_log(f"[DB Backup] Validação do snapshot falhou: {exc}", "error")
          temp_path.unlink(missing_ok=True)
          return None

      entry = self._entry_from_zip(zip_path)
      self._on_log(f"[DB Backup] Backup salvo → {zip_path.name} ({entry.size_mb} MB)", "info")
      self._prune(cfg)
      return str(zip_path)

  def _prune(self, cfg: "DbBackupConfig") -> None:
      bdir = self.backup_dir(cfg)
      if not bdir.exists():
          return
      now = datetime.now()
      recent_cutoff = now - timedelta(hours=_RECENT_BACKUP_HOURS)
      daily_cutoff = now - timedelta(days=_DAILY_BACKUP_DAYS)
      stale_partial_cutoff = now - timedelta(days=1)
      for partial in bdir.glob("*.partial"):
          try:
              if datetime.fromtimestamp(partial.stat().st_mtime) < stale_partial_cutoff:
                  partial.unlink()
          except OSError as exc:
              self._on_log(f"[DB Backup] Não foi possível limpar temporário {partial.name}: {exc}", "warning")
      keep_paths: set[Path] = set()
      named_daily: dict[object, tuple[datetime, Path]] = {}
      legacy_daily: dict[object, tuple[datetime, Path]] = {}
      snapshots: list[tuple[Path, datetime, bool]] = []
      for item in bdir.glob("*.zip"):
          try:
              stamp = datetime.strptime(item.stem.removesuffix("_daily"), "%Y%m%d_%H%M%S")
          except ValueError:
              stamp = datetime.fromtimestamp(item.stat().st_mtime)
          is_daily = item.stem.endswith("_daily")
          snapshots.append((item, stamp, is_daily))
          if stamp >= recent_cutoff:
              keep_paths.add(item)
          elif stamp >= daily_cutoff:
              target = named_daily if is_daily else legacy_daily
              day = stamp.date()
              if day not in target or stamp > target[day][0]:
                  target[day] = (stamp, item)
      for day, snapshot in legacy_daily.items():
          named_daily.setdefault(day, snapshot)
      keep_paths.update(path for _stamp, path in named_daily.values())

      for old, _stamp, _is_daily in snapshots:
          if old in keep_paths:
              continue
          try:
              old.unlink()
              self._on_log(f"[DB Backup] Backup antigo removido: {old.name}", "debug")
          except Exception as exc:
              self._on_log(f"[DB Backup] Erro ao remover {old.name}: {exc}", "warning")

  def _entry_from_zip(self, path: Path) -> DbBackupEntry:
      dbs: List[str] = []
      with zipfile.ZipFile(path, "r") as zf:
          for name in zf.namelist():
              if name.endswith(".sql"):
                  dbs.append(Path(name).stem)
      size_mb = round(path.stat().st_size / (1024 * 1024), 2)
      return DbBackupEntry(path=path, timestamp=path.stem, size_mb=size_mb, databases=sorted(dbs))

  @staticmethod
  def _resolve_mysqldump() -> Optional[Path]:
      local = _mariadb_bin_dir() / "mysqldump.exe"
      if local.exists():
          return local
      found = shutil.which("mysqldump")
      return Path(found) if found else None

  @staticmethod
  def _resolve_mysql() -> Optional[Path]:
      local = _mariadb_bin_dir() / "mysql.exe"
      if local.exists():
          return local
      found = shutil.which("mysql")
      return Path(found) if found else None

  def _run_mysql_import(
      self,
      mysql: Path,
      *,
      host: str,
      port: int,
      user: str,
      password: str,
      sql_data: bytes,
  ) -> bool:
      try:
          proc = subprocess.run(
              [
                  str(mysql),
                  f"-h{host}",
                  f"-P{port}",
                  f"-u{user}",
                  f"-p{password}",
              ],
              input=sql_data,
              capture_output=True,
              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
          )
          if proc.returncode != 0:
              err = (proc.stderr or b"").decode("utf-8", errors="replace")[:300]
              self._on_log(f"[DB Backup] mysql import falhou: {err}", "error")
              return False
          return True
      except Exception as exc:
          self._on_log(f"[DB Backup] Erro no import: {exc}", "error")
          return False
