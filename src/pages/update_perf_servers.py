from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _STATUS_COLOR, _STATUS_LABEL
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def update_perf_servers(app: "ARKServerManagerApp", srv_stats: list) -> None:
    """Atualiza a tabela de consumo por servidor no painel de Desempenho."""
    inner = app._perf_servers_inner
    if not inner:
        return
    for w in list(inner.winfo_children()):
        w.destroy()
    if not srv_stats:
        ctk.CTkLabel(inner, text="Nenhum servidor configurado.",
                     text_color="gray55", font=ctk.CTkFont(size=12)
                     ).grid(row=0, column=0, padx=4, pady=4, sticky="w")
        return
    inner.grid_columnconfigure(0, weight=2)
    inner.grid_columnconfigure(1, weight=2)
    inner.grid_columnconfigure(2, weight=1)
    inner.grid_columnconfigure(3, weight=1)
    for ci, txt in enumerate(["Servidor", "Status", "CPU", "RAM"]):
        ctk.CTkLabel(inner, text=txt, text_color="gray50",
                     font=ctk.CTkFont(size=11, weight="bold")
                     ).grid(row=0, column=ci, padx=(8, 4), pady=(0, 4), sticky="w")
    for ri, (sid, name, status, cpu, mem) in enumerate(srv_stats, start=1):
        ctk.CTkLabel(inner, text=name, font=ctk.CTkFont(size=12),
                     text_color="gray80", anchor="w"
                     ).grid(row=ri, column=0, padx=(8, 4), pady=1, sticky="w")
        ctk.CTkLabel(inner, text=_STATUS_LABEL.get(status, status),
                     font=ctk.CTkFont(size=11),
                     text_color=_STATUS_COLOR.get(status, "gray60")
                     ).grid(row=ri, column=1, padx=(8, 4), pady=1, sticky="w")
        cpu_color = ("#ff4444" if (cpu or 0) > 90
                     else ("#ffaa44" if (cpu or 0) > 70 else "gray70"))
        ctk.CTkLabel(inner,
                     text="—" if cpu is None else f"{cpu:.1f}%",
                     font=ctk.CTkFont(size=12), text_color=cpu_color
                     ).grid(row=ri, column=2, padx=(8, 4), pady=1, sticky="w")
        mem_color = "#ffaa44" if (mem or 0) > 6 else "gray70"
        ctk.CTkLabel(inner,
                     text="—" if mem is None else f"{mem:.2f} GB",
                     font=ctk.CTkFont(size=12), text_color=mem_color
                     ).grid(row=ri, column=3, padx=(8, 4), pady=1, sticky="w")

