from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _CARD_BG
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def refresh_buffs_ui(app: "ARKServerManagerApp") -> None:
    """Reconstrói o conteúdo dinâmico do painel BUFFs."""
    body = app._buffs_body_frame
    if body is None:
        return

    # Cancela ticker de countdown anterior
    if app._buff_countdown_job:
        try:
            app.after_cancel(app._buff_countdown_job)
        except Exception:
            pass
        app._buff_countdown_job = None
    app._buff_countdown_labels = []

    # Limpa conteúdo anterior
    for w in body.winfo_children():
        w.destroy()

    bm = app._buff_manager
    servers = app.config_manager.servers

    # Resolve servidor selecionado
    srv_id: Optional[str] = None
    srv_name_sel = app._buffs_server_var.get() if app._buffs_server_var else ""
    for s in servers:
        if s.name == srv_name_sel:
            srv_id = s.id
            break

    row_idx = 0

    # ── BUFF Ativo ──────────────────────────────────────────────────────
    ctk.CTkLabel(
        body, text="BUFF ATIVO",
        font=ctk.CTkFont(size=12, weight="bold"), text_color="#88d4a0",
    ).grid(row=row_idx, column=0, padx=20, pady=(16, 4), sticky="w")
    row_idx += 1

    active = bm.get_active_event(srv_id) if bm and srv_id else None
    if active:
        app._build_active_buff_card(body, row_idx, active)
    else:
        none_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
        none_card.grid(row=row_idx, column=0, padx=20, pady=(0, 8), sticky="ew")
        ctk.CTkLabel(
            none_card, text="Nenhum BUFF ativo no momento.",
            text_color="gray50", font=ctk.CTkFont(size=12),
        ).pack(padx=20, pady=18)
    row_idx += 1

    # ── BUFFs Agendados ─────────────────────────────────────────────────
    ctk.CTkLabel(
        body, text="BUFFs AGENDADOS",
        font=ctk.CTkFont(size=12, weight="bold"), text_color="#88d4a0",
    ).grid(row=row_idx, column=0, padx=20, pady=(12, 4), sticky="w")
    row_idx += 1

    scheduled = bm.get_scheduled_events(srv_id) if bm and srv_id else []
    if scheduled:
        for evt in scheduled:
            app._build_scheduled_buff_row(body, row_idx, evt)
            row_idx += 1
    else:
        empty = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
        empty.grid(row=row_idx, column=0, padx=20, pady=(0, 4), sticky="ew")
        ctk.CTkLabel(empty, text="Nenhum BUFF agendado.",
                     text_color="gray50").pack(padx=20, pady=12)
        row_idx += 1

    # ── Presets Salvos ──────────────────────────────────────────────────
    presets = bm.get_presets() if bm else []
    if presets:
        ctk.CTkLabel(
            body, text="PRESETS SALVOS",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#88d4a0",
        ).grid(row=row_idx, column=0, padx=20, pady=(12, 4), sticky="w")
        row_idx += 1
        grid_f = ctk.CTkFrame(body, fg_color="transparent")
        grid_f.grid(row=row_idx, column=0, padx=20, pady=(0, 4), sticky="ew")
        grid_f.grid_columnconfigure((0, 1, 2), weight=1)
        row_idx += 1
        for ci, preset in enumerate(presets):
            app._build_preset_chip(grid_f, ci // 3, ci % 3, preset, srv_id)

    # ── Histórico ───────────────────────────────────────────────────────
    finished = bm.get_finished_events(srv_id) if bm and srv_id else []
    if finished:
        ctk.CTkLabel(
            body, text="HISTÓRICO",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#88d4a0",
        ).grid(row=row_idx, column=0, padx=20, pady=(12, 4), sticky="w")
        row_idx += 1
        for evt in finished[:10]:
            app._build_history_row(body, row_idx, evt)
            row_idx += 1

    # Espaço final
    ctk.CTkFrame(body, fg_color="transparent", height=30).grid(
        row=row_idx, column=0)

    # Inicia ticker de countdown (1s)
    app._buff_countdown_job = app.after(1000, app._buff_countdown_tick)

