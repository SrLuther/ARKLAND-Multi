"""
Gerenciador de processos de servidores ARK: Survival Evolved.
Controla start/stop/restart, monitoramento e logs de cada instância.
"""
from __future__ import annotations

import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .server_config import (
    ServerConfig,
    SERVER_STATUS_STOPPED,
    SERVER_STATUS_STARTING,
    SERVER_STATUS_RUNNING,
    SERVER_STATUS_STOPPING,
    SERVER_STATUS_CRASHED,
)


# Linhas de log do ARK SE que indicam que o servidor terminou de inicializar
_ARK_READY_MARKERS = (
    "Full Startup",          # linha clássica no log: "Full Startup Time ..."
    "Server started",
    "BeginPlay",             # servidor entra no game loop
    "server has been listed online",
    "Networking initialized",
)
# Linha que indica registro bem-sucedido no Steam (acessível WAN)
_ARK_STEAM_MARKERS = (
    "OnCreateLobbyComplete",
    "Steam lobby created",
    "OnlineLobbyID",
    "bLANMatch=false",
    "STEAM: Search result",
)


class ServerInstance:
    """Representa o estado de execução de um servidor ARK."""

    def __init__(self, config: ServerConfig) -> None:
        self.config  = config
        self.status  = SERVER_STATUS_STOPPED
        self.process: Optional[subprocess.Popen] = None
        self.log_buffer: List[str] = []
        self.start_time: Optional[datetime] = None
        self.pid: Optional[int] = None
        self.online_mode: str = "—"   # "—" | "LAN" | "WAN"
        self._log_thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None

    @property
    def uptime(self) -> str:
        if not self.start_time or self.status != SERVER_STATUS_RUNNING:
            return "—"
        delta = datetime.now() - self.start_time
        h, rem = divmod(int(delta.total_seconds()), 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def push_log(self, line: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_buffer.append(f"[{ts}] {line}")
        if len(self.log_buffer) > 2000:
            self.log_buffer = self.log_buffer[-2000:]


class ServerManager:
    """
    Gerencia múltiplas instâncias de servidor ARK.
    Thread-safe para operações concorrentes.
    """

    def __init__(
        self,
        on_status_change: Optional[Callable[[str, str], None]] = None,
        on_log: Optional[Callable[[str, str, str], None]] = None,
        on_visibility_change: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self._instances: Dict[str, ServerInstance] = {}
        self._lock = threading.Lock()
        self._on_status_change   = on_status_change   or (lambda server_id, status: None)
        self._on_log             = on_log             or (lambda server_id, msg, level: None)
        self._on_visibility_change = on_visibility_change or (lambda server_id, mode: None)

    # ── CRUD de instâncias ────────────────────────────────────────────────────

    def add_server(self, config: ServerConfig) -> None:
        with self._lock:
            self._instances[config.id] = ServerInstance(config)

    def remove_server(self, server_id: str) -> None:
        self.stop_server(server_id, force=True)
        with self._lock:
            self._instances.pop(server_id, None)

    def update_server_config(self, config: ServerConfig) -> None:
        with self._lock:
            if config.id in self._instances:
                inst = self._instances[config.id]
                if inst.status == SERVER_STATUS_STOPPED:
                    inst.config = config
            else:
                self._instances[config.id] = ServerInstance(config)

    def get_instance(self, server_id: str) -> Optional[ServerInstance]:
        return self._instances.get(server_id)

    def get_all_instances(self) -> List[ServerInstance]:
        return list(self._instances.values())

    # ── Controle de servidores ────────────────────────────────────────────────

    def start_server(self, server_id: str) -> bool:
        """Inicia o servidor. Retorna False se já rodando ou erro."""
        inst = self._instances.get(server_id)
        if not inst:
            return False
        if inst.status in (SERVER_STATUS_RUNNING, SERVER_STATUS_STARTING):
            return False

        cfg = inst.config
        if not cfg.install_dir:
            self._emit_log(server_id, "Diretório de instalação não configurado.", "error")
            return False

        exe_path = Path(cfg.install_dir) / "ShooterGame" / "Binaries" / "Win64" / cfg.server_exe
        if not exe_path.exists():
            exe_path = Path(cfg.install_dir) / cfg.server_exe
        if not exe_path.exists():
            self._emit_log(server_id, f"Executável não encontrado: {exe_path}", "error")
            return False

        self._set_status(server_id, SERVER_STATUS_STARTING)

        thread = threading.Thread(
            target=self._start_worker,
            args=(server_id, str(exe_path)),
            daemon=True,
            name=f"ARKServer-{cfg.name}",
        )
        thread.start()
        return True

    def stop_server(self, server_id: str, force: bool = False) -> bool:
        """Para o servidor graciosamente (RCON SaveWorld + Exit) ou forçado."""
        inst = self._instances.get(server_id)
        if not inst or inst.status == SERVER_STATUS_STOPPED:
            return False

        self._set_status(server_id, SERVER_STATUS_STOPPING)

        if not force and inst.config.rcon_enabled and inst.config.rcon_password:
            self._graceful_shutdown(server_id)

        thread = threading.Thread(
            target=self._stop_worker,
            args=(server_id,),
            daemon=True,
            name=f"ARKStop-{server_id}",
        )
        thread.start()
        return True

    def restart_server(self, server_id: str) -> None:
        """Para e reinicia o servidor."""
        def _do():
            self.stop_server(server_id)
            # Aguarda parar
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                inst = self._instances.get(server_id)
                if inst and inst.status == SERVER_STATUS_STOPPED:
                    break
                time.sleep(1)
            time.sleep(2)
            self.start_server(server_id)

        threading.Thread(target=_do, daemon=True, name=f"ARKRestart-{server_id}").start()

    # ── Workers internos ──────────────────────────────────────────────────────

    def _start_worker(self, server_id: str, exe_path: str) -> None:
        inst = self._instances.get(server_id)
        if not inst:
            return

        cfg = inst.config
        # Monta linha de comando
        launch_str = cfg.build_launch_args()
        # Substitui o placeholder do executável pelo caminho real
        full_cmd = launch_str.replace(f'"{cfg.server_exe}"', f'"{exe_path}"', 1)

        self._emit_log(server_id, f"Iniciando: {full_cmd}", "info")

        try:
            proc = subprocess.Popen(
                full_cmd,
                cwd=str(Path(exe_path).parent),
                # ARK abre janela própria — não capturamos stdout
            )
            inst.process    = proc
            inst.pid        = proc.pid
            inst.start_time = datetime.now()
            inst.online_mode = "—"
            # Status permanece STARTING — será promovido para RUNNING
            # pelo watchdog que monitora o arquivo de log do ARK
            self._emit_log(server_id, f"Processo iniciado (PID {proc.pid}). Aguardando inicialização...", "info")

            # Thread que monitora o arquivo de log do ARK e tem fallback por timeout
            log_thread = threading.Thread(
                target=self._watch_ark_log,
                args=(server_id, proc, Path(exe_path)),
                daemon=True,
            )
            log_thread.start()
            inst._log_thread = log_thread

            # Aguarda o processo terminar
            proc.wait()

            if inst.status == SERVER_STATUS_RUNNING:
                self._emit_log(server_id, f"Servidor encerrou inesperadamente (código {proc.returncode}).", "warning")
                self._set_status(server_id, SERVER_STATUS_CRASHED)
                inst.process = None
                inst.pid = None

                # Auto-restart se configurado
                if cfg.auto_restart_on_crash:
                    self._emit_log(server_id, "Auto-restart configurado. Reiniciando em 30s...", "info")
                    time.sleep(30)
                    if inst.status == SERVER_STATUS_CRASHED:
                        self.start_server(server_id)

        except Exception as exc:
            self._emit_log(server_id, f"Erro ao iniciar servidor: {exc}", "error")
            self._set_status(server_id, SERVER_STATUS_STOPPED)

    def _stop_worker(self, server_id: str) -> None:
        inst = self._instances.get(server_id)
        if not inst:
            return

        proc = inst.process
        if proc and proc.poll() is None:
            try:
                # Aguarda encerramento gracioso
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline and proc.poll() is None:
                    time.sleep(1)

                if proc.poll() is None:
                    self._emit_log(server_id, "Forçando encerramento (kill)...", "warning")
                    proc.kill()
                    proc.wait()
            except Exception as exc:
                self._emit_log(server_id, f"Erro ao parar servidor: {exc}", "error")

        inst.process = None
        inst.pid = None
        inst.online_mode = "—"
        self._on_visibility_change(server_id, "—")
        self._set_status(server_id, SERVER_STATUS_STOPPED)
        self._emit_log(server_id, "Servidor parado.", "info")

    def _graceful_shutdown(self, server_id: str) -> None:
        """Envia SaveWorld e DoExit via RCON antes de matar o processo."""
        from .rcon_client import RconClient, RconError
        inst = self._instances.get(server_id)
        if not inst:
            return
        cfg = inst.config
        try:
            rcon_host = getattr(cfg, "bind_ip", None) or "127.0.0.1"
            rcon = RconClient(rcon_host, cfg.rcon_port, cfg.rcon_password)
            rcon.connect()
            rcon.send_command("SaveWorld")
            time.sleep(2)
            rcon.send_command("DoExit")
            rcon.disconnect()
            self._emit_log(server_id, "Shutdown enviado via RCON.", "info")
        except RconError as e:
            self._emit_log(server_id, f"Não foi possível enviar shutdown via RCON: {e}", "warning")

    def _watch_ark_log(self, server_id: str, proc: subprocess.Popen, exe_path: Path) -> None:
        """
        Monitora o arquivo de log do ARK (ShooterGame/Saved/Logs/ShooterGame.log)
        em busca dos marcadores de pronto e WAN.
        Fallback: se o arquivo não existir ou não contiver marcadores em
        _STARTING_TIMEOUT segundos, promove para RUNNING automaticamente
        (servidor pode estar rodando mas log inacessível).
        """
        _STARTING_TIMEOUT = 15 * 60   # 15 minutos máximo esperando
        _POLL_INTERVAL    = 3          # segundos entre leituras

        # Caminho do log: dois níveis acima do Win64/ → ShooterGame/Saved/Logs/
        # exe_path = .../ShooterGame/Binaries/Win64/ShooterGameServer.exe
        try:
            log_file = exe_path.parents[2] / "Saved" / "Logs" / "ShooterGame.log"
        except Exception:
            log_file = None

        start = time.monotonic()
        last_size = 0
        found_ready = False

        while True:
            inst = self._instances.get(server_id)
            if not inst or inst.status not in (SERVER_STATUS_STARTING,):
                break

            # Processo morreu antes de ficar pronto
            if proc.poll() is not None:
                if inst.status == SERVER_STATUS_STARTING:
                    self._set_status(server_id, SERVER_STATUS_CRASHED)
                    self._emit_log(server_id, f"Processo encerrou antes de inicializar (código {proc.returncode}).", "error")
                break

            # ── Lê novas linhas do arquivo de log ────────────────────────────
            if log_file and log_file.exists():
                try:
                    size = log_file.stat().st_size
                    if size < last_size:
                        last_size = 0  # arquivo rotacionado/truncado
                    if size > last_size:
                        with open(log_file, "r", encoding="utf-8", errors="replace") as fh:
                            fh.seek(last_size)
                            new_lines = fh.read()
                        last_size = size

                        for line in new_lines.splitlines():
                            if not line.strip():
                                continue
                            inst.push_log(line)
                            self._emit_log(server_id, line, "debug")

                            if not found_ready and inst.status == SERVER_STATUS_STARTING:
                                if any(m.lower() in line.lower() for m in _ARK_READY_MARKERS):
                                    found_ready = True
                                    self._set_status(server_id, SERVER_STATUS_RUNNING)
                                    self._emit_log(server_id, "Servidor inicializado e aceitando conexões.", "info")
                                    inst.online_mode = "LAN"
                                    self._on_visibility_change(server_id, "LAN")

                            if inst.status == SERVER_STATUS_RUNNING and inst.online_mode == "—":
                                if any(m.lower() in line.lower() for m in _ARK_STEAM_MARKERS):
                                    inst.online_mode = "WAN"
                                    self._on_visibility_change(server_id, "WAN")
                                    self._emit_log(server_id, "Servidor visível publicamente (WAN/Steam).", "info")

                        if found_ready:
                            # Continua lendo para WAN, mas não precisa mais verificar timeout
                            pass
                except Exception:
                    pass

            # ── Fallback por timeout ─────────────────────────────────────────
            elapsed = time.monotonic() - start
            if not found_ready and elapsed >= _STARTING_TIMEOUT:
                inst2 = self._instances.get(server_id)
                if inst2 and inst2.status == SERVER_STATUS_STARTING and proc.poll() is None:
                    self._set_status(server_id, SERVER_STATUS_RUNNING)
                    inst2.online_mode = "LAN"
                    self._on_visibility_change(server_id, "LAN")
                    self._emit_log(
                        server_id,
                        f"Timeout de {_STARTING_TIMEOUT // 60} min atingido — servidor considerado RODANDO "
                        f"(processo ativo, sem marcadores de log detectados).",
                        "warning",
                    )
                break

            time.sleep(_POLL_INTERVAL)

        # Depois de RUNNING, continua lendo o log para WAN e para logs do usuário
        if log_file:
            self._tail_ark_log(server_id, proc, log_file, last_size)

    def _tail_ark_log(self, server_id: str, proc: subprocess.Popen, log_file: Path, offset: int) -> None:
        """Continua lendo o arquivo de log do ARK após o servidor estar RODANDO."""
        _POLL_INTERVAL = 3
        last_size = offset
        while True:
            inst = self._instances.get(server_id)
            if not inst or inst.status not in (SERVER_STATUS_RUNNING,):
                break
            if proc.poll() is not None:
                break
            try:
                if log_file.exists():
                    size = log_file.stat().st_size
                    if size < last_size:
                        last_size = 0  # arquivo rotacionado/truncado
                    if size > last_size:
                        with open(log_file, "r", encoding="utf-8", errors="replace") as fh:
                            fh.seek(last_size)
                            new_lines = fh.read()
                        last_size = size
                        for line in new_lines.splitlines():
                            if not line.strip():
                                continue
                            inst.push_log(line)
                            self._emit_log(server_id, line, "debug")
                            if inst.online_mode == "—":
                                if any(m.lower() in line.lower() for m in _ARK_STEAM_MARKERS):
                                    inst.online_mode = "WAN"
                                    self._on_visibility_change(server_id, "WAN")
                                    self._emit_log(server_id, "Servidor visível publicamente (WAN/Steam).", "info")
            except Exception:
                pass
            time.sleep(_POLL_INTERVAL)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, server_id: str, status: str) -> None:
        inst = self._instances.get(server_id)
        if inst:
            inst.status = status
        self._on_status_change(server_id, status)

    def _emit_log(self, server_id: str, msg: str, level: str = "info") -> None:
        inst = self._instances.get(server_id)
        if inst:
            inst.push_log(msg)
        self._on_log(server_id, msg, level)

    # ── Status ────────────────────────────────────────────────────────────────

    def is_server_running(self, server_id: str) -> bool:
        inst = self._instances.get(server_id)
        if not inst or not inst.process:
            return False
        return inst.process.poll() is None
