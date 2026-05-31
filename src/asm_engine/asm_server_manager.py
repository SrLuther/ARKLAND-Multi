"""
AsmServerManager — gerenciador de processos TEK.
Controla start/stop/restart e monitora o status de cada servidor ASM.
"""
from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Optional

from .asm_server_config import (
    AsmServerConfig,
    ASM_STATUS_STOPPED,
    ASM_STATUS_STARTING,
    ASM_STATUS_RUNNING,
    ASM_STATUS_STOPPING,
    ASM_STATUS_CRASHED,
)
from .asm_ini_manager import write_ini, build_launch_args


class AsmServerInstance:
    """Estado de uma instância de servidor TEK em execução."""

    def __init__(self, cfg: AsmServerConfig) -> None:
        self.cfg       = cfg
        self.status    = ASM_STATUS_STOPPED
        self._proc:    Optional[subprocess.Popen] = None   # type: ignore[type-arg]
        self._monitor: Optional[threading.Thread] = None
        self._lock     = threading.Lock()

    # ── Status helpers ──────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self.status == ASM_STATUS_RUNNING

    @property
    def pid(self) -> Optional[int]:
        return self._proc.pid if self._proc else None


class AsmServerManager:
    """Gerencia múltiplos servidores TEK."""

    def __init__(self, on_status_change: Optional[Callable[[str, str], None]] = None) -> None:
        """
        Args:
            on_status_change: callback(server_id, new_status) — chamado na thread de monitor.
        """
        self._instances: Dict[str, AsmServerInstance] = {}
        self._on_status = on_status_change
        self._lock = threading.Lock()

    # ── Instance access ──────────────────────────────────────────────────────

    def get_instance(self, server_id: str) -> Optional[AsmServerInstance]:
        return self._instances.get(server_id)

    def get_status(self, server_id: str) -> str:
        inst = self._instances.get(server_id)
        return inst.status if inst else ASM_STATUS_STOPPED

    # ── Start ────────────────────────────────────────────────────────────────

    def start(self, cfg: AsmServerConfig,
              on_done: Optional[Callable[[bool, str], None]] = None) -> None:
        """Inicia o servidor em thread separada.
        Args:
            on_done: callback(success: bool, message: str) — chamado ao terminar
        """
        if not cfg.install_dir:
            if on_done:
                on_done(False, "install_dir não configurado")
            return

        with self._lock:
            inst = self._instances.setdefault(cfg.id, AsmServerInstance(cfg))
            if inst.status in (ASM_STATUS_RUNNING, ASM_STATUS_STARTING):
                if on_done:
                    on_done(False, "Servidor já em execução")
                return
            inst.cfg = cfg
            inst.status = ASM_STATUS_STARTING

        if self._on_status:
            self._on_status(cfg.id, ASM_STATUS_STARTING)

        t = threading.Thread(target=self._start_worker, args=(cfg, inst, on_done), daemon=True)
        t.start()

    def _start_worker(self, cfg: AsmServerConfig, inst: AsmServerInstance,
                      on_done: Optional[Callable[[bool, str], None]]) -> None:
        try:
            # 1. Escreve INIs (⚠️ aguardar T13 antes de usar em produção)
            write_ini(cfg)

            # 2. Monta o comando
            exe = Path(cfg.install_dir) / "ShooterGame" / "Binaries" / "Win64" / cfg.server_exe
            args = build_launch_args(cfg)
            cmd = [str(exe)] + args

            # 3. Lança o processo
            proc = subprocess.Popen(
                cmd,
                cwd=str(exe.parent),
                creationflags=subprocess.CREATE_NEW_CONSOLE,  # type: ignore[attr-defined]
            )
            with inst._lock:
                inst._proc = proc

            # 4. Aguarda início (até 120 s verifica a cada 5 s)
            for _ in range(24):
                time.sleep(5)
                if proc.poll() is not None:
                    # Processo terminou logo após o start — falha
                    inst.status = ASM_STATUS_CRASHED
                    if self._on_status:
                        self._on_status(cfg.id, ASM_STATUS_CRASHED)
                    if on_done:
                        on_done(False, f"Processo terminou com código {proc.returncode}")
                    return
                # Considera online após 10 s sem crash
                if _ >= 2:
                    break

            inst.status = ASM_STATUS_RUNNING
            if self._on_status:
                self._on_status(cfg.id, ASM_STATUS_RUNNING)
            if on_done:
                on_done(True, "Servidor iniciado com sucesso")

            # 5. Aplica affinity/prioridade se configurado
            self._apply_process_settings(cfg, proc)

            # 6. Inicia monitor de processo
            self._start_monitor(inst)

        except Exception as exc:
            inst.status = ASM_STATUS_CRASHED
            if self._on_status:
                self._on_status(cfg.id, ASM_STATUS_CRASHED)
            if on_done:
                on_done(False, str(exc))

    # ── Stop ─────────────────────────────────────────────────────────────────

    def stop(self, server_id: str,
             on_done: Optional[Callable[[bool, str], None]] = None) -> None:
        inst = self._instances.get(server_id)
        if not inst or inst.status == ASM_STATUS_STOPPED:
            if on_done:
                on_done(True, "Servidor já parado")
            return

        inst.status = ASM_STATUS_STOPPING
        if self._on_status:
            self._on_status(server_id, ASM_STATUS_STOPPING)

        t = threading.Thread(target=self._stop_worker, args=(inst, on_done), daemon=True)
        t.start()

    def _stop_worker(self, inst: AsmServerInstance,
                     on_done: Optional[Callable[[bool, str], None]]) -> None:
        try:
            # Tenta RCON saveworld + doexit antes de matar
            self._rcon_shutdown(inst.cfg)
            time.sleep(5)

            proc = inst._proc
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=30)
                except Exception:
                    proc.kill()

            inst.status = ASM_STATUS_STOPPED
            inst._proc = None
            if self._on_status:
                self._on_status(inst.cfg.id, ASM_STATUS_STOPPED)
            if on_done:
                on_done(True, "Servidor parado")
        except Exception as exc:
            inst.status = ASM_STATUS_STOPPED
            inst._proc = None
            if self._on_status:
                self._on_status(inst.cfg.id, ASM_STATUS_STOPPED)
            if on_done:
                on_done(False, str(exc))

    def _rcon_shutdown(self, cfg: AsmServerConfig) -> None:
        """Envia saveworld + doexit via RCON (silencia erros se RCON indisponível)."""
        if not cfg.rcon_enabled or not cfg.admin_password:
            return
        try:
            from ..rcon_client import RconClient
            rc = RconClient("127.0.0.1", cfg.rcon_port, cfg.admin_password)
            rc.connect()
            rc.send_command_safe("saveworld")
            time.sleep(2)
            rc.send_command_safe("doexit")
            rc.disconnect()
        except Exception:
            pass

    # ── Monitor ──────────────────────────────────────────────────────────────

    def _start_monitor(self, inst: AsmServerInstance) -> None:
        if inst._monitor and inst._monitor.is_alive():
            return
        t = threading.Thread(target=self._monitor_worker, args=(inst,), daemon=True)
        inst._monitor = t
        t.start()

    def _monitor_worker(self, inst: AsmServerInstance) -> None:
        while True:
            time.sleep(5)
            proc = inst._proc
            if proc is None:
                break
            rc = proc.poll()
            if rc is not None:
                with inst._lock:
                    if inst.status not in (ASM_STATUS_STOPPED, ASM_STATUS_STOPPING):
                        inst.status = ASM_STATUS_CRASHED
                        inst._proc = None
                        if self._on_status:
                            self._on_status(inst.cfg.id, ASM_STATUS_CRASHED)
                break

    # ── Restart ──────────────────────────────────────────────────────────────

    def restart(self, cfg: AsmServerConfig,
                on_done: Optional[Callable[[bool, str], None]] = None) -> None:
        def _after_stop(ok: bool, msg: str) -> None:
            time.sleep(2)
            self.start(cfg, on_done=on_done)

        self.stop(cfg.id, on_done=_after_stop)

    # ── Process settings (affinity + priority) ────────────────────────────────

    @staticmethod
    def _apply_process_settings(
        cfg: AsmServerConfig, proc: "subprocess.Popen[bytes]"
    ) -> None:
        """Aplica CPU affinity e prioridade de processo via psutil (melhor esforço)."""
        cores    = getattr(cfg, "cpu_affinity_cores", [])
        priority = getattr(cfg, "process_priority", "normal")
        if not cores and priority == "normal":
            return
        try:
            import psutil  # type: ignore[reportMissingImports]
            p = psutil.Process(proc.pid)
            if cores:
                p.cpu_affinity(cores)
            _pri_map = {
                "normal":       psutil.NORMAL_PRIORITY_CLASS,        # type: ignore[attr-defined]
                "above_normal": psutil.ABOVE_NORMAL_PRIORITY_CLASS,  # type: ignore[attr-defined]
                "high":         psutil.HIGH_PRIORITY_CLASS,          # type: ignore[attr-defined]
                "realtime":     psutil.REALTIME_PRIORITY_CLASS,      # type: ignore[attr-defined]
            }
            if priority in _pri_map:
                p.nice(_pri_map[priority])
        except Exception:
            pass  # psutil não instalado ou permissão negada — ignora silenciosamente
