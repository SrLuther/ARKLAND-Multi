"""
AsmServerManager — gerenciador de processos TEK.
Controla start/stop/restart e monitora o status de cada servidor ASM.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# ── psutil (opcional) ─────────────────────────────────────────────────────────
try:
    import psutil as _psutil  # type: ignore[reportMissingImports]
    _PSUTIL_OK = True
except ImportError:
    _psutil = None  # type: ignore[assignment]
    _PSUTIL_OK = False

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


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
        """None = ainda vivo. Não tratar AccessDenied como morte (bug pós-reconnect)."""
        try:
            running = bool(self._proc.is_running())
        except Exception as exc:
            if type(exc).__name__ == "NoSuchProcess":
                if self.returncode is None:
                    self.returncode = -1
                return self.returncode
            # AccessDenied / permissões: processo provavelmente ainda existe
            return None
        if not running:
            if self.returncode is None:
                self.returncode = -1
            return self.returncode
        try:
            if self._proc.status() == "zombie":
                if self.returncode is None:
                    self.returncode = -1
                return self.returncode
        except Exception:
            pass
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

    Baseline v1.10.36: substring simples no exe (sem gate de boundary).
    """
    if not _PSUTIL_OK or _psutil is None:
        return None
    install_norm = (install_dir or "").replace("\\", "/").lower()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            for p in _psutil.process_iter(["pid", "name", "exe", "create_time"]):
                try:
                    name = p.info.get("name") or ""
                    if "shootergameserver" not in name.lower():
                        continue
                    exe = (p.info.get("exe") or "").replace("\\", "/").lower()
                    if install_norm and install_norm not in exe:
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
    """Normaliza pasta de instalação para comparação substring (baseline 1.10.36).

    Também colapsa barras repetidas (`D:\\\\ARK` → `d:/ark`) — configs Windows
    por vezes guardam backslash escapado a mais.
    """
    p = (path or "").replace("\\", "/").lower()
    while "//" in p:
        p = p.replace("//", "/")
    return p.rstrip("/")


def _slash_fold(text: str) -> str:
    p = (text or "").replace("\\", "/").lower()
    while "//" in p:
        p = p.replace("//", "/")
    return p


def _port_token_in_cmdline(cmdline: str, keys: tuple[str, ...], port: int) -> bool:
    """Substring estilo v1.10.36, com guarda para não casar prefixo (777 ⊂ 7777)."""
    if not cmdline or not port:
        return False
    needle_num = str(int(port))
    cl = cmdline.lower()
    for key in keys:
        token = f"{key}{needle_num}"
        start = 0
        while True:
            idx = cl.find(token, start)
            if idx < 0:
                break
            after = idx + len(token)
            if after >= len(cl) or not cl[after].isdigit():
                return True
            start = idx + 1
    return False


def _cmdline_matches_server(cmdline: str, cfg: "AsmServerConfig") -> bool:
    """True se a CLI pertence ao servidor.

    Baseline v1.10.36: ?Port= / -port=. Aditivo seguro: QueryPort nas mesmas formas.
    """
    if not cmdline:
        return False
    cl = cmdline.lower()
    if _port_token_in_cmdline(cl, ("?port=", "-port="), int(cfg.server_port or 0)):
        return True
    if _port_token_in_cmdline(cl, ("?queryport=", "-queryport="), int(cfg.query_port or 0)):
        return True
    return False


def _cfg_identity_ports(cfg: "AsmServerConfig") -> List[int]:
    ports: List[int] = []
    for raw in (getattr(cfg, "server_port", 0), getattr(cfg, "query_port", 0)):
        try:
            p = int(raw or 0)
        except (TypeError, ValueError):
            p = 0
        if p > 0:
            ports.append(p)
    if bool(getattr(cfg, "rcon_enabled", True)):
        try:
            rp = int(getattr(cfg, "rcon_port", 0) or 0)
        except (TypeError, ValueError):
            rp = 0
        if rp > 0:
            ports.append(rp)
    return ports


def _bound_ports_match_cfg(cfg: "AsmServerConfig", bound_ports: Set[int]) -> bool:
    if not bound_ports:
        return False
    return bool(set(_cfg_identity_ports(cfg)) & bound_ports)


def _window_title_matches(title: str, cfg: "AsmServerConfig") -> bool:
    t = (title or "").strip().lower()
    if not t:
        return False
    candidates = [
        getattr(cfg, "name", ""),
        getattr(cfg, "session_name", ""),
        getattr(cfg, "server_map", ""),
    ]
    install = (getattr(cfg, "install_dir", "") or "").strip()
    if install:
        try:
            candidates.append(Path(install).name)
        except Exception:
            pass
    for candidate in candidates:
        c = (candidate or "").strip().lower()
        if not c:
            continue
        # Pasta curta (AM/BR/CI): só igualdade — "am" ⊂ "steam" gerava falso positivo
        if len(c) <= 2:
            if t == c:
                return True
            continue
        if t == c or c in t or (len(c) >= 3 and t in c):
            return True
    return False


def _expected_shooter_exe(cfg: "AsmServerConfig") -> str:
    """Caminho canónico: ``install_dir\\ShooterGame\\Binaries\\Win64\\ShooterGameServer.exe``."""
    install = (getattr(cfg, "install_dir", "") or "").strip()
    if not install:
        return ""
    exe_name = (getattr(cfg, "server_exe", "") or "ShooterGameServer.exe").strip()
    if not exe_name.lower().endswith(".exe"):
        exe_name = f"{exe_name}.exe"
    return _normalize_install_dir(
        str(Path(install) / "ShooterGame" / "Binaries" / "Win64" / exe_name)
    )


def _path_belongs_to_install(
    cfg: "AsmServerConfig",
    exe: str,
    cmdline: str = "",
) -> Optional[bool]:
    """Verifica se o processo pertence ao ``install_dir`` do mapa.

    Prefere o exe canónico Win64\\ShooterGameServer.exe sob install_dir.

    Returns:
      True  — exe (ou cmdline) sob install_dir / path canónico
      False — exe conhecido e NÃO está sob install_dir (outro mapa / helper)
      None  — impossível verificar (sem install_dir, ou exe vazio)
    """
    install_norm = _normalize_install_dir(getattr(cfg, "install_dir", "") or "")
    if not install_norm:
        return None
    exe_l = _slash_fold(exe)
    cmd_l = _slash_fold(cmdline)
    expected = _expected_shooter_exe(cfg)
    if expected and (exe_l == expected or exe_l.endswith(expected.split("/")[-1]) and install_norm in exe_l):
        if install_norm in exe_l:
            return True
    if install_norm in exe_l or install_norm in cmd_l:
        # Exige parecer Shooter quando o path é só a pasta do mapa
        if exe_l and not _looks_like_shooter("", exe_l, cmd_l):
            return False
        return True
    # Só rejeita com certeza quando o caminho do EXE é legível e aponta para fora.
    if exe_l:
        return False
    return None


def _clear_last_pid(server_id: str) -> None:
    try:
        last = _load_last_pids()
        if server_id in last:
            del last[server_id]
            _save_last_pids(last)
    except Exception:
        pass


# PIDs / imagens que NUNCA podem receber taskkill (tela preta / reboot)
_PROTECTED_PIDS = frozenset({0, 4})
_PROTECTED_IMAGES = frozenset({
    "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe", "lsass.exe",
    "smss.exe", "dwm.exe", "explorer.exe", "fontdrvhost.exe", "sihost.exe",
    "taskhostw.exe", "system", "registry", "secure system", "memory compression",
})


def _inspect_pid(pid: int) -> Dict[str, str]:
    """Melhor esforço: name/exe/cmdline de um PID (psutil + QueryFullProcessImageName)."""
    info = {"name": "", "exe": "", "cmdline": ""}
    if pid <= 0:
        return info
    if _PSUTIL_OK and _psutil is not None:
        try:
            raw = _psutil.Process(pid)
            try:
                info["name"] = (raw.name() or "").lower()
            except Exception:
                pass
            try:
                info["exe"] = _slash_fold(raw.exe() or "")
            except Exception:
                pass
            try:
                info["cmdline"] = _slash_fold(" ".join(raw.cmdline() or []))
            except Exception:
                pass
        except Exception:
            pass
    if not info["exe"]:
        img = _query_full_process_image_name(pid)
        if img:
            info["exe"] = img
    return info


def _looks_like_shooter(name: str, exe: str, cmdline: str = "") -> bool:
    blob = f"{name} {exe} {cmdline}".lower()
    return "shootergameserver" in blob


def _is_protected_process(pid: int, name: str, exe: str) -> bool:
    if pid in _PROTECTED_PIDS or pid < 10:
        return True
    n = (name or "").lower().strip()
    try:
        base = Path(exe).name.lower() if exe else ""
    except Exception:
        base = ""
    return n in _PROTECTED_IMAGES or base in _PROTECTED_IMAGES


def _pid_safe_to_kill(cfg: "AsmServerConfig", pid: int) -> bool:
    """True só se o PID for ShooterGameServer sob o install_dir deste mapa.

    Com install_dir configurado: exige path sob essa pasta (sem fallback de portas).
    Ghost / PID reciclado / outro mapa → False (Parar só limpa estado).
    """
    if not pid or pid <= 0:
        return False
    info = _inspect_pid(pid)
    name, exe, cmdline = info["name"], info["exe"], info["cmdline"]
    if _is_protected_process(pid, name, exe):
        return False
    if not _looks_like_shooter(name, exe, cmdline):
        return False
    install_norm = _normalize_install_dir(getattr(cfg, "install_dir", "") or "")
    belongs = _path_belongs_to_install(cfg, exe, cmdline)
    if install_norm:
        return belongs is True
    # Sem install_dir: só nome Shooter + portas (legado)
    if belongs is False:
        return False
    if belongs is True:
        return True
    if not _PSUTIL_OK or _psutil is None:
        return False
    try:
        ports = _cfg_identity_ports(cfg)
        if not ports:
            return False
        idx = _build_listening_port_index(set(ports))
        bound = _ports_for_pid(idx, pid)
        return _bound_ports_match_cfg(cfg, bound)
    except Exception:
        return False


def _query_full_process_image_name(pid: int) -> str:
    """Win32 QueryFullProcessImageNameW — quando psutil.exe() vem vazio."""
    if os.name != "nt" or pid <= 0:
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        OpenProcess = kernel32.OpenProcess
        OpenProcess.restype = wintypes.HANDLE
        OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
        QueryFullProcessImageNameW.restype = wintypes.BOOL
        CloseHandle = kernel32.CloseHandle

        handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return ""
        try:
            size = wintypes.DWORD(1024)
            buf = ctypes.create_unicode_buffer(size.value)
            ok = QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
            if not ok:
                return ""
            return _slash_fold(buf.value or "")
        finally:
            CloseHandle(handle)
    except Exception:
        return ""


def _last_pids_path() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager"
    return base / "asm_last_pids.json"


def _load_last_pids() -> Dict[str, int]:
    path = _last_pids_path()
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: Dict[str, int] = {}
    if isinstance(raw, dict):
        for sid, pid in raw.items():
            try:
                out[str(sid)] = int(pid)
            except (TypeError, ValueError):
                continue
    return out


def _save_last_pids(pids: Dict[str, int]) -> None:
    path = _last_pids_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(pids, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(path)
    except Exception:
        pass


# Pesos das estratégias (maior = mais confiável neste host .bug)
_STRAT_PORTS = 100
_STRAT_EXE = 80
_STRAT_IMAGE = 75
_STRAT_CMDLINE = 70
_STRAT_LAST_PID = 55
_STRAT_TITLE = 40


def _process_matches_cfg(
    cfg: "AsmServerConfig",
    exe: str,
    cmdline: str,
    install_dir_counts: Dict[str, int],
    bound_ports: Optional[Set[int]] = None,
    window_title: str = "",
) -> bool:
    """Baseline v1.10.36 + aditivos que NÃO substituem o path antigo.

    v1.10.36: ``install_norm in exe``; shared install exige ?Port=.
    Aditivos (só ampliam):
      - install_dir também na cmdline (exe vazio)
      - QueryPort na cmdline
      - portas bound / título só quando o path clássico não basta
    Removido de propósito: boundary `_path_contains_install` (v1.10.40).
    """
    install_norm = _normalize_install_dir(cfg.install_dir)
    exe_l = _slash_fold(exe)
    cmd_l = _slash_fold(cmdline)
    install_hit = bool(install_norm) and (
        install_norm in exe_l or install_norm in cmd_l
    )
    # Caminho conhecido de OUTRO mapa: nunca casar só por porta/título
    belongs = _path_belongs_to_install(cfg, exe, cmdline)
    if belongs is False:
        return False
    port_hit = _cmdline_matches_server(cmd_l, cfg)
    # Adjunct: só entra se clássico (cmdline port) falhou
    if not port_hit and bound_ports:
        port_hit = _bound_ports_match_cfg(cfg, bound_ports)
    title_hit = _window_title_matches(window_title, cfg)

    if install_hit:
        if install_dir_counts.get(install_norm, 0) > 1:
            return port_hit or title_hit
        return True
    return port_hit or title_hit


def _parse_netstat_line(line: str) -> Optional[tuple[int, int]]:
    """Extrai (porta, pid) de uma linha `netstat -ano`. None se irrelevante."""
    parts = (line or "").split()
    if len(parts) < 4:
        return None
    kind = parts[0].upper()
    if kind not in ("TCP", "UDP"):
        return None
    local = parts[1]
    if kind == "TCP":
        if len(parts) < 5:
            return None
        status = parts[3].upper()
        if "LISTEN" not in status:
            return None
        pid_s = parts[4]
    else:
        pid_s = parts[-1]
    try:
        pid = int(pid_s)
    except ValueError:
        return None
    if pid <= 0 or ":" not in local:
        return None
    port_s = local.rsplit(":", 1)[-1].strip("[]")
    try:
        port = int(port_s)
    except ValueError:
        return None
    if port <= 0:
        return None
    return port, pid


def _enrich_port_index_netstat(index: Dict[int, Set[int]]) -> None:
    if os.name != "nt":
        return
    for proto in ("tcp", "udp"):
        try:
            completed = subprocess.run(
                ["netstat", "-ano", "-p", proto],
                capture_output=True,
                text=True,
                timeout=20,
                creationflags=_CREATE_NO_WINDOW,
            )
        except Exception:
            continue
        for line in (completed.stdout or "").splitlines():
            parsed = _parse_netstat_line(line)
            if parsed is None:
                continue
            port, pid = parsed
            index.setdefault(port, set()).add(pid)


def _build_listening_port_index(
    interesting_ports: Optional[Set[int]] = None,
) -> Dict[int, Set[int]]:
    """Adjunct: porta → PIDs (TCP LISTEN + UDP). Não usado no path primário 1.10.36."""
    index: Dict[int, Set[int]] = {}
    if _PSUTIL_OK and _psutil is not None:
        try:
            for conn in _psutil.net_connections(kind="inet"):
                try:
                    if not conn.pid or not conn.laddr:
                        continue
                    port = int(conn.laddr.port)
                    if interesting_ports is not None and port not in interesting_ports:
                        continue
                    type_name = getattr(conn.type, "name", str(conn.type))
                    is_udp = "DGRAM" in str(type_name).upper()
                    is_tcp_listen = conn.status == "LISTEN"
                    if is_udp or is_tcp_listen:
                        index.setdefault(port, set()).add(int(conn.pid))
                except Exception:
                    continue
        except Exception:
            pass
    _enrich_port_index_netstat(index)
    if interesting_ports is not None:
        return {p: index.get(p, set()) for p in interesting_ports}
    return index


def _ports_for_pid(port_index: Dict[int, Set[int]], pid: int) -> Set[int]:
    return {port for port, pids in port_index.items() if pid in pids}


def _windows_titles_by_pid() -> Dict[int, str]:
    if os.name != "nt":
        return {}
    titles: Dict[int, str] = {}
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        GetWindowTextLengthW = user32.GetWindowTextLengthW
        GetWindowTextW = user32.GetWindowTextW
        IsWindowVisible = user32.IsWindowVisible
        GetWindowThreadProcessId = user32.GetWindowThreadProcessId

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _enum(hwnd: int, _lparam: int) -> bool:
            try:
                if not IsWindowVisible(hwnd):
                    return True
                pid = wintypes.DWORD()
                GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                length = int(GetWindowTextLengthW(hwnd) or 0)
                if length <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                GetWindowTextW(hwnd, buf, length + 1)
                text = (buf.value or "").strip()
                if text:
                    titles.setdefault(int(pid.value), text)
            except Exception:
                pass
            return True

        user32.EnumWindows(_enum, 0)
    except Exception:
        return {}
    return titles


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
        self.attached_exe: str = ""  # path verificado sob install_dir (UI PID/path)

    # ── Status helpers ──────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self.status == ASM_STATUS_RUNNING

    @property
    def pid(self) -> Optional[int]:
        return self._proc.pid if self._proc else None

    def process_hint(self) -> str:
        """Texto curto do exe anexado p/ o card (ex. ...\\MAPAS\\AM\\...\\ShooterGameServer.exe)."""
        exe = (self.attached_exe or "").replace("/", "\\")
        if not exe:
            return ""
        upper = exe.upper()
        marker = "MAPAS\\"
        idx = upper.find(marker)
        if idx >= 0:
            return "..." + exe[idx:]
        parts = exe.split("\\")
        if len(parts) >= 3:
            return "...\\" + "\\".join(parts[-3:])
        return exe


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
        # Restart intencional: STOPPED não pode limpar pending (race com start).
        self._force_day_restarting: set[str] = set()
        from ..server_visibility import get_steam_poller
        poller = get_steam_poller()
        poller.set_machine_public_ip(self._machine_public_ip)
        poller.set_on_change(self._steam_visibility_callback)

    def mark_force_day_pending(self, server_id: str) -> None:
        with self._lock:
            self._force_day_pending.add(server_id)

    def begin_force_day_restart(self, server_id: str) -> None:
        """Marca restart intencional + pending SetDay (sobrevive ao STOPPED)."""
        with self._lock:
            self._force_day_restarting.add(server_id)
            self._force_day_pending.add(server_id)

    def end_force_day_restart(self, server_id: str) -> None:
        with self._lock:
            self._force_day_restarting.discard(server_id)

    def is_force_day_restarting(self, server_id: str) -> bool:
        with self._lock:
            return server_id in self._force_day_restarting

    def consume_force_day_pending(self, server_id: str) -> bool:
        with self._lock:
            if server_id in self._force_day_pending:
                self._force_day_pending.discard(server_id)
                return True
            return False

    def clear_force_day_pending(self, server_id: str) -> None:
        # #region agent log
        try:
            from .._agent_debug_log import agent_dbg
            agent_dbg("A", "asm_server_manager.py:clear_force_day_pending", "clear_force_day enter", {
                "sid": server_id,
                "lock_held_before": self._lock.locked() if hasattr(self._lock, "locked") else None,
                "thread": threading.current_thread().name,
            })
        except Exception:
            pass
        # #endregion
        with self._lock:
            # Durante restart, STOPPED chega atrasado e apagava o pending do start
            # seguinte — só 1 mapa (ou nenhum) recebia SetDay.
            if server_id in self._force_day_restarting:
                return
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

    def count_running(self, servers: Optional[List[AsmServerConfig]] = None) -> int:
        """ONLINE = status RUNNING (mesma métrica do dashboard / sidebar)."""
        if servers is None:
            return sum(
                1 for inst in self._instances.values() if inst.status == ASM_STATUS_RUNNING
            )
        n = 0
        for cfg in servers:
            inst = self._instances.get(cfg.id)
            if inst and inst.status == ASM_STATUS_RUNNING:
                n += 1
        return n

    def _notify_status(self, server_id: str, status: str) -> None:
        """Emite status FORA de self._lock — callback UI/app pode reentrar no lock."""
        cb = self._on_status
        if not cb:
            return
        try:
            cb(server_id, status)
        except Exception:
            pass

    def _mark_stopped(
        self,
        cfg: AsmServerConfig,
        reason: str = "",
        *,
        notify: bool = True,
    ) -> None:
        inst = self._instances.get(cfg.id)
        if not inst:
            return
        inst._proc = None
        inst.status = ASM_STATUS_STOPPED
        inst.uptime_start = None
        inst.attached_exe = ""
        self._stop_steam_watcher(cfg.id)
        _clear_last_pid(cfg.id)
        if reason:
            try:
                self._on_log(
                    f"Reconnect [{cfg.name or cfg.id}]: ghost RUNNING → STOPPED ({reason})",
                    "warning",
                )
            except Exception:
                pass
        if notify:
            self._notify_status(cfg.id, ASM_STATUS_STOPPED)

    def _reconcile_ghosts(self, servers: List[AsmServerConfig]) -> int:
        """RUNNING/STARTING sem Shooter próprio sob install_dir → STOPPED."""
        cleared_ids: List[str] = []
        for cfg in servers:
            inst = self._instances.get(cfg.id)
            if not inst or inst.status not in (ASM_STATUS_RUNNING, ASM_STATUS_STARTING):
                continue
            proc = inst._proc
            dead = proc is None or proc.poll() is not None
            pid = int(proc.pid) if proc is not None and getattr(proc, "pid", None) else 0
            owned = (not dead) and bool(pid) and _pid_safe_to_kill(cfg, pid)
            if dead or not owned:
                reason = (
                    "poll morto / sem PID"
                    if dead
                    else f"PID {pid} não é Shooter sob install_dir"
                )
                with self._lock:
                    if inst.status in (ASM_STATUS_RUNNING, ASM_STATUS_STARTING):
                        self._mark_stopped(cfg, reason, notify=False)
                        cleared_ids.append(cfg.id)
        for sid in cleared_ids:
            self._notify_status(sid, ASM_STATUS_STOPPED)
        return len(cleared_ids)

    def _attach_running_process(
        self,
        cfg: AsmServerConfig,
        pid: int,
        create_time: Optional[float],
        *,
        strategy: str = "",
        notify: bool = True,
    ) -> bool:
        """Anexa PID ao instance STOPPED.

        Com notify=False o caller DEVE emitir RUNNING fora do lock (evita deadlock
        com clear_force_day_pending / force_day no callback de status).
        Recusa PIDs que não pertençam ao install_dir (anti ghost / PID recycle).
        """
        if not _PSUTIL_OK or _psutil is None:
            return False
        if not _pid_safe_to_kill(cfg, pid):
            # Reaproveita a mesma regra do Stop: sem path do mapa = não anexa
            try:
                self._on_log(
                    f"Reconnect [{cfg.name or cfg.id}]: PID {pid} rejeitado "
                    f"(não é ShooterGameServer sob install_dir)",
                    "warning",
                )
            except Exception:
                pass
            return False
        inst = self._instances.get(cfg.id)
        if not inst or inst.status != ASM_STATUS_STOPPED:
            return False
        try:
            raw = _psutil.Process(pid)
            info = _inspect_pid(pid)
            inst._proc = _PsutilProcessWrapper(raw)
            inst.cfg = cfg
            inst.status = ASM_STATUS_RUNNING
            inst.uptime_start = float(create_time or time.time())
            inst.attached_exe = info.get("exe") or _expected_shooter_exe(cfg)
            self._start_monitor(inst)
            self._start_steam_watcher(inst)
            try:
                last = _load_last_pids()
                last[cfg.id] = int(pid)
                _save_last_pids(last)
            except Exception:
                pass
            if strategy:
                try:
                    self._on_log(
                        f"Reconnect [{cfg.name or cfg.id}] via {strategy} pid={pid}",
                        "info",
                    )
                except Exception:
                    pass
            if notify:
                self._notify_status(cfg.id, ASM_STATUS_RUNNING)
            return True
        except Exception:
            return False

    def scan_running_servers(self, servers: List[AsmServerConfig]) -> int:
        """Reconecta ShooterGameServer com várias estratégias independentes.

        Ordem de preferência (melhor score vence por mapa):
          1) portas TCP/UDP (server/query/RCON) — PRIMARY no host .bug
          2) install_dir no exe
          3) QueryFullProcessImageName (exe vazio)
          4) install_dir / ?Port= / QueryPort na cmdline
          5) last-known PID persistido
          6) título da janela (nome / pasta BR/CI/…)
        """
        if not _PSUTIL_OK or _psutil is None:
            return 0

        self.register_servers(servers)
        self._reconcile_ghosts(servers)

        install_counts: Dict[str, int] = {}
        for cfg in servers:
            key = _normalize_install_dir(cfg.install_dir)
            if key:
                install_counts[key] = install_counts.get(key, 0) + 1

        interesting: Set[int] = set()
        for cfg in servers:
            interesting.update(_cfg_identity_ports(cfg))
        port_index = _build_listening_port_index(interesting or None)
        last_pids = _load_last_pids()

        # Inventário de processos (Shooter + PIDs que escutam portas dos mapas)
        proc_info: Dict[int, Dict[str, Any]] = {}

        def _ensure_pid(pid: int) -> Dict[str, Any]:
            info = proc_info.get(pid)
            if info is not None:
                return info
            info = {
                "pid": pid,
                "name": "",
                "exe": "",
                "cmdline": "",
                "create_time": None,
            }
            try:
                raw = _psutil.Process(pid)
                try:
                    info["name"] = (raw.name() or "").lower()
                except Exception:
                    pass
                try:
                    info["create_time"] = float(raw.create_time())
                except Exception:
                    pass
                try:
                    info["exe"] = _slash_fold(raw.exe() or "")
                except Exception:
                    info["exe"] = ""
                try:
                    info["cmdline"] = _slash_fold(" ".join(raw.cmdline() or []))
                except Exception:
                    info["cmdline"] = ""
            except Exception:
                pass
            if not info["exe"]:
                img = _query_full_process_image_name(pid)
                if img:
                    info["exe"] = img
            proc_info[pid] = info
            return info

        try:
            for proc in _psutil.process_iter(
                ["pid", "name", "exe", "cmdline", "create_time"]
            ):
                try:
                    name = (proc.info.get("name") or "").lower()
                    if "shootergameserver" not in name:
                        continue
                    pid = int(proc.info["pid"])
                    exe = _slash_fold(proc.info.get("exe") or "")
                    cmdline = _slash_fold(" ".join(proc.info.get("cmdline") or []))
                    if not exe:
                        exe = _query_full_process_image_name(pid) or exe
                    proc_info[pid] = {
                        "pid": pid,
                        "name": name,
                        "exe": exe,
                        "cmdline": cmdline,
                        "create_time": proc.info.get("create_time"),
                    }
                except Exception:
                    pass
        except Exception:
            pass

        for pids in port_index.values():
            for pid in pids:
                _ensure_pid(int(pid))

        claimed: Set[int] = set()
        for cfg in servers:
            inst = self._instances.get(cfg.id)
            if inst and inst.status == ASM_STATUS_RUNNING and inst.pid:
                claimed.add(int(inst.pid))

        reconnected = 0
        # Melhor match por server_id: (score, pid, strategy, create_time)
        best: Dict[str, Tuple[int, int, str, Optional[float]]] = {}

        def _offer(cfg: AsmServerConfig, pid: int, score: int, strategy: str) -> None:
            if pid <= 0 or pid in claimed:
                return
            info = _ensure_pid(pid)
            exe = info.get("exe") or ""
            cmdline = info.get("cmdline") or ""
            name = info.get("name") or ""
            if _is_protected_process(int(pid), name, exe):
                return
            belongs = _path_belongs_to_install(cfg, exe, cmdline)
            install_norm = _normalize_install_dir(cfg.install_dir)
            # Com install_dir: SÓ anexa se path sob essa pasta (nunca nome/porta/título sozinhos)
            if install_norm and belongs is not True:
                return
            if belongs is False:
                return
            if not _looks_like_shooter(name, exe, cmdline):
                return
            ct = info.get("create_time")
            prev = best.get(cfg.id)
            if prev is None or score > prev[0]:
                best[cfg.id] = (score, pid, strategy, ct)

        for cfg in servers:
            inst = self._instances.get(cfg.id)
            if not inst or inst.status != ASM_STATUS_STOPPED:
                continue
            cfg_ports = set(_cfg_identity_ports(cfg))
            install_norm = _normalize_install_dir(cfg.install_dir)
            shared = bool(install_norm) and install_counts.get(install_norm, 0) > 1
            miss: List[str] = []

            # 1) PATH no exe (primário — um mapa = um install_dir)
            for pid, info in proc_info.items():
                exe = info.get("exe") or ""
                cmdline = info.get("cmdline") or ""
                if exe and install_norm and install_norm in exe:
                    if (not shared) or _cmdline_matches_server(cmdline, cfg) or _bound_ports_match_cfg(
                        cfg, _ports_for_pid(port_index, int(pid))
                    ):
                        _offer(cfg, int(pid), _STRAT_EXE, "exe+install_dir")
                if cmdline and install_norm and install_norm in cmdline:
                    if (not shared) or _cmdline_matches_server(cmdline, cfg):
                        _offer(cfg, int(pid), _STRAT_CMDLINE, "cmdline+install_dir")

            # 2) Portas — só se _offer confirmar path (QueryFullProcessImageName)
            votes: Counter = Counter()
            for port in cfg_ports:
                for pid in port_index.get(port, ()):
                    votes[int(pid)] += 1
            if votes:
                pid, n = votes.most_common(1)[0]
                bound = _ports_for_pid(port_index, pid)
                if _bound_ports_match_cfg(cfg, bound):
                    _offer(cfg, pid, _STRAT_PORTS + int(n), f"ports={sorted(bound & cfg_ports)}")
                else:
                    miss.append("ports-no-overlap")
            else:
                miss.append("ports-empty")

            # 3) last-known PID — só se path ainda for deste install_dir
            cached = int(last_pids.get(cfg.id, 0) or 0)
            if cached and cached not in claimed:
                info = _ensure_pid(cached)
                belongs = _path_belongs_to_install(
                    cfg, info.get("exe") or "", info.get("cmdline") or ""
                )
                if belongs is True:
                    _offer(cfg, cached, _STRAT_LAST_PID, "last_pid")
                else:
                    miss.append(f"last_pid={cached}-invalid")

            if cfg.id not in best:
                try:
                    self._on_log(
                        f"Reconnect [{cfg.name or cfg.id}] FALHOU: {', '.join(miss) or 'sem path sob install_dir'}",
                        "warning",
                    )
                except Exception:
                    pass

        # Anexa por score desc; um PID só para um mapa.
        # Status callback SEMPRE fora do lock (app_tek.clear_force_day_pending reentra).
        ordered = sorted(
            ((sid, score, pid, strat, ct) for sid, (score, pid, strat, ct) in best.items()),
            key=lambda row: (-row[1], row[0]),
        )
        used_pids: Set[int] = set(claimed)
        attached: List[str] = []
        for sid, _score, pid, strat, ct in ordered:
            if pid in used_pids:
                continue
            cfg = next((s for s in servers if s.id == sid), None)
            if cfg is None:
                continue
            with self._lock:
                ok = self._attach_running_process(
                    cfg, pid, ct, strategy=strat, notify=False
                )
            if ok:
                used_pids.add(pid)
                attached.append(cfg.id)
                reconnected += 1
        for sid in attached:
            self._notify_status(sid, ASM_STATUS_RUNNING)

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
        # #region agent log
        try:
            from .._agent_debug_log import agent_dbg
            agent_dbg("A,B,E", "asm_server_manager.py:start:entry", "manager.start", {
                "name": cfg.name, "sid": cfg.id, "thread": threading.current_thread().name,
            })
        except Exception:
            pass
        # #endregion
        if not cfg.install_dir:
            if on_done:
                on_done(False, "install_dir não configurado")
            return

        with self._lock:
            inst = self._instances.setdefault(cfg.id, AsmServerInstance(cfg))
            if inst.status in (ASM_STATUS_RUNNING, ASM_STATUS_STARTING):
                pid = inst.pid
                owned = bool(pid) and _pid_safe_to_kill(cfg, int(pid))
                if not owned:
                    # Ghost ONLINE/STARTING — limpa e permite Start real
                    self._mark_stopped(cfg, "ghost antes do Start", notify=False)
                else:
                    if on_done:
                        on_done(False, "Servidor já em execução")
                    return
            inst.cfg = cfg

        if inst.status == ASM_STATUS_STOPPED:
            # notifica UI se limpamos ghost (fora do lock)
            pass
        # Re-notifica STOPPED se vínhamos de ghost (dashboard precisa Offline)
        if inst.status == ASM_STATUS_STOPPED and inst._proc is None:
            try:
                self._notify_status(cfg.id, ASM_STATUS_STOPPED)
            except Exception:
                pass

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

        # #region agent log
        try:
            from .._agent_debug_log import agent_dbg
            agent_dbg("A,B", "asm_server_manager.py:start:before_reconnect", "calling try_reconnect_server", {
                "name": cfg.name, "status": inst.status,
            })
        except Exception:
            pass
        # #endregion
        if inst.status == ASM_STATUS_STOPPED and self.try_reconnect_server(cfg):
            # #region agent log
            try:
                from .._agent_debug_log import agent_dbg
                agent_dbg("E", "asm_server_manager.py:start:reconnect_ok", "reconnect instead of launch", {
                    "name": cfg.name,
                })
            except Exception:
                pass
            # #endregion
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
            try:
                _pid = proc.pid if proc is not None else None
                if _pid:
                    _info = _inspect_pid(int(_pid))
                    inst.attached_exe = _info.get("exe") or _expected_shooter_exe(cfg)
                else:
                    inst.attached_exe = _expected_shooter_exe(cfg)
            except Exception:
                inst.attached_exe = _expected_shooter_exe(cfg)
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
        """Para o servidor. NUNCA mata PID sem verificar install_dir + ShooterGameServer.

        Ghost / PID reciclado (ex.: pós-reboot): só limpa estado — sem taskkill.
        taskkill /F /T em PID errado pode derrubar DWM/sessão (tela preta).
        """
        killed = False
        try:
            proc = inst._proc
            pid = proc.pid if proc is not None else None
            safe = bool(pid) and _pid_safe_to_kill(inst.cfg, int(pid))

            if safe:
                # RCON só se o processo é realmente o mapa
                self._rcon_shutdown(inst.cfg)
                time.sleep(5)
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True,
                        timeout=15,
                    )
                    killed = True
                except Exception:
                    pass
                if proc and proc.poll() is None:
                    try:
                        proc.terminate()
                        proc.wait(timeout=10)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                    killed = True
            else:
                # Ghost ONLINE ou PID de outro processo — limpa UI sem TerminateProcess
                try:
                    self._on_log(
                        f"Parar [{inst.cfg.name or inst.cfg.id}]: PID {pid} "
                        f"NÃO verificado sob install_dir — só limpeza de estado "
                        f"(sem taskkill)",
                        "warning",
                    )
                except Exception:
                    pass

            inst.status = ASM_STATUS_STOPPED
            inst._proc = None
            inst.uptime_start = None
            inst.attached_exe = ""
            self._stop_steam_watcher(inst.cfg.id)
            _clear_last_pid(inst.cfg.id)
            if self._on_status:
                self._on_status(inst.cfg.id, ASM_STATUS_STOPPED)
            if on_done:
                msg = (
                    "Servidor parado"
                    if killed
                    else "Estado limpo (processo não verificado — nenhum kill)"
                )
                on_done(True, msg)
        except Exception as exc:
            inst.status = ASM_STATUS_STOPPED
            inst._proc = None
            inst.uptime_start = None
            inst.attached_exe = ""
            self._stop_steam_watcher(inst.cfg.id)
            _clear_last_pid(inst.cfg.id)
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
            if inst.status not in (ASM_STATUS_RUNNING, ASM_STATUS_STARTING):
                break
            rc = proc.poll()
            if rc is not None:
                with inst._lock:
                    if inst.status not in (ASM_STATUS_STOPPED, ASM_STATUS_STOPPING):
                        inst.status = ASM_STATUS_CRASHED
                        inst._proc = None
                        inst.uptime_start = None
                        self._stop_steam_watcher(inst.cfg.id)
                        _clear_last_pid(inst.cfg.id)
                        if self._on_status:
                            self._on_status(inst.cfg.id, ASM_STATUS_CRASHED)
                break
            # PID vivo mas não é o Shooter deste mapa → limpa ghost (não CRASHED)
            pid = int(getattr(proc, "pid", 0) or 0)
            if pid and inst.status == ASM_STATUS_RUNNING and not _pid_safe_to_kill(inst.cfg, pid):
                with inst._lock:
                    if inst.status == ASM_STATUS_RUNNING:
                        inst.status = ASM_STATUS_STOPPED
                        inst._proc = None
                        inst.uptime_start = None
                        self._stop_steam_watcher(inst.cfg.id)
                        _clear_last_pid(inst.cfg.id)
                        try:
                            self._on_log(
                                f"Monitor [{inst.cfg.name or inst.cfg.id}]: "
                                f"PID {pid} inválido sob install_dir → STOPPED",
                                "warning",
                            )
                        except Exception:
                            pass
                        if self._on_status:
                            self._on_status(inst.cfg.id, ASM_STATUS_STOPPED)
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
        self.begin_force_day_restart(cfg.id)

        def _after_stop(ok: bool, msg: str) -> None:
            time.sleep(2)
            # Re-marca pending após o stop (defesa extra contra race STOPPED).
            self.mark_force_day_pending(cfg.id)

            def _done(ok2: bool, msg2: str) -> None:
                try:
                    # Se o start só reconectou / “já em execução”, RUNNING pode
                    # não voltar a disparar — aplica SetDay se ainda estiver pending.
                    if self.consume_force_day_pending(cfg.id) and self._on_status:
                        self.mark_force_day_pending(cfg.id)
                        self._on_status(cfg.id, ASM_STATUS_RUNNING)
                finally:
                    self.end_force_day_restart(cfg.id)
                if on_done:
                    on_done(ok2, msg2)

            self.start(cfg, on_done=_done)

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
