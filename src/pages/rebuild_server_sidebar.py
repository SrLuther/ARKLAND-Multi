from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _STATUS_COLOR
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..server_config import SERVER_STATUS_STOPPED


def rebuild_server_sidebar(app: "ARKServerManagerApp") -> None:
    """Atualiza a lista de botões de servidores na sidebar.

    Se os IDs já existem, apenas atualiza nome e cor do dot (evita
    destruir+recriar todos os widgets a cada salvamento).
    """
    servers = app.config_manager.servers
    current_ids = [s.id for s in servers]
    existing_ids = list(app._sidebar_server_btns.keys())

    # Verifica se a lista mudou (adição/remoção/reordenação)
    if current_ids != existing_ids:
        # Rebuild completo somente quando necessário
        for w in app._servers_list_sb.winfo_children():
            w.destroy()
        app._sidebar_server_btns.clear()

        if not servers:
            ctk.CTkLabel(app._servers_list_sb, text="Nenhum servidor.\nClique ＋ para adicionar.",
                         text_color="gray50", font=ctk.CTkFont(size=11), justify="center").pack(
                pady=10)
            return

        for srv in servers:
            inst = app.server_manager.get_instance(srv.id)
            status = inst.status if inst else SERVER_STATUS_STOPPED
            color = _STATUS_COLOR.get(status, "#ff6666")

            btn_frame = ctk.CTkFrame(app._servers_list_sb, fg_color="transparent")
            btn_frame.pack(fill="x", pady=2)
            btn_frame.grid_columnconfigure(0, weight=1)

            btn = ctk.CTkButton(
                btn_frame,
                text=f"  {srv.name}",
                anchor="w", height=36, corner_radius=8,
                fg_color="transparent", text_color="#d8d8e8",
                hover_color="#252540",
                command=lambda sid=srv.id: app._open_server_panel(sid),
            )
            btn.grid(row=0, column=0, sticky="ew")

            status_dot = ctk.CTkLabel(btn_frame, text="●", text_color=color,
                                       font=ctk.CTkFont(size=10), width=18)
            status_dot.grid(row=0, column=1, padx=(0, 4))

            app._sidebar_server_btns[srv.id] = btn
            btn._status_dot = status_dot  # type: ignore[attr-defined]
    else:
        # Lista igual — apenas atualiza nome e cor sem recriar widgets
        for srv in servers:
            btn = app._sidebar_server_btns.get(srv.id)
            if not btn:
                continue
            btn.configure(text=f"  {srv.name}")
            inst = app.server_manager.get_instance(srv.id)
            status = inst.status if inst else SERVER_STATUS_STOPPED
            color = _STATUS_COLOR.get(status, "#ff6666")
            dot = getattr(btn, "_status_dot", None)
            if dot:
                try:
                    dot.configure(text_color=color)
                except Exception:
                    pass

