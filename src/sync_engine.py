"""
Motor de sincronização bidirecional para o ARKLAND - Server Manager.

Lógica:
  A cada N segundos realiza dois passes:
    1. Pasta local (ARK Cluster) → Pasta compartilhada
    2. Pasta compartilhada       → Pasta local (ARK Cluster)
  Em cada passe, um arquivo só é copiado se:
    - Não existir no destino, OU
    - A origem for mais recente que o destino (tolerância de 500 ms)
  Resultado: ambas as pastas ficam sempre com os arquivos mais recentes.
"""
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


class SyncEngine:
    def __init__(
        self,
        config,
        on_log: Optional[Callable[[str, str], None]] = None,
        on_status_change: Optional[Callable[[str], None]] = None,
        on_stats_update: Optional[Callable[[dict], None]] = None,
    ) -> None:
        self._config = config
        self._on_log = on_log or (lambda msg, level: None)
        self._on_status_change = on_status_change or (lambda s: None)
        self._on_stats_update = on_stats_update or (lambda s: None)

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()          # evita execuções simultâneas
        self._stats = {
            "total_synced": 0,
            "last_sync": "—",
            "errors": 0,
            "cycles": 0,
            "error_list": [],
        }

    # ── Controle público ───────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def stats(self) -> dict:
        return self._stats.copy()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="ArkSyncThread"
        )
        self._thread.start()
        self._on_status_change("running")
        self._log("Sincronização iniciada.", "info")

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._on_status_change("stopped")
        self._log("Sincronização parada.", "info")

    def sync_once(self) -> None:
        """Executa um ciclo imediato em background (não inicia o loop)."""
        threading.Thread(
            target=self._run_cycle, daemon=True, name="ArkForceSyncThread"
        ).start()

    # ── Loop interno ───────────────────────────────────────────────────────────

    def _loop(self) -> None:
        while self._running:
            self._run_cycle()
            interval = max(1, getattr(self._config, "sync_interval", 5))
            time.sleep(interval)

    def clear_errors(self) -> None:
        """Zera o contador e a lista de erros."""
        self._stats["errors"] = 0
        self._stats["error_list"] = []
        self._on_stats_update(self._stats.copy())

    def _add_error(self, message: str, etype: str = "") -> None:
        """Registra um erro: incrementa contador, salva na lista e emite log."""
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self._stats["errors"] += 1
        self._stats["error_list"].append(
            {"time": ts, "type": etype, "message": message}
        )
        self._log(message, "error")

    def _run_cycle(self) -> None:
        """Executa um ciclo de sync com lock para evitar sobreposição."""
        if not self._lock.acquire(blocking=False):
            return  # já está sincronizando
        try:
            self._sync()
        except Exception as exc:
            self._add_error(f"Erro inesperado: {exc}", "geral")
        finally:
            self._lock.release()

    # ── Lógica de sincronização ────────────────────────────────────────────────

    def _sync(self) -> None:
        cycles = getattr(self._config, "sync_cycles", None) or []

        # Compatibilidade com config legado (local_cluster_path / shared_path)
        if not cycles:
            local_str  = getattr(self._config, "local_cluster_path", "").strip()
            shared_str = getattr(self._config, "shared_path", "").strip()
            if local_str and shared_str:
                cycles = [[local_str, shared_str]]

        if not cycles:
            self._log("Nenhum ciclo configurado. Acesse a aba Sincronização.", "warning")
            return

        total_synced = 0
        for idx, cycle in enumerate(cycles):
            if not isinstance(cycle, list):
                continue
            folders = [Path(str(p)) for p in cycle if str(p).strip()]
            if len(folders) < 2:
                continue
            missing = [f for f in folders if not f.exists()]
            if missing:
                for m in missing:
                    self._log(f"[Ciclo {idx + 1}] Pasta não encontrada: {m}", "warning")
                continue
            total_synced += self._sync_cycle(idx + 1, folders)

        self._stats["cycles"] += 1
        self._stats["last_sync"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        if total_synced > 0:
            self._stats["total_synced"] += total_synced
            self._log(
                f"Sync #{self._stats['cycles']}: {total_synced} arquivo(s) copiado(s)  "
                f"[acumulado: {self._stats['total_synced']}]",
                "success",
            )
        elif getattr(self._config, "log_debug", False):
            self._log(f"Ciclo #{self._stats['cycles']}: nenhuma alteração.", "debug")

        self._on_stats_update(self._stats.copy())

    def _sync_cycle(self, cycle_num: int, folders: list) -> int:
        """Sync N-way: propaga a versão mais nova de cada arquivo para todas as pastas."""
        all_rels: set = set()
        for folder in folders:
            try:
                for f in folder.rglob("*"):
                    if f.is_file():
                        all_rels.add(f.relative_to(folder))
            except (PermissionError, OSError) as exc:
                self._add_error(f"[Ciclo {cycle_num}] Leitura: {exc}", "I/O")

        count = 0
        for rel in all_rels:
            # Acha a cópia mais nova entre todas as pastas do ciclo
            newest: Optional[Path] = None
            newest_mtime = -1.0
            for folder in folders:
                candidate = folder / rel
                try:
                    if candidate.exists():
                        m = candidate.stat().st_mtime
                        if m > newest_mtime:
                            newest_mtime = m
                            newest = candidate
                except OSError:
                    pass
            if newest is None:
                continue
            # Propaga para todas as pastas que não têm ou têm versão mais antiga
            for folder in folders:
                dst = folder / rel
                if not self._should_copy(newest, dst):
                    continue
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    is_new = not dst.exists()
                    shutil.copy2(newest, dst)
                    count += 1
                    action = "novo" if is_new else "atualizado"
                    try:
                        size_kb = newest.stat().st_size / 1024
                        size_str = (f"{size_kb:.1f} KB" if size_kb < 1024
                                    else f"{size_kb / 1024:.2f} MB")
                    except OSError:
                        size_str = "?"
                    self._log(
                        f"  ↪ [C{cycle_num}][{action}] {rel}  ({size_str})"
                        f"  {newest.parent.name} → {folder.name}",
                        "debug",
                    )
                except (PermissionError, OSError) as exc:
                    self._add_error(f"[Ciclo {cycle_num}] Cópia {rel}: {exc}", "I/O")
        return count

    def _copy_newer(self, src_root: Path, dst_root: Path) -> int:
        """Copia para dst_root todos os arquivos de src_root que forem mais novos."""
        count = 0
        try:
            for src_file in src_root.rglob("*"):
                if not src_file.is_file():
                    continue
                rel = src_file.relative_to(src_root)
                dst_file = dst_root / rel
                if self._should_copy(src_file, dst_file):
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    is_new = not dst_file.exists()
                    shutil.copy2(src_file, dst_file)
                    count += 1
                    action = "novo" if is_new else "atualizado"
                    try:
                        size_kb = src_file.stat().st_size / 1024
                        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"
                    except OSError:
                        size_str = "?"
                    self._log(
                        f"  ↪ [{action}] {rel}  ({size_str})  "
                        f"{src_root.name} → {dst_root.name}",
                        "debug",
                    )
        except PermissionError as exc:
            self._add_error(f"Permissão negada: {exc}", "permissão")
        except OSError as exc:
            self._add_error(f"Erro de I/O: {exc}", "I/O")
        return count

    @staticmethod
    def _should_copy(src: Path, dst: Path) -> bool:
        if not dst.exists():
            return True
        try:
            # Copia se origem for mais nova que destino (tolerância 500 ms)
            return src.stat().st_mtime > dst.stat().st_mtime + 0.5
        except OSError:
            return True

    # ── Utilitário ────────────────────────────────────────────────────────────

    def _log(self, message: str, level: str = "info") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._on_log(f"[{ts}] {message}", level)
