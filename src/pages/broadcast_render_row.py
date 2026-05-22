from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _RED_DARK, _RED_HOVER, _BLUE, _BLUE_HOVER
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def broadcast_render_row(app: "ARKServerManagerApp", server_id: str, container, index: int, bc: dict, readonly: bool) -> None:
    """Cria uma linha de broadcast na lista."""
    bg = "#252535" if not readonly else "#1e1e2a"
    row = ctk.CTkFrame(container, fg_color=bg, corner_radius=6)
    row.pack(fill="x", padx=4, pady=2)
    row.grid_columnconfigure(1, weight=1)

    # Rótulo
    lbl_color = "#a0a8d0" if not readonly else "#606070"
    ctk.CTkLabel(row, text=bc.get("label", ""), text_color=lbl_color,
                 font=ctk.CTkFont(size=11, weight="bold"),
                 width=160, anchor="w", wraplength=155
                 ).grid(row=0, column=0, sticky="w", padx=(10, 6), pady=6)

    # Mensagem (truncada)
    msg_text = bc.get("message", "")
    display_msg = msg_text if len(msg_text) <= 80 else msg_text[:77] + "..."
    ctk.CTkLabel(row, text=display_msg, text_color="gray55",
                 font=ctk.CTkFont(size=11), anchor="w", wraplength=400
                 ).grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=6)

    # Botões
    btn_fr = ctk.CTkFrame(row, fg_color="transparent")
    btn_fr.grid(row=0, column=2, padx=(4, 8), pady=4)

    ctk.CTkButton(btn_fr, text="📢 Enviar", width=80, height=26,
                  fg_color=_BLUE, hover_color=_BLUE_HOVER,
                  font=ctk.CTkFont(size=10),
                  command=lambda m=msg_text, sid=server_id:
                      app._broadcast_rcon(sid, m)
                  ).pack(side="left", padx=(0, 4))

    if not readonly:
        ctk.CTkButton(btn_fr, text="✏", width=28, height=26,
                      fg_color="#3a3a5a", hover_color="#4a4a7a",
                      font=ctk.CTkFont(size=11),
                      command=lambda i=index, sid=server_id:
                          app._broadcast_edit(sid, i)
                      ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(btn_fr, text="🗑", width=28, height=26,
                      fg_color=_RED_DARK, hover_color=_RED_HOVER,
                      font=ctk.CTkFont(size=11),
                      command=lambda i=index, sid=server_id:
                          app._broadcast_delete(sid, i)
                      ).pack(side="left")

