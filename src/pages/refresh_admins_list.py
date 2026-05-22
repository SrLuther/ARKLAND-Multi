from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _RED_DARK, _RED_HOVER
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def refresh_admins_list(app: "ARKServerManagerApp", server_id: str) -> None:
    srv = app.config_manager.get_server(server_id)
    w = app._server_widgets.get(server_id, {})
    frame: Optional[ctk.CTkScrollableFrame] = w.get("_admins_list_frame")
    if not frame or not srv:
        return
    for child in frame.winfo_children():
        child.destroy()
    if not srv.admin_ids:
        ctk.CTkLabel(
            frame,
            text="Nenhum admin configurado.\nAdicione um Steam ID acima.",
            text_color="gray50",
        ).pack(pady=20)
        return
    for steam_id in srv.admin_ids:
        row_fr = ctk.CTkFrame(frame, corner_radius=8, fg_color="#252535")
        row_fr.pack(fill="x", padx=8, pady=3)
        row_fr.grid_columnconfigure(0, weight=1)
        display_name = app._sanitize_steam_name(srv.admin_names.get(steam_id, ""))
        # Atualiza o dado persistido se estava corrompido
        if display_name != srv.admin_names.get(steam_id, ""):
            if display_name:
                srv.admin_names[steam_id] = display_name
            else:
                srv.admin_names.pop(steam_id, None)
            app.config_manager.update_server(srv)
        label_text = f"🎮  {steam_id}" + (f"  •  {display_name}" if display_name else "")
        ctk.CTkLabel(
            row_fr, text=label_text,
            font=ctk.CTkFont(size=13), anchor="w",
        ).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        ctk.CTkButton(
            row_fr, text="✕", width=32, height=28,
            fg_color=_RED_DARK, hover_color=_RED_HOVER,
            command=lambda sid=steam_id: app._remove_admin_id(server_id, sid),
        ).grid(row=0, column=1, padx=(0, 8), pady=4)

