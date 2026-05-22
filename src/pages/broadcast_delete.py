from __future__ import annotations
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def broadcast_delete(app: "ARKServerManagerApp", server_id: str, index: int) -> None:
    """Remove um broadcast da biblioteca pelo índice."""
    srv = app.config_manager.get_server(server_id)
    if not srv or index >= len(srv.broadcasts):
        return
    if not messagebox.askyesno(
        "Remover broadcast",
        f"Remover o broadcast '{srv.broadcasts[index]['label']}'?",
        parent=app,
    ):
        return
    srv.broadcasts.pop(index)
    app.config_manager.update_server(srv)
    app._broadcast_refresh_list(server_id)

