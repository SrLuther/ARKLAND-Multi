from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import (
    _GREEN, _GREEN_DARK, _GREEN_HOVER,
    _RED_DARK, _RED_HOVER,
    _CARD_BG, _SIDEBAR_BG,
    _STATUS_COLOR, _STATUS_LABEL,
)

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig
from ..server_config import SERVER_STATUS_CRASHED, SERVER_STATUS_RUNNING, SERVER_STATUS_STARTING, SERVER_STATUS_STOPPED, SERVER_STATUS_STOPPING


def build_server_panel(app: "ARKServerManagerApp", parent: "ctk.CTkFrame", srv: "ServerConfig") -> None:
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(3, weight=1)  # row 3 = tabs
    app._config_search_index[srv.id] = []

    # Cabeçalho
    hdr = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=0, height=64)
    hdr.grid(row=0, column=0, sticky="ew")
    hdr.grid_propagate(False)
    hdr.grid_columnconfigure(1, weight=1)

    ctk.CTkButton(
        hdr, text="◀", width=36, height=36,
        fg_color="transparent", hover_color="#252540",
        command=lambda: app._show_frame("dashboard"),
    ).grid(row=0, column=0, padx=(12, 0), pady=14)

    inst = app.server_manager.get_instance(srv.id)
    status = inst.status if inst else SERVER_STATUS_STOPPED

    app._server_widgets[srv.id]["_name_title_var"] = tk.StringVar(value=srv.name)
    ctk.CTkLabel(
        hdr, textvariable=app._server_widgets[srv.id]["_name_title_var"],
        font=ctk.CTkFont(size=20, weight="bold"),
    ).grid(row=0, column=1, padx=8, pady=14, sticky="w")

    # ── Progresso de instalação/validação (vazio por padrão) ─────────────
    install_progress_var = tk.StringVar(value="")
    ctk.CTkLabel(
        hdr, textvariable=install_progress_var,
        text_color="#fbbf24",
        font=ctk.CTkFont(size=13, weight="bold"),
    ).grid(row=0, column=2, padx=(0, 16), pady=14, sticky="w")
    app._server_widgets[srv.id]["_install_progress_var"] = install_progress_var

    status_var = tk.StringVar(value=_STATUS_LABEL.get(status, "PARADO"))
    status_lbl = ctk.CTkLabel(
        hdr, textvariable=status_var,
        text_color=_STATUS_COLOR.get(status, "#ff6666"),
        font=ctk.CTkFont(size=13, weight="bold"),
    )
    status_lbl.grid(row=0, column=3, padx=12, pady=14)
    app._server_widgets[srv.id]["_status_var"] = status_var
    app._server_widgets[srv.id]["_status_lbl"] = status_lbl

    # Badge de visibilidade LAN/WAN (preenchido pelo callback _on_server_visibility_change)
    inst_now = app.server_manager.get_instance(srv.id)
    vis_mode = inst_now.online_mode if inst_now and hasattr(inst_now, "online_mode") else "—"
    vis_text  = "🌐 WAN" if vis_mode == "WAN" else ("🏠 LAN" if vis_mode == "LAN" else "")
    vis_color = _GREEN if vis_mode == "WAN" else ("#ffaa44" if vis_mode == "LAN" else "gray50")
    vis_lbl = ctk.CTkLabel(
        hdr, text=vis_text, text_color=vis_color,
        font=ctk.CTkFont(size=12, weight="bold"),
    )
    vis_lbl.grid(row=0, column=4, padx=(0, 4), pady=14)
    app._server_widgets[srv.id]["_visibility_lbl"] = vis_lbl

    # Badge de jogadores via BattleMetrics
    _bm_inst = app.server_manager.get_instance(srv.id)
    _bm_txt = (
        f"👥 {_bm_inst.bm_players}/{_bm_inst.bm_max_players}"
        if _bm_inst and _bm_inst.bm_players is not None and _bm_inst.bm_max_players
        else ""
    )
    bm_players_lbl = ctk.CTkLabel(
        hdr, text=_bm_txt, text_color="#60c0ff",
        font=ctk.CTkFont(size=12, weight="bold"),
    )
    bm_players_lbl.grid(row=0, column=5, padx=(0, 8), pady=14)
    app._server_widgets[srv.id]["_bm_players_lbl"] = bm_players_lbl

    ctrl = ctk.CTkFrame(hdr, fg_color="transparent")
    ctrl.grid(row=0, column=6, padx=(0, 16), pady=14)

    is_running = status == SERVER_STATUS_RUNNING
    is_busy    = status in (SERVER_STATUS_STARTING, SERVER_STATUS_STOPPING)

    def _toggle_server() -> None:
        inst = app.server_manager.get_instance(srv.id)
        if not inst:
            return
        if inst.status == SERVER_STATUS_RUNNING:
            app._stop_server(srv.id)
        elif inst.status in (SERVER_STATUS_STARTING, SERVER_STATUS_STOPPING,
                              SERVER_STATUS_CRASHED):
            app.server_manager.stop_server(srv.id, force=True)
        else:
            app._start_server(srv.id)

    if is_busy:
        _ss_text   = "⚡ Cancelar"
        _ss_fg     = "#7a4a00"
        _ss_hover  = "#5c3600"
    elif is_running:
        _ss_text   = "⏹ Parar"
        _ss_fg     = _RED_DARK
        _ss_hover  = _RED_HOVER
    else:
        _ss_text   = "▶ Iniciar"
        _ss_fg     = _GREEN_DARK
        _ss_hover  = _GREEN_HOVER

    start_stop_btn = ctk.CTkButton(
        ctrl,
        text=_ss_text, width=110, height=34,
        fg_color=_ss_fg, hover_color=_ss_hover,
        command=_toggle_server,
    )
    start_stop_btn.pack(side="left", padx=(0, 6))
    app._server_widgets[srv.id]["_start_stop_btn"] = start_stop_btn

    ctk.CTkButton(
        ctrl, text="🔄", width=36, height=34,
        fg_color="#3a3a5a", hover_color="#252540",
        command=lambda: app._restart_server(srv.id),
    ).pack(side="left", padx=(0, 6))

    ctk.CTkButton(
        ctrl, text="🗑 Remover", width=100, height=34,
        fg_color=_RED_DARK, hover_color=_RED_HOVER,
        command=lambda: app._confirm_remove_server(srv.id),
    ).pack(side="left")

    # Banner de bloqueio (visível apenas quando servidor não está parado)
    lock_banner = ctk.CTkFrame(parent, fg_color="#3a1a00", corner_radius=0, height=32)
    lock_banner.grid(row=2, column=0, sticky="ew")
    lock_banner.grid_propagate(False)
    lock_banner.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(
        lock_banner,
        text="🔒  Configurações bloqueadas — pare o servidor para editar",
        text_color="#ffaa44", font=ctk.CTkFont(size=12, weight="bold"),
    ).grid(row=0, column=0, pady=6)
    app._server_widgets[srv.id]["_lock_banner"] = lock_banner
    is_stopped = status == SERVER_STATUS_STOPPED
    if is_stopped:
        lock_banner.grid_remove()

    # Abas
    app._build_config_search_bar(parent, srv.id)
    tabs = ctk.CTkTabview(
        parent, fg_color=_CARD_BG, corner_radius=12,
        segmented_button_fg_color=_SIDEBAR_BG,
        segmented_button_selected_color=_GREEN_DARK,
        segmented_button_selected_hover_color=_GREEN_HOVER,
    )
    tabs.grid(row=3, column=0, padx=14, pady=12, sticky="nsew")
    app._server_widgets[srv.id]["_tabs"] = tabs

    _TAB_BUILDERS = {
        "Geral":        lambda: app._build_tab_general    (tabs.tab("Geral"),        srv),
        "Jogo":         lambda: app._build_tab_game       (tabs.tab("Jogo"),         srv),
        "Avançado":     lambda: app._build_tab_advanced   (tabs.tab("Avançado"),     srv),
        "Spawns":       lambda: app._build_tab_spawns     (tabs.tab("Spawns"),       srv),
        "Loot":         lambda: app._build_tab_loot       (tabs.tab("Loot"),         srv),
        "Mods":         lambda: app._build_tab_mods       (tabs.tab("Mods"),         srv),
        "Plugins":      lambda: app._build_tab_plugins    (tabs.tab("Plugins"),      srv),
        "📝 INI":       lambda: app._build_tab_ini_mods   (tabs.tab("📝 INI"),       srv),
        "Admins":       lambda: app._build_tab_admins     (tabs.tab("Admins"),       srv),
        "Jogadores":    lambda: app._build_tab_jogadores  (tabs.tab("Jogadores"),    srv),
        "Console RCON": lambda: app._build_tab_rcon       (tabs.tab("Console RCON"), srv),
        "💬 Chat":      lambda: app._build_tab_chat       (tabs.tab("💬 Chat"),      srv),
        "Logs":         lambda: app._build_tab_logs       (tabs.tab("Logs"),         srv),
        "📋 Histórico": lambda: app._build_tab_historico  (tabs.tab("📋 Histórico"), srv),
        "Backup":       lambda: app._build_tab_backup     (tabs.tab("Backup"),       srv),
        "🔴 Crashes":   lambda: app._build_tab_crashes    (tabs.tab("🔴 Crashes"),   srv),
    }
    _built_tabs: set[str] = set()

    def _on_tab_change() -> None:
        name = tabs.get()
        if name not in _built_tabs:
            _built_tabs.add(name)
            # Exibe placeholder "Carregando..." centrado na aba antes de construir
            tab_frame = tabs.tab(name)
            _loading = ctk.CTkLabel(
                tab_frame, text="⏳  Carregando...",
                font=("Segoe UI", 13), text_color="#55556a",
            )
            _loading.place(relx=0.5, rely=0.5, anchor="center")
            tab_frame.update_idletasks()

            def _do_build(n=name, lbl=_loading) -> None:
                try:
                    lbl.destroy()
                except Exception:
                    pass
                _TAB_BUILDERS[n]()
                # Se o servidor não estiver parado, bloqueia os novos widgets
                inst_chk = app.server_manager.get_instance(srv.id)
                if inst_chk and inst_chk.status != SERVER_STATUS_STOPPED:
                    app.after(50, lambda: app._set_config_editable(srv.id, False))

            app.after(25, _do_build)

    for tab_name in _TAB_BUILDERS:
        tabs.add(tab_name)
    tabs.configure(command=_on_tab_change)
    # Armazena o callback para que a barra de busca possa acioná-lo ao navegar via tabs.set()
    app._server_widgets[srv.id]["_on_tab_change"] = _on_tab_change

    # Constrói apenas a aba inicial (Geral) imediatamente
    _built_tabs.add("Geral")
    app._build_tab_general(tabs.tab("Geral"), srv)

    # Todas as abas são construídas sob demanda (lazy) na primeira visita.
    # Sem pre-build em background para não travar a navegação.

    # Aplicar estado inicial de bloqueio se servidor não estiver parado
    if not is_stopped:
        app.after(100, lambda: app._set_config_editable(srv.id, False))

