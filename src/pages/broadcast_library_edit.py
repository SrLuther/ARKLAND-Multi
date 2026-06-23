from __future__ import annotations

import tkinter as tk
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]
from tkinter import messagebox

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp

from .broadcast_profile_io import get_library, normalize_entry, set_library


def broadcast_library_edit(app: "ARKServerManagerApp", entry_id: str) -> None:
    lib = get_library(app)
    idx = next((i for i, e in enumerate(lib) if str(e.get("id")) == entry_id), None)
    if idx is None:
        return

    entry = lib[idx]
    dlg = ctk.CTkToplevel(app)
    dlg.title("Editar broadcast")
    dlg.geometry("520x220")
    dlg.transient(app)
    dlg.grab_set()

    label_var = tk.StringVar(value=entry.get("label", ""))
    msg_var = tk.StringVar(value=entry.get("message", ""))

    ctk.CTkLabel(dlg, text="Rótulo:").pack(anchor="w", padx=16, pady=(16, 4))
    ctk.CTkEntry(dlg, textvariable=label_var).pack(fill="x", padx=16)
    ctk.CTkLabel(dlg, text="Mensagem:").pack(anchor="w", padx=16, pady=(12, 4))
    ctk.CTkEntry(dlg, textvariable=msg_var).pack(fill="x", padx=16)

    def _save() -> None:
        label = label_var.get().strip()
        msg = msg_var.get().strip()
        if not label or not msg:
            messagebox.showwarning("Campos obrigatórios", "Preencha rótulo e mensagem.", parent=dlg)
            return
        updated = normalize_entry({
            **entry,
            "label": label,
            "message": msg,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        lib[idx] = updated
        set_library(app, lib)
        dlg.destroy()
        app._broadcast_library_refresh()

    btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_row.pack(fill="x", padx=16, pady=16)
    ctk.CTkButton(btn_row, text="Salvar", command=_save).pack(side="right", padx=(8, 0))
    ctk.CTkButton(btn_row, text="Cancelar", command=dlg.destroy).pack(side="right")
