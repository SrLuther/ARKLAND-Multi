"""
Motor de sincronização bidirecional para o ARKLAND-Multi.

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
        local_str = getattr(self._config, "local_cluster_path", "").strip()
        shared_str = getattr(self._config, "shared_path", "").strip()

        if not local_str or not shared_str:
            self._log(
                "Caminhos não configurados. Acesse a aba Configurações.", "warning"
            )
            return

        local = Path(local_str)
        shared = Path(shared_str)

        if not local.exists():
            self._log(f"Pasta local não encontrada: {local}", "warning")
            return
        if not shared.exists():
            self._log(f"Pasta compartilhada não encontrada: {shared}", "warning")
            return

        to_shared = self._copy_newer(local, shared)
        to_local = self._copy_newer(shared, local)

        self._stats["cycles"] += 1
        self._stats["last_sync"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        total = to_shared + to_local

        if total > 0:
            self._stats["total_synced"] += total
            self._log(
                f"Sync #{self._stats['cycles']}: "
                f"{to_shared} arquivo(s) → compartilhada | "
                f"{to_local} arquivo(s) → local  "
                f"[total acumulado: {self._stats['total_synced']}]",
                "success",
            )
        else:
            log_debug = getattr(self._config, "log_debug", False)
            if log_debug:
                self._log(
                    f"Ciclo #{self._stats['cycles']}: nenhuma alteração detectada.", "debug"
                )

        self._on_stats_update(self._stats.copy())

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
                    shutil.copy2(src_file, dst_file)
                    count += 1
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
