from __future__ import annotations
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _BG
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_static_frames(app: "ARKServerManagerApp") -> None:
    dash = ctk.CTkFrame(app, corner_radius=0, fg_color=_BG)
    dash.grid(row=0, column=1, sticky="nsew")
    app._build_dashboard(dash)
    app._frames["dashboard"] = dash
    dash.grid_remove()

    sync = ctk.CTkFrame(app, corner_radius=0, fg_color=_BG)
    sync.grid(row=0, column=1, sticky="nsew")
    app._build_sync_panel(sync)
    app._frames["sync"] = sync
    sync.grid_remove()

    buffs = ctk.CTkFrame(app, corner_radius=0, fg_color=_BG)
    buffs.grid(row=0, column=1, sticky="nsew")
    app._build_buffs_panel(buffs)
    app._frames["buffs"] = buffs
    buffs.grid_remove()

    desemp = ctk.CTkScrollableFrame(app, corner_radius=0, fg_color=_BG)
    desemp.grid(row=0, column=1, sticky="nsew")
    app._build_performance_panel(desemp)
    app._frames["desempenho"] = desemp
    desemp.grid_remove()

    clusters = ctk.CTkFrame(app, corner_radius=0, fg_color=_BG)
    clusters.grid(row=0, column=1, sticky="nsew")
    app._build_clusters_panel(clusters)
    app._frames["clusters"] = clusters
    clusters.grid_remove()

    conf = ctk.CTkScrollableFrame(app, corner_radius=0, fg_color=_BG)
    conf.grid(row=0, column=1, sticky="nsew")
    app._build_global_config(conf)
    app._frames["config"] = conf
    conf.grid_remove()

    remoto = ctk.CTkScrollableFrame(app, corner_radius=0, fg_color=_BG)
    remoto.grid(row=0, column=1, sticky="nsew")
    app._build_remote_panel(remoto)
    app._frames["remoto"] = remoto
    remoto.grid_remove()

    sobre = ctk.CTkScrollableFrame(app, corner_radius=0, fg_color=_BG)
    sobre.grid(row=0, column=1, sticky="nsew")
    app._build_about(sobre)
    app._frames["sobre"] = sobre
    sobre.grid_remove()

