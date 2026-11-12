"""Read-only viewer for a TEK server's safe configuration audit history."""
from __future__ import annotations

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_change_history import get_asm_change_logger
from ..asm_engine.asm_server_config import AsmServerConfig


def open_asm_change_history(app, srv: AsmServerConfig) -> None:
    win = ctk.CTkToplevel(app)
    win.title(f"Histórico de alterações — {srv.name}")
    win.geometry("760x520")
    win.grid_columnconfigure(0, weight=1)
    win.grid_rowconfigure(1, weight=1)
    ctk.CTkLabel(
        win,
        text="Registro local do perfil TEK. Senhas, tokens e texto INI bruto são omitidos.",
        anchor="w",
    ).grid(row=0, column=0, padx=12, pady=10, sticky="ew")
    text = ctk.CTkTextbox(win, wrap="word", font=ctk.CTkFont(family="Consolas", size=11))
    text.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="nsew")
    rows = get_asm_change_logger(srv.id).read_all()
    if not rows:
        text.insert("1.0", "Nenhuma alteração registrada ainda.")
    else:
        lines = [
            f"{row.get('ts', '')} | {row.get('label', '')}\n"
            f"  Antes: {row.get('old', '')}\n"
            f"  Depois: {row.get('new', '')}\n"
            for row in rows[:500]
        ]
        text.insert("1.0", "\n".join(lines))
    text.configure(state="disabled")
