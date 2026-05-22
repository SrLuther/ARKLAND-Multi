from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _RED_DARK, _RED_HOVER, _BLUE, _BLUE_HOVER
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def refresh_backup_list(app: "ARKServerManagerApp", server_id: str) -> None:
    srv = app.config_manager.get_server(server_id)
    w   = app._server_widgets.get(server_id, {})
    frame: Optional[ctk.CTkScrollableFrame] = w.get("_backup_list_frame")
    if not frame or not srv:
        return

    for child in frame.winfo_children():
        child.destroy()

    entries = app._backup_manager.list_backups(srv) if app._backup_manager else []

    if not entries:
        ctk.CTkLabel(
            frame,
            text="Nenhum backup encontrado.\nClique em 📸 Fazer Backup Agora para criar o primeiro.",
            text_color="gray50",
        ).pack(pady=20)
        return

    for entry in entries:
        row_fr = ctk.CTkFrame(frame, corner_radius=8, fg_color="#252535")
        row_fr.pack(fill="x", padx=8, pady=3)
        row_fr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            row_fr, text=entry.label,
            anchor="w", font=ctk.CTkFont(family="Courier New", size=11),
        ).grid(row=0, column=0, padx=12, pady=8, sticky="ew")

        btn_fr = ctk.CTkFrame(row_fr, fg_color="transparent")
        btn_fr.grid(row=0, column=1, padx=(0, 8))

        ep = str(entry.path)
        ctk.CTkButton(
            btn_fr, text="↩ Restaurar", width=100, height=28,
            fg_color=_BLUE, hover_color=_BLUE_HOVER,
            command=lambda p=ep, sid=server_id: app._confirm_restore_backup(sid, p),
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            btn_fr, text="🗑", width=36, height=28,
            fg_color=_RED_DARK, hover_color=_RED_HOVER,
            command=lambda p=ep, sid=server_id: app._confirm_delete_backup(sid, p),
        ).pack(side="left")

