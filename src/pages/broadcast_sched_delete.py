"""Remove um broadcast agendado por ID."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def broadcast_sched_delete(app: "ARKServerManagerApp", server_id: str, bc_id: str) -> None:
    """Remove o broadcast com o dado ID e persiste."""
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return

    before = len(getattr(srv, "auto_broadcasts", []))
    srv.auto_broadcasts = [b for b in srv.auto_broadcasts if b.get("id") != bc_id]
    if len(srv.auto_broadcasts) < before:
        app.config_manager.update_server(srv)

    app._bc_sched_refresh(server_id)
