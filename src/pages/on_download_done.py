from __future__ import annotations
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def on_download_done(app: "ARKServerManagerApp", success: bool, message: str) -> None:
    if success:
        app._update_progress_label.configure(
            text="✅  Agente iniciado. O app será fechado e a atualização instalada automaticamente.")
        app._update_progress_label.grid(row=4, column=0, columnspan=2, padx=18, sticky="w")
        messagebox.showinfo(
            "Atualização",
            "O agente de atualização foi iniciado.\n\n"
            "O ARKLAND será fechado agora. Quando a instalação terminar, o app reiniciará automaticamente.",
            parent=app,
        )
        app._do_quit()
    else:
        app._check_update_btn.configure(state="normal")
        app._update_progress_label.configure(text=f"❌  Erro: {message}")
        app._update_progress_label.grid(row=4, column=0, columnspan=2, padx=18, sticky="w")
        app._install_update_btn.configure(state="normal", text="⬇️  Tentar Novamente")

