"""Envia um broadcast agendado imediatamente e reinicia seu timer."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def broadcast_sched_send_now(app: "ARKServerManagerApp", server_id: str, bc_id: str) -> None:
    """Envia imediatamente e reseta last_sent para agora."""
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return

    for bc in getattr(srv, "auto_broadcasts", []):
        if bc.get("id") == bc_id:
            msg = bc.get("message", "").strip()
            if msg:
                bc["last_sent"] = time.time()
                app.config_manager.update_server(srv)
                try:
                    app._broadcast_rcon(server_id, msg)
                except Exception:
                    pass
                app.after(200, lambda: app._bc_sched_refresh(server_id))
            break
