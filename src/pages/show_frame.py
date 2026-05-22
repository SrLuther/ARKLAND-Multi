from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def show_frame(app: "ARKServerManagerApp", name: str) -> None:
    prev = app._current_frame
    if prev == name:
        return
    app._current_frame = name

    # Esconde apenas o frame anterior; mostra apenas o novo
    if prev in app._frames:
        app._frames[prev].grid_remove()
    if name in app._frames:
        app._frames[name].grid()

    # Atualiza somente os dois botões afetados
    if prev in app._nav_buttons:
        app._nav_buttons[prev].configure(fg_color="transparent")
    elif prev.startswith("server_"):
        sid = prev[len("server_"):]
        if sid in app._sidebar_server_btns:
            app._sidebar_server_btns[sid].configure(fg_color="transparent")

    if name in app._nav_buttons:
        app._nav_buttons[name].configure(fg_color="#1e2a3a")
    elif name.startswith("server_"):
        sid = name[len("server_"):]
        if sid in app._sidebar_server_btns:
            app._sidebar_server_btns[sid].configure(fg_color="#1e2a3a")

    if name == "buffs":
        app.after(50, app._refresh_buffs_ui)

