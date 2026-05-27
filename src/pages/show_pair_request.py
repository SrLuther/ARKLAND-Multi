from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _GREEN_DARK, _GREEN_HOVER, _RED_DARK, _RED_HOVER, _BG

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def show_pair_request_dialog(
    app: "ARKServerManagerApp", req_id: str, name: str, host: str
) -> None:
    """Exibe diálogo de autorização quando uma máquina LAN solicita conexão remota."""
    agent = app._remote_agent
    if not agent:
        return

    dlg = tk.Toplevel(app)
    dlg.title("Solicitação de Conexão Remota")
    dlg.geometry("440x210")
    dlg.configure(bg=_BG)
    dlg.attributes("-topmost", True)
    dlg.grab_set()
    dlg.resizable(False, False)

    ctk.CTkLabel(
        dlg, text="🔗  Solicitação de Acesso",
        font=ctk.CTkFont(size=15, weight="bold"),
    ).pack(pady=(20, 8))

    ctk.CTkLabel(
        dlg,
        text=f"A máquina  '{name}'  ({host})\nquer se conectar a este agente remotamente.",
        text_color="gray70",
        justify="center",
    ).pack(pady=(0, 4))

    ctk.CTkLabel(
        dlg, text="Autorizar o acesso completo a esta instância?",
        text_color="gray50", font=ctk.CTkFont(size=11),
    ).pack(pady=(0, 12))

    btn_fr = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_fr.pack()

    def _approve() -> None:
        agent.approve_pair(req_id)
        dlg.destroy()
        app._toast(f"✅  '{name}' autorizado.")

    def _deny() -> None:
        agent.deny_pair(req_id)
        dlg.destroy()
        app._toast(f"❌  '{name}' negado.")

    ctk.CTkButton(
        btn_fr, text="✅  Autorizar", height=36, width=130,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=_approve,
    ).pack(side="left", padx=(0, 10))

    ctk.CTkButton(
        btn_fr, text="❌  Negar", height=36, width=100,
        fg_color=_RED_DARK, hover_color=_RED_HOVER,
        command=_deny,
    ).pack(side="left")

    # Auto-nega após 60 s sem resposta
    def _auto_deny() -> None:
        if dlg.winfo_exists():
            _deny()

    dlg.after(60_000, _auto_deny)
