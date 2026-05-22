from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def historico_refresh(app: "ARKServerManagerApp", server_id: str, filter_var: "tk.StringVar") -> None:
    """Recarrega e exibe as entradas do histórico."""
    w = app._server_widgets.get(server_id, {})
    tw = w.get("_historico_tw")
    if tw is None:
        return
    logger = app._get_change_logger(server_id)
    entries = logger.read_all()

    f_tab = filter_var.get() if filter_var.get() != "Todas as abas" else None
    if f_tab:
        entries = [e for e in entries if e.get("tab") == f_tab]

    tw.configure(state="normal")
    tw.delete("1.0", "end")

    if not entries:
        tw.insert("end", "\n  Nenhuma alteração registrada ainda.\n\n", "empty")
        tw.insert("end", "  As configurações são registradas automaticamente\n"
                         "  cada vez que você salva o servidor (💾 Salvar).\n", "empty")
    else:
        for entry in entries:
            tw.insert("end", f"[{entry.get('ts','??')}]", "ts")
            tw.insert("end", f"  {entry.get('tab','?')}", "tab")
            tw.insert("end", f"  ›  {entry.get('label','?')}", "label")
            tw.insert("end", "   ", "arrow")
            tw.insert("end", entry.get("old", ""), "old")
            tw.insert("end", " → ", "arrow")
            tw.insert("end", entry.get("new", ""), "new")
            tw.insert("end", "\n")
    tw.configure(state="disabled")

