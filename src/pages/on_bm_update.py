from __future__ import annotations
import os
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def on_bm_update(app: "ARKServerManagerApp", server_id: str) -> None:
    """Callback chamado quando os dados BattleMetrics de um servidor são atualizados."""
    def _do():
        inst = app.server_manager.get_instance(server_id)
        w = app._server_widgets.get(server_id, {})
        bm_lbl: Optional[ctk.CTkLabel] = w.get("_bm_players_lbl")
        if bm_lbl:
            if inst and inst.bm_players is not None and inst.bm_max_players:
                bm_lbl.configure(text=f"👥 {inst.bm_players}/{inst.bm_max_players}")
            else:
                bm_lbl.configure(text="")
        app._refresh_dashboard()
    app.after(0, _do)

