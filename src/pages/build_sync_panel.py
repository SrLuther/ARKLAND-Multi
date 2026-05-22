from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import (
    _BLUE,
    _BLUE_HOVER,
    _CARD_BG,
    _GREEN_DARK,
    _GREEN_HOVER,
    _MAX_SYNC_CYCLES,
    _MAX_SYNC_FOLDERS,
)
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_sync_panel(app: "ARKServerManagerApp", parent: "ctk.CTkFrame") -> None:
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(5, weight=1)

    # ── Cabeçalho ─────────────────────────────────────────────────────────
    ctk.CTkLabel(parent, text="Sincronização de Cluster",
                 font=ctk.CTkFont(size=24, weight="bold")).grid(
        row=0, column=0, padx=24, pady=(24, 2), sticky="w")
    ctk.CTkLabel(
        parent,
        text=(f"Até {_MAX_SYNC_CYCLES} ciclos independentes · "
              f"até {_MAX_SYNC_FOLDERS} pastas por ciclo · sync N-way bidirecional."),
        text_color="gray60").grid(row=1, column=0, padx=24, pady=(0, 12), sticky="w")

    # ── Card de Status ────────────────────────────────────────────────────
    status_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    status_card.grid(row=2, column=0, padx=20, pady=(0, 8), sticky="ew")
    status_card.grid_columnconfigure(1, weight=1)

    app._sync_status_lbl = ctk.CTkLabel(
        status_card, text="⬜  Parado",
        font=ctk.CTkFont(size=14, weight="bold"), text_color="gray60")
    app._sync_status_lbl.grid(row=0, column=0, padx=20, pady=(14, 6), sticky="w")

    app._sync_stats_lbl = ctk.CTkLabel(
        status_card, text="Ciclos: 0  |  Arquivos: 0  |  Erros: 0  |  Último: —",
        text_color="gray50", font=ctk.CTkFont(size=11))
    app._sync_stats_lbl.grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 14), sticky="w")

    btn_frame = ctk.CTkFrame(status_card, fg_color="transparent")
    btn_frame.grid(row=0, column=1, padx=12, pady=10, sticky="e")

    app._sync_toggle_btn = ctk.CTkButton(
        btn_frame, text="▶  Iniciar Sync", width=150, height=36,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=app._toggle_sync)
    app._sync_toggle_btn.grid(row=0, column=0, padx=(0, 8))

    ctk.CTkButton(
        btn_frame, text="⟳  Sincronizar Agora", width=160, height=36,
        fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=app._force_sync_once).grid(row=0, column=1)

    # ── Card de Ciclos ────────────────────────────────────────────────────
    cycles_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    cycles_card.grid(row=3, column=0, padx=20, pady=(0, 8), sticky="ew")
    cycles_card.grid_columnconfigure(0, weight=1)

    # Cabeçalho do card: título + intervalo + salvar
    ch = ctk.CTkFrame(cycles_card, fg_color="transparent")
    ch.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
    ch.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(ch, text="Ciclos de Sincronização",
                 font=ctk.CTkFont(size=13, weight="bold"),
                 text_color="gray70").grid(row=0, column=0, sticky="w")

    cf_right = ctk.CTkFrame(ch, fg_color="transparent")
    cf_right.grid(row=0, column=1, sticky="e")
    ctk.CTkLabel(cf_right, text="Intervalo (s):", text_color="gray60",
                 font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(0, 4))
    app._sync_interval_var = tk.StringVar(
        value=str(app.config_manager.config.sync_interval))
    ctk.CTkEntry(cf_right, textvariable=app._sync_interval_var,
                 width=64, height=30).grid(row=0, column=1, padx=(0, 8))
    ctk.CTkButton(cf_right, text="💾  Salvar", width=110, height=30,
                  fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  command=app._save_sync_config).grid(row=0, column=2)

    # Frame rolável com os cards de cada ciclo
    app._sync_cycles_frame = ctk.CTkScrollableFrame(
        cycles_card, fg_color="transparent", height=200)
    app._sync_cycles_frame.grid(row=1, column=0, padx=8, pady=0, sticky="ew")
    app._sync_cycles_frame.grid_columnconfigure(0, weight=1)

    # Botão "+ Adicionar Ciclo"
    app._sync_add_cycle_btn = ctk.CTkButton(
        cycles_card, text="＋  Adicionar Ciclo", height=30, width=160,
        fg_color="#2a2a40", hover_color="#363656",
        command=app._add_sync_cycle)
    app._sync_add_cycle_btn.grid(row=2, column=0, padx=12, pady=(4, 10), sticky="w")

    # ── Log de Sync ────────────────────────────────────────────────────────
    ctk.CTkLabel(parent, text="Log de Sincronização",
                 font=ctk.CTkFont(size=13, weight="bold"),
                 text_color="gray70").grid(
        row=4, column=0, padx=24, pady=(4, 4), sticky="w")

    app._sync_log_box = ctk.CTkTextbox(
        parent, state="disabled", font=ctk.CTkFont(family="Consolas", size=11),
        fg_color="#0d0d18", text_color="#c8c8d8", corner_radius=8)
    app._sync_log_box.grid(row=5, column=0, padx=20, pady=(0, 20), sticky="nsew")

    # Carrega ciclos salvos na config
    app._sync_cycle_vars = []
    saved = app.config_manager.config.sync_cycles or []
    if not saved:
        saved = [[""]]  # 1 ciclo vazio por padrão
    for cycle_paths in saved[:_MAX_SYNC_CYCLES]:
        app._add_sync_cycle(cycle_paths if isinstance(cycle_paths, list) else [""])

