"""Ponte unificada de servidores para ModAutoUpdater (TEK + legado)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .server_config import (
    SERVER_STATUS_CRASHED,
    SERVER_STATUS_RUNNING,
    SERVER_STATUS_STARTING,
    SERVER_STATUS_STOPPED,
    SERVER_STATUS_STOPPING,
)


@dataclass
class ModServerView:
    id: str
    name: str
    install_dir: str
    mods: list[str]
    rcon_enabled: bool
    rcon_port: int
    rcon_password: str


def _rcon_password(cfg: Any) -> str:
    return (
        getattr(cfg, "rcon_password", "") or getattr(cfg, "admin_password", "") or ""
    ).strip()


def list_mod_servers(app: Any) -> list[ModServerView]:
    out: list[ModServerView] = []
    seen: set[str] = set()
    asm_cm = getattr(app, "asm_config_manager", None)
    if asm_cm is not None:
        for srv in asm_cm.servers:
            if not srv.install_dir or srv.id in seen:
                continue
            seen.add(srv.id)
            out.append(ModServerView(
                id=srv.id,
                name=srv.name,
                install_dir=srv.install_dir,
                mods=list(srv.active_mods or []),
                rcon_enabled=bool(srv.rcon_enabled),
                rcon_port=int(srv.rcon_port or 27020),
                rcon_password=_rcon_password(srv),
            ))
    for srv in app.config_manager.servers:
        if not srv.install_dir or srv.id in seen:
            continue
        seen.add(srv.id)
        out.append(ModServerView(
            id=srv.id,
            name=srv.name,
            install_dir=srv.install_dir,
            mods=list(srv.mods or []),
            rcon_enabled=bool(srv.rcon_enabled),
            rcon_port=int(srv.rcon_port or 27020),
            rcon_password=_rcon_password(srv),
        ))
    return out


def mod_get_server_view(app: Any, server_id: str) -> Optional[ModServerView]:
    for srv in list_mod_servers(app):
        if srv.id == server_id:
            return srv
    return None


def mod_get_status(app: Any, server_id: str) -> Optional[str]:
    asm_cm = getattr(app, "asm_config_manager", None)
    if asm_cm is not None and asm_cm.get_server(server_id):
        from .asm_engine.asm_server_config import (
            ASM_STATUS_CRASHED,
            ASM_STATUS_RUNNING,
            ASM_STATUS_STARTING,
            ASM_STATUS_STOPPED,
            ASM_STATUS_STOPPING,
        )
        st = app.asm_server_manager.get_status(server_id)
        if st == ASM_STATUS_RUNNING:
            return SERVER_STATUS_RUNNING
        if st == ASM_STATUS_STARTING:
            return SERVER_STATUS_STARTING
        if st == ASM_STATUS_STOPPING:
            return SERVER_STATUS_STOPPING
        if st == ASM_STATUS_CRASHED:
            return SERVER_STATUS_CRASHED
        return SERVER_STATUS_STOPPED
    inst = app.server_manager.get_instance(server_id)
    return inst.status if inst else SERVER_STATUS_STOPPED


def mod_stop_server(app: Any, server_id: str) -> None:
    asm_cm = getattr(app, "asm_config_manager", None)
    if asm_cm is not None and asm_cm.get_server(server_id):
        if hasattr(app, "_asm_stop_server"):
            app._asm_stop_server(server_id)
        else:
            app.asm_server_manager.stop(server_id)
        return
    app.server_manager.stop_server(server_id)


def mod_start_server(app: Any, server_id: str) -> None:
    asm_cm = getattr(app, "asm_config_manager", None)
    if asm_cm is not None:
        srv = asm_cm.get_server(server_id)
        if srv is not None:
            if hasattr(app, "_asm_start_server"):
                app._asm_start_server(srv)
            else:
                app.asm_server_manager.start(srv)
            return
    app.server_manager.start_server(server_id)
