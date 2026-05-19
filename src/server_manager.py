"""
Gerenciador de processos de servidores ARK: Survival Evolved.
Controla start/stop/restart, monitoramento e logs de cada instância.
"""
from __future__ import annotations

import subprocess
import threading
import time
from datetime import datetime, date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

try:
    import psutil as _psutil  # type: ignore[import-untyped]
    _PSUTIL_OK = True
except ImportError:
    _psutil = None  # type: ignore[assignment]
    _PSUTIL_OK = False

from .server_config import (
    ServerConfig,
    SERVER_STATUS_STOPPED,
    SERVER_STATUS_STARTING,
    SERVER_STATUS_RUNNING,
    SERVER_STATUS_STOPPING,
    SERVER_STATUS_CRASHED,
)
from .battlemetrics_client import BattleMetricsPoller, BattleMetricsData


# Linhas de log do ARK SE que indicam que o servidor terminou de inicializar
# NOTA: Estes marcadores aparecem no ShooterGame.log, não no console do ArkAPI.
# O ArkAPI carrega plugins em ~60s mas o mundo leva 10-15 min para carregar.
_ARK_READY_MARKERS = (
    "Full Startup",              # "Full Startup: X.XX seconds" — marcador definitivo
    "server has been listed online",
    "GameMode BeginPlay",
    "Beacon has completed",
    "LogWorld: Bringing World",
    "World loaded",
    "All levels loaded",
)
# Marcadores que indicam INÍCIO do carregamento (não pronto ainda — apenas log)
_ARK_LOADING_MARKERS = (
    "[API][info] Loaded all plugins",  # ArkAPI: plugins carregados, mundo ainda não
    "Initialized hooks",               # ArkAPI: hooks inicializados
    "API was successfully loaded",     # ArkAPI: API pronta
    "BeginPlay",
    "Networking initialized",
    "Game Engine Initialized",
    "Set New", "Set Summer", "Set Fear", "Set Winter",
    "Set Turkey", "Set Easter", "Set Love", "Set Anniversary",
)
# Linha que indica registro bem-sucedido no Steam (acessível WAN)
_ARK_STEAM_MARKERS = (
    "OnCreateLobbyComplete",
    "Steam lobby created",
    "OnlineLobbyID",
    "bLANMatch=false",
    "STEAM: Search result",
)

# DLLs/módulos do engine que NÃO são candidatos a "culpado" em crash
_ENGINE_DLL_PREFIXES = (
    "shootergameserver",
    "kernel32",
    "ntdll",
    "msvcrt",
    "vcruntime",
    "d3d",
    "opengl32",
    "dxgi",
    "ue4",
    "steamapi",
    "steamclient",
    "tier0",
    "vstdlib",
)


def _identify_crash_culprit(crash_text: str) -> str:
    """Retorna o primeiro DLL não-engine encontrado no call stack do crash."""
    import re
    for line in crash_text.splitlines():
        m = re.search(r'([\w\-]+\.dll)', line, re.IGNORECASE)
        if m:
            dll = m.group(1).lower()
            if not any(dll.startswith(p) for p in _ENGINE_DLL_PREFIXES):
                return m.group(1)
    return ""


def _read_crash_info(install_dir: str) -> str:
    """Lê arquivos de crash do ARK e retorna um resumo diagnóstico.

    Examina:
    - ShooterGame/Saved/Crashes/<mais_recente>/   (CrashContext, .dmp)
    - ShooterGame/Saved/Logs/ShooterGame.log      (tail com Fatal error!)
    """
    import re

    base = Path(install_dir)
    parts: list[str] = []

    # ── 1. Pasta de crash mais recente ────────────────────────────────────
    crash_base = base / "ShooterGame" / "Saved" / "Crashes"
    crash_dir: Optional[Path] = None
    if crash_base.exists():
        try:
            subdirs = [d for d in crash_base.iterdir() if d.is_dir()]
            if subdirs:
                crash_dir = max(subdirs, key=lambda d: d.stat().st_mtime)
        except Exception:
            pass

    if crash_dir:
        parts.append(f"Pasta de crash: {crash_dir.name}")

        # CrashContext.runtime-xml
        ctx_file = crash_dir / "CrashContext.runtime-xml"
        if ctx_file.exists():
            try:
                ctx = ctx_file.read_text(encoding="utf-8", errors="replace")
                for tag, label in (
                    ("ErrorMessage", "Erro"),
                    ("CallStack", None),
                ):
                    m = re.search(rf'<{tag}>(.*?)</{tag}>', ctx, re.DOTALL | re.IGNORECASE)
                    if m:
                        content = m.group(1).strip()
                        if tag == "CallStack":
                            stack_lines = [sl.strip() for sl in content.splitlines() if sl.strip()]
                            if stack_lines:
                                culprit = _identify_crash_culprit("\n".join(stack_lines[:15]))
                                if culprit:
                                    parts.append(f"** Possível causador: {culprit} **")
                                parts.append("Call Stack (CrashContext):")
                                for sl in stack_lines[:12]:
                                    parts.append(f"  {sl}")
                        else:
                            parts.append(f"{label}: {content[:200]}")
            except Exception:
                pass

        # .dmp
        try:
            dmp_files = sorted(crash_dir.glob("*.dmp"), key=lambda f: f.stat().st_size, reverse=True)
            if dmp_files:
                kb = dmp_files[0].stat().st_size // 1024
                parts.append(f"Dump gerado: {dmp_files[0].name} ({kb} KB) — em {crash_dir}")
        except Exception:
            pass

    # ── 2. Tail de ShooterGame.log ────────────────────────────────────────
    log_file = base / "ShooterGame" / "Saved" / "Logs" / "ShooterGame.log"
    # Fallback: cópia dentro da pasta de crash
    if not log_file.exists() and crash_dir:
        alt = crash_dir / "ShooterGame.log"
        if alt.exists():
            log_file = alt

    if log_file.exists():
        try:
            file_size = log_file.stat().st_size
            offset = max(0, file_size - 20480)  # últimos 20 KB
            with open(log_file, "rb") as fh:
                fh.seek(offset)
                tail = fh.read().decode("utf-8", errors="replace")

            # Última ocorrência de "Fatal error!" no log
            fatal_idx = tail.rfind("Fatal error!")
            if fatal_idx != -1:
                crash_section = tail[fatal_idx:]
                crash_lines = [cl for cl in crash_section.splitlines() if cl.strip()]

                culprit = _identify_crash_culprit(crash_section)
                if culprit and not any("Possível causador" in p for p in parts):
                    parts.append(f"** Possível causador: {culprit} **")

                parts.append("Log (Fatal error!):")
                for cl in crash_lines[:20]:
                    parts.append(f"  {cl.strip()}")
        except Exception:
            pass

    return "\n".join(parts)


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
        # BattleMetrics — dados da API pública (None = ainda não consultado ou sem BM ID)
        self.bm_online: Optional[bool] = None
        self.bm_players: Optional[int] = None
        self.bm_max_players: Optional[int] = None

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
        on_bm_update: Optional[Callable[[str], None]] = None,
        get_cluster_profile: Optional[Callable[[str], Optional[Any]]] = None,
        get_dynamic_config_url: Optional[Callable[[str], str]] = None,
        discord_notifier: Optional[Any] = None,
    ) -> None:
        self._instances: Dict[str, ServerInstance] = {}
        self._lock = threading.Lock()
        self._on_status_change   = on_status_change   or (lambda server_id, status: None)
        self._on_log             = on_log             or (lambda server_id, msg, level: None)
        self._on_visibility_change = on_visibility_change or (lambda server_id, mode: None)
        self._on_bm_update_cb    = on_bm_update       or (lambda server_id: None)
        self._get_cluster_profile: Optional[Callable[[str], Optional[Any]]] = get_cluster_profile
        self._get_dynamic_config_url: Optional[Callable[[str], str]] = get_dynamic_config_url
        self._discord_notifier   = discord_notifier

        # BattleMetrics poller
        self._bm_poller = BattleMetricsPoller(on_update=self._on_bm_update)
        self._bm_poller.start()

        # Scheduler de tarefas agendadas
        self._sched_fired: Dict[str, date] = {}   # chave: "{srv_id}::{task_idx}::{hhmm}"
        self._sched_warned: Dict[str, date] = {}  # idem, para avisos de warn_minutes
        self._sched_stop = threading.Event()
        self._sched_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True, name="ARKTaskScheduler"
        )
        self._sched_thread.start()

    # ── Scheduler de tarefas agendadas ────────────────────────────────────────

    def _scheduler_loop(self) -> None:
        while not self._sched_stop.is_set():
            try:
                self._scheduler_tick()
            except Exception:
                pass
            self._sched_stop.wait(30)

    def _scheduler_tick(self) -> None:
        from .rcon_client import RconClient
        now = datetime.now()
        today = now.date()
        hhmm = now.strftime("%H:%M")
        weekday = now.weekday()  # 0=Seg..6=Dom

        # Limpeza de entradas antigas (dias anteriores) para evitar crescimento indefinido
        for d in (self._sched_fired, self._sched_warned):
            stale = [k for k, v in d.items() if v < today]
            for k in stale:
                del d[k]

        with self._lock:
            instances = list(self._instances.values())

        for inst in instances:
            if inst.status not in (SERVER_STATUS_RUNNING, SERVER_STATUS_STARTING):
                continue
            cfg = inst.config
            for idx, task in enumerate(cfg.scheduled_tasks):
                if not task.get("enabled", True):
                    continue
                days = task.get("days", list(range(7)))
                if weekday not in days:
                    continue
                task_time = task.get("time", "")
                action    = task.get("action", "restart")
                warn_min  = int(task.get("warn_minutes", 0))

                # ── Aviso antecipado ──────────────────────────────────────
                if warn_min > 0:
                    try:
                        from datetime import timedelta
                        h, m = map(int, task_time.split(":"))
                        scheduled_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
                        warn_dt = scheduled_dt - timedelta(minutes=warn_min)
                        warn_hhmm = warn_dt.strftime("%H:%M")
                        warn_key = f"{cfg.id}::{idx}::warn::{warn_hhmm}"
                        if hhmm == warn_hhmm and self._sched_warned.get(warn_key) != today:
                            self._sched_warned[warn_key] = today
                            _labels = {"restart": "reiniciado", "stop": "desligado", "update_restart": "atualizado e reiniciado"}
                            self._sched_broadcast(cfg, f"⚠ Servidor será {_labels.get(action, action)} em {warn_min} minuto(s)!")
                    except Exception:
                        pass

                # ── Ação principal ────────────────────────────────────────
                if hhmm != task_time:
                    continue
                fire_key = f"{cfg.id}::{idx}::{hhmm}"
                if self._sched_fired.get(fire_key) == today:
                    continue
                self._sched_fired[fire_key] = today

                self._emit_log(cfg.id, f"[Agendador] Executando tarefa: {action} às {hhmm}", "info")
                server_id = cfg.id

                if action == "stop":
                    threading.Thread(target=self.stop_server, args=(server_id,), daemon=True).start()
                elif action == "restart":
                    threading.Thread(target=self.restart_server, args=(server_id,), daemon=True).start()
                elif action == "update_restart":
                    def _update_restart(sid=server_id):
                        self.stop_server(sid)
                        deadline = time.monotonic() + 120
                        while time.monotonic() < deadline:
                            with self._lock:
                                inst2 = self._instances.get(sid)
                            if inst2 and inst2.status == SERVER_STATUS_STOPPED:
                                break
                            time.sleep(2)
                        self.start_server(sid)
                    threading.Thread(target=_update_restart, daemon=True).start()

    def _sched_broadcast(self, cfg, message: str) -> None:
        from .rcon_client import RconClient
        if not cfg.rcon_enabled:
            return
        try:
            rcon = RconClient("127.0.0.1", cfg.rcon_port, cfg.rcon_password)
            rcon.connect()
            rcon.send_command(f"Broadcast {message[:900]}")
            rcon.disconnect()
        except Exception:
            pass

    def stop_scheduler(self) -> None:
        """Para o scheduler de tarefas agendadas."""
        self._sched_stop.set()

    # ── BattleMetrics ─────────────────────────────────────────────────────────

    def _bm_mapping(self) -> Dict[str, str]:
        """Retorna {server_id: battlemetrics_id} para todos os servidores configurados."""
        result: Dict[str, str] = {}
        with self._lock:
            for sid, inst in self._instances.items():
                bm_id = inst.config.battlemetrics_id
                if bm_id and bm_id.strip():
                    result[sid] = bm_id.strip()
        return result

    def _refresh_bm_poller(self) -> None:
        """Atualiza a lista de servidores monitorados pelo BattleMetrics poller."""
        self._bm_poller.set_servers(self._bm_mapping())

    def _on_bm_update(self, server_id: str, data: Optional[BattleMetricsData]) -> None:
        """Callback chamado pelo BattleMetricsPoller após cada consulta."""
        with self._lock:
            inst = self._instances.get(server_id)
            if not inst:
                return
            if data is not None:
                inst.bm_online = data.online
                inst.bm_players = data.players
                inst.bm_max_players = data.max_players
            else:
                inst.bm_online = None
                inst.bm_players = None
                inst.bm_max_players = None
        try:
            self._on_bm_update_cb(server_id)
        except Exception:
            pass

    # ── CRUD de instâncias ────────────────────────────────────────────────────

    def add_server(self, config: ServerConfig) -> None:
        with self._lock:
            self._instances[config.id] = ServerInstance(config)
        self._refresh_bm_poller()

    def remove_server(self, server_id: str) -> None:
        self.stop_server(server_id, force=True)
        with self._lock:
            self._instances.pop(server_id, None)
        self._refresh_bm_poller()

    def update_server_config(self, config: ServerConfig) -> None:
        with self._lock:
            if config.id in self._instances:
                inst = self._instances[config.id]
                if inst.status == SERVER_STATUS_STOPPED:
                    inst.config = config
            else:
                self._instances[config.id] = ServerInstance(config)
        self._refresh_bm_poller()

    def get_instance(self, server_id: str) -> Optional[ServerInstance]:
        return self._instances.get(server_id)

    def get_all_instances(self) -> List[ServerInstance]:
        return list(self._instances.values())

    # ── Reconexão de processos já em execução ─────────────────────────────────

    def scan_running_servers(self) -> int:
        """Varre processos em execução buscando ShooterGameServer.exe e reconecta
        instâncias configuradas cujo servidor já estava rodando (ex: após restart
        do app por atualização). A correspondência é feita pela porta TCP (-port=N).
        Retorna o número de instâncias reconectadas.
        """
        if not _PSUTIL_OK:
            return 0
        assert _psutil is not None

        reconnected = 0
        try:
            for proc in _psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
                try:
                    name = proc.info.get("name") or ""
                    if "ShooterGameServer" not in name:
                        continue
                    cmdline = " ".join(proc.info.get("cmdline") or []).lower()
                    pid = proc.info["pid"]
                    create_time = proc.info.get("create_time")

                    with self._lock:
                        for inst in self._instances.values():
                            if inst.status != SERVER_STATUS_STOPPED:
                                continue  # já tem processo associado
                            port_flag = f"-port={inst.config.server_port}"
                            if port_flag not in cmdline:
                                continue
                            # Reconecta: sem subprocess.Popen, mas com PID e monitor
                            inst.pid = pid
                            inst.process = None
                            inst.start_time = (
                                datetime.fromtimestamp(create_time)
                                if create_time else datetime.now()
                            )
                            inst.status = SERVER_STATUS_RUNNING
                            self._emit_log(
                                inst.config.id,
                                f"Servidor detectado em execução (PID {pid}). Reconectado.",
                                "info",
                            )
                            self._on_status_change(inst.config.id, SERVER_STATUS_RUNNING)
                            # Inicia monitor para detectar quando o processo morrer
                            threading.Thread(
                                target=self._reconnect_monitor,
                                args=(inst.config.id, pid),
                                daemon=True,
                                name=f"ARKReconnect-{inst.config.id}",
                            ).start()
                            reconnected += 1
                            break
                except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                    pass
        except Exception:
            pass
        if reconnected:
            self._refresh_bm_poller()
        return reconnected

    def _reconnect_monitor(self, server_id: str, pid: int) -> None:
        """Monitora um processo reconectado (sem subprocess.Popen).
        Atualiza o status para CRASHED/STOPPED quando o processo encerrar.
        """
        while True:
            time.sleep(5)
            with self._lock:
                inst = self._instances.get(server_id)
            if not inst or inst.status not in (SERVER_STATUS_RUNNING, SERVER_STATUS_STARTING):
                break
            # Verifica se o processo ainda existe
            alive = False
            try:
                if _PSUTIL_OK:
                    assert _psutil is not None
                    p = _psutil.Process(pid)
                    alive = p.is_running() and p.status() != _psutil.STATUS_ZOMBIE
            except Exception:
                alive = False
            if not alive:
                do_crash_action = False
                cfg = None
                with self._lock:
                    inst = self._instances.get(server_id)
                    if inst and inst.status == SERVER_STATUS_RUNNING:
                        inst.process = None
                        inst.pid = None
                        cfg = inst.config
                        do_crash_action = True
                if do_crash_action and cfg is not None:
                    if cfg.install_dir:
                        self._emit_crash_details(server_id, cfg.install_dir)
                    self._emit_log(
                        server_id,
                        f"Servidor encerrou (PID {pid} não encontrado).",
                        "warning",
                    )
                    self._set_status(server_id, SERVER_STATUS_CRASHED)
                    if cfg.auto_restart_on_crash:
                        self._emit_log(server_id, "Auto-restart configurado. Reiniciando em 30s...", "info")
                        time.sleep(30)
                        with self._lock:
                            inst = self._instances.get(server_id)
                        if inst and inst.status == SERVER_STATUS_CRASHED:
                            self.start_server(server_id)
                break

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

        thread = threading.Thread(
            target=self._stop_worker,
            args=(server_id, force),
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
                with self._lock:
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
        # Resolve perfil de cluster (se o servidor tiver um vínculo)
        cluster_profile = None
        if cfg.cluster_profile_id and self._get_cluster_profile:
            cluster_profile = self._get_cluster_profile(cfg.cluster_profile_id)
            if cluster_profile:
                self._emit_log(server_id, f"Usando perfil de cluster: {cluster_profile.name}", "info")
        # Resolve URL de config dinâmica (se habilitada)
        dynamic_url = ""
        if cfg.dynamic_config_enabled and self._get_dynamic_config_url:
            dynamic_url = self._get_dynamic_config_url(server_id)
            if dynamic_url:
                self._emit_log(server_id, f"Config dinâmica ativa: {dynamic_url}", "info")
        # Monta linha de comando
        launch_str = cfg.build_launch_args(cluster_profile=cluster_profile, dynamic_config_url=dynamic_url)
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

            # Afinidade de CPU (se configurado)
            if _PSUTIL_OK and cfg.cpu_core_count > 0:
                assert _psutil is not None
                try:
                    total = _psutil.cpu_count(logical=True) or 1
                    n = min(cfg.cpu_core_count, total)
                    _psutil.Process(proc.pid).cpu_affinity(list(range(n)))
                    self._emit_log(server_id, f"Afinidade de CPU definida: {n} núcleo(s).", "info")
                except Exception as e:
                    self._emit_log(server_id, f"Aviso: não foi possível definir afinidade de CPU: {e}", "warning")
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
                if cfg.install_dir:
                    self._emit_crash_details(server_id, cfg.install_dir)
                self._set_status(server_id, SERVER_STATUS_CRASHED)
                inst.process = None
                inst.pid = None

                # Auto-restart se configurado
                if cfg.auto_restart_on_crash:
                    self._emit_log(server_id, "Auto-restart configurado. Reiniciando em 30s...", "info")
                    time.sleep(30)
                    if inst.status == SERVER_STATUS_CRASHED:
                        self.start_server(server_id)
            else:
                # Processo encerrou durante STOPPING/STARTING — limpa referências
                # (_stop_worker definirá STOPPED; aqui só garantimos limpeza)
                inst.process = None
                inst.pid = None

        except Exception as exc:
            self._emit_log(server_id, f"Erro ao iniciar servidor: {exc}", "error")
            self._set_status(server_id, SERVER_STATUS_STOPPED)

    def _stop_worker(self, server_id: str, force: bool = False) -> None:
        inst = self._instances.get(server_id)
        if not inst:
            return

        proc = inst.process
        pid  = inst.pid

        # ── 1. Graceful shutdown via RCON (só se não for force e processo vivo) ──
        if not force and proc and proc.poll() is None:
            if inst.config.rcon_enabled and inst.config.rcon_password:
                self._graceful_shutdown(server_id)
            # Aguarda encerramento gracioso (90 s — suficiente para salvar mapa grande)
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline and proc.poll() is None:
                time.sleep(1)

        # ── 2. taskkill /F /T mata toda a árvore de processos (Windows) ─────────
        #    ShooterGameServer.exe cria processos filhos que proc.terminate()
        #    não alcança. taskkill com /T encerra os filhos também.
        if pid:
            self._emit_log(server_id, f"Encerrando árvore de processos (PID {pid})...", "warning")
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    timeout=15,
                )
            except Exception:
                pass

        # ── 3. terminate() como fallback (não-Windows ou taskkill falhou) ────
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
            except Exception:
                pass

        # ── 4. kill() forçado ────────────────────────────────────────────────
        if proc and proc.poll() is None:
            self._emit_log(server_id, "Forçando encerramento (kill)...", "warning")
            try:
                proc.kill()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
            except Exception:
                pass

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
            time.sleep(15)  # aguarda o servidor concluir o salvamento do mundo e perfis
            rcon.send_command("DoExit")
            rcon.disconnect()
            self._emit_log(server_id, "Shutdown enviado via RCON.", "info")
        except RconError as e:
            self._emit_log(server_id, f"Não foi possível enviar shutdown via RCON: {e}", "warning")

    def _watch_ark_log(self, server_id: str, proc: subprocess.Popen, exe_path: Path) -> None:
        """
        Monitora o arquivo de log do ARK (ShooterGame/Saved/Logs/ShooterGame.log)
        em busca dos marcadores de pronto e WAN.
        Fallback 1: sonda RCON a cada 30s (após 60s) — se conectar, promove para RUNNING.
        Fallback 2: timeout de 45 min — promove automaticamente se processo ativo.
        """
        _STARTING_TIMEOUT  = 45 * 60   # 45 minutos máximo esperando
        _POLL_INTERVAL     = 3          # segundos entre leituras
        # RCON fica disponível cedo (ArkAPI hooks ~60s) mas o mundo leva 10-15 min.
        # Só usamos RCON como fallback se nenhum marcador de log for encontrado.
        _RCON_FIRST_CHECK  = 10 * 60   # aguarda 10 min antes da 1ª sonda RCON
        _RCON_CHECK_EVERY  = 60        # sonda RCON a cada 60s

        # Caminho do log: dois níveis acima do Win64/ → ShooterGame/Saved/Logs/
        # exe_path = .../ShooterGame/Binaries/Win64/ShooterGameServer.exe
        # Mas se o exe estiver diretamente em install_dir, parents[2] ficaria errado;
        # por isso tentamos o caminho canônico primeiro.
        log_file_candidates = []
        try:
            log_file_candidates.append(exe_path.parents[2] / "Saved" / "Logs" / "ShooterGame.log")
        except Exception:
            pass
        # Fallback: tenta subir só 1 nível (install_dir/ShooterGame/...)
        try:
            log_file_candidates.append(exe_path.parent / "ShooterGame" / "Saved" / "Logs" / "ShooterGame.log")
        except Exception:
            pass
        log_file: Optional[Path] = None
        for cand in log_file_candidates:
            if cand.exists():
                log_file = cand
                break

        start = time.monotonic()
        last_size = 0
        found_ready = False
        last_rcon_check = start

        # Começa lendo só as linhas novas (ignora o conteúdo pré-existente do log)
        if log_file and log_file.exists():
            try:
                last_size = log_file.stat().st_size
            except Exception:
                last_size = 0

        # Se o log ainda não existe, tenta descobrir o caminho depois
        if log_file is None:
            self._emit_log(server_id, "Arquivo de log do ARK não encontrado ainda. Aguardando...", "debug")

        while True:
            inst = self._instances.get(server_id)
            if not inst or inst.status not in (SERVER_STATUS_STARTING,):
                break

            # Processo morreu antes de ficar pronto
            if proc.poll() is not None:
                if inst.status == SERVER_STATUS_STARTING:
                    self._set_status(server_id, SERVER_STATUS_CRASHED)
                    self._emit_log(server_id, f"Processo encerrou antes de inicializar (código {proc.returncode}).", "error")
                    cfg2 = inst.config
                    if cfg2.install_dir:
                        self._emit_crash_details(server_id, cfg2.install_dir)
                break

            # ── Tenta descobrir o log_file se ainda não encontrado ────────────
            if log_file is None:
                for cand in log_file_candidates:
                    if cand.exists():
                        log_file = cand
                        self._emit_log(server_id, f"Log detectado: {log_file}", "debug")
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
                                # Avisa que ArkAPI carregou mas mundo ainda não está pronto
                                if any(m.lower() in line.lower() for m in _ARK_LOADING_MARKERS):
                                    self._emit_log(
                                        server_id,
                                        "[ARKLAND] Engine/ArkAPI inicializados — aguardando carregamento do mundo...",
                                        "info",
                                    )
                                if any(m.lower() in line.lower() for m in _ARK_READY_MARKERS):
                                    found_ready = True
                                    self._set_status(server_id, SERVER_STATUS_RUNNING)
                                    self._emit_log(server_id, "Servidor inicializado e aceitando conexões.", "info")
                                    _init_mode = "LAN" if self._is_lan_only(inst.config) else "WAN"
                                    inst.online_mode = _init_mode
                                    self._on_visibility_change(server_id, _init_mode)

                            if inst.status == SERVER_STATUS_RUNNING and inst.online_mode != "WAN":
                                if any(m.lower() in line.lower() for m in _ARK_STEAM_MARKERS):
                                    inst.online_mode = "WAN"
                                    self._on_visibility_change(server_id, "WAN")
                                    self._emit_log(server_id, "Servidor visível publicamente (WAN/Steam).", "info")
                except Exception:
                    pass

            # ── Fallback RCON: sonda a cada 30s após 60s de espera ────────────
            if not found_ready and inst.status == SERVER_STATUS_STARTING:
                elapsed = time.monotonic() - start
                since_last = time.monotonic() - last_rcon_check
                cfg = inst.config
                if (elapsed >= _RCON_FIRST_CHECK
                        and since_last >= _RCON_CHECK_EVERY
                        and cfg.rcon_enabled
                        and cfg.rcon_password):
                    last_rcon_check = time.monotonic()
                    try:
                        from .rcon_client import RconClient, RconError  # noqa: F401
                        _rcon = RconClient("127.0.0.1", cfg.rcon_port, cfg.rcon_password)
                        _rcon.connect()
                        _rcon.disconnect()
                        found_ready = True
                        self._set_status(server_id, SERVER_STATUS_RUNNING)
                        elapsed_min = int((time.monotonic() - start) / 60)
                        self._emit_log(
                            server_id,
                            f"Servidor marcado como rodando via RCON (fallback após {elapsed_min} min — "
                            f"marcadores de log não detectados; mundo pode estar carregando).",
                            "warning",
                        )
                        _init_mode = "LAN" if self._is_lan_only(inst.config) else "WAN"
                        inst.online_mode = _init_mode
                        self._on_visibility_change(server_id, _init_mode)
                    except Exception:
                        pass  # RCON ainda não disponível — continua aguardando

            # ── Fallback por timeout ─────────────────────────────────────────
            elapsed = time.monotonic() - start
            if not found_ready and elapsed >= _STARTING_TIMEOUT:
                inst2 = self._instances.get(server_id)
                if inst2 and inst2.status == SERVER_STATUS_STARTING and proc.poll() is None:
                    self._set_status(server_id, SERVER_STATUS_RUNNING)
                    _init_mode = "LAN" if self._is_lan_only(inst2.config) else "WAN"
                    inst2.online_mode = _init_mode
                    self._on_visibility_change(server_id, _init_mode)
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
                            if inst.online_mode != "WAN":
                                if any(m.lower() in line.lower() for m in _ARK_STEAM_MARKERS):
                                    inst.online_mode = "WAN"
                                    self._on_visibility_change(server_id, "WAN")
                                    self._emit_log(server_id, "Servidor visível publicamente (WAN/Steam).", "info")
            except Exception:
                pass
            time.sleep(_POLL_INTERVAL)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _is_lan_only(cfg: ServerConfig) -> bool:
        """Retorna True se o servidor foi configurado explicitamente como LAN.
        Um servidor ARK é LAN apenas quando ``?bIsLanMatch=True`` é passado
        nos argumentos de lançamento; caso contrário ele se registra no Steam
        automaticamente (WAN).
        """
        combined = (cfg.extra_args or "").lower()
        if "bislanmatch=true" in combined:
            return True
        # Verifica também nos params de mapa/URL gerados por build_launch_args
        try:
            full_cmd = cfg.build_launch_args().lower()
            return "bislanmatch=true" in full_cmd
        except Exception:
            return False

    def _set_status(self, server_id: str, status: str) -> None:
        inst = self._instances.get(server_id)
        if inst:
            inst.status = status
        self._on_status_change(server_id, status)
        if self._discord_notifier and inst:
            detail_parts = []
            if inst.config.map:
                detail_parts.append(f"🗺  {inst.config.map}")
            if inst.config.server_port:
                detail_parts.append(f"🔌  Porta: {inst.config.server_port}")
            self._discord_notifier.notify_status(
                inst.config.name or server_id, status,
                detail="\n".join(detail_parts),
            )

    def _emit_log(self, server_id: str, msg: str, level: str = "info") -> None:
        inst = self._instances.get(server_id)
        if inst:
            inst.push_log(msg)
        self._on_log(server_id, msg, level)

    def _emit_crash_details(self, server_id: str, install_dir: str) -> None:
        """Lê arquivos de crash do ARK e emite as informações diagnósticas nos logs."""
        try:
            time.sleep(1.5)  # aguarda o ARK terminar de gravar os arquivos de crash
            info = _read_crash_info(install_dir)
            if info:
                self._emit_log(server_id, "─── Diagnóstico de Crash ───────────────────────────────", "error")
                for line in info.splitlines():
                    level = "error" if line.startswith("**") else "warning"
                    self._emit_log(server_id, line, level)
                self._emit_log(server_id, "────────────────────────────────────────────────────────", "error")
        except Exception as exc:
            self._emit_log(server_id, f"Não foi possível ler arquivos de crash: {exc}", "debug")

    # ── Status ────────────────────────────────────────────────────────────────

    def is_server_running(self, server_id: str) -> bool:
        inst = self._instances.get(server_id)
        if not inst or not inst.process:
            return False
        return inst.process.poll() is None
