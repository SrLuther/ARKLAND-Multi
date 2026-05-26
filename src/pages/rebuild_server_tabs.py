"""
Reconstrói as tabs de servidor na ServerTabBar.
Substitui rebuild_server_sidebar.py — sem CTkScrollableFrame.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..ui_constants import _STATUS_COLOR
from ..server_config import SERVER_STATUS_STOPPED

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def rebuild_server_tabs(app: "ARKServerManagerApp") -> None:
    """Sincroniza a ServerTabBar com os servidores configurados."""
    if not getattr(app, "_server_tab_bar", None):
        return

    tab_bar = app._server_tab_bar

    if app._active_mode == "tek":
        _rebuild_tek_tabs(app, tab_bar)
    else:
        _rebuild_primitive_tabs(app, tab_bar)


def _rebuild_primitive_tabs(app: "ARKServerManagerApp", tab_bar) -> None:
    servers = app.config_manager.servers
    current_ids = {srv.id for srv in servers}
    for removed_id in set(tab_bar._tabs.keys()) - current_ids:
        tab_bar.remove_tab(removed_id)
    for srv in servers:
        inst = app.server_manager.get_instance(srv.id)
        status = inst.status if inst else SERVER_STATUS_STOPPED
        color = _STATUS_COLOR.get(status, "#ff6666")
        tab_bar.add_tab(srv.id, srv.name, color)


_TEK_STATUS_COLOR = {
    "running":  "#00BCD4",
    "stopped":  "#ff6666",
    "starting": "#ffaa44",
    "stopping": "#ffaa44",
    "crashed":  "#ff3333",
    "updating": "#ffaa44",
}


def _rebuild_tek_tabs(app: "ARKServerManagerApp", tab_bar) -> None:
    from ..asm_engine.asm_server_config import ASM_STATUS_STOPPED  # noqa: PLC0415
    servers = app.asm_config_manager.servers
    current_ids = {srv.id for srv in servers}
    for removed_id in set(tab_bar._tabs.keys()) - current_ids:
        tab_bar.remove_tab(removed_id)
    for srv in servers:
        inst = app.asm_server_manager.get_instance(srv.id)
        status = inst.status if inst else ASM_STATUS_STOPPED
        color = _TEK_STATUS_COLOR.get(status, "#ff6666")
        tab_bar.add_tab(srv.id, srv.name, color)
