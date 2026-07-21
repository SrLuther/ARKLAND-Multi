from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..app_tek import ARKTEKApp

_log = logging.getLogger(__name__)


def auto_start_servers(app: "ARKServerManagerApp | ARKTEKApp") -> None:
    """Inicia automaticamente os servidores com auto_start_on_launch=True."""
    asm_cm = getattr(app, "asm_config_manager", None)
    asm_sm = getattr(app, "asm_server_manager", None)
    if asm_cm is not None and asm_sm is not None:
        _auto_start_asm_servers(app, asm_cm, asm_sm)
        return

    servers = [s for s in app.config_manager.servers if s.auto_start_on_launch]
    if not servers:
        return

    def _do_legacy() -> None:
        for srv in servers:
            def _kick(s=srv) -> None:
                app._global_log(
                    f"[Auto-Start] Iniciando servidor '{s.name}'...", "info"
                )
                app._start_server(s.id)

            app.after(0, _kick)

    threading.Thread(target=_do_legacy, daemon=True, name="AutoStartServers").start()


def _auto_start_asm_servers(app: Any, asm_cm: Any, asm_sm: Any) -> None:
    from ..asm_engine.asm_server_config import ASM_STATUS_RUNNING, ASM_STATUS_STARTING

    servers = [
        s for s in asm_cm.servers
        if getattr(s, "auto_start_on_launch", False)
    ]
    if not servers:
        return

    def _do() -> None:
        for srv in servers:
            status = asm_sm.get_status(srv.id)
            if status in (ASM_STATUS_RUNNING, ASM_STATUS_STARTING):
                continue
            fresh = asm_cm.get_server(srv.id) or srv
            name = fresh.name or fresh.id

            def _start(srv_cfg=fresh, srv_name=name) -> None:
                app._global_log(
                    f"[Auto-Start] Iniciando servidor '{srv_name}'...", "info"
                )
                app._asm_start_server(srv_cfg)

            app.after(0, _start)

    threading.Thread(target=_do, daemon=True, name="AutoStartAsmServers").start()
