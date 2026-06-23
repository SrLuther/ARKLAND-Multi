from __future__ import annotations

from typing import TYPE_CHECKING

from tkinter import messagebox

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp

from .broadcast_profile_io import get_library, set_library


def broadcast_library_delete(app: "ARKServerManagerApp", entry_id: str) -> None:
    lib = get_library(app)
    entry = next((e for e in lib if str(e.get("id")) == entry_id), None)
    if not entry:
        return
    if not messagebox.askyesno(
        "Remover broadcast",
        f"Remover «{entry.get('label', '')}» da biblioteca?",
        parent=app,
    ):
        return
    lib = [e for e in lib if str(e.get("id")) != entry_id]
    set_library(app, lib)
