from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING, Optional
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _MAX_SYNC_CYCLES, _MAX_SYNC_FOLDERS, _RED_DARK
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def add_sync_cycle(app: "ARKServerManagerApp", initial_paths: "Optional[list]" = None) -> None:
    """Adiciona um card de ciclo no painel de sincronização."""
    if len(app._sync_cycle_vars) >= _MAX_SYNC_CYCLES:
        return
    folder_vars: List[tk.StringVar] = []
    app._sync_cycle_vars.append(folder_vars)
    cycle_num = len(app._sync_cycle_vars)

    card = ctk.CTkFrame(app._sync_cycles_frame, corner_radius=8, fg_color="#17172a")
    card.grid(row=cycle_num - 1, column=0, padx=4, pady=(0, 8), sticky="ew")
    card.grid_columnconfigure(0, weight=1)

    # Título + botão remover ciclo
    th = ctk.CTkFrame(card, fg_color="transparent")
    th.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
    th.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(th, text=f"Ciclo {cycle_num}",
                 font=ctk.CTkFont(size=12, weight="bold"),
                 text_color="gray60").grid(row=0, column=0, sticky="w")
    ctk.CTkButton(
        th, text="🗑", width=30, height=24,
        fg_color="transparent", hover_color=_RED_DARK, text_color="gray50",
        command=lambda c=card, fv=folder_vars: app._remove_sync_cycle(c, fv),
    ).grid(row=0, column=1, sticky="e")

    # Container das linhas de pasta (pack facilita remoção individual)
    folders_frame = ctk.CTkFrame(card, fg_color="transparent")
    folders_frame.grid(row=1, column=0, padx=8, pady=0, sticky="ew")

    # Botão "+ Pasta" (criado antes para ser passado aos helpers)
    add_folder_btn = ctk.CTkButton(
        card, text="＋  Pasta", height=26, width=100,
        fg_color="transparent", hover_color="#363656",
        border_width=1, border_color="#363656")
    add_folder_btn.configure(
        command=lambda ff=folders_frame, fv=folder_vars, ab=add_folder_btn:
            app._add_sync_folder(ff, fv, ab))
    add_folder_btn.grid(row=2, column=0, padx=8, pady=(4, 8), sticky="w")

    # Popula pastas iniciais
    paths = initial_paths if initial_paths else [""]
    for p in paths[:_MAX_SYNC_FOLDERS]:
        app._add_sync_folder(folders_frame, folder_vars, add_folder_btn, str(p))

    app._refresh_add_cycle_btn()

