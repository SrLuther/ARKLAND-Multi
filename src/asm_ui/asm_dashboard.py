"""
TEK — Dashboard principal do modo ASM.
Visual inspirado no ARKLAND SM (React/Tailwind): TopBar com saudação,
grid de stats (Total / Rodando / Parados / CPU / RAM), cards de servidor.
"""
from __future__ import annotations

import platform
import tkinter as tk
from datetime import datetime
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import get_theme
from ..ui.server_field_widgets import refresh_scrollable_frame
from ..asm_engine.asm_server_config import (
    ASM_STATUS_RUNNING, ASM_STATUS_STOPPED,
    ASM_STATUS_STARTING, ASM_STATUS_STOPPING, ASM_STATUS_UPDATING,
)

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


# ── Helpers ──────────────────────────────────────────────────────────────────

def _greeting() -> tuple[str, str]:
    """Retorna (saudação, ícone) baseado no horário."""
    hour = datetime.now().hour
    if hour < 12:
        return "Bom dia", "☀"
    if hour < 18:
        return "Boa tarde", "⛅"
    return "Boa noite", "🌙"


def _get_perf() -> tuple[float, float]:
    """Retorna (cpu_pct, ram_pct) ou (0, 0) se psutil não estiver disponível."""
    try:
        import psutil  # type: ignore[reportMissingImports]
        cpu = psutil.cpu_percent(interval=None)
        vm  = psutil.virtual_memory()
        return cpu, vm.percent
    except Exception:
        return 0.0, 0.0


# ── Construção principal ─────────────────────────────────────────────────────

def build_asm_dashboard(app: "ARKServerManagerApp", parent: ctk.CTkFrame) -> None:
    """Constrói o dashboard TEK dentro de `parent`."""
    theme   = get_theme("tek")
    accent  = theme["accent"]
    bg      = theme["bg"]
    card_bg = theme["card_bg"]
    sep     = theme["separator"]
    topbar  = theme["topbar_bg"]
    t_pri   = theme["text_primary"]
    t_sec   = theme["text_secondary"]
    t_mut   = theme["text_muted"]
    acc_mb  = theme["accent_muted_bg"]
    acc_dk  = theme["accent_dark"]
    is_light = theme.get("_is_light", False)
    card_bdr = theme.get("card_border", sep)

    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=0)  # TopBar
    parent.grid_rowconfigure(1, weight=0)  # Stats grid
    parent.grid_rowconfigure(2, weight=1)  # Scroll de cards

    # ── TopBar ────────────────────────────────────────────────────────────────
    topbar_f = ctk.CTkFrame(parent, fg_color=topbar, corner_radius=0, height=72,
                            border_width=1, border_color=card_bdr)
    topbar_f.grid(row=0, column=0, sticky="ew")
    topbar_f.grid_propagate(False)
    topbar_f.grid_columnconfigure(1, weight=1)

    # Saudação
    greet_txt, greet_icon = _greeting()
    ctk.CTkLabel(
        topbar_f, text=greet_icon,
        font=ctk.CTkFont(size=28),
        text_color=accent,
    ).grid(row=0, column=0, padx=(20, 8), pady=12, sticky="w")

    greet_col = ctk.CTkFrame(topbar_f, fg_color="transparent")
    greet_col.grid(row=0, column=1, sticky="w")
    ctk.CTkLabel(
        greet_col,
        text=f"{greet_txt}, Sobrevivente",
        font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
        text_color=t_pri,
    ).pack(anchor="w")

    # Contagem de servidores online
    servers  = app.asm_config_manager.servers
    running  = sum(
        1 for s in servers
        if (inst := app.asm_server_manager.get_instance(s.id)) and inst.status == ASM_STATUS_RUNNING
    )
    sub_text = (
        f"{running} sistema(s) ativo(s)" if running > 0
        else "Todos os sistemas em standby"
    )
    app._dashboard_subtitle_lbl = ctk.CTkLabel(
        greet_col, text=sub_text,
        font=ctk.CTkFont(size=12), text_color=t_sec,
    )
    app._dashboard_subtitle_lbl.pack(anchor="w")

    # Badge versão + botão Novo Servidor
    right_f = ctk.CTkFrame(topbar_f, fg_color="transparent")
    right_f.grid(row=0, column=2, padx=(0, 20), sticky="e")

    ctk.CTkButton(
        right_f, text="＋  Novo Servidor", width=154, height=36,
        fg_color=acc_mb, hover_color=acc_dk,
        border_width=1, border_color=accent,
        text_color=accent,
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        corner_radius=10,
        command=app._asm_add_server_dialog,
    ).pack(side="right", padx=(8, 0))

    from ..version import APP_VERSION
    ctk.CTkLabel(
        right_f, text=f"v{APP_VERSION}",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color=t_mut,
        fg_color=acc_mb, corner_radius=6,
    ).pack(side="right", padx=(0, 4), ipady=6, ipadx=10)

    # Linha separadora
    ctk.CTkFrame(parent, height=1, fg_color=sep).grid(row=0, column=0, sticky="ews")

    # ── Stats grid ────────────────────────────────────────────────────────────
    total   = len(servers)
    stopped = sum(
        1 for s in servers
        if not (inst := app.asm_server_manager.get_instance(s.id)) or inst.status == ASM_STATUS_STOPPED
    )
    cpu_pct, ram_pct = _get_perf()

    stats_f = ctk.CTkFrame(parent, fg_color=bg, corner_radius=0)
    stats_f.grid(row=1, column=0, sticky="ew", padx=16, pady=(14, 4))
    for i in range(5):
        stats_f.grid_columnconfigure(i, weight=1)

    # icon · label · value · bar · subtitle  (padrão ARKLAND SM)
    _icon_bgs = (
        ["#dbeafe", "#dcfce7", "#f1f5f9", "#ede9fe", "#fce7f3"] if is_light
        else ["#1e3a5f", "#052e16", "#0f172a", "#1e1b4b", "#3b0764"]
    )
    _stat_cards = [
        # (label_upper, value, subtitle, cor_valor, cor_icone_bg, icone)
        ("TOTAL",   str(total),        "servidores",           "#60a5fa", _icon_bgs[0], "🖥"),
        ("ONLINE",  str(running),      "rodando",              "#22c55e", _icon_bgs[1], "▶"),
        ("OFFLINE", str(stopped),      "parados",              "#64748b", _icon_bgs[2], "■"),
        ("CPU",     f"{cpu_pct:.0f}%", "processador",          "#a78bfa", _icon_bgs[3], "⚙"),
        ("RAM",     f"{ram_pct:.0f}%", "memória",              "#f472b6", _icon_bgs[4], "◈"),
    ]

    for col_idx, (label, value, sub, fg_col, bg_col, icon) in enumerate(_stat_cards):
        card = ctk.CTkFrame(stats_f, corner_radius=12,
                            fg_color=card_bg,
                            border_width=1, border_color=card_bdr)
        card.grid(row=0, column=col_idx, padx=6, pady=4, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        # ── Linha topo: [bolha icon] [LABEL] ─────────────────────────────────
        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.grid(row=0, column=0, padx=12, pady=(12, 0), sticky="ew")
        top_row.grid_columnconfigure(1, weight=1)

        icon_f = ctk.CTkFrame(top_row, fg_color=bg_col, corner_radius=8,
                               width=28, height=28)
        icon_f.grid(row=0, column=0, padx=(0, 8))
        icon_f.grid_propagate(False)
        ctk.CTkLabel(icon_f, text=icon,
                     font=ctk.CTkFont(size=11),
                     text_color=fg_col).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(top_row, text=label,
                     font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                     text_color=t_sec,
                     ).grid(row=0, column=1, sticky="w")

        # ── Valor grande ──────────────────────────────────────────────────────
        val_lbl = ctk.CTkLabel(card, text=value,
                     font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
                     text_color=fg_col,
                     )
        val_lbl.grid(row=1, column=0, padx=12, pady=(6, 0), sticky="w")
        if not hasattr(app, "_asm_stat_value_labels"):
            app._asm_stat_value_labels = {}
        app._asm_stat_value_labels[label] = val_lbl

        # ── Barra fina (CPU / RAM) ────────────────────────────────────────────
        if label in ("CPU", "RAM"):
            val_float = float(value.rstrip("%")) / 100.0
            bar = ctk.CTkProgressBar(card, height=3, corner_radius=2,
                                     progress_color=fg_col, fg_color=sep)
            bar.set(min(val_float, 1.0))
            bar.grid(row=2, column=0, padx=12, pady=(6, 0), sticky="ew")
            if not hasattr(app, "_asm_stat_bars"):
                app._asm_stat_bars = {}
            app._asm_stat_bars[label] = bar

        # ── Subtítulo ─────────────────────────────────────────────────────────
        ctk.CTkLabel(card, text=sub[:26],
                     font=ctk.CTkFont(size=9), text_color=t_mut,
                     ).grid(row=3, column=0, padx=12, pady=(4, 10), sticky="w")

    # Guarda referência para refresh de stats sem recriar o dashboard todo
    app._asm_stats_frame = stats_f

    # Linha separadora
    ctk.CTkFrame(parent, height=1, fg_color=sep).grid(row=1, column=0, sticky="ews")

    # ── Scroll de cards (CTkScrollableFrame — CTk nativo; FastScrollFrame clipava cards)
    scroll = ctk.CTkScrollableFrame(parent, fg_color=bg, corner_radius=0,
                                    scrollbar_button_color=sep)
    scroll.grid(row=2, column=0, padx=0, pady=0, sticky="nsew")
    scroll.grid_columnconfigure((0, 1), weight=1)
    app._asm_dashboard_scroll = scroll

    _refresh_asm_dashboard(app)


def _dashboard_scroll(app: "ARKServerManagerApp"):
    """Retorna o CTkScrollableFrame do dashboard ou None."""
    scroll = getattr(app, "_asm_dashboard_scroll", None)
    if scroll is None:
        return None
    try:
        return scroll if scroll.winfo_exists() else None
    except Exception:
        return None


def _schedule_dashboard_scroll_refresh(scroll, n_cards: int) -> None:
    """Atualiza scrollregion após rebuild — CTk layouta cards de forma assíncrona."""
    min_h = 120 + max(1, (n_cards + 1) // 2) * 300

    def _apply() -> None:
        refresh_scrollable_frame(scroll)
        try:
            canvas = scroll._parent_canvas
            bbox = canvas.bbox("all")
            w = max(canvas.winfo_width(), 1)
            h = min_h
            if bbox:
                h = max(h, int(bbox[3]) + 16)
            canvas.configure(scrollregion=(0, 0, w, h))
        except (AttributeError, tk.TclError):
            pass

    for ms in (0, 50, 150, 400, 800):
        scroll.after(ms, _apply)


def _refresh_asm_stats(app: "ARKServerManagerApp", servers: list) -> None:
    """Atualiza cards de estatísticas do topo sem rebuild completo."""
    labels = getattr(app, "_asm_stat_value_labels", None)
    if not labels:
        return
    total = len(servers)
    running = sum(
        1 for s in servers
        if (inst := app.asm_server_manager.get_instance(s.id))
        and inst.status == ASM_STATUS_RUNNING
    )
    stopped = sum(
        1 for s in servers
        if not (inst := app.asm_server_manager.get_instance(s.id))
        or inst.status == ASM_STATUS_STOPPED
    )
    cpu_pct, ram_pct = _get_perf()
    if "TOTAL" in labels:
        labels["TOTAL"].configure(text=str(total))
    if "ONLINE" in labels:
        labels["ONLINE"].configure(text=str(running))
    if "OFFLINE" in labels:
        labels["OFFLINE"].configure(text=str(stopped))
    if "CPU" in labels:
        labels["CPU"].configure(text=f"{cpu_pct:.0f}%")
    if "RAM" in labels:
        labels["RAM"].configure(text=f"{ram_pct:.0f}%")
    bars = getattr(app, "_asm_stat_bars", None) or {}
    if "CPU" in bars:
        bars["CPU"].set(min(cpu_pct / 100.0, 1.0))
    if "RAM" in bars:
        bars["RAM"].set(min(ram_pct / 100.0, 1.0))


def _refresh_asm_dashboard(app: "ARKServerManagerApp") -> None:
    """Popula / atualiza os cards de servidor no scroll do dashboard TEK."""
    from .asm_server_card import build_asm_server_card

    inner = _dashboard_scroll(app)
    if inner is None:
        return

    for w in inner.winfo_children():
        w.destroy()

    theme   = get_theme("tek")
    accent  = theme["accent"]
    bg      = theme["bg"]
    card_bg = theme["card_bg"]
    sep     = theme["separator"]
    t_pri   = theme["text_primary"]
    t_sec   = theme["text_secondary"]
    t_mut   = theme["text_muted"]
    acc_mb  = theme["accent_muted_bg"]
    acc_dk  = theme["accent_dark"]
    is_light = theme.get("_is_light", False)
    card_bdr = theme.get("card_border", sep)
    folder_bg = theme.get("folder_hdr_bg", "#0a111c" if not is_light else "#eef2f6")
    folder_bdr = theme.get("folder_hdr_border", "#1a2840" if not is_light else "#94a3b8")

    servers = app.asm_config_manager.servers
    if not servers:
        ctk.CTkLabel(
            inner,
            text="Nenhum servidor TEK configurado.\nClique em '＋ Novo Servidor' para começar.",
            font=ctk.CTkFont(family="Segoe UI", size=15), text_color=t_sec, justify="center",
        ).grid(row=0, column=0, columnspan=2, pady=60)
        _update_subtitle(app, servers)
        return

    # ── S3.2 — Toolbar de Bulk Actions ───────────────────────────────────────
    if not hasattr(app, "_asm_selected_servers"):
        app._asm_selected_servers: set = set()

    bulk_bar = ctk.CTkFrame(inner, fg_color=card_bg, corner_radius=8,
                            border_width=1, border_color=card_bdr)
    bulk_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4))
    bulk_bar.grid_columnconfigure(8, weight=1)

    # Checkbox "Selecionar Todos"
    sel_all_var = tk.BooleanVar(value=False)

    def _toggle_all():
        all_ids = {s.id for s in servers}
        if sel_all_var.get():
            app._asm_selected_servers = all_ids
        else:
            app._asm_selected_servers = set()

    ctk.CTkCheckBox(
        bulk_bar, text="Selecionar Todos", variable=sel_all_var,
        font=ctk.CTkFont(size=11), text_color=t_sec,
        checkmark_color=accent, border_color=accent,
        command=_toggle_all,
    ).grid(row=0, column=0, padx=(10, 10), pady=8, sticky="w")

    def _bulk_start():
        import threading
        for sid in list(app._asm_selected_servers):
            srv = app.asm_config_manager.get_server(sid)
            if srv:
                threading.Thread(
                    target=lambda s=srv: app._asm_start_server(s),
                    daemon=True,
                ).start()

    def _bulk_stop():
        import threading
        for sid in list(app._asm_selected_servers):
            threading.Thread(
                target=lambda sid_=sid: app._asm_stop_server(sid_),
                daemon=True,
            ).start()

    def _bulk_restart():
        import threading
        for sid in list(app._asm_selected_servers):
            srv = app.asm_config_manager.get_server(sid)
            if srv:
                threading.Thread(
                    target=lambda s=srv: app._asm_restart_server(s),
                    daemon=True,
                ).start()

    def _bulk_update_mods():
        import threading
        for sid in list(app._asm_selected_servers):
            srv = app.asm_config_manager.get_server(sid)
            if srv and srv.active_mods:
                threading.Thread(
                    target=lambda s=srv: app._asm_update_mods(s),
                    daemon=True,
                ).start()

    _bulk_btns = (
        [
            ("\u25b6  Iniciar",        _bulk_start,       "#dcfce7", "#166534"),
            ("\u23f9  Parar",          _bulk_stop,        "#fee2e2", "#991b1b"),
            ("\U0001f504  Reiniciar",  _bulk_restart,     "#f1f5f9", t_sec),
            ("\U0001f4e6  Atualizar Mods", _bulk_update_mods, "#e0f2fe", "#0369a1"),
        ] if is_light else [
            ("\u25b6  Iniciar",        _bulk_start,       "#052e16", "#4ade80"),
            ("\u23f9  Parar",          _bulk_stop,        "#7f1d1d", "#fca5a5"),
            ("\U0001f504  Reiniciar",  _bulk_restart,     "#1e293b", t_sec),
            ("\U0001f4e6  Atualizar Mods", _bulk_update_mods, "#0c1a2e", "#7dd3fc"),
        ]
    )
    _bulk_hover = "#e2e8f0" if is_light else "#1e293b"
    for col_i, (txt, cmd, bg_c, tc) in enumerate(_bulk_btns, start=1):
        ctk.CTkButton(
            bulk_bar, text=txt, width=130, height=28,
            fg_color=bg_c, hover_color=_bulk_hover,
            text_color=tc, corner_radius=6,
            font=ctk.CTkFont(size=11),
            command=cmd,
        ).grid(row=0, column=col_i, padx=3, pady=8)

    # ── S3.1 — Grupos (pastas) ────────────────────────────────────────────────
    fm      = app.asm_config_manager.folder_manager
    grouped = fm.grouped()   # dict: {pasta: [servidores]}

    grid_row = 1
    for folder_name, folder_servers in grouped.items():
        display_name = folder_name or "Geral"
        is_root      = (folder_name == "")

        # ── Header da pasta ───────────────────────────────────────────────────
        folder_hdr = ctk.CTkFrame(
            inner,
            fg_color=folder_bg,
            corner_radius=6,
            border_width=1,
            border_color=folder_bdr,
        )
        folder_hdr.grid(row=grid_row, column=0, columnspan=2,
                        sticky="ew", padx=8, pady=(10, 2))
        folder_hdr.grid_columnconfigure(1, weight=1)
        grid_row += 1

        icon = "📁" if not is_root else "🖥"
        ctk.CTkLabel(
            folder_hdr, text=f"{icon}  {display_name}",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=accent if not is_root else t_sec,
        ).grid(row=0, column=0, padx=(12, 6), pady=7, sticky="w")

        count_active = sum(
            1 for s in folder_servers
            if (inst := app.asm_server_manager.get_instance(s.id))
            and inst.status in (ASM_STATUS_RUNNING, ASM_STATUS_STARTING)
        )
        ctk.CTkLabel(
            folder_hdr,
            text=f"{count_active}/{len(folder_servers)} online",
            font=ctk.CTkFont(size=10), text_color=t_mut,
        ).grid(row=0, column=1, padx=4, pady=7, sticky="w")

        # Botão "▶ Iniciar Todos" na pasta
        if not is_root:
            def _start_folder(fsvrs=folder_servers):
                import threading
                for s in fsvrs:
                    threading.Thread(
                        target=lambda srv=s: app._asm_start_server(srv),
                        daemon=True,
                    ).start()

            ctk.CTkButton(
                folder_hdr, text="▶  Iniciar Todos", width=110, height=26,
                fg_color="#dcfce7" if is_light else "#052e16",
                hover_color="#bbf7d0" if is_light else "#14532d",
                text_color="#166534" if is_light else "#4ade80",
                corner_radius=6,
                font=ctk.CTkFont(size=10),
                command=_start_folder,
            ).grid(row=0, column=2, padx=(0, 10), pady=7, sticky="e")

        # ── Cards no scroll (sem frame aninhado — evita clip/overlap no CTkScrollableFrame)
        card_row_base = grid_row
        for idx, srv in enumerate(folder_servers):
            r, c = divmod(idx, 2)
            build_asm_server_card(app, inner, srv, card_row_base + r, c)
        grid_row += (len(folder_servers) + 1) // 2

    _update_subtitle(app, servers)
    _refresh_asm_stats(app, servers)
    inner.update_idletasks()
    _schedule_dashboard_scroll_refresh(inner, len(servers))


def _update_subtitle(app: "ARKServerManagerApp", servers: list) -> None:
    running = sum(
        1 for s in servers
        if (inst := app.asm_server_manager.get_instance(s.id)) and inst.status == ASM_STATUS_RUNNING
    )
    sub = (
        f"{running} sistema(s) ativo(s)" if running > 0
        else "Todos os sistemas em standby"
    )
    lbl = getattr(app, "_dashboard_subtitle_lbl", None)
    if lbl and lbl.winfo_exists():
        lbl.configure(text=sub)
