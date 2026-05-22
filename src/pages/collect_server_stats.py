from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..server_config import SERVER_STATUS_RUNNING, SERVER_STATUS_STARTING, SERVER_STATUS_STOPPED


def collect_server_stats(app: "ARKServerManagerApp") -> list:
    """Retorna [(server_id, name, status, cpu_pct|None, mem_gb|None)] por servidor."""
    if not _PSUTIL_OK or _psutil is None:
        return []
    result = []
    for srv in app.config_manager.servers:
        inst = app.server_manager.get_instance(srv.id)
        status = inst.status if inst else SERVER_STATUS_STOPPED
        if inst and inst.pid and status in (SERVER_STATUS_RUNNING, SERVER_STATUS_STARTING):
            try:
                proc = app._perf_server_procs.get(srv.id)
                if proc is None or proc.pid != inst.pid:
                    proc = _psutil.Process(inst.pid)
                    proc.cpu_percent(interval=None)  # prime
                    app._perf_server_procs[srv.id] = proc
                cpu = proc.cpu_percent(interval=None)
                mem = proc.memory_info().rss / (1024 ** 3)
                result.append((srv.id, srv.name, status, cpu, mem))
            except Exception:
                app._perf_server_procs.pop(srv.id, None)
                result.append((srv.id, srv.name, status, None, None))
        else:
            app._perf_server_procs.pop(srv.id, None)
            result.append((srv.id, srv.name, status, None, None))
    return result

