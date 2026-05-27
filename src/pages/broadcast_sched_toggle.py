"""Ativa/desativa um broadcast agendado individual."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def broadcast_sched_toggle(
    app: "ARKServerManagerApp",
    server_id: str,
    bc_id: str,
    enabled: bool,
) -> None:
    """Altera o flag `enabled` do broadcast identificado por bc_id."""
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return

    for bc in getattr(srv, "auto_broadcasts", []):
        if bc.get("id") == bc_id:
            bc["enabled"] = enabled
            break
    else:
        return  # não encontrado, nada a fazer

    app.config_manager.update_server(srv)
    app._bc_sched_refresh(server_id)
