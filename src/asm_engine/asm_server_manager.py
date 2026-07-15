"""
AsmServerManager — gerenciador de processos TEK.
Controla start/stop/restart e monitora o status de cada servidor ASM.
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ── psutil (opcional) ─────────────────────────────────────────────────────────
try:
    import psutil as _psutil  # type: ignore[reportMissingImports]
    _PSUTIL_OK = True
except ImportError:
    _psutil = None  # type: ignore[assignment]
    _PSUTIL_OK = False


class _PsutilProcessWrapper:
    """Simula subprocess.Popen usando psutil.Process.
    Usado quando o servidor é lançado via RunServer.cmd (os.startfile),
    onde não temos handle Popen direto do ShooterGameServer.exe.
    """

    def __init__(self, proc: Any) -> None:
        self._proc = proc
        self.pid: int = proc.pid
        self.returncode: Optional[int] = None

    def poll(self) -> Optional[int]:
        try:
            if not self._proc.is_running() or self._proc.status() == "zombie":
                if self.returncode is None:
                    self.returncode = -1
                return self.returncode
        except Exception:
            if self.returncode is None:
                self.returncode = -1
            return self.returncode
        return None

    def wait(self, timeout: Optional[float] = None) -> int:
        try:
            rc = self._proc.wait(timeout=timeout)
            self.returncode = rc if rc is not None else -1
        except Exception:
            self.returncode = -1
        return self.returncode  # type: ignore[return-value]

    def terminate(self) -> None:
        try:
            self._proc.terminate()
        except Exception:
            pass

    def kill(self) -> None:
        try:
            self._proc.kill()
        except Exception:
            pass


def _find_server_process(
    install_dir: str,
    after: datetime,
    timeout: float = 20.0,
) -> Any:
    """Busca ShooterGameServer.exe criado após `after` com caminho dentro de
    `install_dir`. Sonda process_iter por até `timeout` segundos.
    Retorna None se não encontrado ou se psutil indisponível.
    """
    if not _PSUTIL_OK or _psutil is None:
        return None
    install_norm = install_dir.replace("\\", "/").lower()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            for p in _psutil.process_iter(["pid", "name", "exe", "create_time"]):
                try:
                    name = p.info.get("name") or ""
                    if "shootergameserver" not in name.lower():
                        continue
                    exe = (p.info.get("exe") or "").replace("\\", "/").lower()
                    if install_norm not in exe:
                        continue
                    ct = p.info.get("create_time") or 0.0
                    if ct >= after.timestamp() - 5:
                        return p
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(0.5)
    return None


def _normalize_install_dir(path: str) -> str:
    return (path or "").replace("\\", "/").lower().rstrip("/")


def _path_contains_install(haystack: str, install_norm: str) -> bool:
    """Evita falso positivo quando um install_dir é prefixo de outro."""
    if not haystack or not install_norm:
        return False
    hay = haystack.replace("\\", "/").lower()
    idx = hay.find(install_norm)
    if idx < 0:
        return False
    after = hay[idx + len(install_norm):]
    return after == "" or after[0] in "/\\?\"'"


def _install_dir_in_process(exe: str, cmdline: str, install_norm: str) -> bool:
    return (
        _path_contains_install(exe, install_norm)
        or _path_contains_install(cmdline, install_norm)
    )


def _cmdline_has_port(cmdline: str, port: int) -> bool:
    if not cmdline or not port:
        return False
    needle = str(port)
    return (
        f"?port={needle}" in cmdline
        or f"-port={needle}" in cmdline
        or f"?port={needle}?" in cmdline
    )


def _cmdline_has_query_port(cmdline: str, query_port: int) -> bool:
    if not cmdline or not query_port:
        return False
    needle = str(query_port)
    return (
        f"?queryport={needle}" in cmdline
        or f"-queryport={needle}" in cmdline
        or f"?queryport={needle}?" in cmdline
    )


def _map_token_in_cmdline(cmdline: str, cfg: "AsmServerConfig") -> bool:
    if not cmdline:
        return False
    from .asm_mod_utils import map_cli_name

    token = map_cli_name(cfg.server_map, cfg.install_dir or "").lower()
    return bool(token) and token in cmdline


def _alt_save_in_cmdline(cmdline: str, cfg: "AsmServerConfig") -> bool:
    alt = (cfg.alt_save_directory_name or "").strip().lower()
    if not cmdline or not alt or alt == "savegame":
        return False
    return f"?altsavedirectoryname={alt}" in cmdline


def _cmdline_matches_server(cmdline: str, cfg: "AsmServerConfig") -> bool:
    """True se a linha de comando pertence ao servidor (porta / query port)."""
    if not cmdline:
        return False
    return (
        _cmdline_has_port(cmdline, cfg.server_port)
        or _cmdline_has_query_port(cmdline, cfg.query_port)
    )


def _cmdline_disambiguate(cmdline: str, cfg: "AsmServerConfig") -> bool:
    """Desambigua vários mapas no mesmo install_dir ou exe indisponível."""
    if _alt_save_in_cmdline(cmdline, cfg):
        return True
    if not _map_token_in_cmdline(cmdline, cfg):
        return False
    return (
        _cmdline_has_port(cmdline, cfg.server_port)
        or _cmdline_has_query_port(cmdline, cfg.query_port)
    )


def _process_matches_cfg(
    cfg: "AsmServerConfig",
    exe: str,
    cmdline: str,
    install_dir_counts: Dict[str, int],
) -> bool:
    install_norm = _normalize_install_dir(cfg.install_dir)
    install_hit = bool(install_norm) and _install_dir_in_process(exe, cmdline, install_norm)
    port_hit = _cmdline_matches_server(cmdline, cfg)

    if install_hit:
        if install_dir_counts.get(install_norm, 0) > 1:
            return port_hit or _cmdline_disambiguate(cmdline, cfg)
        return True
    return port_hit or _cmdline_disambiguate(cmdline, cfg)


def _read_shooter_process_fields(proc: Any) -> tuple[str, str]:
    """exe/cmdline normalizados; relê via Process(pid) se process_iter vier incompleto."""
    exe = proc.info.get("exe") or ""
    cmdline_parts = proc.info.get("cmdline") or []
    pid = proc.info.get("pid")
    if _PSUTIL_OK and _psutil is not None and pid and (not exe or not cmdline_parts):
        try:
            raw = _psutil.Process(int(pid))
            if not exe:
                exe = raw.exe() or ""
            if not cmdline_parts:
                cmdline_parts = raw.cmdline() or []
        except Exception:
            pass
    return exe.replace("\\", "/").lower(), " ".join(cmdline_parts).lower()


from .asm_server_config import (
    AsmServerConfig,
    ASM_STATUS_STOPPED,
    ASM_STATUS_STARTING,
    ASM_STATUS_RUNNING,
    ASM_STATUS_STOPPING,
    ASM_STATUS_CRASHED,
)
from ..mod_manager import ModManager
from .asm_ini_manager import write_ini, build_launch_args, mirror_ini_to_user_config_folder
from .asm_mod_utils import collect_mod_ids_for_install


def _escape_runserver_cmd_line(cmd: str) -> str:
    """Duplica % para RunServer.cmd — cmd.exe expande %VAR% e corrompe URL-encoding."""
    return cmd.replace("%", "%%")


class AsmServerInstance:
    """Estado de uma instância de servidor TEK em execução."""

    def __init__(self, cfg: AsmServerConfig) -> None:
        self.cfg       = cfg
        self.status    = ASM_STATUS_STOPPED
        self._proc:    Optional[subprocess.Popen] = None   # type: ignore[type-arg]
        self._monitor: Optional[threading.Thread] = None
        self._lock     = threading.Lock()
        self.uptime_start: Optional[float] = None
        self.steam_status: str = "unavailable"
        self.steam_status_detail: str = ""
        self.listing_mode: str = "unavailable"
        self.listing_detail: str = ""
        self.a2s_players: Optional[int] = None
        self.a2s_max_players: Optional[int] = None

    # ── Status helpers ──────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self.status == ASM_STATUS_RUNNING

    @property
    def pid(self) -> Optional[int]:
        return self._proc.pid if self._proc else None


class AsmServerManager:
    """Gerencia múltiplos servidores TEK."""

    def __init__(
        self,
        on_status_change: Optional[Callable[[str, str], None]] = None,
        on_visibility_change: Optional[Callable[[str, str, str], None]] = None,
        machine_public_ip: str = "",
        get_mod_path_blacklist: Optional[Callable[[], List[str]]] = None,
        on_log: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        """
        Args:
            on_status_change: callback(server_id, new_status) — chamado na thread de monitor.
            on_visibility_change: callback(server_id, steam_status, detail) — listagem Steam/LAN.
            machine_public_ip: IP público global (paridade ASM MachinePublicIP).
            get_mod_path_blacklist: paths relativos a apagar antes do start.
            on_log: callback(msg, level) para avisos de limpeza/start.
        """
        self._instances: Dict[str, AsmServerInstance] = {}
        self._on_status = on_status_change
        self._on_visibility = on_visibility_change
        self._machine_public_ip = (machine_public_ip or "").strip()
        self._get_mod_path_blacklist = get_mod_path_blacklist
        self._on_log = on_log or (lambda _msg, _level: None)
        self._lock = threading.Lock()
        # IDs com start/restart real (não scan/reconnect) — para ForceDay pós-RUNNING
        self._force_day_pending: set[str] = set()
        from ..server_visibility import get_steam_poller
        poller = get_steam_poller()
        poller.set_machine_public_ip(self._machine_public_ip)
        poller.set_on_change(self._steam_visibility_callback)

    def mark_force_day_pending(self, server_id: str) -> None:
        with self._lock:
            self._force_day_pending.add(server_id)

    def consume_force_day_pending(self, server_id: str) -> bool:
        with self._lock:
            if server_id in self._force_day_pending:
                self._force_day_pending.discard(server_id)
                return True
            return False

    def clear_force_day_pending(self, server_id: str) -> None:
        with self._lock:
            self._force_day_pending.discard(server_id)

    def set_machine_public_ip(self, ip: str) -> None:
        self._machine_public_ip = (ip or "").strip()
        from ..server_visibility import get_steam_poller
        get_steam_poller().set_machine_public_ip(self._machine_public_ip)

    def _steam_visibility_callback(self, server_id: str, mode: str, detail: str) -> None:
        if self._on_visibility:
            self._on_visibility(server_id, mode, detail)

    # ── Instance access ──────────────────────────────────────────────────────

    def get_instance(self, server_id: str) -> Optional[AsmServerInstance]:
        return self._instances.get(server_id)

    def get_status(self, server_id: str) -> str:
        inst = self._instances.get(server_id)
        return inst.status if inst else ASM_STATUS_STOPPED

    def register_servers(self, servers: List[AsmServerConfig]) -> None:
        """Garante uma instância interna para cada servidor configurado."""
        with self._lock:
            for cfg in servers:
                inst = self._instances.setdefault(cfg.id, AsmServerInstance(cfg))
                inst.cfg = cfg

    def scan_running_servers(self, servers: List[AsmServerConfig]) -> int:
        """Reconecta processos ShooterGameServer já em execução (ex.: após reiniciar o app).

        Correspondência por pasta de instalação no executável e/ou ?Port= / -port= na CLI.
        """
        if not _PSUTIL_OK or _psutil is None:
            return 0

        self.register_servers(servers)
        install_counts: Dict[str, int] = {}
        for cfg in servers:
            key = _normalize_install_dir(cfg.install_dir)
            if key:
                install_counts[key] = install_counts.get(key, 0) + 1

        claimed: set[int] = set()
        reconnected = 0

        try:
            for proc in _psutil.process_iter(["pid", "name", "exe", "cmdline", "create_time"]):
                try:
                    name = proc.info.get("name") or ""
                    if "shootergameserver" not in name.lower():
                        continue
                    pid = int(proc.info["pid"])
                    if pid in claimed:
                        continue
                    exe, cmdline = _read_shooter_process_fields(proc)
                    create_time = proc.info.get("create_time")

                    with self._lock:
                        for cfg in servers:
                            inst = self._instances.get(cfg.id)
                            if not inst or inst.status != ASM_STATUS_STOPPED:
                                continue
                            if not _process_matches_cfg(cfg, exe, cmdline, install_counts):
                                continue

                            raw = _psutil.Process(pid)
                            inst._proc = _PsutilProcessWrapper(raw)
                            inst.cfg = cfg
                            inst.status = ASM_STATUS_RUNNING
                            inst.uptime_start = float(create_time or time.time())
                            if self._on_status:
                                self._on_status(cfg.id, ASM_STATUS_RUNNING)
                            self._start_monitor(inst)
                            self._start_steam_watcher(inst)
                            claimed.add(pid)
                            reconnected += 1
                            break
                except Exception:
                    pass
        except Exception:
            pass

        return reconnected

    def try_reconnect_server(self, cfg: AsmServerConfig) -> bool:
        """Tenta reconectar um único servidor já em execução. Retorna True se reconectou."""
        return self.scan_running_servers([cfg]) > 0

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

        # Grava INI antes de reconectar — nome da sessão e demais configs no disco
        try:
            write_ini(cfg)
            mirror_ini_to_user_config_folder(cfg)
        except Exception as exc:
            if on_done:
                on_done(False, f"Falha ao gravar GameUserSettings.ini: {exc}")
            return

        from ..ark_server_files import write_allowed_cheater_steam_ids_safe
        write_allowed_cheater_steam_ids_safe(cfg.install_dir, list(cfg.admin_ids or []))

        if inst.status == ASM_STATUS_STOPPED and self.try_reconnect_server(cfg):
            if on_done:
                on_done(
                    True,
                    "Servidor já em execução — reconectado. "
                    "Reinicie o servidor para aplicar nome e configurações atualizados.",
                )
            return

        with self._lock:
            inst.status = ASM_STATUS_STARTING
            self._force_day_pending.add(cfg.id)

        if self._on_status:
            self._on_status(cfg.id, ASM_STATUS_STARTING)

        t = threading.Thread(target=self._start_worker, args=(cfg, inst, on_done), daemon=True)
        t.start()

    def _start_worker(self, cfg: AsmServerConfig, inst: AsmServerInstance,
                      on_done: Optional[Callable[[bool, str], None]]) -> None:
        try:
            # 0a. Remove pastas de mod na blacklist (ex.: Mek que causa crash)
            if cfg.install_dir:
                bl = (
                    self._get_mod_path_blacklist()
                    if self._get_mod_path_blacklist
                    else None
                )
                ModManager.purge_blacklisted_mod_paths(
                    cfg.install_dir,
                    bl,
                    on_log=self._on_log,
                )

            # 0b. Repara .mod antes do start (paridade modo primitivo)
            if cfg.install_dir:
                ModManager.ensure_mod_dot_files_before_start(
                    cfg.install_dir,
                    collect_mod_ids_for_install(cfg),
                )

            # 1. Escreve INIs (cfg é fonte de verdade; não copiar custom antes — evita rampa colapsada)
            write_ini(cfg)

            # 2. Monta comando como string (igual ao PRIMITIVE)
            exe = Path(cfg.install_dir) / "ShooterGame" / "Binaries" / "Win64" / cfg.server_exe
            args = build_launch_args(cfg)
            full_cmd = f'"{exe}" ' + " ".join(args)

            from ..ui_constants import active_event_launch_flag, normalize_active_event
            _evt = normalize_active_event(cfg.active_event)
            if _evt:
                _flag = active_event_launch_flag(_evt)
                self._on_log(
                    f"[{cfg.name}] ActiveEvent CLI: {_flag} "
                    f"(verifique em RunServer.cmd / process cmdline)",
                    "info",
                )
                if _flag and _flag not in full_cmd:
                    self._on_log(
                        f"[{cfg.name}] AVISO: {_flag} ausente na cmdline gerada — "
                        "evento sazonal pode não aplicar.",
                        "warning",
                    )

            # 3. Gera RunServer.cmd idêntico ao ASM SaveLauncher
            _CREATE_BREAKAWAY_FROM_JOB = 0x01000000
            _run_server_cmd_path: Optional[Path] = None
            try:
                _run_server_dir = (
                    Path(cfg.install_dir) / "ShooterGame" / "Saved" / "Config" / "WindowsServer"
                )
                _run_server_dir.mkdir(parents=True, exist_ok=True)
                _rsc = _run_server_dir / "RunServer.cmd"
                _win_title = (cfg.name or cfg.session_name or "ARK Server").replace('"', "'")
                _rsc.write_text(
                    f'start "{_win_title}" /min /normal {_escape_runserver_cmd_line(full_cmd)}\r\n',
                    encoding="utf-8",
                )
                _run_server_cmd_path = _rsc
            except Exception as _rsc_err:
                pass  # prossegue para Popen fallback

            proc: Any = None
            _startfile_called = False

            # 4. Lança via os.startfile() = ShellExecute (igual ao ASM)
            # Remove __COMPAT_LAYER antes do startfile para evitar que o shim
            # DetectorsAppHealth seja herdado pelo servidor e cause crash no
            # CheckOnTimerCallbacks do ArkApi.
            #
            # IMPORTANTE: NÃO reutilizamos processo pré-existente aqui.
            # O botão Start deve SEMPRE lançar um novo processo para garantir
            # que o GUS.ini recém-escrito seja lido pelo servidor. Reutilizar
            # um processo já em execução manteria o nome/config antigos.
            if _run_server_cmd_path is not None and _PSUTIL_OK:
                try:
                    _launch_time = datetime.now()
                    _compat_saved = os.environ.pop('__COMPAT_LAYER', None)
                    try:
                        os.startfile(str(_run_server_cmd_path))
                    finally:
                        if _compat_saved is not None:
                            os.environ['__COMPAT_LAYER'] = _compat_saved
                    _startfile_called = True
                    time.sleep(2)
                    _raw = _find_server_process(cfg.install_dir, _launch_time, timeout=20.0)
                    if _raw is not None:
                        proc = _PsutilProcessWrapper(_raw)
                except Exception:
                    proc = None

            # 5. Fallback: Popen direto (psutil indisponível ou startfile falhou)
            if proc is None and not _startfile_called:
                proc = subprocess.Popen(
                    full_cmd,
                    cwd=str(exe.parent),
                    creationflags=subprocess.CREATE_NEW_CONSOLE | _CREATE_BREAKAWAY_FROM_JOB,  # type: ignore[attr-defined]
                )

            with inst._lock:
                inst._proc = proc

            # 6. Considera online após 10 s sem crash
            for _ in range(24):
                time.sleep(5)
                if proc is not None and proc.poll() is not None:
                    with self._lock:
                        self._force_day_pending.discard(cfg.id)
                    inst.status = ASM_STATUS_CRASHED
                    self._stop_steam_watcher(cfg.id)
                    if self._on_status:
                        self._on_status(cfg.id, ASM_STATUS_CRASHED)
                    if on_done:
                        on_done(False, f"Processo terminou com código {proc.returncode}")
                    return
                if _ >= 2:
                    break

            inst.status = ASM_STATUS_RUNNING
            inst.uptime_start = time.time()
            if self._on_status:
                self._on_status(cfg.id, ASM_STATUS_RUNNING)
            if on_done:
                on_done(True, "Servidor iniciado com sucesso")

            # 7. Aplica affinity/prioridade se configurado
            self._apply_process_settings(cfg, proc)

            # 8. Inicia monitor de processo + listagem Steam/LAN
            self._start_monitor(inst)
            self._start_steam_watcher(inst)

        except Exception as exc:
            with self._lock:
                self._force_day_pending.discard(cfg.id)
            inst.status = ASM_STATUS_CRASHED
            self._stop_steam_watcher(cfg.id)
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
            pid  = proc.pid if proc is not None else None

            # taskkill /F /T encerra toda a árvore (filho criado por cmd.exe start)
            if pid:
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True,
                        timeout=15,
                    )
                except Exception:
                    pass

            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except Exception:
                    proc.kill()

            inst.status = ASM_STATUS_STOPPED
            inst._proc = None
            inst.uptime_start = None
            self._stop_steam_watcher(inst.cfg.id)
            if self._on_status:
                self._on_status(inst.cfg.id, ASM_STATUS_STOPPED)
            if on_done:
                on_done(True, "Servidor parado")
        except Exception as exc:
            inst.status = ASM_STATUS_STOPPED
            inst._proc = None
            inst.uptime_start = None
            self._stop_steam_watcher(inst.cfg.id)
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
                        inst.uptime_start = None
                        self._stop_steam_watcher(inst.cfg.id)
                        if self._on_status:
                            self._on_status(inst.cfg.id, ASM_STATUS_CRASHED)
                break

    def _start_steam_watcher(self, inst: AsmServerInstance) -> None:
        from ..server_visibility import get_steam_poller

        def _is_running() -> bool:
            return inst.status == ASM_STATUS_RUNNING

        get_steam_poller().register(
            inst.cfg.id,
            inst.cfg,
            inst,
            is_running=_is_running,
        )

    def _stop_steam_watcher(self, server_id: str) -> None:
        from ..server_visibility import get_steam_poller
        get_steam_poller().unregister(server_id)

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
