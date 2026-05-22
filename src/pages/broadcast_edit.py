from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _GREEN_DARK, _GREEN_HOVER
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def broadcast_edit(app: "ARKServerManagerApp", server_id: str, index: int) -> None:
    """Abre diálogo inline para editar rótulo/mensagem de um broadcast salvo."""
    srv = app.config_manager.get_server(server_id)
    if not srv or index >= len(srv.broadcasts):
        return
    bc = srv.broadcasts[index]

    dlg = ctk.CTkToplevel(app)
    dlg.title("Editar Broadcast")
    dlg.geometry("560x180")
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(dlg, text="Rótulo:").grid(row=0, column=0, padx=(16, 8), pady=(16, 6), sticky="w")
    lv = tk.StringVar(value=bc["label"])
    ctk.CTkEntry(dlg, textvariable=lv, height=32, font=ctk.CTkFont(size=12)).grid(
        row=0, column=1, sticky="ew", padx=(0, 16), pady=(16, 6))

    ctk.CTkLabel(dlg, text="Mensagem:").grid(row=1, column=0, padx=(16, 8), pady=(0, 6), sticky="w")
    mv = tk.StringVar(value=bc["message"])
    ctk.CTkEntry(dlg, textvariable=mv, height=32, font=ctk.CTkFont(size=12)).grid(
        row=1, column=1, sticky="ew", padx=(0, 16), pady=(0, 6))

    def _save():
        new_label = lv.get().strip()
        new_msg = mv.get().strip()
        if not new_label or not new_msg:
            return
        srv.broadcasts[index] = {"label": new_label, "message": new_msg}
        app.config_manager.update_server(srv)
        app._broadcast_refresh_list(server_id)
        dlg.destroy()

    btn_fr = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_fr.grid(row=2, column=0, columnspan=2, pady=(4, 12), padx=16, sticky="e")
    ctk.CTkButton(btn_fr, text="Cancelar", width=90, height=30,
                  fg_color="gray30", hover_color="gray40",
                  command=dlg.destroy).pack(side="left", padx=(0, 8))
    ctk.CTkButton(btn_fr, text="💾 Salvar", width=100, height=30,
                  fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  command=_save).pack(side="left")

