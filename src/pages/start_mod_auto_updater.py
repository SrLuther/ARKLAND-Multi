from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..mod_auto_updater import ModAutoUpdater
from ..mod_server_bridge import (
    list_mod_servers,
    mod_get_server_view,
    mod_get_status,
    mod_start_server,
    mod_stop_server,
)

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def create_mod_auto_updater(
    app: "ARKServerManagerApp",
    *,
    check_interval_minutes: int = 15,
    warning_minutes: int = 5,
) -> ModAutoUpdater:
    on_log = getattr(app, "_on_auto_updater_log", app._global_log)
    return ModAutoUpdater(
        server_manager=app.server_manager,
        mod_manager=app.mod_manager,
        get_servers=lambda: list_mod_servers(app),
        on_log=on_log,
        check_interval_minutes=check_interval_minutes,
        warning_minutes=warning_minutes,
        discord_notifier=getattr(app, "_discord_notifier", None),
        steam_api_key=getattr(app.config_manager.config, "steam_api_key", ""),
        get_server_status=lambda sid: mod_get_status(app, sid),
        stop_server=lambda sid: mod_stop_server(app, sid),
        start_server=lambda sid: mod_start_server(app, sid),
        get_server_view=lambda sid: mod_get_server_view(app, sid),
    )


def start_mod_auto_updater(app: "ARKServerManagerApp") -> None:
    """Inicia o verificador automático de mods ao carregar o app."""
    from ..ui_constants import _GREEN, _RED_DARK, _RED_HOVER

    if app._mod_auto_updater is not None and app._mod_auto_updater.enabled:
        return
    if app._mod_auto_updater is None:
        app._mod_auto_updater = create_mod_auto_updater(app)
    app._mod_auto_updater.start()
    _refresh_auto_updater_ui(app, active=True)


def _refresh_auto_updater_ui(app: Any, *, active: bool) -> None:
    from ..ui_constants import _GREEN, _GREEN_DARK, _GREEN_HOVER, _RED_DARK, _RED_HOVER

    widgets = getattr(app, "_server_widgets", {}) or {}
    tek_btn = getattr(app, "_tek_au_toggle_btn", None)
    tek_lbl = getattr(app, "_tek_au_status_lbl", None)
    if tek_btn:
        tek_btn.configure(
            text="⏸ Parar" if active else "▶ Ativar",
            fg_color=_RED_DARK if active else _GREEN_DARK,
            hover_color=_RED_HOVER if active else _GREEN_HOVER,
        )
    if tek_lbl:
        tek_lbl.configure(
            text="● ATIVO" if active else "● INATIVO",
            text_color=_GREEN if active else "gray50",
        )
    for ww in widgets.values():
        btn = ww.get("_au_toggle_btn")
        lbl = ww.get("_au_status_lbl")
        if btn:
            btn.configure(
                text="⏸ Parar" if active else "▶ Ativar",
                fg_color=_RED_DARK if active else _GREEN_DARK,
                hover_color=_RED_HOVER if active else _GREEN_HOVER,
            )
        if lbl:
            lbl.configure(
                text="● ATIVO" if active else "● INATIVO",
                text_color=_GREEN if active else "gray50",
            )
