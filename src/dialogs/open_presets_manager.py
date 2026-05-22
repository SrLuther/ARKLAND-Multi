from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _RED_DARK, _RED_HOVER, _CARD_BG
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def open_presets_manager(app: "ARKServerManagerApp") -> None:
    if not app._buff_manager:
        return

    dlg = ctk.CTkToplevel(app)
    dlg.title("Gerenciar Presets de BUFF")
    dlg.geometry("680x540")
    dlg.resizable(True, True)
    dlg.grab_set()
    dlg.grid_columnconfigure(0, weight=1)
    dlg.grid_rowconfigure(1, weight=1)

    ctk.CTkLabel(dlg, text="📋  Presets de BUFF",
                 font=ctk.CTkFont(size=18, weight="bold")).grid(
        row=0, column=0, padx=20, pady=(18, 4), sticky="w")

    def _rebuild() -> None:
        for w in list_frame.winfo_children():
            w.destroy()
        presets = app._buff_manager.get_presets() if app._buff_manager else []
        if not presets:
            ctk.CTkLabel(list_frame, text="Nenhum preset salvo.",
                         text_color="gray50").pack(pady=30)
            return
        for preset in presets:
            row_f = ctk.CTkFrame(list_frame, fg_color=_CARD_BG, corner_radius=10)
            row_f.pack(fill="x", padx=16, pady=4)
            row_f.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(row_f, text=preset.name,
                         font=ctk.CTkFont(size=13, weight="bold")).grid(
                row=0, column=0, padx=14, pady=(10, 2), sticky="w")
            types_str = "  ·  ".join(BUFF_TYPE_LABELS.get(t, t) for t in preset.types)
            ctk.CTkLabel(row_f, text=types_str, text_color="#ffaa44",
                         font=ctk.CTkFont(size=11)).grid(
                row=1, column=0, padx=14, pady=(0, 4), sticky="w")
            ctk.CTkLabel(row_f,
                         text=preset.rates.summary(),
                         text_color="gray55",
                         font=ctk.CTkFont(size=10),
                         wraplength=480, justify="left").grid(
                row=2, column=0, padx=14, pady=(0, 10), sticky="w")

            btn_f = ctk.CTkFrame(row_f, fg_color="transparent")
            btn_f.grid(row=0, column=1, rowspan=3, padx=14, pady=10)
            ctk.CTkButton(
                btn_f, text="🗑", width=40, height=34,
                fg_color=_RED_DARK, hover_color=_RED_HOVER,
                command=lambda pid=preset.id: _delete(pid),
            ).pack()

    def _delete(pid: str) -> None:
        if messagebox.askyesno("Excluir Preset", "Confirmar exclusão?", parent=dlg):
            if app._buff_manager:
                app._buff_manager.delete_preset(pid)
            _rebuild()

    list_frame = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
    list_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=4)
    _rebuild()

    ctk.CTkButton(dlg, text="Fechar", height=38,
                  fg_color="#2a2a44", hover_color="#1e2a3a",
                  command=dlg.destroy).grid(
        row=2, column=0, padx=20, pady=(4, 16), sticky="e")

