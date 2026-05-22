from __future__ import annotations
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def confirm_remove_server(app: "ARKServerManagerApp", server_id: str) -> None:
    srv = app.config_manager.get_server(server_id)
    name = srv.name if srv else server_id
    if messagebox.askyesno(
        "Remover Servidor",
        f"Deseja remover o servidor '{name}'?\nEsta ação não pode ser desfeita.",
        parent=app,
    ):
        app.server_manager.remove_server(server_id)
        app.config_manager.remove_server(server_id)
        frame_key = f"server_{server_id}"
        if frame_key in app._frames:
            app._frames[frame_key].destroy()
            del app._frames[frame_key]
        if server_id in app._server_frames:
            del app._server_frames[server_id]
        if server_id in app._server_widgets:
            del app._server_widgets[server_id]
        if server_id in app._rcon_clients:
            try:
                app._rcon_clients[server_id].disconnect()
            except Exception:
                pass
            del app._rcon_clients[server_id]
        app._rebuild_server_sidebar()
        app._refresh_dashboard()
        app._show_frame("dashboard")

