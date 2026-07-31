from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional, Tuple

try:
    import psutil as _psutil  # type: ignore[reportMissingModuleSource]
    _PSUTIL_OK = True
except Exception:
    _psutil = None  # type: ignore[assignment]
    _PSUTIL_OK = False

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

from ..server_config import SERVER_STATUS_RUNNING, SERVER_STATUS_STARTING, SERVER_STATUS_STOPPED


def _servers_and_manager(app: Any) -> Tuple[list, Any]:
    """TEK usa asm_*; fallback para o ServerManager clássico."""
    asm_mgr = getattr(app, "asm_server_manager", None)
    asm_cfg = getattr(app, "asm_config_manager", None)
    if asm_mgr is not None and asm_cfg is not None:
        servers = getattr(asm_cfg, "servers", None) or []
        if servers:
            return list(servers), asm_mgr
    cfg = getattr(app, "config_manager", None)
    mgr = getattr(app, "server_manager", None)
    servers = getattr(cfg, "servers", None) or [] if cfg else []
    return list(servers), mgr


def collect_server_stats(app: "ARKServerManagerApp") -> list:
    """Retorna [(server_id, name, status, cpu_pct|None, mem_gb|None)] por servidor."""
    if not _PSUTIL_OK or _psutil is None:
        return []
    servers, mgr = _servers_and_manager(app)
    if not mgr:
        return []
    result: List[Tuple[str, str, str, Optional[float], Optional[float]]] = []
    for srv in servers:
        sid = getattr(srv, "id", "")
        name = getattr(srv, "name", sid) or sid
        inst = mgr.get_instance(sid)
        status = inst.status if inst else SERVER_STATUS_STOPPED
        pid = getattr(inst, "pid", None) if inst else None
        if inst and pid and status in (SERVER_STATUS_RUNNING, SERVER_STATUS_STARTING):
            try:
                proc = app._perf_server_procs.get(sid)
                if proc is None or proc.pid != pid:
                    proc = _psutil.Process(int(pid))
                    proc.cpu_percent(interval=None)  # prime
                    app._perf_server_procs[sid] = proc
                cpu = proc.cpu_percent(interval=None)
                mem = proc.memory_info().rss / (1024 ** 3)
                result.append((sid, name, status, cpu, mem))
            except Exception:
                app._perf_server_procs.pop(sid, None)
                result.append((sid, name, status, None, None))
        else:
            app._perf_server_procs.pop(sid, None)
            result.append((sid, name, status, None, None))
    return result
