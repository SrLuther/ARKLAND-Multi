from __future__ import annotations

import threading
import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _GREEN, _CARD_BG
import platform

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_performance_panel(app: "ARKServerManagerApp", parent) -> None:
    parent.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(parent, text="Desempenho do Sistema",
                 font=ctk.CTkFont(size=24, weight="bold")).grid(
        row=0, column=0, padx=24, pady=(24, 2), sticky="w")
    ctk.CTkLabel(parent, text="Monitoramento em tempo real dos recursos desta máquina.",
                 text_color="gray60").grid(row=1, column=0, padx=24, pady=(0, 18), sticky="w")

    cards = ctk.CTkFrame(parent, fg_color="transparent")
    cards.grid(row=2, column=0, padx=16, pady=0, sticky="ew")
    cards.grid_columnconfigure((0, 1, 2), weight=1)

    # ── CPU ───────────────────────────────────────────────────────────────
    cpu_card = ctk.CTkFrame(cards, corner_radius=12, fg_color=_CARD_BG)
    cpu_card.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")
    cpu_card.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(cpu_card, text="🖥  CPU",
                 font=ctk.CTkFont(size=14, weight="bold"),
                 text_color="#88d4a0").grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

    app._perf_cpu_pct_var = tk.StringVar(value="—")
    ctk.CTkLabel(cpu_card, textvariable=app._perf_cpu_pct_var,
                 font=ctk.CTkFont(size=32, weight="bold"),
                 text_color=_GREEN).grid(row=1, column=0, padx=16, pady=(0, 4), sticky="w")

    app._perf_cpu_bar = ctk.CTkProgressBar(cpu_card, height=8, corner_radius=4,
                                             progress_color=_GREEN)
    app._perf_cpu_bar.set(0)
    app._perf_cpu_bar.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")

    cpu_name = platform.processor() or "Processador"
    ctk.CTkLabel(cpu_card, text=cpu_name, font=ctk.CTkFont(size=10),
                 text_color="gray55", wraplength=230, justify="left").grid(
        row=3, column=0, padx=16, pady=(0, 4), sticky="w")

    app._perf_cpu_info_var = tk.StringVar(value="Aguardando...")
    ctk.CTkLabel(cpu_card, textvariable=app._perf_cpu_info_var,
                 font=ctk.CTkFont(size=11), text_color="gray60").grid(
        row=4, column=0, padx=16, pady=(0, 4), sticky="w")
    app._perf_cpu_temp_var = tk.StringVar(value="🌡 Temperatura: —")
    ctk.CTkLabel(cpu_card, textvariable=app._perf_cpu_temp_var,
                 font=ctk.CTkFont(size=11), text_color="#ff9944").grid(
        row=5, column=0, padx=16, pady=(0, 16), sticky="w")

    # ── RAM ───────────────────────────────────────────────────────────────
    ram_card = ctk.CTkFrame(cards, corner_radius=12, fg_color=_CARD_BG)
    ram_card.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")
    ram_card.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(ram_card, text="💾  RAM",
                 font=ctk.CTkFont(size=14, weight="bold"),
                 text_color="#88d4a0").grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

    app._perf_ram_pct_var = tk.StringVar(value="—")
    ctk.CTkLabel(ram_card, textvariable=app._perf_ram_pct_var,
                 font=ctk.CTkFont(size=32, weight="bold"),
                 text_color=_GREEN).grid(row=1, column=0, padx=16, pady=(0, 4), sticky="w")

    app._perf_ram_bar = ctk.CTkProgressBar(ram_card, height=8, corner_radius=4,
                                              progress_color=_GREEN)
    app._perf_ram_bar.set(0)
    app._perf_ram_bar.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")

    app._perf_ram_info_var = tk.StringVar(value="Aguardando...")
    ctk.CTkLabel(ram_card, textvariable=app._perf_ram_info_var,
                 font=ctk.CTkFont(size=11), text_color="gray60").grid(
        row=3, column=0, padx=16, pady=(0, 16), sticky="w")

    # ── GPU ───────────────────────────────────────────────────────────────
    gpu_card = ctk.CTkFrame(cards, corner_radius=12, fg_color=_CARD_BG)
    gpu_card.grid(row=0, column=2, padx=6, pady=6, sticky="nsew")
    gpu_card.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(gpu_card, text="🎮  GPU",
                 font=ctk.CTkFont(size=14, weight="bold"),
                 text_color="#88d4a0").grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

    app._perf_gpu_pct_var = tk.StringVar(value="—")
    ctk.CTkLabel(gpu_card, textvariable=app._perf_gpu_pct_var,
                 font=ctk.CTkFont(size=32, weight="bold"),
                 text_color=_GREEN).grid(row=1, column=0, padx=16, pady=(0, 4), sticky="w")

    app._perf_gpu_bar = ctk.CTkProgressBar(gpu_card, height=8, corner_radius=4,
                                              progress_color=_GREEN)
    app._perf_gpu_bar.set(0)
    app._perf_gpu_bar.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")

    app._perf_gpu_info_var = tk.StringVar(value="Coletando informações...")
    ctk.CTkLabel(gpu_card, textvariable=app._perf_gpu_info_var,
                 font=ctk.CTkFont(size=11), text_color="gray60",
                 wraplength=230, justify="left").grid(
        row=3, column=0, padx=16, pady=(0, 4), sticky="w")
    app._perf_gpu_temp_var = tk.StringVar(value="🌡 Temperatura: —")
    ctk.CTkLabel(gpu_card, textvariable=app._perf_gpu_temp_var,
                 font=ctk.CTkFont(size=11), text_color="#ff9944").grid(
        row=4, column=0, padx=16, pady=(0, 16), sticky="w")

    threading.Thread(target=app._collect_gpu_info, daemon=True,
                     name="gpu-info").start()

    # ── Consumo por Servidor ──────────────────────────────────────────────
    srv_section = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    srv_section.grid(row=3, column=0, padx=22, pady=(0, 8), sticky="ew")
    srv_section.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(
        srv_section, text="📡  Consumo por Servidor",
        font=ctk.CTkFont(size=14, weight="bold"), text_color="#88d4a0",
    ).grid(row=0, column=0, padx=16, pady=(14, 6), sticky="w")
    app._perf_servers_inner = ctk.CTkFrame(srv_section, fg_color="transparent")
    app._perf_servers_inner.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="ew")
    ctk.CTkLabel(app._perf_servers_inner, text="Iniciando monitoramento...",
                 text_color="gray55", font=ctk.CTkFont(size=12)
                 ).grid(row=0, column=0, padx=4, pady=4, sticky="w")

    # ── Seção de Pontos Críticos ─────────────────────────────────────────
    crit_outer = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    crit_outer.grid(row=4, column=0, padx=22, pady=(0, 16), sticky="ew")
    crit_outer.grid_columnconfigure(0, weight=1)

    crit_hdr = ctk.CTkFrame(crit_outer, fg_color="transparent")
    crit_hdr.grid(row=0, column=0, padx=16, pady=(14, 4), sticky="ew")
    crit_hdr.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        crit_hdr, text="⚠️  Pontos Críticos",
        font=ctk.CTkFont(size=14, weight="bold"), text_color="#fbbf24",
    ).grid(row=0, column=0, sticky="w")

    ctk.CTkButton(
        crit_hdr, text="🗑 Limpar", width=90, height=28,
        fg_color="#3a1515", hover_color="#5a2020",
        font=ctk.CTkFont(size=11),
        command=app._clear_perf_critical_log,
    ).grid(row=0, column=1)

    thr_fr = ctk.CTkFrame(crit_outer, fg_color="transparent")
    thr_fr.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")

    ctk.CTkLabel(thr_fr, text="Registrar quando:",
                 text_color="gray60", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 8))
    ctk.CTkLabel(thr_fr, text="Aviso ≥",
                 text_color="#ffaa44", font=ctk.CTkFont(size=11)).pack(side="left")
    warn_var = tk.StringVar(value="80")
    ctk.CTkEntry(thr_fr, textvariable=warn_var, width=48, height=26,
                 justify="center").pack(side="left", padx=(4, 2))
    ctk.CTkLabel(thr_fr, text="%     Crítico ≥",
                 text_color="#ff6666", font=ctk.CTkFont(size=11)).pack(side="left", padx=(4, 0))
    crit_var = tk.StringVar(value="90")
    ctk.CTkEntry(thr_fr, textvariable=crit_var, width=48, height=26,
                 justify="center").pack(side="left", padx=(4, 2))
    ctk.CTkLabel(thr_fr, text="%",
                 text_color="gray60", font=ctk.CTkFont(size=11)).pack(side="left")

    app._perf_alert_warn_var = warn_var
    app._perf_alert_crit_var = crit_var

    log_box = ctk.CTkTextbox(
        crit_outer, height=180, state="disabled",
        font=ctk.CTkFont(family="Consolas", size=11),
        fg_color="#0d0d18", text_color="#c8c8d8", corner_radius=6,
    )
    log_box.grid(row=2, column=0, padx=16, pady=(0, 14), sticky="ew")
    app._perf_critical_log = log_box

