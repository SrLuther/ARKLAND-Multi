from __future__ import annotations
from typing import TYPE_CHECKING
from ..ui_constants import _GREEN, _RED_DARK, _RED_HOVER
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..mod_auto_updater import ModAutoUpdater


def start_mod_auto_updater(app: "ARKServerManagerApp") -> None:
    """Inicia o verificador automático de mods ao carregar o app."""
    if app._mod_auto_updater is not None and app._mod_auto_updater.enabled:
        return
    if app._mod_auto_updater is None:
        app._mod_auto_updater = ModAutoUpdater(
            server_manager=app.server_manager,
            mod_manager=app.mod_manager,
            get_servers=lambda: app.config_manager.servers,
            on_log=app._on_auto_updater_log,
            check_interval_minutes=15,
            warning_minutes=5,
        )
    app._mod_auto_updater.start()
    # Atualiza botões/labels em todos os painéis já construídos
    for ww in app._server_widgets.values():
        btn = ww.get("_au_toggle_btn")
        lbl = ww.get("_au_status_lbl")
        if btn:
            btn.configure(text="⏸ Parar", fg_color=_RED_DARK, hover_color=_RED_HOVER)
        if lbl:
            lbl.configure(text="● ATIVO", text_color=_GREEN)

