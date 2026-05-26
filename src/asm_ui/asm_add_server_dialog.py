"""
TEK — Diálogo "Novo Servidor ASM".
Versão mínima: campos básicos para criar um AsmServerConfig.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import AsmServerConfig
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def asm_add_server_dialog(app: "ARKServerManagerApp") -> None:
    theme = get_theme("tek")
    accent  = theme["accent"]
    bg      = theme["bg"]
    card_bg = theme["card_bg"]

    dlg = ctk.CTkToplevel(app)
    dlg.title("TEK — Novo Servidor")
    dlg.geometry("480x320")
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.configure(fg_color=bg)

    ctk.CTkLabel(dlg, text="Novo Servidor TEK",
                 font=ctk.CTkFont(size=16, weight="bold"),
                 text_color=accent).pack(pady=(18, 4))

    form = ctk.CTkFrame(dlg, fg_color=card_bg, corner_radius=10)
    form.pack(fill="x", padx=24, pady=8)
    form.grid_columnconfigure(1, weight=1)

    def row(label: str, r: int, default: str = "") -> ctk.CTkEntry:
        ctk.CTkLabel(form, text=label, anchor="w",
                     font=ctk.CTkFont(size=12)).grid(row=r, column=0, padx=(14, 8), pady=6, sticky="w")
        e = ctk.CTkEntry(form, placeholder_text=default)
        e.grid(row=r, column=1, padx=(0, 14), pady=6, sticky="ew")
        return e

    e_name      = row("Nome no gerenciador",  0, "Meu Servidor TEK")
    e_session   = row("Nome da sessão (INI)", 1, "My ARK Server")
    e_dir       = row("Pasta de instalação",  2, "C:\\ARK\\")
    e_port      = row("Porta (game)",         3, "7777")
    e_query     = row("Porta (query)",        4, "27015")

    def _save() -> None:
        cfg = AsmServerConfig()
        cfg.name         = e_name.get().strip()    or "Servidor TEK"
        cfg.session_name = e_session.get().strip() or "My ARK Server"
        cfg.install_dir  = e_dir.get().strip()
        cfg.server_port  = int(e_port.get().strip() or 7777)
        cfg.query_port   = int(e_query.get().strip() or 27015)
        app.asm_config_manager.add_server(cfg)
        dlg.destroy()
        # Atualiza dashboard se estiver em modo TEK
        if app._active_mode == "tek":
            app._asm_refresh_dashboard()

    btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_row.pack(fill="x", padx=24, pady=(4, 16))

    ctk.CTkButton(btn_row, text="Cancelar", width=100,
                  fg_color=card_bg, hover_color="#1a2830",
                  command=dlg.destroy).pack(side="right", padx=(6, 0))
    ctk.CTkButton(btn_row, text="Criar Servidor", width=140,
                  fg_color="#0a4450", hover_color="#085a68",
                  border_width=1, border_color=accent, text_color=accent,
                  command=_save).pack(side="right")
