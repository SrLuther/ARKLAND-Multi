from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _GREEN_DARK, _GREEN_HOVER, _BG, _SIDEBAR_BG
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_clusters_panel(app: "ARKServerManagerApp", parent: "ctk.CTkFrame") -> None:
    parent.grid_columnconfigure(0, weight=0)
    parent.grid_columnconfigure(1, weight=1)
    parent.grid_rowconfigure(1, weight=1)

    # ── Cabeçalho ─────────────────────────────────────────────────────────
    hdr = ctk.CTkFrame(parent, fg_color="transparent")
    hdr.grid(row=0, column=0, columnspan=2, padx=24, pady=(20, 8), sticky="ew")
    hdr.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(hdr, text="🔗  Clusters Cross-ARK",
                 font=ctk.CTkFont(size=22, weight="bold")).grid(
        row=0, column=0, sticky="w")
    ctk.CTkLabel(
        hdr,
        text=(
            "Gerencie perfis de cluster para conectar múltiplos servidores (mesmo app) "
            "ou máquinas diferentes na rede via pasta compartilhada."
        ),
        text_color="gray55", font=ctk.CTkFont(size=12),
    ).grid(row=1, column=0, sticky="w", pady=(2, 0))

    # ── Lista à esquerda ──────────────────────────────────────────────────
    list_fr = ctk.CTkFrame(parent, fg_color=_SIDEBAR_BG, corner_radius=12, width=220)
    list_fr.grid(row=1, column=0, padx=(20, 6), pady=(0, 20), sticky="nsew")
    list_fr.grid_propagate(False)
    list_fr.grid_rowconfigure(1, weight=1)
    list_fr.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(list_fr, text="PERFIS", font=ctk.CTkFont(size=10, weight="bold"),
                 text_color="gray50").grid(row=0, column=0, padx=14, pady=(12, 4), sticky="w")

    app._cluster_list_box = ctk.CTkScrollableFrame(list_fr, fg_color="transparent")
    app._cluster_list_box.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
    app._cluster_list_box.grid_columnconfigure(0, weight=1)

    add_btn = ctk.CTkButton(
        list_fr, text="＋  Novo Cluster", height=34,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        font=ctk.CTkFont(size=12, weight="bold"),
        command=app._cluster_new,
    )
    add_btn.grid(row=2, column=0, padx=10, pady=10, sticky="ew")

    # ── Detalhe à direita ─────────────────────────────────────────────────
    app._cluster_detail_fr = ctk.CTkScrollableFrame(parent, fg_color=_BG)
    app._cluster_detail_fr.grid(row=1, column=1, padx=(0, 20), pady=(0, 20), sticky="nsew")
    app._cluster_detail_fr.grid_columnconfigure(0, weight=1)

    app._cluster_selected_id: str = ""
    app._cluster_detail_widgets: dict = {}

    app._clusters_refresh_list()

