"""Ponte unificada de servidores para o sistema de BUFFs (TEK + modo legado)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class BuffServerEntry:
    id: str
    name: str
    kind: str  # "tek" | "primitive"
    label: str


def list_buff_servers(app: Any) -> list[BuffServerEntry]:
    """Lista servidores TEK e legados (primitivo) para BUFFs."""
    out: list[BuffServerEntry] = []
    asm_cm = getattr(app, "asm_config_manager", None)
    if asm_cm is not None:
        for srv in asm_cm.servers:
            out.append(BuffServerEntry(
                id=srv.id,
                name=srv.name,
                kind="tek",
                label=f"{srv.name} (TEK)",
            ))
    for srv in app.config_manager.servers:
        out.append(BuffServerEntry(
            id=srv.id,
            name=srv.name,
            kind="primitive",
            label=f"{srv.name} (legado)",
        ))
    return out


def resolve_buff_server_id(app: Any, label_or_name: str) -> Optional[str]:
    """Resolve rótulo do combo (ou nome) para server_id."""
    key = (label_or_name or "").strip()
    if not key:
        return None
    for entry in list_buff_servers(app):
        if entry.label == key or entry.name == key:
            return entry.id
    return None


def get_buff_server_config(app: Any, server_id: str) -> Any:
    asm_cm = getattr(app, "asm_config_manager", None)
    if asm_cm is not None:
        srv = asm_cm.get_server(server_id)
        if srv is not None:
            return srv
    return app.config_manager.get_server(server_id)


def buff_server_kind(app: Any, server_id: str) -> Optional[str]:
    asm_cm = getattr(app, "asm_config_manager", None)
    if asm_cm is not None and asm_cm.get_server(server_id):
        return "tek"
    if app.config_manager.get_server(server_id):
        return "primitive"
    return None


def buff_start_server(app: Any, server_id: str) -> None:
    kind = buff_server_kind(app, server_id)
    if kind == "tek":
        asm_cm = getattr(app, "asm_config_manager", None)
        srv = asm_cm.get_server(server_id) if asm_cm else None
        if srv is not None:
            app.asm_server_manager.start(
                srv,
                on_done=lambda _ok, _msg: (
                    app.after(0, app._asm_refresh_dashboard)
                    if hasattr(app, "_asm_refresh_dashboard")
                    else None
                ),
            )
        return
    app.server_manager.start_server(server_id)


def buff_stop_server(app: Any, server_id: str) -> None:
    kind = buff_server_kind(app, server_id)
    if kind == "tek":
        if hasattr(app, "_asm_stop_server"):
            app._asm_stop_server(server_id)
        return
    app.server_manager.stop_server(server_id)


def buff_get_server_status(app: Any, server_id: str) -> str:
    from .server_config import (
        SERVER_STATUS_CRASHED,
        SERVER_STATUS_RUNNING,
        SERVER_STATUS_STARTING,
        SERVER_STATUS_STOPPED,
        SERVER_STATUS_STOPPING,
    )

    kind = buff_server_kind(app, server_id)
    if kind == "tek":
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


def buff_persist_server_config(app: Any, server_id: str, cfg: Any) -> None:
    kind = buff_server_kind(app, server_id)
    if kind == "tek":
        asm_cm = getattr(app, "asm_config_manager", None)
        if asm_cm:
            asm_cm.update_server(cfg)
            asm_cm.save()
        return
    app.config_manager.update_server(cfg)


def remove_primitive_server(app: Any, server_id: str) -> None:
    """Remove servidor do modo legado (primitivo) — utilizável no app TEK."""
    app.server_manager.remove_server(server_id)
    app.config_manager.remove_server(server_id)
    app.config_manager.save()
