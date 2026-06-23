"""
TEK — Card de servidor para o dashboard ASM.
Layout: cabeçalho com badge de status, chips de info inline,
linha de ações primárias com divisor e barra de ferramentas separada.
"""
from __future__ import annotations

import time
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import (
    AsmServerConfig,
    ASM_STATUS_STOPPED, ASM_STATUS_STARTING, ASM_STATUS_RUNNING,
    ASM_STATUS_STOPPING, ASM_STATUS_CRASHED, ASM_STATUS_UPDATING,
)
from ..server_visibility import format_status_badge, STEAM_UNAVAILABLE
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

_STATUS_COLOR = {
    ASM_STATUS_STOPPED:  "#64748b",
    ASM_STATUS_STARTING: "#f59e0b",
    ASM_STATUS_RUNNING:  "#22c55e",
    ASM_STATUS_STOPPING: "#f59e0b",
    ASM_STATUS_CRASHED:  "#ef4444",
    ASM_STATUS_UPDATING: "#38bdf8",
}
_STATUS_LABEL = {
    ASM_STATUS_STOPPED:  "PARADO",
    ASM_STATUS_STARTING: "INICIANDO",
    ASM_STATUS_RUNNING:  "ONLINE",
    ASM_STATUS_STOPPING: "PARANDO",
    ASM_STATUS_CRASHED:  "TRAVADO",
    ASM_STATUS_UPDATING: "ATUALIZANDO",
}

ARK_MAP_LABELS: dict[str, str] = {
    "TheIsland":        "The Island",
    "TheCenter":        "The Center",
    "ScorchedEarth_P":  "Scorched Earth",
    "Ragnarok":         "Ragnarok",
    "Aberration_P":     "Aberration",
    "Extinction":       "Extinction",
    "Valguero_P":       "Valguero",
    "Genesis":          "Genesis",
    "CrystalIsles":     "Crystal Isles",
    "Gen2":             "Genesis 2",
    "Fjordur":          "Fjordur",
    "LostIsland":       "Lost Island",
}


def build_asm_server_card(app: "ARKServerManagerApp", parent: tk.Widget,
                          srv: AsmServerConfig, row: int, col: int) -> None:
    th      = get_theme("tek")
    accent  = th["accent"]
    card_bg = th["card_bg"]
    sep     = th["separator"]
    hover   = th["accent_hover"]
    acc_mb  = th["accent_muted_bg"]
    acc_dk  = th["accent_dark"]
    t_pri   = th["text_primary"]
    t_sec   = th["text_secondary"]
    t_mut   = th["text_muted"]
    is_light = th.get("_is_light", False)
    chip_bg  = th.get("chip_bg", "#0a1525")
    chip_bdr = th.get("chip_border", sep)
    inset_bg = th.get("inset_bg", "#0f172a")
    card_bdr = th.get("card_border", sep)
    toolbar_bg = th.get("toolbar_bg", "#080e18")
    toolbar_bdr = th.get("toolbar_border", "#0d1929")

    inst       = app.asm_server_manager.get_instance(srv.id)
    status     = inst.status if inst else ASM_STATUS_STOPPED
    steam_st   = getattr(inst, "steam_status", STEAM_UNAVAILABLE) if inst else STEAM_UNAVAILABLE
    status_txt, color = format_status_badge(status, steam_st)
    is_running = status == ASM_STATUS_RUNNING
    is_busy    = status in (ASM_STATUS_STARTING, ASM_STATUS_STOPPING, ASM_STATUS_UPDATING)
    is_crashed = status == ASM_STATUS_CRASHED
    rcon_ready = is_running and srv.rcon_enabled and bool(srv.admin_password)

    custom_color = getattr(srv, "color", "") or ""
    border_col = (
        custom_color if custom_color
        else "#166534" if is_running
        else "#7f1d1d" if is_crashed
        else "#78350f" if is_busy
        else sep
    )

    # ── Card ──────────────────────────────────────────────────────────────────
    card = ctk.CTkFrame(parent, corner_radius=10, fg_color=card_bg,
                        border_width=1, border_color=border_col)
    card.grid(row=row, column=col, padx=8, pady=6, sticky="ew")
    card.grid_columnconfigure(0, weight=1)

    # ── CABEÇALHO: checkbox + dot + nome + badge ─────────────────────────────
    hdr = ctk.CTkFrame(card, fg_color="transparent")
    hdr.grid(row=0, column=0, padx=14, pady=(12, 6), sticky="ew")
    hdr.grid_columnconfigure(2, weight=1)

    # Checkbox de seleção individual
    if not hasattr(app, "_asm_selected_servers"):
        app._asm_selected_servers: set = set()

    sel_var = tk.BooleanVar(value=srv.id in app._asm_selected_servers)

    def _toggle_select():
        if sel_var.get():
            app._asm_selected_servers.add(srv.id)
        else:
            app._asm_selected_servers.discard(srv.id)

    ctk.CTkCheckBox(
        hdr, text="", variable=sel_var, width=20, height=20,
        checkbox_width=16, checkbox_height=16,
        checkmark_color=accent, border_color=sep,
        fg_color=acc_mb, hover_color=acc_mb,
        command=_toggle_select,
    ).grid(row=0, column=0, padx=(0, 6))

    dot_col = custom_color if custom_color else color
    tk.Label(hdr, text="●", fg=dot_col, bg=card_bg,
             font=("Segoe UI", 13)).grid(row=0, column=1, padx=(0, 8))

    name_lbl = ctk.CTkLabel(
        hdr, text=srv.name,
        font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
        text_color=t_pri, cursor="hand2",
    )
    name_lbl.grid(row=0, column=2, sticky="w")

    def _start_rename(event=None) -> None:
        name_lbl.grid_remove()
        v = tk.StringVar(value=srv.name)
        e = ctk.CTkEntry(hdr, textvariable=v,
                         font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                         height=28, border_color=accent)
        e.grid(row=0, column=2, sticky="ew", padx=(0, 4))
        e.focus_set()
        e.select_range(0, "end")

        def _commit(_=None) -> None:
            n = v.get().strip()
            if n and n != srv.name:
                srv.name = n
                app.asm_config_manager.save()
                app._rebuild_server_sidebar()
            e.grid_remove()
            name_lbl.configure(text=srv.name)
            name_lbl.grid()

        def _cancel(_=None) -> None:
            e.grid_remove()
            name_lbl.grid()

        e.bind("<Return>", _commit)
        e.bind("<Escape>", _cancel)
        e.bind("<FocusOut>", _commit)

    name_lbl.bind("<Double-Button-1>", _start_rename)

    # Badge de status
    _badge_cfg = (
        {
            "running": ("#dcfce7", "#166534"),
            "crashed": ("#fee2e2", "#991b1b"),
            "busy":    ("#fef3c7", "#92400e"),
            "stopped": ("#f1f5f9", "#64748b"),
        } if is_light else {
            "running": ("#052e16", "#4ade80"),
            "crashed": ("#450a0a", "#f87171"),
            "busy":    ("#431407", "#fbbf24"),
            "stopped": ("#111827", "#475569"),
        }
    )
    bk = ("running" if is_running else "crashed" if is_crashed
          else "busy" if is_busy else "stopped")
    b_bg, b_tc = _badge_cfg[bk]

    # Ações rápidas no cabeçalho (sempre visíveis — evita sumiço abaixo da dobra)
    if is_running or is_busy:
        qa = ctk.CTkFrame(hdr, fg_color="transparent")
        qa.grid(row=0, column=3, sticky="e", padx=(4, 0))
        if is_running:
            ctk.CTkButton(
                qa, text="⏹", width=34, height=28,
                fg_color="#7f1d1d", hover_color="#450a0a",
                text_color="#fca5a5", corner_radius=6,
                font=ctk.CTkFont(size=12),
                command=lambda sid=srv.id: app._asm_stop_server(sid),
            ).pack(side="left", padx=(0, 3))
            ctk.CTkButton(
                qa, text="🔄", width=34, height=28,
                fg_color="#0f172a", hover_color="#1e3a5f",
                text_color=t_sec, corner_radius=6,
                border_width=1, border_color=sep,
                font=ctk.CTkFont(size=11),
                command=lambda s=srv: app._asm_restart_server(s),
            ).pack(side="left", padx=(0, 3))
        ctk.CTkButton(
            qa, text="⚙", width=34, height=28,
            fg_color=acc_mb, hover_color=acc_dk,
            text_color=accent, corner_radius=6,
            border_width=1, border_color=acc_dk,
            font=ctk.CTkFont(size=12),
            command=lambda sid=srv.id: app._asm_open_server_panel(sid),
        ).pack(side="left")

    badge = ctk.CTkFrame(hdr, fg_color=b_bg, corner_radius=5)
    badge.grid(row=0, column=4 if (is_running or is_busy) else 3, sticky="e")
    tk.Label(badge, text="●", fg=b_tc, bg=b_bg,
             font=("Segoe UI", 7)).pack(side="left", padx=(8, 3), pady=5)
    ctk.CTkLabel(
        badge, text=status_txt,
        font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
        text_color=b_tc,
    ).pack(side="left", padx=(0, 8), pady=5)

    # ── CHIPS DE INFO ─────────────────────────────────────────────────────────
    map_label = ARK_MAP_LABELS.get(srv.server_map, srv.server_map)
    info_r = ctk.CTkFrame(card, fg_color="transparent")
    info_r.grid(row=1, column=0, padx=14, pady=(0, 4), sticky="w")

    def _chip(text: str, border: str = chip_bdr, tc: str = t_mut) -> None:
        f = ctk.CTkFrame(info_r, fg_color=chip_bg,
                         corner_radius=4, border_width=1, border_color=border)
        f.pack(side="left", padx=(0, 4))
        ctk.CTkLabel(f, text=text,
                     font=ctk.CTkFont(family="Segoe UI", size=10),
                     text_color=tc).pack(padx=6, pady=2)

    _chip(f"🗺  {map_label}", tc=t_sec)
    _chip(f"🔌  :{srv.server_port}")
    _chip(f"🔍  :{srv.query_port}")
    if srv.rcon_enabled:
        _chip(f"🖥  :{srv.rcon_port}",
              border="#1e3a5f" if is_running else sep,
              tc="#7dd3fc" if is_running else t_mut)
    if srv.active_mods:
        _chip(f"🔧  {len(srv.active_mods)} mods", border="#1e3a5f", tc="#7dd3fc")

    if is_running and steam_st not in (STEAM_UNAVAILABLE, STEAM_UNKNOWN):
        from ..server_visibility import steam_chip
        vis_label, vis_color = steam_chip(steam_st)
        _chip(f"📡  {vis_label}", border=vis_color, tc=vis_color)

    # ── AÇÕES PRIMÁRIAS (logo abaixo dos chips — prioridade sobre stats) ───────
    act = ctk.CTkFrame(card, fg_color="transparent")
    act.grid(row=2, column=0, padx=14, pady=(4, 6), sticky="ew")

    if is_running:
        ctk.CTkButton(
            act, text="⏹  Parar", width=96, height=34,
            fg_color="#7f1d1d", hover_color="#450a0a",
            text_color="#fca5a5", corner_radius=7,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=lambda sid=srv.id: app._asm_stop_server(sid),
        ).pack(side="left", padx=(0, 4))
    else:
        ctk.CTkButton(
            act, text="▶  Iniciar", width=96, height=34,
            fg_color=acc_mb if is_busy else ("#dcfce7" if is_light else "#052e16"),
            hover_color=hover if is_busy else ("#bbf7d0" if is_light else "#14532d"),
            text_color=t_mut if is_busy else ("#166534" if is_light else "#4ade80"),
            corner_radius=7,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            state="disabled" if is_busy else "normal",
            command=lambda s=srv: app._asm_start_server(s),
        ).pack(side="left", padx=(0, 2))
        if srv.active_mods and not is_busy:
            ctk.CTkButton(
                act, text="⚡", width=26, height=34,
                fg_color="#dcfce7" if is_light else "#0b1e10",
                hover_color="#bbf7d0" if is_light else "#14532d",
                text_color="#166534" if is_light else "#4ade80",
                corner_radius=7,
                border_width=1,
                border_color="#86efac" if is_light else "#166634",
                font=ctk.CTkFont(size=11),
                command=lambda s=srv: app._asm_start_server(s, no_mods=True),
            ).pack(side="left", padx=(0, 4))
        else:
            tk.Frame(act, width=6, bg=card_bg).pack(side="left")

    ctk.CTkButton(
        act, text="🔄  Restart", width=94, height=34,
        fg_color="#f1f5f9" if is_light else "#0f172a",
        hover_color="#e2e8f0" if is_light else "#1e3a5f",
        text_color=t_mut if (is_busy or not is_running) else t_sec,
        border_width=1, border_color=sep,
        corner_radius=7,
        font=ctk.CTkFont(family="Segoe UI", size=11),
        state="disabled" if (is_busy or not is_running) else "normal",
        command=lambda s=srv: app._asm_restart_server(s),
    ).pack(side="left", padx=(0, 4))

    ctk.CTkButton(
        act, text="⚙  Configurar", width=108, height=34,
        fg_color=acc_mb, hover_color=acc_dk,
        text_color=accent, border_width=1, border_color=acc_dk,
        corner_radius=7,
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        command=lambda sid=srv.id: app._asm_open_server_panel(sid),
    ).pack(side="left", padx=(0, 14))

    tk.Frame(act, width=1, bg=sep).pack(side="left", fill="y", padx=(0, 12), pady=4)

    rcon_color  = "#0369a1" if (is_light and rcon_ready) else ("#7dd3fc" if rcon_ready else t_mut)
    rcon_border = ("#7dd3fc" if rcon_ready else "#cbd5e1") if is_light else ("#1e3a5f" if rcon_ready else "#111827")
    rcon_bg     = ("#e0f2fe" if rcon_ready else "#f8fafc") if is_light else ("#071526" if rcon_ready else "#090f1a")
    rcon_hover  = "#bae6fd" if is_light else "#1e3a5f"

    ctk.CTkButton(
        act, text="🖥  RCON", width=82, height=34,
        fg_color=rcon_bg, hover_color=rcon_hover,
        text_color=rcon_color, border_width=1, border_color=rcon_border,
        corner_radius=7, font=ctk.CTkFont(family="Segoe UI", size=11),
        state="normal" if rcon_ready else "disabled",
        command=lambda s=srv: app._asm_open_rcon(s),
    ).pack(side="left", padx=(0, 4))

    ctk.CTkButton(
        act, text="👥  Players", width=84, height=34,
        fg_color=rcon_bg, hover_color=rcon_hover,
        text_color=rcon_color, border_width=1, border_color=rcon_border,
        corner_radius=7, font=ctk.CTkFont(family="Segoe UI", size=11),
        state="normal" if rcon_ready else "disabled",
        command=lambda s=srv: app._asm_open_player_list(s),
    ).pack(side="left", padx=(0, 0))

    # ── INDICADORES RICOS (jogadores, uptime, RAM, versão) ─────────────────
    rich_r = ctk.CTkFrame(
        card,
        fg_color=inset_bg,
        corner_radius=8,
        border_width=1,
        border_color=card_bdr,
    )
    rich_r.grid(row=3, column=0, padx=14, pady=(0, 8), sticky="ew")

    rich_key = f"_asm_rich_status_{srv.id}"
    rich_data: dict = getattr(app, rich_key, {})

    players_txt = rich_data.get("players", "—")
    uptime_txt  = rich_data.get("uptime", "—")
    ram_txt     = rich_data.get("ram", "—")
    ver_txt     = rich_data.get("version", "—")

    _val_tc = accent if is_running else t_sec
    _val_font = ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
    _hint_font = ctk.CTkFont(family="Segoe UI", size=10)

    for icon, val, hint in (
        ("👥", players_txt, "Jogadores"),
        ("🕐", uptime_txt, "Uptime"),
        ("💾", ram_txt, "Memória"),
        ("📋", ver_txt, "Versão"),
    ):
        chip = ctk.CTkFrame(rich_r, fg_color="transparent")
        chip.pack(side="left", padx=(12, 16), pady=10)
        ctk.CTkLabel(
            chip, text=f"{icon}  {val}",
            font=_val_font, text_color=_val_tc,
        ).pack(anchor="w")
        ctk.CTkLabel(
            chip, text=hint,
            font=_hint_font, text_color=t_mut,
        ).pack(anchor="w", pady=(2, 0))

    # ── SEPARADOR ─────────────────────────────────────────────────────────────
    ctk.CTkFrame(card, height=1, fg_color=sep).grid(
        row=4, column=0, sticky="ew", padx=14, pady=0)

    # ── BARRA DE FERRAMENTAS ──────────────────────────────────────────────────
    _tbg     = toolbar_bg
    _tborder = toolbar_bdr
    _thover  = th.get("nav_hover", "#162032") if not is_light else th.get("card_hover", "#e0f2fe")
    _tlabel  = t_mut if is_light else "#1e3a5f"

    tools = ctk.CTkFrame(card, fg_color=_tbg, corner_radius=7,
                         border_width=1, border_color=_tborder)
    tools.grid(row=5, column=0, sticky="ew", padx=10, pady=(8, 10))

    def _tbtn(text: str, cmd, width: int = 82) -> None:
        ctk.CTkButton(
            tools, text=text, width=width, height=26,
            fg_color="transparent", hover_color=_thover,
            text_color=t_sec,
            corner_radius=5,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=cmd,
        ).pack(side="left", padx=(0, 1))

    ctk.CTkLabel(
        tools, text="FERRAMENTAS",
        font=ctk.CTkFont(family="Segoe UI", size=8, weight="bold"),
        text_color=_tlabel,
    ).pack(side="left", padx=(10, 6), pady=5)

    tk.Frame(tools, width=1, bg=_tborder).pack(
        side="left", fill="y", padx=(0, 6), pady=4)

    _tbtn("💾  Backup",   lambda s=srv: app._asm_open_save_restore(s))
    _tbtn("🔧  Mods",     lambda s=srv: app._asm_open_workshop(s), width=72)
    _tbtn("📁  Arquivos", lambda s=srv: app._asm_open_file_manager(s))
    _tbtn("🔒  Firewall", lambda s=srv: app._asm_open_firewall(s))
    _tbtn("📊  Perf",     lambda s=srv: app._asm_open_perf(s), width=68)
    _tbtn("📜  Tribe Log",lambda s=srv: app._asm_open_tribe_log(s))
    _tbtn("🦕  SpawnExact", lambda s=srv: app._asm_open_spawn_exact(s), width=90)
    _tbtn("🔬  Log",      lambda s=srv: app._asm_open_server_log(s), width=58)
    _tbtn("📡  Monitor",  lambda s=srv: app._asm_open_monitor(s))
    _tbtn("🤖  IA",       lambda s=srv: app._asm_open_ai_assistant(s), width=58)


