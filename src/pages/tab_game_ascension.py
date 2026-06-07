"""
Painel de ascensão do jogador extraído de tab_game.py.
Mantém tab_game.py abaixo de 1000 linhas.
"""
from __future__ import annotations

import tkinter as tk

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _GREEN, _GREEN_DARK, _GREEN_HOVER


def build_ascension_panel(parent_frame, row_n: int) -> None:
    """Painel informativo de níveis base e calculadora de ascensões."""
    _BG_PANEL = "#12122a"
    _BDR      = "#2a2a55"
    panel = tk.Frame(parent_frame, bg=_BG_PANEL, highlightthickness=1,
                     highlightbackground=_BDR)
    panel.grid(row=row_n, column=0, columnspan=2,
               padx=6, pady=(2, 10), sticky="ew")
    panel.columnconfigure(0, weight=1)

    # Cabeçalho
    tk.Label(panel, text="📊  Referência de Níveis Vanilla (ARK oficial)",
             bg=_BG_PANEL, fg="#c8c8e8",
             font=ctk.CTkFont(size=12, weight="bold"),
             anchor="w").grid(row=0, column=0, padx=12, pady=(8, 2), sticky="w")
    tk.Frame(panel, bg=_GREEN, height=1).grid(
        row=1, column=0, padx=12, sticky="ew")

    # Info estática
    info = tk.Frame(panel, bg=_BG_PANEL)
    info.grid(row=2, column=0, padx=12, pady=(6, 4), sticky="w")
    _HINT = "gray50"
    tk.Label(info, text="Nível base do jogador (sem ascensões):",
             bg=_BG_PANEL, fg=_HINT,
             font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w", padx=(0, 8))
    tk.Label(info, text="105", bg=_BG_PANEL, fg=_GREEN,
             font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=1, sticky="w")
    tk.Label(info, text="Nível máximo de dino selvagem (Dificuldade 5.0):",
             bg=_BG_PANEL, fg=_HINT,
             font=ctk.CTkFont(size=11)).grid(row=1, column=0, sticky="w", padx=(0, 8))
    tk.Label(info, text="150", bg=_BG_PANEL, fg=_GREEN,
             font=ctk.CTkFont(size=11, weight="bold")).grid(row=1, column=1, sticky="w")

    # Divisor
    tk.Frame(panel, bg="#1e1e3a", height=1).grid(
        row=3, column=0, padx=12, sticky="ew", pady=(4, 2))

    # Título calculadora
    tk.Label(panel, text="🧮  Calculadora de Ascensões do Jogador",
             bg=_BG_PANEL, fg="#c8c8e8",
             font=ctk.CTkFont(size=11, weight="bold"),
             anchor="w").grid(row=4, column=0, padx=12, pady=(4, 2), sticky="w")
    tk.Label(panel,
             text="Selecione as ascensões completadas para ver o nível máximo final:",
             bg=_BG_PANEL, fg=_HINT,
             font=ctk.CTkFont(size=10)).grid(row=5, column=0, padx=12,
                                              pady=(0, 6), sticky="w")

    # Ascensões disponíveis:  (nome, níveis concedidos por tier)
    # Tier α/β/γ — usa o maior tier selecionado (são mutuamente exclusivos por mapa)
    # Mapas com tiers γ/β/α — cada um concede +5/+10/+15 níveis (cumulativo: usa o maior)
    _TIERED = [
        # (nome,               γ,  β,  α,  hint)
        ("The Island",         5, 10, 15, "Overseer — The Island (cavernas γ/β/α)"),
        ("Scorched Earth",     5, 10, 15, "Manticore — Scorched Earth (γ/β/α)"),
        ("Aberration",         5, 10, 15, "Rockwell — Aberration (γ/β/α)"),
        ("Extinction",         5, 10, 15, "King Titan — Extinction (γ/β/α)"),
        ("Genesis: Part 1",    5, 10, 15, "Corrupted Master Controller (γ/β/α)"),
        ("Genesis: Part 2",    5, 10, 15, "Rockwell Prime — Genesis Part 2 (γ/β/α)"),
    ]
    # DLCs com tier único (sem γ/β — somente α)
    _SINGLE = [
        ("Aquatica (α)", 5, "DLC — Mapa Aquatica (conta na soma oficial)"),
    ]
    _EXTRA = [
        ("Chibis",             5, "Coletar chibis dourados no Fear Evolved / Winter Wonderland"),
        ("Notas de Explorador (todas)", 10, "Completar todas as notas de explorador (todas as Story ARKs)"),
        ("Runas de Hjemskr",   5, "Runas de Fjordur"),
    ]

    chk_vars: list[tk.BooleanVar] = []

    chk_fr = tk.Frame(panel, bg=_BG_PANEL)
    chk_fr.grid(row=6, column=0, padx=12, pady=(0, 4), sticky="ew")
    chk_fr.columnconfigure((0, 1, 2), weight=1)

    tier_vars: dict[str, list[tk.BooleanVar]] = {}  # name → [γ, β, α]

    _col = 0
    _row_chk = 0

    def _add_chk(parent_fr, label: str, hint: str, var: tk.BooleanVar,
                 result_var: tk.IntVar, levels: int, c: int, rw: int) -> None:
        fr = tk.Frame(parent_fr, bg=_BG_PANEL)
        fr.grid(row=rw, column=c, padx=4, pady=2, sticky="w")
        ctk.CTkCheckBox(fr, text=label, variable=var, width=20,
                        checkmark_color="white", fg_color=_GREEN_DARK,
                        hover_color=_GREEN_HOVER,
                        command=lambda: _recalc(result_var)).pack(side="left")
        tk.Label(fr, text=f"+{levels}", bg=_BG_PANEL, fg=_GREEN,
                 font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=(4, 0))
        if hint:
            tk.Label(fr, text=f"  {hint}", bg=_BG_PANEL, fg=_HINT,
                     font=ctk.CTkFont(size=9)).pack(side="left")

    result_var = tk.IntVar(value=105)

    def _recalc(rv: tk.IntVar) -> None:
        total = 105
        # single checkboxes
        for sv, lvls in zip(chk_vars, [t[1] for t in _SINGLE]):
            if sv.get():
                total += lvls
        # tiered: pick highest tier selected per map
        for name, tv_list in tier_vars.items():
            best = 0
            for tier_idx, (tv, bonus) in enumerate(zip(tv_list, [5, 10, 15])):
                if tv.get():
                    best = max(best, bonus)
            total += best
        # extras
        for sv, lvls in zip(extra_vars, [e[1] for e in _EXTRA]):
            if sv.get():
                total += lvls
        rv.set(total)

    extra_vars: list[tk.BooleanVar] = []

    # Seção: mapas com tier
    tier_sec = tk.LabelFrame(chk_fr, text="  Mapas com Tiers γ/β/α (boss caves)  ",
                              bg=_BG_PANEL, fg="gray60",
                              font=ctk.CTkFont(size=10))
    tier_sec.grid(row=0, column=0, columnspan=3, padx=2, pady=(0, 6), sticky="ew")
    for col_idx in range(4):
        tier_sec.columnconfigure(col_idx, weight=1)

    for t_idx, (tname, g_b, b_b, a_b, t_hint) in enumerate(_TIERED):
        tier_row = tk.Frame(tier_sec, bg=_BG_PANEL)
        tier_row.grid(row=t_idx, column=0, columnspan=4,
                      padx=4, pady=1, sticky="w")
        tk.Label(tier_row, text=tname, width=16, anchor="w",
                 bg=_BG_PANEL, fg="gray70",
                 font=ctk.CTkFont(size=10)).pack(side="left", padx=(2, 8))
        tvs = []
        for tier_lbl, tier_bonus in [("γ", g_b), ("β", b_b), ("α", a_b)]:
            tv = tk.BooleanVar(value=False)
            tvs.append(tv)
            ctk.CTkCheckBox(tier_row, text=f"{tier_lbl} +{tier_bonus}", variable=tv,
                            width=20, fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                            checkmark_color="white",
                            command=lambda: _recalc(result_var)).pack(
                side="left", padx=6)
        tier_vars[tname] = tvs

    # Seção: mapas de expansão (single tier)
    exp_sec = tk.LabelFrame(chk_fr, text="  DLCs (+5 cada)  ",
                             bg=_BG_PANEL, fg="gray60",
                             font=ctk.CTkFont(size=10))
    exp_sec.grid(row=1, column=0, columnspan=3, padx=2, pady=(0, 6), sticky="ew")
    for ci in range(3):
        exp_sec.columnconfigure(ci, weight=1)

    for s_idx, (s_name, s_lvls, s_hint) in enumerate(_SINGLE):
        sv = tk.BooleanVar(value=False)
        chk_vars.append(sv)
        fr = tk.Frame(exp_sec, bg=_BG_PANEL)
        fr.grid(row=s_idx // 3, column=s_idx % 3, padx=4, pady=2, sticky="w")
        ctk.CTkCheckBox(fr, text=s_name, variable=sv, width=20,
                        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                        checkmark_color="white",
                        command=lambda: _recalc(result_var)).pack(side="left")
        tk.Label(fr, text=f"+{s_lvls}", bg=_BG_PANEL, fg=_GREEN,
                 font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=(4, 0))

    # Seção: extras
    ext_sec = tk.LabelFrame(chk_fr, text="  Extras (Chibis, Notas, Runas)  ",
                             bg=_BG_PANEL, fg="gray60",
                             font=ctk.CTkFont(size=10))
    ext_sec.grid(row=2, column=0, columnspan=3, padx=2, pady=(0, 8), sticky="ew")
    for ci in range(3):
        ext_sec.columnconfigure(ci, weight=1)

    for e_idx, (e_name, e_lvls, e_hint) in enumerate(_EXTRA):
        ev = tk.BooleanVar(value=False)
        extra_vars.append(ev)
        fr = tk.Frame(ext_sec, bg=_BG_PANEL)
        fr.grid(row=e_idx // 3, column=e_idx % 3, padx=4, pady=2, sticky="w")
        ctk.CTkCheckBox(fr, text=e_name, variable=ev, width=20,
                        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                        checkmark_color="white",
                        command=lambda: _recalc(result_var)).pack(side="left")
        tk.Label(fr, text=f"+{e_lvls}", bg=_BG_PANEL, fg=_GREEN,
                 font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=(4, 0))
        if e_hint:
            tk.Label(fr, text=f"  {e_hint}", bg=_BG_PANEL, fg=_HINT,
                     font=ctk.CTkFont(size=9)).pack(side="left")

    # Resultado
    res_fr = tk.Frame(panel, bg="#0d1a1f",
                      highlightthickness=1, highlightbackground=_GREEN_DARK)
    res_fr.grid(row=7, column=0, padx=12, pady=(0, 10), sticky="ew")
    tk.Label(res_fr, text="Nível máximo calculado do jogador:",
             bg="#0d1a1f", fg="gray60",
             font=ctk.CTkFont(size=11)).pack(side="left", padx=(12, 6), pady=8)
    ctk.CTkLabel(res_fr, textvariable=result_var,  # type: ignore[arg-type]
                 text_color=_GREEN,
                 font=ctk.CTkFont(size=18, weight="bold")).pack(
        side="left", pady=8)
    tk.Label(res_fr,
             text="  ← inclui todas as ascensões selecionadas (Aquatica contabilizada)",
             bg="#0d1a1f", fg="gray45",
             font=ctk.CTkFont(size=9)).pack(side="left", padx=(4, 12), pady=8)

