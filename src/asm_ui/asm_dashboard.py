"""
TEK — Dashboard principal do modo ASM.
Visual inspirado no ARKLAND SM (React/Tailwind): TopBar com saudação,
grid de stats (Total / Rodando / Parados / CPU / RAM), cards de servidor.
"""
from __future__ import annotations

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


def _format_disk_gb(gb: float) -> str:
    if gb >= 1024:
        return f"{gb / 1024:.1f} TB"
    if gb >= 100:
        return f"{gb:.0f} GB"
    return f"{gb:.1f} GB"


def _get_disk_usage() -> list[dict]:
    """Lista partições locais com espaço livre/total (Windows: C:\\, D:\\, …)."""
    out: list[dict] = []
    try:
        import psutil  # type: ignore[reportMissingImports]
        seen: set[str] = set()
        for part in psutil.disk_partitions(all=False):
            opts = (part.opts or "").lower()
            if "cdrom" in opts or not (part.fstype or "").strip():
                continue
            mp = (part.mountpoint or "").strip()
            if not mp or mp in seen:
                continue
            try:
                usage = psutil.disk_usage(mp)
            except (PermissionError, OSError):
                continue
            seen.add(mp)
            total_gb = usage.total / (1024 ** 3)
            free_gb = usage.free / (1024 ** 3)
            out.append({
                "mount": mp.rstrip("\\/"),
                "label": mp,
                "total_gb": total_gb,
                "free_gb": free_gb,
                "used_pct": float(usage.percent),
            })
    except Exception:
        pass
    return sorted(out, key=lambda d: d["mount"].lower())


def _disk_bar_color(used_pct: float, is_light: bool) -> str:
    if used_pct >= 90:
        return "#ef4444"
    if used_pct >= 75:
        return "#f59e0b"
    return "#22c55e" if not is_light else "#16a34a"


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
    parent.grid_rowconfigure(2, weight=0)  # Discos
    parent.grid_rowconfigure(3, weight=0)  # Bulk bar
    parent.grid_rowconfigure(4, weight=1)  # Scroll de cards

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

    # ── Discos da máquina ─────────────────────────────────────────────────────
    disks_outer = ctk.CTkFrame(parent, fg_color=bg, corner_radius=0)
    disks_outer.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 4))
    disks_outer.grid_columnconfigure(0, weight=1)
    app._asm_disks_outer = disks_outer
    _build_disk_section(app, disks_outer, theme)

    # Linha separadora
    ctk.CTkFrame(parent, height=1, fg_color=sep).grid(row=2, column=0, sticky="ews")

    # ── Bulk bar (fixo — fora do scroll) ─────────────────────────────────────
    app._asm_bulk_bar = ctk.CTkFrame(parent, fg_color=card_bg, corner_radius=8,
                                     border_width=1, border_color=card_bdr)
    app._asm_bulk_bar.grid(row=3, column=0, sticky="ew", padx=8, pady=(8, 4))
    _build_bulk_bar(app)

    # ── Scroll: um único cards_host interno — nunca destruído no refresh ───
    scroll = ctk.CTkScrollableFrame(parent, fg_color=bg, corner_radius=0,
                                    scrollbar_button_color=sep)
    scroll.grid(row=4, column=0, padx=0, pady=0, sticky="nsew")
    scroll.grid_columnconfigure(0, weight=1)
    scroll.grid_rowconfigure(0, weight=1)
    app._asm_dashboard_scroll = scroll

    cards_host = ctk.CTkFrame(scroll, fg_color=bg, corner_radius=0)
    cards_host.grid(row=0, column=0, sticky="nsew")
    cards_host.grid_columnconfigure((0, 1), weight=1)
    app._asm_dashboard_cards_host = cards_host
    app._asm_dashboard_layout_sig = None
    app._asm_dashboard_cards = {}
    app._asm_folder_count_labels = {}
    app._asm_card_grid_pos: dict = {}

    _refresh_asm_dashboard(app, force_layout=True)


def _build_disk_section(app: "ARKServerManagerApp", parent, theme: dict) -> None:
    """Seção de armazenamento — um card por unidade de disco."""
    card_bg = theme["card_bg"]
    sep = theme["separator"]
    t_sec = theme["text_secondary"]
    t_mut = theme["text_muted"]
    is_light = theme.get("_is_light", False)
    card_bdr = theme.get("card_border", sep)

    hdr = ctk.CTkFrame(parent, fg_color="transparent")
    hdr.pack(fill="x", pady=(0, 6))
    ctk.CTkLabel(
        hdr, text="ARMAZENAMENTO",
        font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
        text_color=t_sec,
    ).pack(side="left", padx=(4, 0))

    disks_row = ctk.CTkFrame(parent, fg_color="transparent")
    disks_row.pack(fill="x")
    app._asm_disks_row = disks_row
    app._asm_disk_widgets: dict = {}
    _refresh_asm_disks(app, theme)


def _refresh_asm_disks(app: "ARKServerManagerApp", theme: dict | None = None) -> None:
    """Atualiza cards de disco (recria se a lista de unidades mudar)."""
    disks_row = getattr(app, "_asm_disks_row", None)
    if disks_row is None:
        return
    try:
        if not disks_row.winfo_exists():
            return
    except Exception:
        return

    if theme is None:
        theme = get_theme("tek")

    card_bg = theme["card_bg"]
    sep = theme["separator"]
    t_mut = theme["text_muted"]
    is_light = theme.get("_is_light", False)
    card_bdr = theme.get("card_border", sep)

    disks = _get_disk_usage()
    mounts = [d["mount"] for d in disks]
    existing = getattr(app, "_asm_disk_widgets", {}) or {}

    if set(existing.keys()) != set(mounts):
        for w in disks_row.winfo_children():
            w.destroy()
        app._asm_disk_widgets = {}

        if not disks:
            ctk.CTkLabel(
                disks_row,
                text="Não foi possível ler o espaço em disco.",
                text_color=t_mut,
                font=ctk.CTkFont(size=11),
            ).pack(anchor="w", padx=4, pady=8)
            return

        cols = min(4, max(1, len(disks)))
        for i in range(cols):
            disks_row.grid_columnconfigure(i, weight=1)

        for idx, d in enumerate(disks):
            mount = d["mount"]
            card = ctk.CTkFrame(
                disks_row, corner_radius=10, fg_color=card_bg,
                border_width=1, border_color=card_bdr,
            )
            card.grid(
                row=idx // cols, column=idx % cols,
                padx=5, pady=4, sticky="ew",
            )

            title = mount if len(mount) <= 4 else mount
            ctk.CTkLabel(
                card, text=f"💾  {title}",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=theme["text_secondary"],
            ).grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")

            free_txt = _format_disk_gb(d["free_gb"])
            total_txt = _format_disk_gb(d["total_gb"])
            val_lbl = ctk.CTkLabel(
                card, text=free_txt,
                font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
                text_color=_disk_bar_color(d["used_pct"], is_light),
            )
            val_lbl.grid(row=1, column=0, padx=10, pady=(4, 0), sticky="w")

            bar_color = _disk_bar_color(d["used_pct"], is_light)
            bar = ctk.CTkProgressBar(
                card, height=4, corner_radius=2,
                progress_color=bar_color, fg_color=sep,
            )
            bar.set(min(d["used_pct"] / 100.0, 1.0))
            bar.grid(row=2, column=0, padx=10, pady=(6, 0), sticky="ew")

            sub_lbl = ctk.CTkLabel(
                card,
                text=f"livres de {total_txt}  ({d['used_pct']:.0f}% usado)",
                font=ctk.CTkFont(size=9),
                text_color=t_mut,
            )
            sub_lbl.grid(row=3, column=0, padx=10, pady=(4, 10), sticky="w")

            app._asm_disk_widgets[mount] = {
                "val": val_lbl, "bar": bar, "sub": sub_lbl,
            }
        return

    for d in disks:
        w = existing.get(d["mount"])
        if not w:
            continue
        used = d["used_pct"]
        color = _disk_bar_color(used, is_light)
        w["val"].configure(text=_format_disk_gb(d["free_gb"]), text_color=color)
        w["bar"].set(min(used / 100.0, 1.0))
        w["bar"].configure(progress_color=color)
        w["sub"].configure(
            text=f"livres de {_format_disk_gb(d['total_gb'])}  ({used:.0f}% usado)",
        )


def _dashboard_scroll(app: "ARKServerManagerApp"):
    """Retorna o CTkScrollableFrame do dashboard ou None."""
    scroll = getattr(app, "_asm_dashboard_scroll", None)
    if scroll is None:
        return None
    try:
        return scroll if scroll.winfo_exists() else None
    except Exception:
        return None


def _cards_host(app: "ARKServerManagerApp"):
    host = getattr(app, "_asm_dashboard_cards_host", None)
    if host is None:
        return None
    try:
        return host if host.winfo_exists() else None
    except Exception:
        return None


def _layout_signature(app: "ARKServerManagerApp") -> tuple:
    fm = app.asm_config_manager.folder_manager
    return tuple(
        (folder, tuple(s.id for s in servers))
        for folder, servers in fm.grouped().items()
    )


def _schedule_dashboard_scroll_refresh(scroll) -> None:
    """Atualiza scrollregion sem rebuild — cards_host permanece estável."""
    for ms in (0, 50, 150, 300):
        scroll.after(ms, lambda s=scroll: refresh_scrollable_frame(s))


def _build_bulk_bar(app: "ARKServerManagerApp") -> None:
    """Constrói a barra de ações em massa (uma vez)."""
    bulk = getattr(app, "_asm_bulk_bar", None)
    if bulk is None:
        return
    for w in bulk.winfo_children():
        w.destroy()

    theme = get_theme("tek")
    accent = theme["accent"]
    card_bdr = theme.get("card_border", theme["separator"])
    t_sec = theme["text_secondary"]
    is_light = theme.get("_is_light", False)

    bulk.grid_columnconfigure(8, weight=1)
    servers = app.asm_config_manager.servers

    if not hasattr(app, "_asm_selected_servers"):
        app._asm_selected_servers: set = set()

    sel_all_var = tk.BooleanVar(value=False)

    def _toggle_all():
        all_ids = {s.id for s in servers}
        app._asm_selected_servers = all_ids if sel_all_var.get() else set()

    ctk.CTkCheckBox(
        bulk, text="Selecionar Todos", variable=sel_all_var,
        font=ctk.CTkFont(size=11), text_color=t_sec,
        checkmark_color=accent, border_color=accent,
        command=_toggle_all,
    ).grid(row=0, column=0, padx=(10, 10), pady=8, sticky="w")

    def _bulk_start():
        import threading
        # #region agent log
        try:
            from .._agent_debug_log import agent_dbg
            _sel = list(getattr(app, "_asm_selected_servers", set()) or [])
            agent_dbg("D", "asm_dashboard.py:_bulk_start", "bulk start clicked", {
                "selected_count": len(_sel), "selected": _sel[:8],
            })
        except Exception:
            pass
        # #endregion
        for sid in list(app._asm_selected_servers):
            srv = app.asm_config_manager.get_server(sid)
            if srv:
                threading.Thread(target=lambda s=srv: app._asm_start_server(s), daemon=True).start()

    def _bulk_stop():
        import threading
        for sid in list(app._asm_selected_servers):
            threading.Thread(target=lambda sid_=sid: app._asm_stop_server(sid_), daemon=True).start()

    def _bulk_restart():
        import threading
        for sid in list(app._asm_selected_servers):
            srv = app.asm_config_manager.get_server(sid)
            if srv:
                threading.Thread(target=lambda s=srv: app._asm_restart_server(s), daemon=True).start()

    def _bulk_update_mods():
        import threading
        for sid in list(app._asm_selected_servers):
            srv = app.asm_config_manager.get_server(sid)
            if srv and srv.active_mods:
                threading.Thread(target=lambda s=srv: app._asm_update_mods(s), daemon=True).start()

    def _bulk_schedule_shutdown():
        ids = list(app._asm_selected_servers)
        app._asm_open_shutdown_schedule(preselected=ids or None)

    _bulk_btns = (
        [
            ("\u25b6  Iniciar", _bulk_start, "#dcfce7", "#166534"),
            ("\u23f9  Parar", _bulk_stop, "#fee2e2", "#991b1b"),
            ("\U0001f504  Reiniciar", _bulk_restart, "#f1f5f9", t_sec),
            ("\U0001f4e6  Atualizar Mods", _bulk_update_mods, "#e0f2fe", "#0369a1"),
            ("\u23f1  Desligar agend.", _bulk_schedule_shutdown, "#fee2e2", "#991b1b"),
        ] if is_light else [
            ("\u25b6  Iniciar", _bulk_start, "#052e16", "#4ade80"),
            ("\u23f9  Parar", _bulk_stop, "#7f1d1d", "#fca5a5"),
            ("\U0001f504  Reiniciar", _bulk_restart, "#1e293b", t_sec),
            ("\U0001f4e6  Atualizar Mods", _bulk_update_mods, "#0c1a2e", "#7dd3fc"),
            ("\u23f1  Desligar agend.", _bulk_schedule_shutdown, "#450a0a", "#fca5a5"),
        ]
    )
    _bulk_hover = "#e2e8f0" if is_light else "#1e293b"
    for col_i, (txt, cmd, bg_c, tc) in enumerate(_bulk_btns, start=1):
        ctk.CTkButton(
            bulk, text=txt, width=130, height=28,
            fg_color=bg_c, hover_color=_bulk_hover,
            text_color=tc, corner_radius=6,
            font=ctk.CTkFont(size=11), command=cmd,
        ).grid(row=0, column=col_i, padx=3, pady=8)


def _populate_cards_grid(app: "ARKServerManagerApp", host: ctk.CTkFrame) -> None:
    """Monta pastas + cards dentro de cards_host (shell estável)."""
    from .asm_server_card import build_asm_server_card

    for w in host.winfo_children():
        w.destroy()

    app._asm_dashboard_cards = {}
    app._asm_folder_count_labels = {}
    app._asm_card_grid_pos = {}

    theme = get_theme("tek")
    accent = theme["accent"]
    bg = theme["bg"]
    t_sec = theme["text_secondary"]
    t_mut = theme["text_muted"]
    is_light = theme.get("_is_light", False)
    folder_bg = theme.get("folder_hdr_bg", "#0a111c" if not is_light else "#eef2f6")
    folder_bdr = theme.get("folder_hdr_border", "#1a2840" if not is_light else "#94a3b8")

    servers = app.asm_config_manager.servers
    if not servers:
        ctk.CTkLabel(
            host,
            text="Nenhum servidor TEK configurado.\nClique em '＋ Novo Servidor' para começar.",
            font=ctk.CTkFont(family="Segoe UI", size=15), text_color=t_sec, justify="center",
        ).grid(row=0, column=0, columnspan=2, pady=60)
        return

    fm = app.asm_config_manager.folder_manager
    grouped = fm.grouped()
    grid_row = 0

    for folder_name, folder_servers in grouped.items():
        display_name = folder_name or "Geral"
        is_root = (folder_name == "")

        folder_hdr = ctk.CTkFrame(
            host, fg_color=folder_bg, corner_radius=6,
            border_width=1, border_color=folder_bdr,
        )
        folder_hdr.grid(row=grid_row, column=0, columnspan=2, sticky="ew", padx=8, pady=(10, 2))
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
        count_lbl = ctk.CTkLabel(
            folder_hdr,
            text=f"{count_active}/{len(folder_servers)} online",
            font=ctk.CTkFont(size=10), text_color=t_mut,
        )
        count_lbl.grid(row=0, column=1, padx=4, pady=7, sticky="w")
        app._asm_folder_count_labels[folder_name] = count_lbl

        if not is_root:
            def _start_folder(fsvrs=folder_servers):
                import threading
                for s in fsvrs:
                    threading.Thread(
                        target=lambda srv=s: app._asm_start_server(srv), daemon=True,
                    ).start()

            ctk.CTkButton(
                folder_hdr, text="▶  Iniciar Todos", width=110, height=26,
                fg_color="#dcfce7" if is_light else "#052e16",
                hover_color="#bbf7d0" if is_light else "#14532d",
                text_color="#166534" if is_light else "#4ade80",
                corner_radius=6, font=ctk.CTkFont(size=10),
                command=_start_folder,
            ).grid(row=0, column=2, padx=(0, 10), pady=7, sticky="e")

        card_row_base = grid_row
        for idx, srv in enumerate(folder_servers):
            r, c = divmod(idx, 2)
            row, col = card_row_base + r, c
            build_asm_server_card(app, host, srv, row, col)
            app._asm_card_grid_pos[srv.id] = (row, col)
        grid_row += (len(folder_servers) + 1) // 2


def _update_folder_counts(app: "ARKServerManagerApp") -> None:
    labels = getattr(app, "_asm_folder_count_labels", None) or {}
    if not labels:
        return
    fm = app.asm_config_manager.folder_manager
    for folder_name, folder_servers in fm.grouped().items():
        lbl = labels.get(folder_name)
        if not lbl or not lbl.winfo_exists():
            continue
        count_active = sum(
            1 for s in folder_servers
            if (inst := app.asm_server_manager.get_instance(s.id))
            and inst.status in (ASM_STATUS_RUNNING, ASM_STATUS_STARTING)
        )
        lbl.configure(text=f"{count_active}/{len(folder_servers)} online")


def _rebuild_all_cards(app: "ARKServerManagerApp") -> None:
    """Recria somente os cards (mantém cards_host e bulk bar)."""
    from .asm_server_card import build_asm_server_card

    host = _cards_host(app)
    if host is None:
        return

    positions = dict(getattr(app, "_asm_card_grid_pos", {}) or {})
    cards = getattr(app, "_asm_dashboard_cards", {}) or {}

    for sid, frame in list(cards.items()):
        try:
            if frame.winfo_exists():
                frame.destroy()
        except Exception:
            pass

    app._asm_dashboard_cards = {}
    for srv_id, (row, col) in positions.items():
        srv = app.asm_config_manager.get_server(srv_id)
        if srv:
            build_asm_server_card(app, host, srv, row, col)

    scroll = _dashboard_scroll(app)
    if scroll:
        host.update_idletasks()
        _schedule_dashboard_scroll_refresh(scroll)


def _update_card_rich_labels(app: "ARKServerManagerApp") -> None:
    """Atualiza métricas nos cards sem rebuild (tick 30s)."""
    theme = get_theme("tek")
    accent = theme["accent"]
    t_sec = theme["text_secondary"]

    for srv in app.asm_config_manager.servers:
        card = (getattr(app, "_asm_dashboard_cards", {}) or {}).get(srv.id)
        if card is None:
            continue
        try:
            if not card.winfo_exists():
                continue
        except Exception:
            continue

        refs = getattr(card, "_asm_rich_value_labels", None)
        if not refs:
            continue

        inst = app.asm_server_manager.get_instance(srv.id)
        is_running = inst and inst.status == ASM_STATUS_RUNNING
        rich_key = f"_asm_rich_status_{srv.id}"
        rich_data: dict = getattr(app, rich_key, {})
        val_tc = accent if is_running else t_sec
        val_font = ctk.CTkFont(family="Segoe UI", size=14, weight="bold")

        proc_val = rich_data.get("proc", "—")
        if proc_val and proc_val != "—" and len(proc_val) > 32:
            proc_val = "…" + proc_val[-31:]

        mapping = (
            ("Jogadores", rich_data.get("players", "—")),
            ("Uptime", rich_data.get("uptime", "—")),
            ("Memória", rich_data.get("ram", "—")),
            ("Versão", rich_data.get("version", "—")),
            ("PID", rich_data.get("pid", "—")),
            ("Processo", proc_val),
        )
        for hint, val in mapping:
            lbl = refs.get(hint)
            if lbl and lbl.winfo_exists():
                icon = {
                    "Jogadores": "👥", "Uptime": "🕐", "Memória": "💾",
                    "Versão": "📋", "PID": "#", "Processo": "📁",
                }[hint]
                lbl.configure(text=f"{icon}  {val}", text_color=val_tc, font=val_font)


def refresh_dashboard_metrics(app: "ARKServerManagerApp") -> None:
    """Refresh leve: stats + métricas dos cards — sem destruir widgets."""
    servers = app.asm_config_manager.servers
    _update_subtitle(app, servers)
    _refresh_asm_stats(app, servers)
    _refresh_asm_disks(app)
    _update_folder_counts(app)
    _update_card_rich_labels(app)


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


def rebuild_asm_dashboard_card(app: "ARKServerManagerApp", server_id: str) -> None:
    """Recria um único card (ex.: status parado↔online) sem destruir os demais."""
    from .asm_server_card import build_asm_server_card

    host = _cards_host(app)
    if host is None:
        return
    pos = (getattr(app, "_asm_card_grid_pos", {}) or {}).get(server_id)
    if not pos:
        return
    srv = app.asm_config_manager.get_server(server_id)
    if not srv:
        return

    cards = getattr(app, "_asm_dashboard_cards", {}) or {}
    old = cards.get(server_id)
    if old is not None:
        try:
            if old.winfo_exists():
                old.destroy()
        except Exception:
            pass

    row, col = pos
    build_asm_server_card(app, host, srv, row, col)

    scroll = _dashboard_scroll(app)
    if scroll:
        host.update_idletasks()
        _schedule_dashboard_scroll_refresh(scroll)


def _refresh_asm_dashboard(app: "ARKServerManagerApp", *, force_layout: bool = False) -> None:
    """Atualiza dashboard — rebuild completo só se layout mudou; senão refresh leve."""
    host = _cards_host(app)
    scroll = _dashboard_scroll(app)
    if host is None or scroll is None:
        return

    servers = app.asm_config_manager.servers
    sig = _layout_signature(app)
    layout_changed = force_layout or sig != getattr(app, "_asm_dashboard_layout_sig", None)

    if layout_changed:
        app._asm_dashboard_layout_sig = sig
        _build_bulk_bar(app)
        _populate_cards_grid(app, host)
        _update_subtitle(app, servers)
        _refresh_asm_stats(app, servers)
        _refresh_asm_disks(app)
        _update_folder_counts(app)
        host.update_idletasks()
        _schedule_dashboard_scroll_refresh(scroll)
    else:
        refresh_dashboard_metrics(app)


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
