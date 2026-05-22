from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def set_config_editable(app: "ARKServerManagerApp", server_id: str, editable: bool) -> None:
    """Habilita ou desabilita todos os widgets de configuração das abas do servidor."""
    w = app._server_widgets.get(server_id, {})

    # Banner de bloqueio
    banner = w.get("_lock_banner")
    if banner:
        if editable:
            banner.grid_remove()
        else:
            banner.grid()

    # Abas de configuração (exceto Console RCON e Logs)
    tabs: Optional[ctk.CTkTabview] = w.get("_tabs")
    if not tabs:
        return

    _CONFIG_TABS = ("Geral", "Jogo", "Avançado", "Spawns", "Loot", "Mods")
    state = "normal" if editable else "disabled"

    def _set_recursive(widget) -> None:
        try:
            wclass = widget.winfo_class()
            if wclass in ("TButton", "TEntry", "TCheckbutton", "TCombobox", "TSpinbox"):
                widget.configure(state=state)
            elif hasattr(widget, "configure"):
                try:
                    widget.configure(state=state)
                except Exception:
                    pass
        except Exception:
            pass
        for child in widget.winfo_children():
            _set_recursive(child)

    for tab_name in _CONFIG_TABS:
        try:
            tab_frame = tabs.tab(tab_name)
            _set_recursive(tab_frame)
        except Exception:
            pass

