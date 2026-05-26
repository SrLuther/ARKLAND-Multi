from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def show_frame(app: "ARKServerManagerApp", name: str) -> None:
    import traceback as _tb
    try:
        _show_frame_impl(app, name)
    except Exception:
        _tb.print_exc()


def _show_frame_impl(app: "ARKServerManagerApp", name: str) -> None:
    prev = app._current_frame
    if prev == name:
        return
    app._current_frame = name

    # Esconde apenas o frame anterior; mostra apenas o novo
    if prev in app._frames:
        app._frames[prev].grid_remove()
    if name in app._frames:
        app._frames[name].grid()

    # ── Rail: atualiza destaque de ícone de nav ───────────────────────────────
    from .rail import _set_rail_active
    nav_key = name if name in getattr(app, "_rail_nav_btns", {}) else None
    if nav_key:
        _set_rail_active(app, nav_key)

    # ── Server tab bar: sincroniza tab ativa ──────────────────────────────────
    if getattr(app, "_server_tab_bar", None):
        if name.startswith("server_"):
            sid = name[len("server_"):]
            app._server_tab_bar.set_active(sid)
        else:
            app._server_tab_bar.set_active(None)

    # ── Compatibilidade legada: _nav_buttons e _sidebar_server_btns ──────────
    if prev in getattr(app, "_nav_buttons", {}):
        app._nav_buttons[prev].configure(fg_color="transparent")
    elif prev.startswith("server_"):
        sid = prev[len("server_"):]
        if sid in getattr(app, "_sidebar_server_btns", {}):
            app._sidebar_server_btns[sid].configure(fg_color="transparent")

    if name in getattr(app, "_nav_buttons", {}):
        app._nav_buttons[name].configure(fg_color="#1e2a3a")
    elif name.startswith("server_"):
        sid = name[len("server_"):]
        if sid in getattr(app, "_sidebar_server_btns", {}):
            app._sidebar_server_btns[sid].configure(fg_color="#1e2a3a")

    if name == "buffs":
        app.after(50, app._refresh_buffs_ui)

