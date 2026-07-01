"""Verifica tarefas agendadas para todos os servidores TEK (roda a cada 60 s)."""
from __future__ import annotations
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from ..asm_engine.asm_server_config import ASM_STATUS_STOPPED, ASM_STATUS_RUNNING
from ..backup_interval import parse_interval_seconds
if TYPE_CHECKING:
    from ..app_tek import ARKTEKApp


def _process_global_backups(app, now: datetime) -> None:
    """Backup global de servidores e do banco de dados (config em Configurações / Banco)."""
    bk = app.config_manager.config.backup
    if bk.auto_backup and not getattr(app, "_global_backup_running", False):
        interval_s = parse_interval_seconds(bk.backup_interval, default=6 * 3600)
        last: Optional[datetime] = getattr(app, "_global_backup_last_run", None)
        elapsed = (now - last).total_seconds() if last else interval_s + 1
        if elapsed >= interval_s:
            threading.Thread(target=app._run_global_backup, daemon=True).start()

    db_cfg = app.config_manager.config.db_backup
    if db_cfg.enabled and not getattr(app, "_db_backup_running", False):
        interval_s = max(3600, db_cfg.interval_hours * 3600)
        last_db: Optional[datetime] = getattr(app, "_db_backup_last_run", None)
        elapsed_db = (now - last_db).total_seconds() if last_db else interval_s + 1
        if elapsed_db >= interval_s:
            threading.Thread(target=app._run_scheduled_db_backup, daemon=True).start()


def _auto_restart_days_list(srv) -> list[int]:
    """Dias habilitados para reinício (0=Seg … 6=Dom). None = todos (legado)."""
    days = getattr(srv, "auto_restart_days", None)
    if days is None:
        return list(range(7))
    if not isinstance(days, list):
        return list(range(7))
    return [int(d) for d in days if isinstance(d, (int, float)) and 0 <= int(d) <= 6]


def _process_server_scheduled_tasks(app, srv, now, now_hhmm: str) -> None:
    """Verifica e dispara tarefas agendadas de um servidor TEK."""
    if srv.enable_auto_restart and (srv.auto_restart_time or "").strip() == now_hhmm:
        if now.weekday() in _auto_restart_days_list(srv):
            status = app.asm_server_manager.get_status(srv.id)
            if status not in (ASM_STATUS_STOPPED, "stopping"):
                app._asm_do_scheduled_restart(srv)

    if srv.enable_auto_update_check and srv.auto_update_check_minutes > 0:
        last_attr = f"_last_update_check_{srv.id}"
        last: Optional[datetime] = getattr(app, last_attr, None)
        delta_min = (now - last).total_seconds() / 60 if last else srv.auto_update_check_minutes + 1
        if delta_min >= srv.auto_update_check_minutes:
            setattr(app, last_attr, now)
            threading.Thread(target=app._asm_check_update_worker, args=(srv,), daemon=True).start()

    if getattr(srv, "enable_auto_backup", False):
        backup_time = (getattr(srv, "auto_backup_time", "") or "").strip()
        if backup_time == now_hhmm:
            last_date_attr = f"_backup_last_date_{srv.id}"
            today_str = now.strftime("%Y-%m-%d")
            if getattr(app, last_date_attr, None) != today_str:
                setattr(app, last_date_attr, today_str)
                threading.Thread(target=app._run_global_backup, daemon=True).start()

    if getattr(srv, "enable_scheduled_broadcast", False):
        bc_time = (getattr(srv, "scheduled_broadcast_time", "") or "").strip()
        bc_msg  = (getattr(srv, "scheduled_broadcast_message", "") or "").strip()
        if bc_time == now_hhmm and bc_msg:
            last_bc_attr = f"_bc_last_date_{srv.id}"
            today_str = now.strftime("%Y-%m-%d")
            if getattr(app, last_bc_attr, None) != today_str:
                setattr(app, last_bc_attr, today_str)
                threading.Thread(target=app._asm_do_scheduled_broadcast, args=(srv, bc_msg), daemon=True).start()


def asm_scheduler_tick(app) -> None:
    """Verifica tarefas agendadas para todos os servidores TEK (a cada 60 s)."""
    try:
        now = datetime.now()
        now_hhmm = now.strftime("%H:%M")
        _process_global_backups(app, now)
        for srv in app.asm_config_manager.servers:
            _process_server_scheduled_tasks(app, srv, now, now_hhmm)
    except Exception:
        pass
    finally:
        app.after(60_000, app._asm_scheduler_tick)

