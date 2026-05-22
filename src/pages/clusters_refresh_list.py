from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _CARD_BG
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def clusters_refresh_list(app: "ARKServerManagerApp") -> None:
    """Atualiza o painel esquerdo com os perfis de cluster existentes."""
    for w in app._cluster_list_box.winfo_children():
        w.destroy()

    clusters = app.config_manager.clusters
    if not clusters:
        ctk.CTkLabel(app._cluster_list_box, text="Nenhum perfil criado.",
                     text_color="gray50", font=ctk.CTkFont(size=11)).grid(
            row=0, column=0, padx=12, pady=16)

        # Detecta servidores com cluster manual sem perfil vinculado
        _manual = [s for s in app.config_manager.servers
                   if getattr(s.cluster, "enabled", False)
                   and getattr(s.cluster, "cluster_id", "")
                   and not s.cluster_profile_id]
        if _manual:
            _warn_fr = ctk.CTkFrame(app._cluster_list_box,
                                    fg_color="#3a2800", corner_radius=8)
            _warn_fr.grid(row=1, column=0, padx=4, pady=(4, 0), sticky="ew")
            _warn_fr.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                _warn_fr,
                text=f"⚠️  {len(_manual)} servidor(es) com\ncluster manual detectado(s).",
                text_color="#ffb74d", font=ctk.CTkFont(size=11),
                justify="left", anchor="w",
            ).grid(row=0, column=0, padx=10, pady=(8, 2), sticky="w")
            ctk.CTkButton(
                _warn_fr, text="Importar como Perfil →",
                height=28, fg_color="#7a5000", hover_color="#a06800",
                font=ctk.CTkFont(size=11),
                command=app._cluster_import_from_manual,
            ).grid(row=1, column=0, padx=10, pady=(2, 8), sticky="w")
        return

    for i, prof in enumerate(clusters):
        mode_icon = "🖥" if prof.mode == "local" else "🌐"
        row_fr = ctk.CTkFrame(app._cluster_list_box,
                              fg_color=_CARD_BG if prof.id == app._cluster_selected_id else "transparent",
                              corner_radius=8)
        row_fr.grid(row=i, column=0, padx=4, pady=2, sticky="ew")
        row_fr.grid_columnconfigure(0, weight=1)
        btn = ctk.CTkButton(
            row_fr,
            text=f"{mode_icon}  {prof.name}",
            anchor="w", fg_color="transparent", hover_color="#252540",
            text_color="#d8d8e8", height=34,
            command=lambda pid=prof.id: app._cluster_select(pid),
        )
        btn.grid(row=0, column=0, sticky="ew", padx=2)

