from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import (_GREEN, _GREEN_DARK, _GREEN_HOVER, _RED_DARK, _RED_HOVER,
                             _BLUE, _BLUE_HOVER, _CARD_BG, _STATUS_COLOR, _STATUS_LABEL)
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig
from ..server_config import ARK_MAP_NAMES, SERVER_STATUS_CRASHED, SERVER_STATUS_RUNNING, SERVER_STATUS_STARTING, SERVER_STATUS_STOPPED, SERVER_STATUS_STOPPING


def build_server_card(app: "ARKServerManagerApp", parent, srv: "ServerConfig", row: int, col: int) -> None:
    inst = app.server_manager.get_instance(srv.id)
    status = inst.status if inst else SERVER_STATUS_STOPPED
    color = _STATUS_COLOR.get(status, "#ff6666")
    status_txt = _STATUS_LABEL.get(status, "PARADO")

    card = ctk.CTkFrame(parent, corner_radius=14, fg_color=_CARD_BG, border_width=1,
                        border_color="#2a2a44")
    card.grid(row=row, column=col, padx=8, pady=8, sticky="ew")
    card.grid_columnconfigure(0, weight=1)

    top = ctk.CTkFrame(card, fg_color="transparent")
    top.grid(row=0, column=0, padx=16, pady=(14, 4), sticky="ew")
    top.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(top, text=srv.name,
                 font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, sticky="w")

    vis_mode  = inst.online_mode if inst else "—"
    vis_text  = "🌐 WAN" if vis_mode == "WAN" else ("🏠 LAN" if vis_mode == "LAN" else "")
    vis_color = _GREEN if vis_mode == "WAN" else ("#ffaa44" if vis_mode == "LAN" else "gray50")
    if vis_text:
        ctk.CTkLabel(top, text=vis_text, text_color=vis_color,
                     font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=1, padx=(0, 8), sticky="e")

    ctk.CTkLabel(top, text=status_txt, text_color=color,
                 font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=2, sticky="e")

    map_name = ARK_MAP_NAMES.get(srv.map, srv.map)
    info_lines = [
        f"🗺  {map_name}",
        f"🔌  Porta: {srv.server_port}  |  Query: {srv.query_port}",
    ]
    # Contagem de jogadores via BattleMetrics (quando disponível) ou máximo configurado
    if inst and inst.bm_players is not None and inst.bm_max_players:
        info_lines.append(f"👥  Jogadores: {inst.bm_players}/{inst.bm_max_players}")
    else:
        info_lines.append(f"👥  Máx Jogadores: {srv.max_players}")
    if srv.mods:
        info_lines.append(f"🔧  Mods: {len(srv.mods)}")
    if inst and hasattr(inst, "uptime") and inst.uptime != "—":
        info_lines.append(f"⏱  Uptime: {inst.uptime}")

    ctk.CTkLabel(card, text="\n".join(info_lines),
                 text_color="gray60", justify="left",
                 font=ctk.CTkFont(size=12)).grid(
        row=1, column=0, padx=16, pady=(0, 10), sticky="w")

    btn_row = ctk.CTkFrame(card, fg_color="transparent")
    btn_row.grid(row=2, column=0, padx=12, pady=(0, 14), sticky="ew")

    is_running = status == SERVER_STATUS_RUNNING
    is_busy    = status in (SERVER_STATUS_STARTING, SERVER_STATUS_STOPPING)
    is_crashed = status == SERVER_STATUS_CRASHED

    if is_busy:
        _d_text, _d_fg, _d_hover = "⚡ Cancelar", "#7a4a00", "#5c3600"
        def _d_cmd(sid=srv.id): app.server_manager.stop_server(sid, force=True)
    elif is_crashed:
        _d_text, _d_fg, _d_hover = "💀 Forçar Enc.", _RED_DARK, _RED_HOVER
        def _d_cmd(sid=srv.id): app.server_manager.stop_server(sid, force=True)
    elif is_running:
        _d_text, _d_fg, _d_hover = "⏹ Parar", _RED_DARK, _RED_HOVER
        def _d_cmd(sid=srv.id): app._stop_server(sid)
    else:
        _d_text, _d_fg, _d_hover = "▶ Iniciar", _GREEN_DARK, _GREEN_HOVER
        def _d_cmd(sid=srv.id): app._start_server(sid)

    ctk.CTkButton(
        btn_row, text=_d_text, width=100, height=32,
        fg_color=_d_fg, hover_color=_d_hover,
        command=_d_cmd,
    ).pack(side="left", padx=(0, 6))

    ctk.CTkButton(
        btn_row, text="🔄 Restart", width=90, height=32,
        fg_color="#3a3a5a", hover_color="#252540",
        state="disabled" if is_busy or is_crashed or not is_running else "normal",
        command=lambda sid=srv.id: app._restart_server(sid),
    ).pack(side="left", padx=(0, 6))

    ctk.CTkButton(
        btn_row, text="⚙ Configurar", width=110, height=32,
        fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=lambda sid=srv.id: app._open_server_panel(sid),
    ).pack(side="right")

