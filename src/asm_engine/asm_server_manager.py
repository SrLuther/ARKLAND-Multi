"""
AsmServerManager — gerenciador de processos TEK.
Controla start/stop/restart e monitora o status de cada servidor ASM.
"""
from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

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
    """
    if not _PSUTIL_OK or _psutil is None:
        return None
    install_norm = _normalize_install_dir(install_dir)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            for p in _psutil.process_iter(["pid", "name", "exe", "cmdline", "create_time"]):
                try:
                    name = p.info.get("name") or ""
                    if "shootergameserver" not in name.lower():
                        continue
                    exe, cmdline = _read_shooter_process_fields(p)
                    if not _install_dir_in_process(exe, cmdline, install_norm):
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
    needle = str(int(port))
    return bool(re.search(rf"(?:\?port=|-port=){re.escape(needle)}(?!\d)", cmdline))


def _cmdline_has_query_port(cmdline: str, query_port: int) -> bool:
    if not cmdline or not query_port:
        return False
    needle = str(int(query_port))
    return bool(
        re.search(rf"(?:\?queryport=|-queryport=){re.escape(needle)}(?!\d)", cmdline)
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


def _cfg_identity_ports(cfg: "AsmServerConfig") -> List[int]:
    """Portas que identificam o mapa: game, query e RCON (TCP)."""
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
    wanted = set(_cfg_identity_ports(cfg))
    return bool(wanted & bound_ports)


def _window_title_matches(title: str, cfg: "AsmServerConfig") -> bool:
    t = (title or "").strip().lower()
    if not t:
        return False
    for candidate in (getattr(cfg, "name", ""), getattr(cfg, "session_name", "")):
        c = (candidate or "").strip().lower()
        if c and len(c) >= 3 and (t == c or c in t or t in c):
            return True
    return False


def _process_matches_cfg(
    cfg: "AsmServerConfig",
    exe: str,
    cmdline: str,
    install_dir_counts: Dict[str, int],
    bound_ports: Optional[Set[int]] = None,
    window_title: str = "",
) -> bool:
    install_norm = _normalize_install_dir(cfg.install_dir)
    install_hit = bool(install_norm) and _install_dir_in_process(exe, cmdline, install_norm)
    port_hit = _cmdline_matches_server(cmdline, cfg) or _bound_ports_match_cfg(
        cfg, bound_ports or set()
    )
    title_hit = _window_title_matches(window_title, cfg)
    disambig = _cmdline_disambiguate(cmdline, cfg)

    if install_hit:
        if install_dir_counts.get(install_norm, 0) > 1:
            return port_hit or disambig or title_hit
        return True
    return port_hit or disambig or title_hit


def _match_diagnostic(
    cfg: "AsmServerConfig",
    exe: str,
    cmdline: str,
    install_dir_counts: Dict[str, int],
    bound_ports: Optional[Set[int]] = None,
    window_title: str = "",
) -> List[str]:
    """Sinais parciais — útil quando o processo existe mas não fechou match."""
    bits: List[str] = []
    install_norm = _normalize_install_dir(cfg.install_dir)
    if install_norm and _install_dir_in_process(exe, cmdline, install_norm):
        bits.append("install_dir")
    if _cmdline_has_port(cmdline, cfg.server_port):
        bits.append(f"cmdline_port={cfg.server_port}")
    if _cmdline_has_query_port(cmdline, cfg.query_port):
        bits.append(f"cmdline_query={cfg.query_port}")
    hit_ports = sorted(set(_cfg_identity_ports(cfg)) & (bound_ports or set()))
    if hit_ports:
        bits.append(f"bound={hit_ports}")
    if _window_title_matches(window_title, cfg):
        bits.append("window_title")
    if _map_token_in_cmdline(cmdline, cfg):
        bits.append("map_token")
    if install_dir_counts.get(install_norm, 0) > 1:
        bits.append("shared_install")
    if not exe and not cmdline:
        bits.append("exe_cmdline_empty")
    return bits


def _query_full_process_image_name(pid: int) -> str:
    """Win32 QueryFullProcessImageName — funciona sem cmdline elevada."""
    if os.name != "nt" or not pid:
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buf))
            ok = kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
            return buf.value if ok else ""
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return ""


def _read_shooter_process_fields(proc: Any) -> tuple[str, str]:
    """exe/cmdline normalizados; relê via Process(pid) / Win32 se process_iter vier incompleto."""
    info = getattr(proc, "info", None) or {}
    exe = info.get("exe") or ""
    cmdline_parts = info.get("cmdline") or []
    pid = info.get("pid") or getattr(proc, "pid", None)
    if _PSUTIL_OK and _psutil is not None and pid and (not exe or not cmdline_parts):
        try:
            raw = _psutil.Process(int(pid))
            if not exe:
                try:
                    exe = raw.exe() or ""
                except Exception:
                    pass
            if not cmdline_parts:
                try:
                    cmdline_parts = raw.cmdline() or []
                except Exception:
                    pass
        except Exception:
            pass
    if not exe and pid:
        exe = _query_full_process_image_name(int(pid))
    if isinstance(cmdline_parts, str):
        cmdline_joined = cmdline_parts
    else:
        cmdline_joined = " ".join(str(x) for x in (cmdline_parts or []))
    return exe.replace("\\", "/").lower(), cmdline_joined.lower()


def _parse_netstat_line(line: str) -> Optional[tuple[int, int]]:
    """Extrai (porta, pid) de uma linha `netstat -ano`. None se irrelevante.

    Formatos Windows típicos (colunas em inglês mesmo em UI PT):
      TCP    0.0.0.0:27020    0.0.0.0:0    LISTENING    5555
      UDP    0.0.0.0:7777     *:*                        5555
      TCP    [::]:27020       [::]:0       LISTENING    5555
    """
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
        # Aceita LISTENING / LISTEN (e variantes localizadas com "LISTEN")
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
    # IPv6 [::]:7777 → rsplit pega a porta após o último ':'
    port_s = local.rsplit(":", 1)[-1].strip("[]")
    try:
        port = int(port_s)
    except ValueError:
        return None
    if port <= 0:
        return None
    return port, pid


def _enrich_port_index_netstat(index: Dict[int, Set[int]]) -> None:
    """Fallback sem elevação: netstat -ano → porta → PID (TCP LISTEN + UDP)."""
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


def _build_listening_port_index(interesting_ports: Optional[Set[int]] = None) -> Dict[int, Set[int]]:
    """Mapa porta → PIDs (TCP LISTEN + UDP bound). Preferência: psutil, depois netstat."""
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
                    if not (is_udp or is_tcp_listen):
                        continue
                    index.setdefault(port, set()).add(int(conn.pid))
                except Exception:
                    continue
        except Exception:
            pass
    before = sum(len(v) for v in index.values())
    _enrich_port_index_netstat(index)
    if interesting_ports is not None:
        # netstat preenche tudo — filtrar o que não interessa
        for port in list(index.keys()):
            if port not in interesting_ports:
                del index[port]
    _ = before  # reserved for future diagnostics
    return index


def _ports_for_pid(index: Dict[int, Set[int]], pid: int) -> Set[int]:
    return {port for port, pids in index.items() if pid in pids}


def _windows_titles_by_pid() -> Dict[int, str]:
    """Título da janela (RunServer `start \"nome\"`) → PID."""
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


def _is_shooter_candidate(name: str, exe: str, cmdline: str) -> bool:
    blob = f"{name} {exe} {cmdline}".lower()
    if "shootergameserver" in blob:
        return True
    # Sem nome/exe/cmdline (AccessDenied): candidato só via porta
    return not (name or exe or cmdline)


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

        Estratégias (host Windows onde os mapas correm):
        1) install_dir / ?Port= / QueryPort / mapa na cmdline (mesmo com exe vazio)
        2) PID dono de TCP/UDP em server_port, query_port ou rcon_port
           (psutil.net_connections + netstat -ano — funciona sem cmdline legível)
        3) título da janela (RunServer ``start "nome"``)

        A v1.10.40 só usava (1). Se exe+cmdline vierem vazios (psutil sem permissão
        ou attrs incompletos), nenhum mapa casava — daí o refuerço por porta.
        """
        if not _PSUTIL_OK or _psutil is None:
            self._on_log(
                "Scan reconnect: psutil indisponível — não é possível detectar mapas em execução.",
                "warning",
            )
            return 0

        if not servers:
            self._on_log(
                "Scan reconnect: nenhum mapa em asm_servers.json — skip.",
                "warning",
            )
            return 0

        self.register_servers(servers)
        install_counts: Dict[str, int] = {}
        interesting_ports: Set[int] = set()
        stopped = 0
        for cfg in servers:
            key = _normalize_install_dir(cfg.install_dir)
            if key:
                install_counts[key] = install_counts.get(key, 0) + 1
            interesting_ports.update(_cfg_identity_ports(cfg))
            inst = self._instances.get(cfg.id)
            if inst is None or inst.status == ASM_STATUS_STOPPED:
                stopped += 1

        port_index = _build_listening_port_index(interesting_ports)
        titles = _windows_titles_by_pid()
        claimed: Set[int] = set()
        reconnected = 0

        # Candidatos: nome ShooterGameServer + PIDs que escutam portas dos perfis
        candidates: Dict[int, Dict[str, Any]] = {}
        try:
            for proc in _psutil.process_iter(
                ["pid", "name", "exe", "cmdline", "create_time"]
            ):
                try:
                    name = (proc.info.get("name") or "").lower()
                    pid = int(proc.info["pid"])
                    if "shootergameserver" in name:
                        candidates[pid] = {
                            "proc": proc,
                            "name": proc.info.get("name") or "",
                            "create_time": proc.info.get("create_time"),
                        }
                except Exception:
                    continue
        except Exception as exc:
            self._on_log(f"Scan reconnect: process_iter falhou ({exc}).", "warning")

        for port, pids in port_index.items():
            for pid in pids:
                if pid in candidates:
                    continue
                candidates[pid] = {
                    "proc": None,
                    "name": "",
                    "create_time": None,
                    "via_port": port,
                }

        for pid, meta in list(candidates.items()):
            if pid in claimed:
                continue
            try:
                proc = meta.get("proc")
                if proc is None:
                    class _Stub:
                        info: Dict[str, Any]

                    stub = _Stub()
                    stub.info = {"pid": pid, "exe": "", "cmdline": []}
                    if _psutil is not None:
                        try:
                            raw_probe = _psutil.Process(pid)
                            stub.info["name"] = raw_probe.name() or ""
                            meta["name"] = stub.info["name"]
                            meta["create_time"] = raw_probe.create_time()
                        except Exception:
                            pass
                    proc = stub

                name = (
                    meta.get("name")
                    or (proc.info.get("name") if hasattr(proc, "info") else "")
                    or ""
                )
                exe, cmdline = _read_shooter_process_fields(proc)
                if not _is_shooter_candidate(name, exe, cmdline):
                    continue

                bound = _ports_for_pid(port_index, pid)
                title = titles.get(pid, "")
                create_time = meta.get("create_time")
                matched = False

                with self._lock:
                    for cfg in servers:
                        inst = self._instances.get(cfg.id)
                        if not inst or inst.status != ASM_STATUS_STOPPED:
                            continue
                        if not _process_matches_cfg(
                            cfg,
                            exe,
                            cmdline,
                            install_counts,
                            bound_ports=bound,
                            window_title=title,
                        ):
                            continue

                        raw = _psutil.Process(pid)
                        inst._proc = _PsutilProcessWrapper(raw)
                        inst.cfg = cfg
                        inst.status = ASM_STATUS_RUNNING
                        inst.uptime_start = float(create_time or time.time())
                        how = _match_diagnostic(
                            cfg, exe, cmdline, install_counts, bound, title
                        )
                        self._on_log(
                            f"Reconnect [{cfg.name}] PID {pid} via {', '.join(how) or 'match'}.",
                            "info",
                        )
                        if self._on_status:
                            self._on_status(cfg.id, ASM_STATUS_RUNNING)
                        self._start_monitor(inst)
                        self._start_steam_watcher(inst)
                        claimed.add(pid)
                        reconnected += 1
                        matched = True
                        break

                if matched:
                    continue

                # Processo Shooter / porta dos perfis sem mapa correspondente
                if "shootergameserver" in f"{name} {exe}".lower() or (
                    not exe and not cmdline and bound
                ):
                    partials: List[str] = []
                    for cfg in servers:
                        bits = _match_diagnostic(
                            cfg, exe, cmdline, install_counts, bound, title
                        )
                        if bits:
                            partials.append(f"{cfg.name}:{','.join(bits)}")
                    self._on_log(
                        f"Scan reconnect: PID {pid} não casou com nenhum mapa "
                        f"(exe={'ok' if exe else 'vazio'}, "
                        f"cmdline={'ok' if cmdline else 'vazio'}, "
                        f"portas={sorted(bound) or '—'}, título={title or '—'}). "
                        f"Parcial: {'; '.join(partials) or 'nenhum'}.",
                        "warning",
                    )
            except Exception as exc:
                self._on_log(
                    f"Scan reconnect: erro ao inspecionar PID {pid}: {exc}",
                    "warning",
                )
                continue

        if reconnected == 0 and stopped > 0:
            self._on_log(
                f"Scan reconnect: 0 reconectados "
                f"({len(candidates)} candidato(s), {stopped} mapa(s) STOPPED, "
                f"portas indexadas={sorted(port_index.keys()) or '—'}, "
                f"títulos={len(titles)}).",
                "warning",
            )

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
