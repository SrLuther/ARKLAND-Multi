"""Detecção de listagem Steam/LAN — paridade com ASM ServerStatusWatcher."""
from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

# ── Estados de disponibilidade (paridade ASM SteamStatus) ─────────────────────
STEAM_UNKNOWN = "unknown"
STEAM_NEED_PUBLIC_IP = "need_public_ip"
STEAM_UNAVAILABLE = "unavailable"
STEAM_WAITING = "waiting"
STEAM_AVAILABLE = "available"
STEAM_LAN = "lan"

STEAM_LABELS: dict[str, tuple[str, str]] = {
    STEAM_UNKNOWN: ("—", "#64748b"),
    STEAM_NEED_PUBLIC_IP: ("Defina IP público", "#f59e0b"),
    STEAM_UNAVAILABLE: ("Indisponível", "#64748b"),
    STEAM_WAITING: ("Aguardando publicação", "#38bdf8"),
    STEAM_AVAILABLE: ("Steam", "#22c55e"),
    STEAM_LAN: ("LAN", "#f59e0b"),
}

# Aliases legados (VIS_*)
VIS_UNKNOWN = STEAM_UNKNOWN
VIS_LOADING = STEAM_UNAVAILABLE
VIS_LAN = STEAM_LAN
VIS_STEAM = STEAM_AVAILABLE
VIS_NO_LIST = STEAM_WAITING
VIS_LABELS = STEAM_LABELS

LOCAL_POLL_DELAY = 5.0
REMOTE_POLL_DELAY = 60.0

VisibilityCallback = Callable[[str, str, str], None]


def steam_chip(status: str) -> tuple[str, str]:
    """(texto curto, cor hex) para badge de disponibilidade."""
    if status in STEAM_LABELS:
        return STEAM_LABELS[status]
    return "", "gray50"


def visibility_chip(mode: str) -> tuple[str, str]:
    return steam_chip(mode)


def format_status_badge(
    process_status: str,
    steam_status: str,
    *,
    running_label: str = "ONLINE",
) -> tuple[str, str]:
    """Combina status do processo com disponibilidade na lista (paridade ASM)."""
    from .asm_engine.asm_server_config import ASM_STATUS_RUNNING, ASM_STATUS_STARTING

    if process_status == ASM_STATUS_STARTING:
        return "INICIANDO", "#f59e0b"
    if process_status != ASM_STATUS_RUNNING:
        if process_status in ("stopping",):
            return "PARANDO", "#f59e0b"
        if process_status in ("crashed",):
            return "TRAVADO", "#ef4444"
        return "PARADO", "#64748b"

    label, color = steam_chip(steam_status)
    if not label or label == "—":
        return running_label, "#22c55e"
    if steam_status == STEAM_UNAVAILABLE:
        return f"{running_label} · Inicializando", "#38bdf8"
    return f"{running_label} · {label}", color


def resolve_machine_public_ip(app_config: Any = None) -> str:
    """IP público global (paridade ASM MachinePublicIP)."""
    if app_config is None:
        return ""
    direct = (getattr(app_config, "machine_public_ip", None) or "").strip()
    if direct:
        return direct
    shop = getattr(app_config, "shop", None)
    if shop:
        fallback = (getattr(shop, "public_ip", None) or "").strip()
        if fallback:
            return fallback
    return ""


def _args_text_from_cfg(cfg: Any) -> str:
    parts: list[str] = []
    extra = getattr(cfg, "additional_args", None) or getattr(cfg, "extra_args", None) or ""
    if extra:
        parts.append(str(extra))
    try:
        if hasattr(cfg, "server_map"):
            from .asm_engine.asm_ini_manager import build_launch_args
            parts.append(" ".join(build_launch_args(cfg)))
        else:
            parts.append(" ".join(cfg.build_launch_args()))
    except Exception:
        pass
    return " ".join(parts).lower()


def is_lan_match_config(cfg: Any) -> bool:
    """True se ?bIsLanMatch=True / bLANMatch na linha de comando."""
    text = _args_text_from_cfg(cfg)
    return "bislanmatch=true" in text or "blanmatch=true" in text


def probe_a2s_query(host: str, port: int, timeout: float = 2.0) -> bool:
    """Ping A2S_INFO na porta de query (UDP)."""
    return probe_a2s_info(host, port, timeout=timeout) is not None


def probe_a2s_info(host: str, port: int, timeout: float = 2.0) -> Optional[dict[str, Any]]:
    """Consulta A2S_INFO; retorna dict com name/players/max_players ou None."""
    if not port:
        return None
    target = (host or "127.0.0.1").strip() or "127.0.0.1"
    payload = b"\xFF\xFF\xFF\xFFTSource Engine Query\x00"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.sendto(payload, (target, int(port)))
            data, _ = sock.recvfrom(4096)
            if len(data) < 6 or data[:4] != b"\xFF\xFF\xFF\xFF":
                return None
            if data[4] != 0x49:  # 'I' — A2S_INFO response
                return None
            return _parse_a2s_info(data[5:])
    except OSError:
        return None


def _parse_a2s_info(payload: bytes) -> dict[str, Any]:
    """Parser mínimo A2S_INFO (campos usados pelo ASM)."""
    try:
        idx = 0
        idx += 1  # protocol
        name, idx = _read_cstring(payload, idx)
        idx = payload.index(b"\x00", idx) + 1  # map
        idx = payload.index(b"\x00", idx) + 1  # folder
        idx = payload.index(b"\x00", idx) + 1  # game
        idx += 2  # app id
        players = payload[idx]
        max_players = payload[idx + 1]
        return {"name": name, "players": players, "max_players": max_players}
    except (ValueError, IndexError):
        return {}


def _read_cstring(data: bytes, start: int) -> tuple[str, int]:
    end = data.index(b"\x00", start)
    return data[start:end].decode("utf-8", errors="replace"), end + 1


def check_steam_master_list(host: str, game_port: int, query_port: int, timeout: float = 8.0) -> bool:
    """Fallback: API Steam GetServersAtAddress (tenta porta de jogo e de query)."""
    host = (host or "").strip()
    if not host:
        return False
    ports: list[int] = []
    for p in (game_port, query_port):
        if p and p not in ports:
            ports.append(int(p))
    for port in ports:
        url = (
            "https://api.steampowered.com/ISteamApps/GetServersAtAddress/v1/"
            f"?format=json&addr={host}:{port}"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ARKLAND/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8", errors="replace"))
            servers = (body.get("response") or {}).get("servers") or []
            if servers:
                return True
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            continue
    return False


def classify_steam_status(
    *,
    process_running: bool,
    lan_configured: bool,
    local_query_ok: bool,
    public_ip: str,
    public_query_ok: bool,
    steam_master_ok: bool,
) -> tuple[str, str]:
    """Classifica disponibilidade (paridade ASM ServerRuntime + ServerStatusWatcher)."""
    if not process_running:
        return STEAM_UNAVAILABLE, "Servidor parado"
    if lan_configured:
        if local_query_ok:
            return STEAM_LAN, "Modo LAN — visível na rede local"
        return STEAM_UNAVAILABLE, "Modo LAN — aguardando resposta na porta de query"
    if not local_query_ok:
        return STEAM_UNAVAILABLE, "Processo ativo — aguardando porta de query (A2S)"
    if not public_ip:
        return STEAM_NEED_PUBLIC_IP, "Configure o IP público da máquina nas configurações globais"
    if public_query_ok or steam_master_ok:
        return STEAM_AVAILABLE, "Publicado na lista Steam"
    return (
        STEAM_WAITING,
        "Query local OK — aguardando publicação na lista Steam (pode levar alguns minutos)",
    )


@dataclass
class _ServerRegistration:
    server_id: str
    cfg: Any
    inst: Any
    is_running: Callable[[], bool]


class SteamStatusPoller:
    """Poller central — espelha ASM ServerStatusWatcher (5s local, 60s remoto)."""

    def __init__(self) -> None:
        self._regs: dict[str, _ServerRegistration] = {}
        self._last_remote: dict[str, float] = {}
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._on_change: Optional[VisibilityCallback] = None
        self._machine_public_ip: str = ""
        self._stop = threading.Event()

    def set_machine_public_ip(self, ip: str) -> None:
        self._machine_public_ip = (ip or "").strip()

    def set_on_change(self, callback: Optional[VisibilityCallback]) -> None:
        self._on_change = callback

    def register(
        self,
        server_id: str,
        cfg: Any,
        inst: Any,
        *,
        is_running: Optional[Callable[[], bool]] = None,
    ) -> None:
        with self._lock:
            self._regs[server_id] = _ServerRegistration(
                server_id=server_id,
                cfg=cfg,
                inst=inst,
                is_running=is_running or (lambda: True),
            )
            self._last_remote.setdefault(server_id, 0.0)
            self._ensure_thread()

    def unregister(self, server_id: str) -> None:
        with self._lock:
            self._regs.pop(server_id, None)
            self._last_remote.pop(server_id, None)
        self._apply(server_id, None, STEAM_UNAVAILABLE, "Servidor parado")

    def _ensure_thread(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="steam-status")
        self._thread.start()

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                items = list(self._regs.values())
            for reg in items:
                try:
                    self._poll_one(reg)
                except Exception:
                    pass
            if not items:
                time.sleep(LOCAL_POLL_DELAY)
                with self._lock:
                    if not self._regs:
                        return
            else:
                time.sleep(LOCAL_POLL_DELAY)

    def _poll_one(self, reg: _ServerRegistration) -> None:
        cfg = reg.cfg
        inst = reg.inst
        sid = reg.server_id
        running = reg.is_running()

        lan_cfg = is_lan_match_config(cfg)
        query_port = int(getattr(cfg, "query_port", 0) or 0)
        game_port = int(getattr(cfg, "server_port", 0) or 0)
        bind_ip = (getattr(cfg, "server_ip", None) or "").strip()
        public_ip = self._machine_public_ip

        local_hosts = [h for h in (bind_ip, "127.0.0.1") if h]
        local_info = None
        for host in local_hosts:
            local_info = probe_a2s_info(host, query_port)
            if local_info:
                break
        local_ok = local_info is not None

        if local_info:
            inst.a2s_players = local_info.get("players")
            inst.a2s_max_players = local_info.get("max_players")

        public_ok = False
        steam_master_ok = False
        if running and local_ok and public_ip and not lan_cfg:
            public_ok = probe_a2s_query(public_ip, query_port)
            now = time.monotonic()
            last = self._last_remote.get(sid, 0.0)
            if not public_ok and now - last >= REMOTE_POLL_DELAY:
                steam_master_ok = check_steam_master_list(public_ip, game_port, query_port)
                self._last_remote[sid] = now
            elif public_ok:
                self._last_remote[sid] = now

        mode, detail = classify_steam_status(
            process_running=running,
            lan_configured=lan_cfg,
            local_query_ok=local_ok,
            public_ip=public_ip,
            public_query_ok=public_ok,
            steam_master_ok=steam_master_ok,
        )
        self._apply(sid, inst, mode, detail)

    def _apply(self, server_id: str, inst: Any, mode: str, detail: str) -> None:
        if inst is not None:
            if getattr(inst, "steam_status", None) == mode and getattr(inst, "steam_status_detail", "") == detail:
                return
            inst.steam_status = mode
            inst.steam_status_detail = detail
            inst.listing_mode = mode
            inst.listing_detail = detail
        if self._on_change:
            self._on_change(server_id, mode, detail)


_poller: Optional[SteamStatusPoller] = None
_poller_lock = threading.Lock()


def get_steam_poller() -> SteamStatusPoller:
    global _poller
    with _poller_lock:
        if _poller is None:
            _poller = SteamStatusPoller()
        return _poller


# ── Monitor de log (complementar — marcadores rápidos) ───────────────────────

ARK_READY_MARKERS = (
    "Full Startup",
    "server has been listed online",
    "GameMode BeginPlay",
    "Beacon has completed",
    "LogWorld: Bringing World",
    "World loaded",
    "All levels loaded",
)

ARK_STEAM_MARKERS = (
    "OnCreateLobbyComplete",
    "Steam lobby created",
    "OnlineLobbyID",
    "bLANMatch=false",
    "STEAM: Search result",
    "server has been listed online",
)

ARK_LAN_MARKERS = (
    "bLANMatch=true",
    "bIsLanMatch=true",
)


def resolve_listing_mode(
    *,
    lan_configured: bool,
    steam_log_seen: bool,
    lan_log_seen: bool,
    world_ready: bool,
    query_ok: bool,
) -> tuple[str, str]:
    """Classificação legada por log — preferir SteamStatusPoller."""
    if lan_configured or lan_log_seen:
        return STEAM_LAN, "Modo LAN"
    if steam_log_seen and query_ok:
        return STEAM_AVAILABLE, "Registrado no Steam (log)"
    if not world_ready:
        return STEAM_UNAVAILABLE, "Mundo carregando"
    if query_ok:
        return STEAM_WAITING, "Query OK — verificando Steam"
    return STEAM_WAITING, "Query UDP não responde"


def probe_listing_now(cfg: Any, inst: Any) -> tuple[str, str]:
    steam_seen = bool(getattr(inst, "_listing_steam_seen", False))
    lan_seen = bool(getattr(inst, "_listing_lan_seen", False))
    world_ready = bool(getattr(inst, "_listing_world_ready", False))
    lan_cfg = is_lan_match_config(cfg)
    host = getattr(cfg, "server_ip", None) or "127.0.0.1"
    query_port = int(getattr(cfg, "query_port", 0) or 0)
    query_ok = probe_a2s_query(host, query_port) if world_ready else False
    if not query_ok and world_ready:
        query_ok = probe_a2s_query("127.0.0.1", query_port)
    return resolve_listing_mode(
        lan_configured=lan_cfg,
        steam_log_seen=steam_seen,
        lan_log_seen=lan_seen,
        world_ready=world_ready,
        query_ok=query_ok,
    )


def find_shooter_log(install_dir: str, server_exe: str = "ShooterGameServer.exe") -> Optional[Path]:
    if not install_dir:
        return None
    exe_path = Path(install_dir) / "ShooterGame" / "Binaries" / "Win64" / server_exe
    candidates = [
        exe_path.parents[2] / "Saved" / "Logs" / "ShooterGame.log",
        exe_path.parent / "ShooterGame" / "Saved" / "Logs" / "ShooterGame.log",
        Path(install_dir) / "ShooterGame" / "Saved" / "Logs" / "ShooterGame.log",
    ]
    return next((c for c in candidates if c.exists()), candidates[0] if candidates else None)


def start_listing_monitor(
    *,
    server_id: str,
    cfg: Any,
    proc: Any,
    inst: Any,
    on_change: Callable[[str, str, str], None],
    stop_flag: Callable[[], bool],
) -> None:
    """Monitora ShooterGame.log (legado). TEK usa SteamStatusPoller."""

    def _apply(mode: str, detail: str) -> None:
        if getattr(inst, "listing_mode", STEAM_UNKNOWN) == mode and getattr(inst, "listing_detail", "") == detail:
            return
        inst.listing_mode = mode
        inst.listing_detail = detail
        on_change(server_id, mode, detail)

    def _worker() -> None:
        log_path = find_shooter_log(cfg.install_dir, getattr(cfg, "server_exe", "ShooterGameServer.exe"))
        last_size = 0
        if log_path and log_path.exists():
            try:
                last_size = log_path.stat().st_size
            except OSError:
                pass

        inst._listing_steam_seen = False
        inst._listing_lan_seen = False
        inst._listing_world_ready = False
        _apply(STEAM_UNAVAILABLE, "Aguardando log do servidor")

        while not stop_flag():
            if proc is not None and proc.poll() is not None:
                break
            if log_path and log_path.exists():
                try:
                    size = log_path.stat().st_size
                    if size < last_size:
                        last_size = 0
                    if size > last_size:
                        with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
                            fh.seek(last_size)
                            chunk = fh.read()
                        last_size = size
                        low = chunk.lower()
                        if any(m.lower() in low for m in ARK_LAN_MARKERS):
                            inst._listing_lan_seen = True
                        if any(m.lower() in low for m in ARK_STEAM_MARKERS):
                            inst._listing_steam_seen = True
                        if any(m.lower() in low for m in ARK_READY_MARKERS):
                            inst._listing_world_ready = True
                        mode, detail = probe_listing_now(cfg, inst)
                        _apply(mode, detail)
                except OSError:
                    pass
            else:
                log_path = find_shooter_log(cfg.install_dir, getattr(cfg, "server_exe", "ShooterGameServer.exe"))

            if getattr(inst, "_listing_world_ready", False):
                mode, detail = probe_listing_now(cfg, inst)
                _apply(mode, detail)
            time.sleep(3)

    threading.Thread(target=_worker, daemon=True, name=f"listing-{server_id[:8]}").start()
