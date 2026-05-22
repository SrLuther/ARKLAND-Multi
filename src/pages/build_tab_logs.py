from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig


def build_tab_logs(app: "ARKServerManagerApp", parent, srv: "ServerConfig") -> None:
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(1, weight=1)

    w = app._server_widgets[srv.id]

    hdr = ctk.CTkFrame(parent, fg_color="transparent")
    hdr.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
    hdr.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(hdr, text=f"Logs do Servidor — {srv.name}",
                 font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w")
    ctk.CTkButton(hdr, text="🗑 Limpar", width=90, height=30,
                  fg_color="#3a3a5a", hover_color="#252540",
                  command=lambda: app._clear_server_log(srv.id)).grid(
        row=0, column=1, sticky="e")

    log_box = ctk.CTkTextbox(
        parent, font=ctk.CTkFont(family="Courier New", size=11),
        wrap="word", state="disabled", fg_color="#0a0a14",
    )
    log_box.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
    tw = log_box._textbox
    tw.tag_config("info",    foreground="#d0d0e0")
    tw.tag_config("warning", foreground="#ffaa44")
    tw.tag_config("error",   foreground="#ff6666")
    tw.tag_config("debug",   foreground="#555570")
    w["_log_box"] = log_box

