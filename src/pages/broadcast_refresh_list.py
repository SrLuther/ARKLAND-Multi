from __future__ import annotations
import time
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def broadcast_refresh_list(app: "ARKServerManagerApp", server_id: str) -> None:
    """Reconstrói a lista visual de broadcasts da biblioteca."""
    w = app._server_widgets.get(server_id, {})
    scroll = w.get("bc_list_scroll")
    if scroll is None:
        return
    for ch in scroll.winfo_children():
        ch.destroy()

    srv = app.config_manager.get_server(server_id)
    bcs = srv.broadcasts if srv else []

    # Broadcasts do sistema (tarefas agendadas com warn > 0 — somente leitura)
    sys_entries = []
    if srv:
        for task in srv.scheduled_tasks:
            wm = task.get("warn_minutes", 0)
            if wm and wm > 0:
                action_map = {"restart": "Reiniciar", "stop": "Desligar",
                              "update_restart": "Atualizar + Reiniciar"}
                action_lbl = action_map.get(task.get("action", ""), task.get("action", ""))
                t_time = task.get("time", "??:??")
                sys_entries.append({
                    "label": f"[Auto] Aviso {action_lbl} às {t_time}",
                    "message": f"⚠ Servidor será {action_lbl} em {wm} minuto(s)!",
                })
        # MOTD como broadcast
        if srv.motd:
            sys_entries.append({
                "label": "[Auto] MOTD",
                "message": srv.motd,
            })

    if not bcs and not sys_entries:
        ctk.CTkLabel(scroll,
                     text="Nenhum broadcast salvo.\n"
                          "Adicione um usando o formulário acima.",
                     text_color="gray40", font=ctk.CTkFont(size=11),
                     justify="center").pack(pady=24)
        return

    # Cabeçalho de colunas
    hdr = ctk.CTkFrame(scroll, fg_color="transparent")
    hdr.pack(fill="x", padx=4, pady=(4, 0))
    hdr.grid_columnconfigure(0, weight=0, minsize=160)
    hdr.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(hdr, text="Rótulo", text_color="gray45",
                 font=ctk.CTkFont(size=10, weight="bold")).grid(row=0, column=0, sticky="w", padx=4)
    ctk.CTkLabel(hdr, text="Mensagem", text_color="gray45",
                 font=ctk.CTkFont(size=10, weight="bold")).grid(row=0, column=1, sticky="w", padx=8)

    # Broadcasts do usuário
    for idx, bc in enumerate(bcs):
        app._broadcast_render_row(server_id, scroll, idx, bc, readonly=False)

    # Broadcasts do sistema
    if sys_entries:
        ctk.CTkLabel(scroll, text="Broadcasts automáticos do sistema",
                     text_color="gray40", font=ctk.CTkFont(size=10, weight="bold")
                     ).pack(anchor="w", padx=8, pady=(12, 2))
        for bc in sys_entries:
            app._broadcast_render_row(server_id, scroll, -1, bc, readonly=True)

