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
                          srv: AsmServerConfig, row: int, col: int) -> ctk.CTkFrame:
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
    info_r.grid(row=1, column=0, padx=10, pady=(0, 4), sticky="ew")

    def _chip(text: str, border: str = chip_bdr, tc: str = t_mut) -> None:
        f = ctk.CTkFrame(info_r, fg_color=chip_bg,
                         corner_radius=4, border_width=1, border_color=border)
        f.pack(side="left", padx=(0, 4))
        ctk.CTkLabel(f, text=text,
                     font=ctk.CTkFont(family="Segoe UI", size=10),
                     text_color=tc).pack(padx=6, pady=2)

    _chip(f"🗺  {map_label}", tc=t_sec)
    rcon_port = srv.rcon_port if srv.rcon_enabled else "—"
    _chip(f"P/Q/R  {srv.server_port}/{srv.query_port}/{rcon_port}")
    if srv.active_mods:
        _chip(f"🔧  {len(srv.active_mods)} mods", border="#1e3a5f", tc="#7dd3fc")
    # ── DESLIGAMENTO AGENDADO (countdown + cancelar) ─────────────────────────
    shutdown_row = ctk.CTkFrame(card, fg_color="transparent")
    shutdown_row.grid(row=2, column=0, padx=14, pady=(0, 4), sticky="ew")
    card._asm_shutdown_row = shutdown_row  # type: ignore[attr-defined]
    card._asm_shutdown_countdown_lbl = None  # type: ignore[attr-defined]
    _build_shutdown_row(app, card, srv, shutdown_row, is_running)

    # ── AÇÕES PRIMÁRIAS (logo abaixo dos chips — prioridade sobre stats) ───────
    act = ctk.CTkFrame(card, fg_color="transparent")
    act.grid(row=3, column=0, padx=10, pady=(3, 5), sticky="ew")
    primary_row = ctk.CTkFrame(act, fg_color="transparent")
    primary_row.pack(fill="x")
    quick_row = ctk.CTkFrame(act, fg_color="transparent")
    quick_row.pack(fill="x", pady=(3, 0))

    ctk.CTkButton(
        primary_row, text="▶ Iniciar", width=70, height=30,
        fg_color=acc_mb if is_busy else ("#dcfce7" if is_light else "#052e16"),
        hover_color=hover if is_busy else ("#bbf7d0" if is_light else "#14532d"),
        text_color=t_mut if (is_busy or is_running) else ("#166534" if is_light else "#4ade80"),
        corner_radius=7,
        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        state="disabled" if (is_busy or is_running) else "normal",
        command=lambda s=srv: app._asm_start_server(s),
    ).pack(side="left", padx=(0, 3))

    ctk.CTkButton(
        primary_row, text="⏹ Parar", width=70, height=30,
        fg_color="#7f1d1d", hover_color="#450a0a",
        text_color="#fca5a5" if is_running and not is_busy else t_mut,
        corner_radius=7,
        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        state="normal" if is_running and not is_busy else "disabled",
        command=lambda sid=srv.id: app._asm_stop_server(sid),
    ).pack(side="left", padx=(0, 3))

    ctk.CTkButton(
        primary_row, text="↻ Reiniciar", width=82, height=30,
        fg_color="#f1f5f9" if is_light else "#0f172a",
        hover_color="#e2e8f0" if is_light else "#1e3a5f",
        text_color=t_mut if (is_busy or not is_running) else t_sec,
        border_width=1, border_color=sep,
        corner_radius=7,
        font=ctk.CTkFont(family="Segoe UI", size=10),
        state="disabled" if (is_busy or not is_running) else "normal",
        command=lambda s=srv: app._asm_restart_server(s),
    ).pack(side="left", padx=(0, 4))

    ctk.CTkButton(
        primary_row, text="⚙ Config", width=92, height=30,
        fg_color=acc_mb, hover_color=acc_dk,
        text_color=accent, border_width=1, border_color=acc_dk,
        corner_radius=7,
        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        command=lambda sid=srv.id: app._asm_open_server_panel(sid),
    ).pack(side="left")

    rcon_color  = "#0369a1" if (is_light and rcon_ready) else ("#7dd3fc" if rcon_ready else t_mut)
    rcon_border = ("#7dd3fc" if rcon_ready else "#cbd5e1") if is_light else ("#1e3a5f" if rcon_ready else "#111827")
    rcon_bg     = ("#e0f2fe" if rcon_ready else "#f8fafc") if is_light else ("#071526" if rcon_ready else "#090f1a")
    rcon_hover  = "#bae6fd" if is_light else "#1e3a5f"

    ctk.CTkButton(
        quick_row, text="🖥  RCON", width=82, height=29,
        fg_color=rcon_bg, hover_color=rcon_hover,
        text_color=rcon_color, border_width=1, border_color=rcon_border,
        corner_radius=7, font=ctk.CTkFont(family="Segoe UI", size=11),
        state="normal" if rcon_ready else "disabled",
        command=lambda s=srv: app._asm_open_rcon(s),
    ).pack(side="left", padx=(0, 4))

    ctk.CTkButton(
        quick_row, text="👥  Players", width=84, height=29,
        fg_color=rcon_bg, hover_color=rcon_hover,
        text_color=rcon_color, border_width=1, border_color=rcon_border,
        corner_radius=7, font=ctk.CTkFont(family="Segoe UI", size=11),
        state="normal" if rcon_ready else "disabled",
        command=lambda s=srv: app._asm_open_player_list(s),
    ).pack(side="left", padx=(0, 0))

    menu = tk.Menu(card, tearoff=False, bg=toolbar_bg, fg=t_sec,
                   activebackground=th.get("nav_hover", "#162032"), activeforeground=t_pri)
    menu.add_command(label="Backup e restauração", command=lambda s=srv: app._asm_open_save_restore(s))
    menu.add_command(label="Mods / Workshop", command=lambda s=srv: app._asm_open_workshop(s))
    menu.add_command(label="Arquivos", command=lambda s=srv: app._asm_open_file_manager(s))
    menu.add_command(label="Firewall", command=lambda s=srv: app._asm_open_firewall(s))
    menu.add_command(label="Desempenho", command=lambda s=srv: app._asm_open_perf(s))
    menu.add_command(label="Tribe Log", command=lambda s=srv: app._asm_open_tribe_log(s))
    menu.add_command(label="SpawnExact", command=lambda s=srv: app._asm_open_spawn_exact(s))
    menu.add_command(label="Log do servidor", command=lambda s=srv: app._asm_open_server_log(s))
    menu.add_command(label="Monitor", command=lambda s=srv: app._asm_open_monitor(s))
    menu.add_command(label="Assistente IA", command=lambda s=srv: app._asm_open_ai_assistant(s))
    if srv.active_mods and not is_running and not is_busy:
        menu.add_separator()
        menu.add_command(label="Iniciar sem mods", command=lambda s=srv: app._asm_start_server(s, no_mods=True))
    menu.add_command(label="Atualizar mods", command=lambda s=srv: app._asm_update_mods(s))
    if is_running:
        menu.add_command(label="Agendar desligamento", command=lambda sid=srv.id: app._asm_open_shutdown_schedule(sid))

    def _show_more_menu() -> None:
        button = card._asm_more_button
        try:
            menu.tk_popup(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height())
        finally:
            menu.grab_release()

    more_btn = ctk.CTkButton(
        quick_row, text="⋯ Mais", width=72, height=29,
        fg_color=toolbar_bg, hover_color=th.get("nav_hover", "#162032"),
        text_color=t_sec, border_width=1, border_color=toolbar_bdr,
        corner_radius=6, font=ctk.CTkFont(family="Segoe UI", size=10),
        command=_show_more_menu,
    )
    more_btn.pack(side="left", padx=(4, 0))
    card._asm_more_button = more_btn  # type: ignore[attr-defined]

    # ── INDICADORES RICOS (jogadores, uptime, RAM, versão) ─────────────────
    rich_r = ctk.CTkFrame(
        card,
        fg_color=inset_bg,
        corner_radius=8,
        border_width=1,
        border_color=card_bdr,
    )
    rich_r.grid(row=4, column=0, padx=14, pady=(0, 8), sticky="ew")

    rich_key = f"_asm_rich_status_{srv.id}"
    rich_data: dict = getattr(app, rich_key, {})

    players_txt = rich_data.get("players", "—")
    uptime_txt  = rich_data.get("uptime", "—")
    ram_txt     = rich_data.get("ram", "—")
    _val_tc = accent if is_running else t_sec
    _val_font = ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
    _hint_font = ctk.CTkFont(family="Segoe UI", size=9)

    # Exibe apenas os três indicadores essenciais em uma única faixa.
    rich_r.grid_columnconfigure((0, 1, 2), weight=1)
    for i, (icon, val, hint) in enumerate((
        ("👥", players_txt, "Jogadores"),
        ("🕐", uptime_txt, "Uptime"),
        ("💾", ram_txt, "Memória"),
    )):
        chip = ctk.CTkFrame(rich_r, fg_color="transparent")
        chip.grid(row=0, column=i, sticky="ew", padx=7, pady=5)
        ctk.CTkLabel(
            chip, text=f"{icon}  {val}",
            font=_val_font, text_color=_val_tc,
            anchor="w",
        ).pack(anchor="w", fill="x")
        ctk.CTkLabel(
            chip, text=hint,
            font=_hint_font, text_color=t_mut,
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

    if not hasattr(app, "_asm_dashboard_cards"):
        app._asm_dashboard_cards = {}
    app._asm_dashboard_cards[srv.id] = card

    refs: dict[str, ctk.CTkLabel] = {}
    for chip in rich_r.winfo_children():
        if not isinstance(chip, ctk.CTkFrame):
            continue
        kids = chip.winfo_children()
        if len(kids) >= 2 and isinstance(kids[0], ctk.CTkLabel) and isinstance(kids[1], ctk.CTkLabel):
            refs[kids[1].cget("text")] = kids[0]
    card._asm_rich_value_labels = refs  # type: ignore[attr-defined]

    return card


def _build_shutdown_row(
    app: "ARKServerManagerApp",
    card: ctk.CTkFrame,
    srv: AsmServerConfig,
    row: ctk.CTkFrame,
    is_running: bool,
) -> None:
    """Monta ou atualiza a faixa de countdown de desligamento agendado."""
    from ..pages.asm_scheduled_shutdown import (
        format_shutdown_countdown,
        has_scheduled_shutdown,
        remaining_seconds,
    )

    for w in row.winfo_children():
        w.destroy()
    card._asm_shutdown_countdown_lbl = None  # type: ignore[attr-defined]

    if not is_running or not has_scheduled_shutdown(app, srv.id):
        row.grid_remove()
        return

    th = get_theme("tek")
    warn_bg = "#431407" if not th.get("_is_light") else "#fef3c7"
    warn_tc = "#fbbf24" if not th.get("_is_light") else "#92400e"
    warn_bdr = "#78350f" if not th.get("_is_light") else "#fcd34d"

    row.grid()
    bar = ctk.CTkFrame(row, fg_color=warn_bg, corner_radius=6, border_width=1, border_color=warn_bdr)
    bar.pack(fill="x")

    secs = remaining_seconds(app, srv.id)
    countdown_lbl = ctk.CTkLabel(
        bar,
        text=f"⏱  Desliga em {format_shutdown_countdown(secs)}",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color=warn_tc,
    )
    countdown_lbl.pack(side="left", padx=(10, 6), pady=6)
    card._asm_shutdown_countdown_lbl = countdown_lbl  # type: ignore[attr-defined]

    ctk.CTkButton(
        bar, text="Cancelar", width=72, height=26,
        fg_color="transparent", hover_color=warn_bdr,
        text_color=warn_tc, corner_radius=5,
        font=ctk.CTkFont(size=10),
        command=lambda sid=srv.id: app._asm_cancel_scheduled_shutdown(sid),
    ).pack(side="right", padx=8, pady=4)


def refresh_shutdown_row(
    app: "ARKServerManagerApp",
    card: ctk.CTkFrame,
    srv: AsmServerConfig,
) -> None:
    """Atualiza visibilidade da faixa de desligamento após agendar/cancelar."""
    row = getattr(card, "_asm_shutdown_row", None)
    if row is None:
        return
    try:
        if not row.winfo_exists():
            return
    except Exception:
        return

    inst = app.asm_server_manager.get_instance(srv.id)
    is_running = bool(inst and inst.status == ASM_STATUS_RUNNING)
    _build_shutdown_row(app, card, srv, row, is_running)

