"""Troca o frame principal no modo TEK (com cache)."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import get_theme
if TYPE_CHECKING:
    from ..app_tek import ARKTEKApp


def _scrollable_inner(frame, bg: str) -> "ctk.CTkScrollableFrame":
    """Cria um CTkScrollableFrame filho que preenche `frame`."""
    scroll = ctk.CTkScrollableFrame(frame, fg_color=bg, corner_radius=0)
    scroll.grid(row=0, column=0, sticky="nsew")
    scroll.grid_columnconfigure(0, weight=1)
    return scroll


def _dispatch_tek_frame(app, name: str, frame, kwargs: dict) -> None:
    """Constrói o conteúdo correto dentro de `frame` com base em `name`."""
    bg = get_theme("tek")["bg"]
    if name == "dashboard":
        from ..asm_ui.asm_dashboard import build_asm_dashboard
        build_asm_dashboard(app, frame)
    elif name == "shop":
        from .customshop_panel import build_customshop_panel
        build_customshop_panel(app, frame)
    elif name == "database":
        from .db_manager_panel import build_db_manager_panel
        build_db_manager_panel(app, frame)
    elif name == "sync":
        from .build_sync_panel import build_sync_panel
        build_sync_panel(app, frame)
    elif name == "buffs":
        from .build_buffs_panel import build_buffs_panel
        build_buffs_panel(app, frame)
        if app._buff_manager is None:
            app._init_buff_manager()
        app._refresh_buffs_ui()
    elif name == "broadcasts":
        from ..asm_ui.asm_broadcasts_panel import build_broadcasts_panel
        build_broadcasts_panel(app, frame)
    elif name == "desempenho":
        from .performance_panel import build_performance_panel
        build_performance_panel(app, frame)
        app._start_perf_monitor()
    elif name == "clusters":
        from .build_clusters_panel import build_clusters_panel
        build_clusters_panel(app, frame)
    elif name == "remoto":
        from .remote_panel import build_remote_panel
        build_remote_panel(app, _scrollable_inner(frame, bg))
    elif name == "settings":
        from .global_config import build_global_config
        build_global_config(app, _scrollable_inner(frame, bg))
    elif name == "about":
        from .build_about import build_about
        build_about(app, _scrollable_inner(frame, bg))
    elif name == "crashes":
        from .global_crash_monitor import build_global_crash_monitor
        build_global_crash_monitor(app, frame)
    elif name == "server_panel":
        from ..asm_ui.asm_server_panel import build_asm_server_panel
        build_asm_server_panel(app, frame, kwargs["srv"])


def show_frame_tek(app, name: str, **kwargs) -> None:
    """Troca o conteúdo principal pelo frame indicado (com cache de frame)."""
    srv = kwargs.get("srv")
    cache_key = f"server_{srv.id}" if srv else name

    _static_nav = ("dashboard", "shop", "database", "broadcasts", "crashes", "settings", "about")
    app._set_nav_active(name if name in _static_nav else "")

    # ── Oculta frame corrente (preserva no cache) ─────────────────────────
    if app._current_frame:
        try:
            if app._current_frame.winfo_exists():
                app._current_frame.grid_remove()
        except Exception:
            pass

    # ── Reutiliza frame em cache ───────────────────────────────────────────
    if cache_key in app._frame_cache:
        cached = app._frame_cache[cache_key]
        try:
            if cached.winfo_exists():
                cached.grid()
                app._current_frame = cached
                # Callbacks de "on show" ainda são disparados mesmo com cache
                if name == "buffs":
                    if app._buff_manager is None:
                        app._init_buff_manager()
                    app._refresh_buffs_ui()
                elif name == "desempenho":
                    app._start_perf_monitor()
                elif name == "dashboard":
                    app._asm_refresh_dashboard(immediate=True)
                elif name == "clusters":
                    clusters = app.config_manager.clusters
                    if clusters and getattr(app, "_cluster_detail_fr", None):
                        try:
                            if not app._cluster_detail_fr.winfo_children():
                                from .cluster_select import cluster_select
                                cid = app._cluster_selected_id
                                valid = {c.id for c in clusters}
                                if cid not in valid:
                                    cid = clusters[0].id
                                cluster_select(app, cid)
                        except Exception:
                            pass
                return
        except Exception:
            pass
        app._frame_cache.pop(cache_key, None)

    # ── Constrói novo frame ───────────────────────────────────────────────
    frame = ctk.CTkFrame(app._page_area, fg_color=get_theme("tek")["bg"],
                         corner_radius=0)
    frame.grid(row=0, column=0, sticky="nsew")
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)
    app._current_frame = frame
    app._frame_cache[cache_key] = frame

    _dispatch_tek_frame(app, name, frame, kwargs)

    # Watermark em todas as páginas, atrás do conteúdo
    app._apply_watermark_to_frame(frame)

