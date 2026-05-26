from __future__ import annotations
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import get_theme
from ..ui_components import FastScrollFrame

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def _plain(app: "ARKServerManagerApp", bg: str) -> ctk.CTkFrame:
    """Frame simples sem scroll — parente = _page_area."""
    f = ctk.CTkFrame(app._page_area, corner_radius=0, fg_color=bg)
    f.grid(row=0, column=0, sticky="nsew")
    f.grid_columnconfigure(0, weight=1)
    # Não configura rowconfigure aqui — cada builder define seus próprios pesos
    return f


def _scrollable(app: "ARKServerManagerApp", bg: str) -> tuple:
    """Frame externo + FastScrollFrame interno — retorna (frame_host, inner).
    frame_host é guardado em app._frames; builder recebe inner (tk.Frame).
    """
    host = ctk.CTkFrame(app._page_area, corner_radius=0, fg_color=bg)
    host.grid(row=0, column=0, sticky="nsew")
    host.grid_columnconfigure(0, weight=1)
    host.grid_rowconfigure(0, weight=1)
    sf = FastScrollFrame(host, bg=bg)
    sf.grid(row=0, column=0, sticky="nsew")
    return host, sf.inner


def build_static_frames(app: "ARKServerManagerApp") -> None:
    """Constrói todos os frames estáticos.

    O Dashboard muda conforme o modo; as demais páginas são compartilhadas.
    """
    theme = get_theme(app._active_mode)
    bg = theme["bg"]

    # ── Dashboard (diferente por modo) ────────────────────────────────────────
    dash = _plain(app, bg)
    if app._active_mode == "tek":
        from ..asm_ui.asm_dashboard import build_asm_dashboard
        build_asm_dashboard(app, dash)
    else:
        app._build_dashboard(dash)
    app._frames["dashboard"] = dash
    dash.grid_remove()

    # ── Páginas compartilhadas (iguais em ambos os modos) ─────────────────────
    sync = _plain(app, bg)
    app._build_sync_panel(sync)
    app._frames["sync"] = sync
    sync.grid_remove()

    buffs = _plain(app, bg)
    app._build_buffs_panel(buffs)
    app._frames["buffs"] = buffs
    buffs.grid_remove()

    desemp, desemp_inner = _scrollable(app, bg)
    app._build_performance_panel(desemp_inner)
    app._frames["desempenho"] = desemp
    desemp.grid_remove()

    clusters = _plain(app, bg)
    app._build_clusters_panel(clusters)
    app._frames["clusters"] = clusters
    clusters.grid_remove()

    conf, conf_inner = _scrollable(app, bg)
    app._build_global_config(conf_inner)
    app._frames["config"] = conf
    conf.grid_remove()

    remoto, remoto_inner = _scrollable(app, bg)
    app._build_remote_panel(remoto_inner)
    app._frames["remoto"] = remoto
    remoto.grid_remove()

    sobre, sobre_inner = _scrollable(app, bg)
    app._build_about(sobre_inner)
    app._frames["sobre"] = sobre
    sobre.grid_remove()

