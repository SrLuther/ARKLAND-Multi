"""Inicia um servidor ASM com validação de config e conflito de portas."""
from __future__ import annotations
from tkinter import messagebox
from typing import TYPE_CHECKING
from ..asm_engine.asm_config import AsmServerConfig
if TYPE_CHECKING:
    from ..app_tek import ARKTEKApp


def asm_start_server(app: "ARKTEKApp", srv: AsmServerConfig, no_mods: bool = False) -> None:

    errors = app._validate_server_config(srv)
    if errors:
        msg = "\n\n".join(f"• {e}" for e in errors)
        messagebox.showerror(
            "Configuração Incompleta",
            f"Não é possível iniciar '{srv.name}':\n\n{msg}\n\n"
            "Corrija as configurações antes de iniciar o servidor.",
            parent=app,
        )
        return

    conflicts = app._check_port_conflicts(srv)
    if conflicts:
        msg = "\n".join(f"• Porta {p} ({label}) já está em uso" for p, label in conflicts)
        messagebox.showwarning(
            "Conflito de Portas",
            f"Não é possível iniciar '{srv.name}':\n\n{msg}\n\n"
            "Verifique se outro processo está usando essas portas.",
            parent=app,
        )
        return
    cfg = srv
    if no_mods and srv.active_mods:
        import copy
        cfg = copy.copy(srv)
        cfg.active_mods = []
    app.asm_server_manager.start(
        cfg,
        on_done=lambda ok, msg: app.after(0, app._asm_refresh_dashboard),
    )
    app._asm_refresh_dashboard()

