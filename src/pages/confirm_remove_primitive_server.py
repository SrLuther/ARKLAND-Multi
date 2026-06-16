from __future__ import annotations

from typing import TYPE_CHECKING

from tkinter import messagebox

if TYPE_CHECKING:
    pass


def confirm_remove_primitive_server(app, server_id: str) -> None:
    """Remove servidor legado (primitivo) — disponível no app TEK."""
    from ..buff_server_bridge import remove_primitive_server

    srv = app.config_manager.get_server(server_id)
    name = srv.name if srv else server_id
    if not messagebox.askyesno(
        "Remover Servidor Legado",
        f"Remover '{name}' do gerenciador?\n\n"
        "Os arquivos na pasta de instalação NÃO serão apagados.",
        parent=app,
    ):
        return

    remove_primitive_server(app, server_id)

    if hasattr(app, "_refresh_buffs_ui"):
        try:
            app._refresh_buffs_ui()
        except Exception:
            pass

    messagebox.showinfo(
        "Servidor removido",
        f"'{name}' foi removido da lista de servidores legados.",
        parent=app,
    )

    # Reabre configurações para atualizar a lista
    if hasattr(app, "_show_frame"):
        try:
            app._show_frame("settings")
        except Exception:
            pass
