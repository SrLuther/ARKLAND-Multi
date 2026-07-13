"""Painel global de broadcasts TEK — cadastro, envio, scheduler e sync."""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import get_theme
from ..asm_engine.asm_server_config import ASM_STATUS_RUNNING
from ..pages.broadcast_tek_settings import (
    all_server_ids,
    format_countdown,
    get_settings,
    seconds_until_next,
)

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp


_INTERVALS = ["5", "10", "15", "30", "60", "120", "180"]


def build_broadcasts_panel(app: "ARKServerManagerApp", parent: ctk.CTkFrame) -> None:
    theme = get_theme("tek")
    accent = theme["accent"]
    bg = theme["bg"]
    card_bg = theme["card_bg"]
    sep = theme["separator"]
    t_pri = theme["text_primary"]
    t_sec = theme["text_secondary"]
    t_mut = theme["text_muted"]
    acc_mb = theme["accent_muted_bg"]
    acc_dk = theme["accent_dark"]
    is_light = theme.get("_is_light", False)
    card_bdr = theme.get("card_border", sep)
    send_bg = "#dcfce7" if is_light else "#052e16"
    send_hover = "#bbf7d0" if is_light else "#14532d"
    send_tc = "#166534" if is_light else "#4ade80"

    settings = get_settings(app)
    servers = list(app.asm_config_manager.servers)

    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(4, weight=1)

    app._broadcast_server_vars = {}
    app._broadcast_message_vars = {}

    # ── Cabeçalho ─────────────────────────────────────────────────────────────
    hdr = ctk.CTkFrame(parent, fg_color="transparent")
    hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 8))
    hdr.grid_columnconfigure(0, weight=1)

    title_col = ctk.CTkFrame(hdr, fg_color="transparent")
    title_col.grid(row=0, column=0, sticky="w")
    ctk.CTkLabel(
        title_col, text="📢  Broadcasts",
        font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
        text_color=t_pri,
    ).pack(anchor="w")
    ctk.CTkLabel(
        title_col,
        text="Biblioteca global, envio por RCON, reenvio automático e seleção de destinos.",
        font=ctk.CTkFont(size=12),
        text_color=t_sec,
    ).pack(anchor="w", pady=(4, 0))

    btn_bar = ctk.CTkFrame(hdr, fg_color="transparent")
    btn_bar.grid(row=0, column=1, sticky="e")
    ctk.CTkButton(
        btn_bar, text="📜 Regulamento", width=130, height=36,
        fg_color=acc_mb, hover_color=acc_dk,
        text_color=accent, border_width=1, border_color=acc_dk,
        command=app._broadcast_tek_seed_regulamento,
    ).pack(side="left", padx=(0, 8))
    ctk.CTkButton(
        btn_bar, text="⬇  Importar", width=110, height=36,
        fg_color=acc_mb, hover_color=acc_dk,
        text_color=accent, border_width=1, border_color=acc_dk,
        command=app._broadcast_tek_import,
    ).pack(side="left", padx=(0, 8))
    ctk.CTkButton(
        btn_bar, text="⬆  Exportar", width=110, height=36,
        fg_color=acc_mb, hover_color=acc_dk,
        text_color=accent, border_width=1, border_color=acc_dk,
        command=app._broadcast_tek_export,
    ).pack(side="left")

    # ── Scheduler ─────────────────────────────────────────────────────────────
    sched = ctk.CTkFrame(parent, fg_color=card_bg, corner_radius=10,
                         border_width=1, border_color=card_bdr)
    sched.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 8))
    sched.grid_columnconfigure(4, weight=1)

    ctk.CTkLabel(
        sched, text="🕐  Reenvio automático",
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=t_sec,
    ).grid(row=0, column=0, padx=(14, 10), pady=(12, 4), sticky="w")

    app._broadcast_random_var = tk.BooleanVar(value=settings.random_order)
    ctk.CTkCheckBox(
        sched, text="Ordem aleatória",
        variable=app._broadcast_random_var,
        font=ctk.CTkFont(size=11),
        command=app._broadcast_tek_save_settings_from_ui,
    ).grid(row=0, column=1, padx=(0, 12), pady=(12, 4), sticky="w")

    ctk.CTkLabel(sched, text="Intervalo:", text_color=t_mut,
                 font=ctk.CTkFont(size=11)).grid(row=0, column=2, padx=(0, 4), pady=(12, 4))
    app._broadcast_interval_var = tk.StringVar(
        value=str(settings.interval_minutes)
        if str(settings.interval_minutes) in _INTERVALS else "30",
    )
    ctk.CTkOptionMenu(
        sched, variable=app._broadcast_interval_var, values=_INTERVALS,
        width=72, height=28,
        command=lambda _: app._broadcast_tek_save_settings_from_ui(),
    ).grid(row=0, column=3, padx=(0, 4), pady=(12, 4))
    ctk.CTkLabel(sched, text="min", text_color=t_mut,
                 font=ctk.CTkFont(size=11)).grid(row=0, column=4, sticky="w", pady=(12, 4))

    ctrl = ctk.CTkFrame(sched, fg_color="transparent")
    ctrl.grid(row=1, column=0, columnspan=5, sticky="ew", padx=14, pady=(4, 12))
    ctrl.grid_columnconfigure(2, weight=1)

    ctk.CTkButton(
        ctrl, text="▶  Iniciar ciclo", width=120, height=32,
        fg_color=send_bg, hover_color=send_hover, text_color=send_tc,
        font=ctk.CTkFont(size=11, weight="bold"),
        command=app._broadcast_tek_scheduler_start,
    ).grid(row=0, column=0, padx=(0, 8))

    ctk.CTkButton(
        ctrl, text="⏹  Parar", width=90, height=32,
        fg_color="#fee2e2" if is_light else "#7f1d1d",
        hover_color="#fecaca" if is_light else "#450a0a",
        text_color="#991b1b" if is_light else "#fca5a5",
        command=app._broadcast_tek_scheduler_stop,
    ).grid(row=0, column=1, padx=(0, 12))

    sched_active = settings.scheduler_enabled or getattr(
        app, "_broadcast_tek_scheduler_running", False,
    )
    status_txt = "Parado"
    if sched_active:
        status_txt = f"Ativo — próximo envio em {format_countdown(seconds_until_next(settings, active=True))}"
    app._broadcast_sched_status_var = tk.StringVar(value=status_txt)
    ctk.CTkLabel(
        ctrl, textvariable=app._broadcast_sched_status_var,
        font=ctk.CTkFont(size=11), text_color=t_sec,
    ).grid(row=0, column=2, sticky="w")
    app._broadcast_sched_countdown_var = tk.StringVar(
        value=format_countdown(seconds_until_next(settings, active=sched_active)) if sched_active else "—",
    )
    ctk.CTkLabel(
        ctrl, textvariable=app._broadcast_sched_countdown_var,
        font=ctk.CTkFont(family="Consolas", size=18, weight="bold"),
        text_color=accent,
    ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 4))

    ctk.CTkButton(
        ctrl, text="📢 Enviar próxima agora", width=160, height=32,
        fg_color=acc_mb, hover_color=acc_dk, text_color=accent,
        border_width=1, border_color=acc_dk,
        command=app._broadcast_tek_send_next_now,
    ).grid(row=0, column=3, sticky="e")

    # ── Servidores destino ────────────────────────────────────────────────────
    srv_card = ctk.CTkFrame(parent, fg_color=card_bg, corner_radius=10,
                            border_width=1, border_color=card_bdr)
    srv_card.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 8))
    srv_card.grid_columnconfigure(0, weight=1)

    srv_hdr = ctk.CTkFrame(srv_card, fg_color="transparent")
    srv_hdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
    ctk.CTkLabel(
        srv_hdr, text="🖥  Servidores destino",
        font=ctk.CTkFont(size=12, weight="bold"), text_color=t_sec,
    ).pack(side="left")

    all_ids = all_server_ids(app)
    saved_targets = set(settings.target_server_ids) if settings.target_server_ids else set(all_ids)
    app._broadcast_srv_all_var = tk.BooleanVar(value=bool(all_ids) and saved_targets >= set(all_ids))

    def _toggle_all_servers() -> None:
        val = app._broadcast_srv_all_var.get()
        for var in app._broadcast_server_vars.values():
            var.set(val)
        app._broadcast_tek_save_settings_from_ui()

    ctk.CTkCheckBox(
        srv_hdr, text="Selecionar todos",
        variable=app._broadcast_srv_all_var,
        font=ctk.CTkFont(size=11),
        command=_toggle_all_servers,
    ).pack(side="right")

    srv_row = ctk.CTkFrame(srv_card, fg_color="transparent")
    srv_row.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))

    if not servers:
        ctk.CTkLabel(
            srv_row, text="Nenhum servidor TEK configurado.",
            text_color=t_mut, font=ctk.CTkFont(size=11),
        ).pack(anchor="w")
    else:
        for srv in servers:
            inst = app.asm_server_manager.get_instance(srv.id)
            online = inst and inst.status == ASM_STATUS_RUNNING
            dot = "🟢" if online else "⚫"
            checked = srv.id in saved_targets if settings.target_server_ids else True
            var = tk.BooleanVar(value=checked)
            app._broadcast_server_vars[srv.id] = var

            def _on_srv_toggle(sid=srv.id) -> None:
                all_on = all(v.get() for v in app._broadcast_server_vars.values())
                app._broadcast_srv_all_var.set(all_on)
                app._broadcast_tek_save_settings_from_ui()

            chip = ctk.CTkFrame(srv_row, fg_color="transparent")
            chip.pack(side="left", padx=(0, 14), pady=2)
            ctk.CTkCheckBox(
                chip, text=f"{dot}  {srv.name}",
                variable=var, font=ctk.CTkFont(size=11),
                command=_on_srv_toggle,
            ).pack(anchor="w")

    # ── Envio rápido ──────────────────────────────────────────────────────────
    quick = ctk.CTkFrame(parent, fg_color=card_bg, corner_radius=10,
                         border_width=1, border_color=card_bdr)
    quick.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 8))
    quick.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        quick, text="📡 Envio rápido",
        font=ctk.CTkFont(size=12, weight="bold"), text_color=t_sec,
    ).grid(row=0, column=0, padx=(14, 8), pady=12, sticky="w")

    app._broadcast_quick_var = tk.StringVar()
    ctk.CTkEntry(
        quick, textvariable=app._broadcast_quick_var, height=34,
        placeholder_text="Mensagem avulsa para os servidores marcados acima...",
        font=ctk.CTkFont(size=11),
    ).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=12)

    ctk.CTkButton(
        quick, text="📢  Enviar", width=120, height=34,
        fg_color=send_bg, hover_color=send_hover, text_color=send_tc,
        font=ctk.CTkFont(size=11, weight="bold"),
        command=app._broadcast_tek_send_quick,
    ).grid(row=0, column=2, padx=(0, 14), pady=12)

    # ── Biblioteca ────────────────────────────────────────────────────────────
    body = ctk.CTkScrollableFrame(parent, fg_color=bg, corner_radius=0)
    body.grid(row=4, column=0, sticky="nsew", padx=0, pady=0)
    body.grid_columnconfigure(0, weight=1)

    add_fr = ctk.CTkFrame(body, fg_color=card_bg, corner_radius=10,
                          border_width=1, border_color=card_bdr)
    add_fr.grid(row=0, column=0, sticky="ew", padx=20, pady=(8, 8))
    add_fr.grid_columnconfigure(2, weight=1)

    ctk.CTkLabel(
        add_fr, text="+ Nova mensagem",
        font=ctk.CTkFont(size=12, weight="bold"), text_color=t_sec,
    ).grid(row=0, column=0, columnspan=4, padx=(14, 14), pady=(12, 6), sticky="w")

    ctk.CTkLabel(
        add_fr, text="Rótulo",
        font=ctk.CTkFont(size=10, weight="bold"), text_color=t_mut,
    ).grid(row=1, column=1, padx=(0, 8), sticky="w")
    ctk.CTkLabel(
        add_fr, text="Mensagem (texto exibido aos jogadores)",
        font=ctk.CTkFont(size=10, weight="bold"), text_color=t_mut,
    ).grid(row=1, column=2, padx=(0, 8), sticky="w")

    app._broadcast_new_label = tk.StringVar()
    ctk.CTkEntry(
        add_fr, textvariable=app._broadcast_new_label, height=32, width=180,
        placeholder_text="Ex: Reinício em 5 min",
        font=ctk.CTkFont(size=11),
    ).grid(row=2, column=1, padx=(0, 8), pady=(2, 12), sticky="w")

    app._broadcast_new_msg = tk.StringVar()
    ctk.CTkEntry(
        add_fr, textvariable=app._broadcast_new_msg, height=32,
        placeholder_text="Ex: [ARKLAND] Servidor reinicia em 5 minutos!",
        font=ctk.CTkFont(size=11),
    ).grid(row=2, column=2, sticky="ew", padx=(0, 8), pady=(2, 12))

    ctk.CTkButton(
        add_fr, text="Adicionar", width=100, height=32,
        fg_color=acc_mb, hover_color=acc_dk, text_color=accent,
        border_width=1, border_color=acc_dk,
        font=ctk.CTkFont(size=11, weight="bold"),
        command=app._broadcast_library_add_from_ui,
    ).grid(row=2, column=3, padx=(0, 14), pady=(2, 12), sticky="s")

    lib_hdr = ctk.CTkFrame(body, fg_color="transparent")
    lib_hdr.grid(row=1, column=0, sticky="ew", padx=24, pady=(4, 2))
    ctk.CTkLabel(
        lib_hdr, text="Mensagens salvas",
        font=ctk.CTkFont(size=11, weight="bold"), text_color=t_mut,
    ).pack(side="left")
    ctk.CTkLabel(
        lib_hdr,
        text="☑ = ciclo · «Regulamento» = pacote oficial (intervalo acima)",
        font=ctk.CTkFont(size=10), text_color=t_mut,
    ).pack(side="right")

    lib_scroll = ctk.CTkScrollableFrame(body, fg_color="transparent")
    lib_scroll.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 8))
    lib_scroll.grid_columnconfigure(0, weight=1)
    body.grid_rowconfigure(2, weight=1)
    app._broadcast_lib_scroll = lib_scroll

    ctk.CTkLabel(
        body,
        text="Biblioteca global — sincronize entre PCs com Exportar / Importar (.arkbroadcast)",
        font=ctk.CTkFont(size=10), text_color=t_mut,
    ).grid(row=3, column=0, sticky="w", padx=24, pady=(0, 16))

    app._broadcast_library_refresh()
    if sched_active:
        app.after(100, app._broadcast_tek_sync_scheduler_ui)
