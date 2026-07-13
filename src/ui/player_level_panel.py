"""Painel unificado de nível máximo do jogador (ASM clássico e TEK)."""
from __future__ import annotations

import tkinter as tk
from typing import Any, Callable, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..player_engram_points import ARK_ENGRAM_POINTS_PER_LEVEL, engram_points_per_level
from ..player_level_ascension import (
    ARK_DEFAULT_BASE_LEVEL,
    ARK_TOTAL_BONUS_LEVELS,
    ARK_BOSS_ASCENSION_LEVELS,
    ARK_CONQUEST_LEVELS,
    ASCENSION_BOSSES,
    CONQUEST_BONUSES,
    calc_max_total_level,
    level_to_xp,
    serialize_ascension_state,
)
from ..player_level_ramp import (
    _curve_params_from_cfg,
    build_ramp_values,
    cumulative_xp_on_ramp,
    detect_and_apply_legacy_curve,
    export_ramp_raw,
    is_legacy_geometric_xp_cap,
    is_player_level_progressions_enabled,
    total_ramp_slots,
)
from ..ui_constants import _GREEN, _GREEN_DARK


def _resolve_initial(cfg: object, *, game_settings: bool) -> int:
    if game_settings:
        gs = cfg
        return int(getattr(gs, "player_base_level", 0) or 0) or ARK_DEFAULT_BASE_LEVEL
    return int(getattr(cfg, "player_base_level", 0) or 0) or ARK_DEFAULT_BASE_LEVEL


def sync_player_level_vars(vars_ref: dict, cfg: object | None = None) -> tuple[int, int, int, int]:
    """Recalcula derivados a partir do nível base. Retorna (base, total, xp_cap, rampa)."""
    try:
        base = int(float(vars_ref["player_base_level"].get()))
    except (KeyError, ValueError, TypeError, tk.TclError):
        base = ARK_DEFAULT_BASE_LEVEL
    base = max(1, base)

    progressions = False
    prog_var = vars_ref.get("player_level_progressions_enabled")
    if prog_var is not None:
        try:
            progressions = bool(prog_var.get())
        except tk.TclError:
            progressions = False
    elif cfg is not None:
        progressions = is_player_level_progressions_enabled(cfg)

    if cfg is not None:
        if hasattr(cfg, "player_base_level"):
            cfg.player_base_level = base
        if hasattr(cfg, "player_level_progressions_enabled"):
            cfg.player_level_progressions_enabled = progressions
        if progressions:
            detect_and_apply_legacy_curve(cfg)

    total = calc_max_total_level(base)
    if progressions:
        curve = _curve_params_from_cfg(cfg)
        ramp_values = build_ramp_values(
            base,
            mode=str(curve["mode"]),
            xp_base=int(curve["xp_base"]),
            xp_mult=float(curve["xp_mult"]),
            formula=str(curve["formula"]),
        )
        xp = cumulative_xp_on_ramp(ramp_values, base) if ramp_values else level_to_xp(base)
        if cfg is not None:
            existing = int(getattr(cfg, "override_max_xp_player", 0) or 0)
            gs = getattr(cfg, "game_settings", None)
            if gs is not None:
                existing = max(
                    existing,
                    int(getattr(gs, "override_max_experience_points_player", 0) or 0),
                )
            if is_legacy_geometric_xp_cap(existing, base):
                xp = existing
        ramp_entries = len(ramp_values)
    else:
        ramp_values = []
        xp = level_to_xp(base)
        ramp_entries = 0

    if "player_ascension_state" in vars_ref:
        vars_ref["player_ascension_state"].set(serialize_ascension_state())
    if "override_max_xp_player" in vars_ref:
        vars_ref["override_max_xp_player"].set(str(xp))
    if "gs_player_level_cap" in vars_ref:
        vars_ref["gs_player_level_cap"].set(str(total))
    if "gs_override_max_experience_points_player" in vars_ref:
        vars_ref["gs_override_max_experience_points_player"].set(str(xp))
    if "_pl_total_var" in vars_ref:
        vars_ref["_pl_total_var"].set(str(total))
    if "_pl_xp_var" in vars_ref:
        xp_label = (
            f"{xp:,} XP (cap farmável no nível base)"
            if progressions
            else f"{xp:,} XP (curva vanilla — cap GUS)"
        )
        vars_ref["_pl_xp_var"].set(xp_label)
    if "_pl_asc_bonus_var" in vars_ref:
        vars_ref["_pl_asc_bonus_var"].set(f"+{ARK_TOTAL_BONUS_LEVELS}")
    if "_pl_effective_var" in vars_ref:
        vars_ref["_pl_effective_var"].set(str(total))
    if "_pl_ramp_var" in vars_ref:
        vars_ref["_pl_ramp_var"].set(
            str(ramp_entries) if progressions else "— (vanilla)"
        )
    if "_pl_engram_var" in vars_ref:
        vars_ref["_pl_engram_var"].set(
            str(engram_points_per_level()) if progressions else "vanilla (8)"
        )
    if "player_level_stats_raw" in vars_ref:
        vars_ref["player_level_stats_raw"].set(
            export_ramp_raw(ramp_values) if progressions and ramp_values else ""
        )
    if "_pl_warn_var" in vars_ref:
        vars_ref["_pl_warn_var"].set("")

    return base, total, xp, ramp_entries


def apply_classic_player_level_to_gs(w: dict, gs: object) -> None:
    if "player_base_level" not in w and "gs_player_base_level" not in w:
        return
    base_key = "gs_player_base_level" if "gs_player_base_level" in w else "player_base_level"
    try:
        base = int(float(w[base_key].get()))
    except (KeyError, ValueError, TypeError, tk.TclError):
        base = ARK_DEFAULT_BASE_LEVEL

    progressions = False
    prog_var = w.get("player_level_progressions_enabled")
    if prog_var is not None:
        try:
            progressions = bool(prog_var.get())
        except tk.TclError:
            progressions = False
    elif hasattr(gs, "player_level_progressions_enabled"):
        progressions = bool(getattr(gs, "player_level_progressions_enabled", False))

    if hasattr(gs, "player_base_level"):
        gs.player_base_level = base
    if hasattr(gs, "player_level_progressions_enabled"):
        gs.player_level_progressions_enabled = progressions
    if progressions:
        detect_and_apply_legacy_curve(gs)

    total = calc_max_total_level(base)
    if progressions:
        curve = _curve_params_from_cfg(gs)
        ramp_values = build_ramp_values(
            base,
            mode=str(curve["mode"]),
            xp_base=int(curve["xp_base"]),
            xp_mult=float(curve["xp_mult"]),
            formula=str(curve["formula"]),
        )
        xp = cumulative_xp_on_ramp(ramp_values, base) if ramp_values else level_to_xp(base)
    else:
        xp = level_to_xp(base)

    if hasattr(gs, "player_base_level"):
        gs.player_base_level = base
    if hasattr(gs, "player_ascension_state"):
        gs.player_ascension_state = serialize_ascension_state()
    if hasattr(gs, "player_level_cap"):
        gs.player_level_cap = total
    if hasattr(gs, "override_max_experience_points_player"):
        gs.override_max_experience_points_player = xp


def _progressions_toggle_row(
    parent: tk.Misc,
    *,
    row: int,
    var: tk.BooleanVar,
    on_change: Callable[[], None],
    bg: str,
    accent: str,
) -> int:
    fr = tk.Frame(parent, bg=bg)
    fr.grid(row=row, column=0, sticky="ew", padx=12, pady=(2, 4))
    cb = ctk.CTkCheckBox(
        fr,
        text="Progressões customizadas (rampa + engramas no Game.ini)",
        variable=var,
        command=on_change,
        font=ctk.CTkFont(size=11),
        text_color=accent,
        fg_color=accent,
        hover_color=_GREEN_DARK,
    )
    cb.pack(anchor="w")
    tk.Label(
        fr,
        text=(
            "Desmarcado = modo simples (vanilla): só nível base, teto +100 e cap de XP no GUS — "
            "sem LevelExperienceRampOverrides nem OverridePlayerLevelEngramPoints. "
            "Com progressões: curva geométrica default 70×1.05^i (não 1.15)."
        ),
        bg=bg,
        fg="gray50",
        font=ctk.CTkFont(size=9),
        wraplength=540,
        justify="left",
    ).pack(anchor="w", pady=(2, 0))
    return row + 1


def _unified_summary_row(
    parent: tk.Misc,
    *,
    row: int,
    base_var: tk.StringVar,
    asc_var: tk.StringVar,
    total_var: tk.StringVar,
    ramp_var: tk.StringVar,
    xp_var: tk.StringVar,
    engram_var: tk.StringVar,
    on_change: Callable[[], None],
    bg: str,
    accent: str,
) -> None:
    box = tk.Frame(parent, bg=bg, highlightthickness=1, highlightbackground="#1e3a2f")
    box.grid(row=row, column=0, sticky="ew", padx=12, pady=(4, 4))
    for col in range(3):
        box.grid_columnconfigure(col, weight=1)

    cells = (
        (0, "Nível base (XP)", "Farmável sem bosses/conquistas", base_var, True),
        (1, "Bônus fixo", f"+{ARK_BOSS_ASCENSION_LEVELS} boss + {ARK_CONQUEST_LEVELS} conquistas", asc_var, False),
        (2, "Nível máximo", "Base + 100 (automático)", total_var, False),
    )
    for col, title, sub, var, editable in cells:
        fr = tk.Frame(box, bg="#0d1a14" if col % 2 else "#0a1410", padx=8, pady=8)
        fr.grid(row=0, column=col, sticky="nsew", padx=3)
        tk.Label(fr, text=title, bg=fr["bg"], fg="gray55",
                 font=ctk.CTkFont(size=10)).pack(anchor="w")
        if editable:
            ent = ctk.CTkEntry(fr, textvariable=var, width=64, height=30,
                               justify="center", text_color=accent,
                               font=ctk.CTkFont(size=18, weight="bold"))
            ent.pack(anchor="w", pady=(4, 0))
            ent.bind("<Return>", lambda _e: on_change())
            ent.bind("<FocusOut>", lambda _e: on_change())
        else:
            ctk.CTkLabel(fr, textvariable=var, text_color=accent,
                         font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(4, 0))
        tk.Label(fr, text=sub, bg=fr["bg"], fg="gray45",
                 font=ctk.CTkFont(size=8), wraplength=160, justify="left").pack(anchor="w", pady=(2, 0))

    meta = tk.Frame(box, bg=bg)
    meta.grid(row=1, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 4))
    tk.Label(meta, text="Rampa Game.ini:", bg=bg, fg="gray50",
             font=ctk.CTkFont(size=10)).pack(side="left")
    tk.Label(meta, textvariable=ramp_var, bg=bg, fg=accent,
             font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=(4, 12))
    tk.Label(meta, text="slots (base + 75)", bg=bg, fg="gray50",
             font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 12))
    tk.Label(meta, textvariable=xp_var, bg=bg, fg="gray50",
             font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 12))
    tk.Label(meta, text="Engramas/nível:", bg=bg, fg="gray50",
             font=ctk.CTkFont(size=10)).pack(side="left")
    tk.Label(meta, textvariable=engram_var, bg=bg, fg=accent,
             font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=(4, 4))


def _bonus_breakdown_row(parent: tk.Misc, *, row: int, bg: str) -> int:
    sec = tk.LabelFrame(
        parent,
        text="  Bônus automáticos (+100)  ",
        bg=bg, fg="gray55", font=ctk.CTkFont(size=10),
    )
    sec.grid(row=row, column=0, sticky="ew", padx=12, pady=(0, 6))

    boss_line = " · ".join(f"{name} +15" for _, name, _ in ASCENSION_BOSSES)
    conquest_line = " · ".join(f"{label} +{pts}" for _, label, pts in CONQUEST_BONUSES)

    tk.Label(
        sec,
        text=f"Rampa INI (+75): {boss_line}",
        bg=bg, fg="gray60", font=ctk.CTkFont(size=9), wraplength=520, justify="left",
    ).grid(row=0, column=0, padx=10, pady=(8, 2), sticky="w")
    tk.Label(
        sec,
        text=f"Implante (+25): {conquest_line}",
        bg=bg, fg="gray60", font=ctk.CTkFont(size=9), wraplength=520, justify="left",
    ).grid(row=1, column=0, padx=10, pady=(0, 8), sticky="w")
    return row + 1


def _engram_info_row(parent: tk.Misc, *, row: int, bg: str, accent: str) -> int:
    sec = tk.LabelFrame(
        parent,
        text=f"  Pontos de engrama — {ARK_ENGRAM_POINTS_PER_LEVEL} fixos por nível  ",
        bg=bg, fg="gray55", font=ctk.CTkFont(size=10),
    )
    sec.grid(row=row, column=0, sticky="ew", padx=12, pady=(0, 8))
    tk.Label(
        sec,
        text=(
            f"Cada level-up na rampa recebe {ARK_ENGRAM_POINTS_PER_LEVEL} pontos de engrama "
            f"(OverridePlayerLevelEngramPoints × entradas na rampa)."
        ),
        bg=bg, fg=accent, font=ctk.CTkFont(size=10), wraplength=520, justify="left",
    ).grid(row=0, column=0, padx=10, pady=8, sticky="w")
    return row + 1


def build_tek_player_level_section(ctx: Any, card: ctk.CTkFrame, start_row: int = 1) -> int:
    base = _resolve_initial(ctx.srv, game_settings=False)

    vars_ref = ctx.vars_ref
    vars_ref.setdefault("player_base_level", tk.StringVar(value=str(base)))
    vars_ref.setdefault("player_ascension_state", tk.StringVar(
        value=serialize_ascension_state()))
    vars_ref.setdefault("override_max_xp_player", tk.StringVar(
        value=str(int(getattr(ctx.srv, "override_max_xp_player", 0) or 0))))
    vars_ref["_pl_total_var"] = tk.StringVar()
    vars_ref["_pl_xp_var"] = tk.StringVar()
    vars_ref["_pl_asc_bonus_var"] = tk.StringVar(value=f"+{ARK_TOTAL_BONUS_LEVELS}")
    vars_ref["_pl_ramp_var"] = tk.StringVar()
    vars_ref["_pl_engram_var"] = tk.StringVar(value=str(ARK_ENGRAM_POINTS_PER_LEVEL))
    vars_ref["_pl_warn_var"] = tk.StringVar()
    vars_ref.setdefault("player_level_stats_raw", tk.StringVar(
        value=str(getattr(ctx.srv, "player_level_stats_raw", "") or "")))
    vars_ref.setdefault(
        "player_level_progressions_enabled",
        tk.BooleanVar(value=bool(getattr(ctx.srv, "player_level_progressions_enabled", False))),
    )

    theme = ctx.theme
    bg = theme.get("card_bg", "#0d1b2a")
    accent = ctx.accent

    body = ctk.CTkFrame(card, fg_color="transparent")
    body.grid(row=start_row, column=0, sticky="ew")
    body.grid_columnconfigure(0, weight=1)

    def _recalc() -> None:
        sync_player_level_vars(vars_ref, cfg=ctx.srv)

    r = 0
    r = _progressions_toggle_row(
        body,
        row=r,
        var=vars_ref["player_level_progressions_enabled"],
        on_change=_recalc,
        bg=bg,
        accent=accent,
    )
    _unified_summary_row(
        body, row=r,
        base_var=vars_ref["player_base_level"],
        asc_var=vars_ref["_pl_asc_bonus_var"],
        total_var=vars_ref["_pl_total_var"],
        ramp_var=vars_ref["_pl_ramp_var"],
        xp_var=vars_ref["_pl_xp_var"],
        engram_var=vars_ref["_pl_engram_var"],
        on_change=_recalc, bg=bg, accent=accent,
    )
    r = r + 1
    r = _bonus_breakdown_row(body, row=r, bg=bg)
    _engram_info_row(body, row=r, bg=bg, accent=accent)
    _recalc()
    return start_row + 1


def build_classic_player_level_panel(
    parent: tk.Misc,
    row_n: int,
    w: dict,
    gs: object,
    *,
    register_fn: Optional[Callable[[str, str, str], None]] = None,
) -> None:
    _BG_PANEL = "#12122a"
    _BDR = "#2a2a55"
    base = _resolve_initial(gs, game_settings=True)

    panel = tk.Frame(parent, bg=_BG_PANEL, highlightthickness=1, highlightbackground=_BDR)
    panel.grid(row=row_n, column=0, columnspan=3, padx=16, pady=(2, 10), sticky="ew")
    panel.grid_columnconfigure(0, weight=1)

    if register_fn:
        register_fn("Nível máximo do jogador", "Defina só o nível base — rampa, XP e engramas são automáticos.", "Jogo")

    w["gs_player_base_level"] = tk.StringVar(value=str(base))
    w["gs_player_level_cap"] = tk.StringVar(value=str(getattr(gs, "player_level_cap", 0) or 0))
    w["gs_override_max_experience_points_player"] = tk.StringVar(
        value=str(getattr(gs, "override_max_experience_points_player", 0) or 0))
    w["gs_player_ascension_state"] = tk.StringVar(value=serialize_ascension_state())
    w["player_base_level"] = w["gs_player_base_level"]
    w["player_ascension_state"] = w["gs_player_ascension_state"]
    w["_pl_total_var"] = tk.StringVar()
    w["_pl_xp_var"] = tk.StringVar()
    w["_pl_asc_bonus_var"] = tk.StringVar(value=f"+{ARK_TOTAL_BONUS_LEVELS}")
    w["_pl_ramp_var"] = tk.StringVar()
    w["_pl_engram_var"] = tk.StringVar(value=str(ARK_ENGRAM_POINTS_PER_LEVEL))
    w["player_level_progressions_enabled"] = tk.BooleanVar(
        value=bool(getattr(gs, "player_level_progressions_enabled", False))
    )

    tk.Label(panel, text="Nível máximo do jogador",
             bg=_BG_PANEL, fg="#c8c8e8",
             font=ctk.CTkFont(size=12, weight="bold"), anchor="w"
             ).grid(row=0, column=0, padx=12, pady=(8, 2), sticky="w")
    tk.Frame(panel, bg=_GREEN, height=1).grid(row=1, column=0, padx=12, sticky="ew")
    tk.Label(
        panel,
        text=(
            "Informe o nível base (farmável com XP). O teto total (+100) é automático. "
            "No modo simples (vanilla), só o cap de XP no GUS é gravado; marque progressões "
            "customizadas para rampa e engramas no Game.ini (curva default 70×1.05^i)."
        ),
        bg=_BG_PANEL, fg="gray50", font=ctk.CTkFont(size=10), justify="left",
        wraplength=560,
    ).grid(row=2, column=0, padx=12, pady=(6, 4), sticky="w")

    def _recalc() -> None:
        sync_player_level_vars(w, cfg=gs)

    r = 3
    r = _progressions_toggle_row(
        panel,
        row=r,
        var=w["player_level_progressions_enabled"],
        on_change=_recalc,
        bg=_BG_PANEL,
        accent=_GREEN,
    )
    _unified_summary_row(
        panel, row=r,
        base_var=w["gs_player_base_level"],
        asc_var=w["_pl_asc_bonus_var"],
        total_var=w["_pl_total_var"],
        ramp_var=w["_pl_ramp_var"],
        xp_var=w["_pl_xp_var"],
        engram_var=w["_pl_engram_var"],
        on_change=_recalc, bg=_BG_PANEL, accent=_GREEN,
    )
    r = r + 1
    r = _bonus_breakdown_row(panel, row=r, bg=_BG_PANEL)
    _engram_info_row(panel, row=r, bg=_BG_PANEL, accent=_GREEN)
    _recalc()
