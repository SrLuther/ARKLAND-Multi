"""Painel unificado de nível máximo do jogador (ASM clássico e TEK)."""
from __future__ import annotations

import tkinter as tk
from typing import Any, Callable, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..player_engram_points import (
    ARK_VANILLA_ENGRAM_POINTS_PER_LEVEL,
    engram_points_per_level,
)
from ..player_level_ascension import (
    ARK_DEFAULT_BASE_LEVEL,
    ASCENSION_BOSSES,
    EXTRA_BONUSES,
    calc_total_player_level,
    level_to_xp,
    parse_ascension_state,
    serialize_ascension_state,
    xp_to_level,
)
from ..ui_constants import _GREEN, _GREEN_DARK, _GREEN_HOVER

_TIER_MENU = ("Nenhum", "Gamma (+5)", "Beta (+10)", "Alpha (+15)")


def _menu_index(label: str) -> int:
    try:
        return _TIER_MENU.index(label)
    except ValueError:
        return 0


def _index_menu(idx: int) -> str:
    return _TIER_MENU[max(0, min(3, int(idx)))]


def _resolve_initial(cfg: object, *, game_settings: bool) -> tuple[int, dict[str, Any]]:
    """Carrega nível base e estado de ascensão a partir da config salva."""
    if game_settings:
        gs = cfg
        base = int(getattr(gs, "player_base_level", 0) or 0) or ARK_DEFAULT_BASE_LEVEL
        state = parse_ascension_state(getattr(gs, "player_ascension_state", ""))
        cap = int(getattr(gs, "player_level_cap", 0) or 0)
        if cap > 0 and not str(getattr(gs, "player_ascension_state", "") or "").strip():
            # Config legada: só o teto total — mantém base e ascensões vazias.
            pass
        return base, state

    base = int(getattr(cfg, "player_base_level", 0) or 0) or ARK_DEFAULT_BASE_LEVEL
    state = parse_ascension_state(getattr(cfg, "player_ascension_state", ""))
    override_xp = int(getattr(cfg, "override_max_xp_player", 0) or 0)
    if override_xp > 0 and not str(getattr(cfg, "player_ascension_state", "") or "").strip():
        total = xp_to_level(override_xp)
        asc_bonus = calc_total_player_level(base, state["bosses"], state["extras"]) - base
        if asc_bonus == 0 and total > base:
            pass  # usuário pode preencher ascensões manualmente
    return base, state


def _collect_boss_tiers(vars_ref: dict, prefix: str = "asc_boss_") -> dict[str, int]:
    tiers: dict[str, int] = {}
    for bid, _, _ in ASCENSION_BOSSES:
        key = f"{prefix}{bid}"
        raw = vars_ref.get(key)
        if raw is None:
            tiers[bid] = 0
            continue
        try:
            tiers[bid] = max(0, min(3, int(raw.get())))
        except (tk.TclError, ValueError, TypeError, AttributeError):
            tiers[bid] = _menu_index(str(raw.get())) if hasattr(raw, "get") else 0
    return tiers


def _collect_extras(vars_ref: dict, prefix: str = "asc_extra_") -> dict[str, bool]:
    out: dict[str, bool] = {}
    for eid, _, _ in EXTRA_BONUSES:
        key = f"{prefix}{eid}"
        var = vars_ref.get(key)
        out[eid] = bool(var.get()) if var is not None else False
    return out


def sync_player_level_vars(vars_ref: dict) -> tuple[int, int, int]:
    """Recalcula totais e atualiza vars ocultas (XP / JSON). Retorna (base, total, xp)."""
    try:
        base = int(float(vars_ref["player_base_level"].get()))
    except (KeyError, ValueError, TypeError, tk.TclError):
        base = ARK_DEFAULT_BASE_LEVEL
    base = max(1, base)

    bosses = _collect_boss_tiers(vars_ref)
    extras = _collect_extras(vars_ref)
    total = calc_total_player_level(base, bosses, extras)
    xp = level_to_xp(total)

    if "player_ascension_state" in vars_ref:
        vars_ref["player_ascension_state"].set(serialize_ascension_state(bosses, extras))
    if "override_max_xp_player" in vars_ref:
        vars_ref["override_max_xp_player"].set(str(xp))
    if "gs_player_level_cap" in vars_ref:
        vars_ref["gs_player_level_cap"].set(str(total))
    if "gs_override_max_experience_points_player" in vars_ref:
        vars_ref["gs_override_max_experience_points_player"].set(str(xp))
    if "_pl_total_var" in vars_ref:
        vars_ref["_pl_total_var"].set(str(total))
    if "_pl_xp_var" in vars_ref:
        vars_ref["_pl_xp_var"].set(f"{xp:,} XP")

    return base, total, xp


def apply_classic_player_level_to_gs(w: dict, gs: object) -> None:
    """Persiste nível base, ascensões e teto na GameSettings (ASM clássico)."""
    if "player_base_level" not in w and "gs_player_base_level" not in w:
        return
    base_key = "gs_player_base_level" if "gs_player_base_level" in w else "player_base_level"
    try:
        base = int(float(w[base_key].get()))
    except (KeyError, ValueError, TypeError, tk.TclError):
        base = ARK_DEFAULT_BASE_LEVEL

    bosses = _collect_boss_tiers(w, prefix="asc_boss_")
    extras = _collect_extras(w, prefix="asc_extra_")
    total = calc_total_player_level(base, bosses, extras)
    xp = level_to_xp(total)

    if hasattr(gs, "player_base_level"):
        gs.player_base_level = base
    if hasattr(gs, "player_ascension_state"):
        gs.player_ascension_state = serialize_ascension_state(bosses, extras)
    if hasattr(gs, "player_level_cap"):
        gs.player_level_cap = total
    if hasattr(gs, "override_max_experience_points_player"):
        gs.override_max_experience_points_player = xp


def _summary_row(
    parent: tk.Misc,
    *,
    row: int,
    base_var: tk.StringVar,
    total_var: tk.StringVar,
    xp_var: tk.StringVar,
    on_change: Callable[[], None],
    bg: str,
    accent: str,
    editable_base: bool = True,
) -> None:
    box = tk.Frame(parent, bg=bg, highlightthickness=1, highlightbackground="#1e3a2f")
    box.grid(row=row, column=0, sticky="ew", padx=12, pady=(4, 8))
    box.grid_columnconfigure(0, weight=1)
    box.grid_columnconfigure(1, weight=1)

    for col, title, sub, var, ro in (
        (0, "Nível base", "Sem ascensões, chibi, runas ou notas", base_var, not editable_base),
        (1, "Nível máximo total", "Com todos os bônus selecionados abaixo", total_var, True),
    ):
        fr = tk.Frame(box, bg="#0d1a14" if col == 1 else "#0a1410", padx=10, pady=8)
        fr.grid(row=0, column=col, sticky="nsew", padx=(6 if col else 0, 6))
        tk.Label(fr, text=title, bg=fr["bg"], fg="gray55",
                 font=ctk.CTkFont(size=10)).pack(anchor="w")
        if col == 0 and editable_base:
            ent = ctk.CTkEntry(fr, textvariable=base_var, width=72, height=32,
                               justify="center", text_color=accent,
                               font=ctk.CTkFont(size=20, weight="bold"))
            ent.pack(anchor="w", pady=(4, 0))
            ent.bind("<Return>", lambda _e: on_change())
            ent.bind("<FocusOut>", lambda _e: on_change())
        else:
            ctk.CTkLabel(fr, textvariable=var, text_color=accent,
                         font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", pady=(4, 0))
        tk.Label(fr, text=sub, bg=fr["bg"], fg="gray45",
                 font=ctk.CTkFont(size=9), wraplength=200, justify="left").pack(anchor="w", pady=(2, 0))

    tk.Label(box, textvariable=xp_var, bg=bg, fg="gray50",
             font=ctk.CTkFont(size=10)).grid(row=1, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 4))


def _boss_grid(parent: tk.Misc, vars_ref: dict, on_change: Callable[[], None], *, row: int, bg: str) -> int:
    sec = tk.LabelFrame(
        parent, text="  Ascensões por mapa (γ / β / α — +5 cada tier)  ",
        bg=bg, fg="gray55", font=ctk.CTkFont(size=10),
    )
    sec.grid(row=row, column=0, sticky="ew", padx=12, pady=(0, 6))
    sec.grid_columnconfigure(1, weight=1)

    for i, (bid, map_name, boss) in enumerate(ASCENSION_BOSSES):
        tk.Label(sec, text=f"{map_name}", width=14, anchor="w", bg=bg, fg="gray65",
                 font=ctk.CTkFont(size=10)).grid(row=i, column=0, padx=(8, 4), pady=2, sticky="w")
        tk.Label(sec, text=boss, anchor="w", bg=bg, fg="gray45",
                 font=ctk.CTkFont(size=9)).grid(row=i, column=1, padx=4, pady=2, sticky="w")

        key = f"asc_boss_{bid}"
        if key not in vars_ref:
            vars_ref[key] = tk.StringVar(value="0")
        var = vars_ref[key]
        menu_var = tk.StringVar(value=_index_menu(int(var.get() or 0)))

        def _on_pick(choice: str, _v=var, _m=menu_var) -> None:
            _v.set(str(_menu_index(choice)))
            _m.set(choice)
            on_change()

        om = ctk.CTkOptionMenu(
            sec, values=list(_TIER_MENU), variable=menu_var, command=_on_pick,
            width=130, height=26, fg_color="#1a2e24", button_color=_GREEN_DARK,
        )
        om.grid(row=i, column=2, padx=(4, 10), pady=2, sticky="e")

    return row + 1


def _extras_grid(parent: tk.Misc, vars_ref: dict, on_change: Callable[[], None], *, row: int, bg: str) -> int:
    sec = tk.LabelFrame(parent, text="  Bônus extras  ", bg=bg, fg="gray55",
                        font=ctk.CTkFont(size=10))
    sec.grid(row=row, column=0, sticky="ew", padx=12, pady=(0, 8))
    for ci in range(2):
        sec.grid_columnconfigure(ci, weight=1)

    for i, (eid, label, pts) in enumerate(EXTRA_BONUSES):
        key = f"asc_extra_{eid}"
        if key not in vars_ref:
            vars_ref[key] = tk.BooleanVar(value=False)
        var = vars_ref[key]
        fr = tk.Frame(sec, bg=bg)
        fr.grid(row=i // 2, column=i % 2, padx=8, pady=3, sticky="w")
        ctk.CTkCheckBox(
            fr, text=label, variable=var, width=20,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER, checkmark_color="white",
            command=on_change,
        ).pack(side="left")
        tk.Label(fr, text=f"+{pts}", bg=bg, fg=_GREEN,
                 font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=(4, 0))
    return row + 1


def _engram_multiplier_row(
    parent: tk.Misc,
    vars_ref: dict,
    cfg: object,
    *,
    row: int,
    bg: str,
    accent: str,
    key: str = "player_engram_points_multiplier",
    gs_key: str | None = None,
) -> int:
    """Campo de multiplicador de pontos de engrama por nível."""
    mult_val = float(getattr(cfg, key, 1.0) or 1.0)
    gs = getattr(cfg, "game_settings", None)
    if gs is not None and hasattr(gs, key):
        mult_val = float(getattr(gs, key, 1.0) or 1.0)

    store_key = gs_key or key
    if store_key not in vars_ref:
        vars_ref[store_key] = tk.StringVar(value=f"{mult_val:g}")
    if key != store_key and key not in vars_ref:
        vars_ref[key] = vars_ref[store_key]
    mult_var = vars_ref[store_key]
    preview_var = tk.StringVar()

    sec = tk.LabelFrame(
        parent,
        text=f"  Pontos de engrama por nível (vanilla = {ARK_VANILLA_ENGRAM_POINTS_PER_LEVEL})  ",
        bg=bg, fg="gray55", font=ctk.CTkFont(size=10),
    )
    sec.grid(row=row, column=0, sticky="ew", padx=12, pady=(0, 8))
    sec.grid_columnconfigure(1, weight=1)

    tk.Label(sec, text="Multiplicador:", bg=bg, fg="gray65",
             font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(10, 6), pady=8, sticky="w")
    ent = ctk.CTkEntry(sec, textvariable=mult_var, width=72, height=30, justify="center")
    ent.grid(row=0, column=1, padx=4, pady=8, sticky="w")

    ctk.CTkLabel(sec, textvariable=preview_var, text_color=accent,
                 font=ctk.CTkFont(size=11, weight="bold")).grid(
        row=0, column=2, padx=(8, 10), pady=8, sticky="w")

    tk.Label(
        sec,
        text="Ex.: 5.0 → 40 pontos/nível — costuma bastar para aprender todos os engramas.",
        bg=bg, fg="gray45", font=ctk.CTkFont(size=9), wraplength=420, justify="left",
    ).grid(row=1, column=0, columnspan=3, padx=10, pady=(0, 8), sticky="w")

    def _update_preview(*_) -> None:
        try:
            m = float(str(mult_var.get()).replace(",", "."))
        except (ValueError, TypeError, tk.TclError):
            preview_var.set("")
            return
        pts = engram_points_per_level(m)
        preview_var.set(f"= {pts} pontos por nível")

    ent.bind("<Return>", lambda _e: _update_preview())
    ent.bind("<FocusOut>", lambda _e: _update_preview())
    _update_preview()
    return row + 1


def build_tek_player_level_section(ctx: Any, card: ctk.CTkFrame, start_row: int = 1) -> int:
    """Monta o painel TEK dentro de um card. Retorna próxima linha lógica."""
    base, state = _resolve_initial(ctx.srv, game_settings=False)

    vars_ref = ctx.vars_ref
    vars_ref.setdefault("player_base_level", tk.StringVar(value=str(base)))
    vars_ref.setdefault("player_ascension_state", tk.StringVar(
        value=serialize_ascension_state(state["bosses"], state["extras"])))
    vars_ref.setdefault("override_max_xp_player", tk.StringVar(
        value=str(int(getattr(ctx.srv, "override_max_xp_player", 0) or 0))))
    vars_ref["_pl_total_var"] = tk.StringVar()
    vars_ref["_pl_xp_var"] = tk.StringVar()

    for bid, _, _ in ASCENSION_BOSSES:
        key = f"asc_boss_{bid}"
        vars_ref.setdefault(key, tk.StringVar(value=str(state["bosses"].get(bid, 0))))
    for eid, _, _ in EXTRA_BONUSES:
        key = f"asc_extra_{eid}"
        vars_ref.setdefault(key, tk.BooleanVar(value=bool(state["extras"].get(eid))))

    theme = ctx.theme
    bg = theme.get("card_bg", "#0d1b2a")
    accent = ctx.accent

    body = ctk.CTkFrame(card, fg_color="transparent")
    body.grid(row=start_row, column=0, sticky="ew")
    body.grid_columnconfigure(0, weight=1)

    def _recalc() -> None:
        sync_player_level_vars(vars_ref)

    _summary_row(
        body, row=0, base_var=vars_ref["player_base_level"],
        total_var=vars_ref["_pl_total_var"], xp_var=vars_ref["_pl_xp_var"],
        on_change=_recalc, bg=bg, accent=accent,
    )
    r = 1
    r = _boss_grid(body, vars_ref, _recalc, row=r, bg=bg)
    r = _extras_grid(body, vars_ref, _recalc, row=r, bg=bg)
    _engram_multiplier_row(body, vars_ref, ctx.srv, row=r, bg=bg, accent=accent)
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
    """Painel ASM clássico — substitui calculadora antiga + campo de nível confuso."""
    _BG_PANEL = "#12122a"
    _BDR = "#2a2a55"
    base, state = _resolve_initial(gs, game_settings=True)

    panel = tk.Frame(parent, bg=_BG_PANEL, highlightthickness=1, highlightbackground=_BDR)
    panel.grid(row=row_n, column=0, columnspan=3, padx=16, pady=(2, 10), sticky="ew")
    panel.grid_columnconfigure(0, weight=1)

    if register_fn:
        register_fn("Nível máximo do jogador", "Base + ascensões e bônus extras.", "Jogo")

    w["gs_player_base_level"] = tk.StringVar(value=str(base))
    w["gs_player_level_cap"] = tk.StringVar(value=str(getattr(gs, "player_level_cap", 0) or 0))
    w["gs_override_max_experience_points_player"] = tk.StringVar(
        value=str(getattr(gs, "override_max_experience_points_player", 0) or 0))
    w["gs_player_ascension_state"] = tk.StringVar(
        value=serialize_ascension_state(state["bosses"], state["extras"]))
    w["player_base_level"] = w["gs_player_base_level"]
    w["player_ascension_state"] = w["gs_player_ascension_state"]
    w["_pl_total_var"] = tk.StringVar()
    w["_pl_xp_var"] = tk.StringVar()

    for bid, _, _ in ASCENSION_BOSSES:
        w[f"asc_boss_{bid}"] = tk.StringVar(value=str(state["bosses"].get(bid, 0)))
    for eid, _, _ in EXTRA_BONUSES:
        w[f"asc_extra_{eid}"] = tk.BooleanVar(value=bool(state["extras"].get(eid)))

    tk.Label(panel, text="Nível máximo do jogador",
             bg=_BG_PANEL, fg="#c8c8e8",
             font=ctk.CTkFont(size=12, weight="bold"), anchor="w"
             ).grid(row=0, column=0, padx=12, pady=(8, 2), sticky="w")
    tk.Frame(panel, bg=_GREEN, height=1).grid(row=1, column=0, padx=12, sticky="ew")
    tk.Label(panel,
             text="Defina o nível base (sem bônus) e marque ascensões / extras — o teto total e o XP no INI são calculados automaticamente.",
             bg=_BG_PANEL, fg="gray50", font=ctk.CTkFont(size=10), justify="left",
             wraplength=560).grid(row=2, column=0, padx=12, pady=(6, 4), sticky="w")

    def _recalc() -> None:
        sync_player_level_vars(w)

    _summary_row(
        panel, row=3, base_var=w["gs_player_base_level"],
        total_var=w["_pl_total_var"], xp_var=w["_pl_xp_var"],
        on_change=_recalc, bg=_BG_PANEL, accent=_GREEN,
    )
    r = 4
    r = _boss_grid(panel, w, _recalc, row=r, bg=_BG_PANEL)
    r = _extras_grid(panel, w, _recalc, row=r, bg=_BG_PANEL)
    _engram_multiplier_row(
        panel, w, gs, row=r, bg=_BG_PANEL, accent=_GREEN,
        key="player_engram_points_multiplier",
        gs_key="gs_player_engram_points_multiplier",
    )
    _recalc()
