"""
Widgets reutilizáveis para painéis de configuração TEK e clássico.
Layout híbrido D: cards duplos, dual-label PT+EN, slider condicional, modified+reset.
"""
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import AsmServerConfig
from ..ui_constants import get_theme
from .responsive import ResponsiveWatcher, attach_slider_visibility
from .server_field_labels import FieldMeta, get_field_meta

STAT_NAMES = [
    ("❤", "Vida"),
    ("⚡", "Stamina"),
    ("😴", "Torpor"),
    ("💧", "Oxigênio"),
    ("🍖", "Comida"),
    ("💦", "Água"),
    ("🌡", "Temperatura"),
    ("⚖", "Peso"),
    ("⚔", "Dano Corpo"),
    ("🏃", "Velocidade"),
    ("🛡", "Fortitude"),
    ("🔨", "Crafting"),
]


@dataclass
class TekPanelCtx:
    """Contexto compartilhado ao construir uma seção piloto."""

    parent: ctk.CTkScrollableFrame
    srv: AsmServerConfig
    vars_ref: dict
    accent: str
    theme: dict
    section_name: str
    responsive: Optional[ResponsiveWatcher] = None

    def ensure_defaults(self) -> dict:
        if "_defaults" not in self.vars_ref:
            self.vars_ref["_defaults"] = {}
        return self.vars_ref["_defaults"]

    def ensure_field_index(self) -> dict:
        if "_field_index" not in self.vars_ref:
            self.vars_ref["_field_index"] = {}
        return self.vars_ref["_field_index"]


def init_panel_context(
    parent: ctk.CTkScrollableFrame,
    srv: AsmServerConfig,
    vars_ref: dict,
    accent: str,
    section_name: str,
    root_for_responsive: Optional[tk.Misc] = None,
) -> TekPanelCtx:
    theme = get_theme("tek")
    watcher = vars_ref.get("_responsive")
    if root_for_responsive is not None and watcher is None:
        watcher = ResponsiveWatcher(root_for_responsive)
        vars_ref["_responsive"] = watcher
    return TekPanelCtx(
        parent=parent, srv=srv, vars_ref=vars_ref, accent=accent,
        theme=theme, section_name=section_name, responsive=watcher,
    )


def setup_dual_column_parent(parent: ctk.CTkScrollableFrame) -> None:
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_columnconfigure(1, weight=1)


def section_title(parent: ctk.CTkFrame, text: str, accent: str, row: int = 0) -> None:
    ctk.CTkLabel(
        parent, text=text,
        font=ctk.CTkFont(size=13, weight="bold"),
        text_color=accent, anchor="w",
    ).grid(row=row, column=0, columnspan=2, padx=12, pady=(12, 6), sticky="w")


def make_card(parent: ctk.CTkScrollableFrame, row: int, col: int, theme: dict) -> ctk.CTkFrame:
    card = ctk.CTkFrame(
        parent,
        fg_color=theme.get("card_bg", "#0d1b2a"),
        corner_radius=10,
        border_width=1,
        border_color=theme.get("separator", "#1e293b"),
    )
    card.grid(row=row, column=col, padx=8, pady=6, sticky="nsew")
    card.grid_columnconfigure(0, weight=1)
    return card


def dual_label(parent: ctk.CTkFrame, meta: FieldMeta, row: int, accent: str, theme: dict) -> ctk.CTkFrame:
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.grid(row=row, column=0, padx=12, pady=(8, 0), sticky="ew")
    frame.grid_columnconfigure(0, weight=1)

    top = ctk.CTkFrame(frame, fg_color="transparent")
    top.grid(row=0, column=0, sticky="ew")
    top.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        top, text=meta.pt, anchor="w",
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=theme["text_primary"],
    ).grid(row=0, column=0, sticky="w")

    if meta.hint:
        hint_btn = ctk.CTkButton(
            top, text="?", width=22, height=22,
            fg_color="transparent", hover_color=theme.get("accent_muted_bg", "#052e16"),
            text_color=accent, font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=11,
        )
        hint_btn.grid(row=0, column=1, padx=(4, 0))
        _bind_tooltip(hint_btn, meta.hint, theme)

    ctk.CTkLabel(
        frame, text=meta.en, anchor="w",
        font=ctk.CTkFont(size=10),
        text_color=theme["text_muted"],
    ).grid(row=1, column=0, sticky="w", pady=(0, 2))

    return frame


def _bind_tooltip(widget: tk.Misc, text: str, theme: dict) -> None:
    """Tooltip por clique — evita ficar preso ao rolar CTkScrollableFrame."""

    tip: list[Optional[ctk.CTkToplevel]] = [None]
    outside_bind: list[Optional[str]] = [None]
    scroll_binds: list[tuple[tk.Misc, str]] = []
    arm_outside: list[Optional[str]] = [None]

    def _hide() -> None:
        if arm_outside[0]:
            try:
                widget.after_cancel(arm_outside[0])
            except tk.TclError:
                pass
            arm_outside[0] = None
        if outside_bind[0]:
            try:
                widget.winfo_toplevel().unbind("<Button-1>", outside_bind[0])
            except tk.TclError:
                pass
            outside_bind[0] = None
        for w, bid in scroll_binds:
            try:
                w.unbind("<MouseWheel>", bid)
                w.unbind("<Button-4>", bid)
                w.unbind("<Button-5>", bid)
            except tk.TclError:
                pass
        scroll_binds.clear()
        if tip[0]:
            try:
                tip[0].destroy()
            except tk.TclError:
                pass
            tip[0] = None

    def _show() -> None:
        if tip[0]:
            return
        tw = ctk.CTkToplevel(widget)
        tw.wm_overrideredirect(True)
        tw.configure(fg_color=theme.get("card_bg", "#0d1b2a"))
        tw.attributes("-topmost", True)
        x = widget.winfo_rootx() + 24
        y = widget.winfo_rooty() + 28
        tw.geometry(f"+{x}+{y}")
        ctk.CTkLabel(
            tw, text=text, wraplength=280, justify="left",
            font=ctk.CTkFont(size=11),
            text_color=theme["text_secondary"],
        ).pack(padx=10, pady=8)
        tip[0] = tw

        def _outside(event: tk.Event) -> None:
            if event.widget is widget:
                return
            try:
                if tip[0] and str(event.widget).startswith(str(tip[0])):
                    return
            except tk.TclError:
                pass
            _hide()

        def _arm_outside() -> None:
            arm_outside[0] = None
            outside_bind[0] = widget.winfo_toplevel().bind("<Button-1>", _outside, add="+")

        arm_outside[0] = widget.after(120, _arm_outside)

        node: Optional[tk.Misc] = widget
        while node is not None:
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                bid = node.bind(seq, lambda _e: _hide(), add="+")
                scroll_binds.append((node, bid))
            node = node.master if hasattr(node, "master") else None
            if node is widget.winfo_toplevel():
                break

    def _toggle() -> None:
        if tip[0]:
            _hide()
        else:
            _show()

    if isinstance(widget, ctk.CTkButton):
        widget.configure(command=_toggle)
    # Checkboxes/outros: sem tooltip no clique (evita conflito com toggle do campo)

    widget.bind("<Destroy>", lambda _e: _hide())


def _track_modified(
    ctx: TekPanelCtx,
    field: str,
    var: tk.Variable,
    badge: ctk.CTkLabel,
    reset_btn: ctk.CTkButton,
    default_val: Any,
    *,
    on_reset: Optional[Callable[[], None]] = None,
) -> None:
    defaults = ctx.ensure_defaults()
    defaults[field] = default_val
    index = ctx.ensure_field_index()
    index[field] = ctx.section_name

    def _check(*_args: object) -> None:
        try:
            cur = var.get()
            if isinstance(default_val, bool):
                modified = bool(cur) != bool(default_val)
            elif isinstance(default_val, (int, float)):
                try:
                    modified = float(cur) != float(default_val)
                except (TypeError, ValueError):
                    modified = str(cur) != str(default_val)
            else:
                modified = str(cur) != str(default_val)
        except tk.TclError:
            modified = False
        if modified:
            badge.grid()
            reset_btn.grid()
        else:
            badge.grid_remove()
            reset_btn.grid_remove()

    var.trace_add("write", _check)
    _check()

    def _reset() -> None:
        if on_reset is not None:
            on_reset()
        elif isinstance(var, tk.BooleanVar):
            var.set(bool(default_val))
        else:
            var.set(str(default_val))

    reset_btn.configure(command=_reset)


def add_float_field(ctx: TekPanelCtx, card: ctk.CTkFrame, field: str, row: int) -> None:
    meta = get_field_meta(field)
    dual_label(card, meta, row * 2, ctx.accent, ctx.theme)

    ctrl = ctk.CTkFrame(card, fg_color="transparent")
    ctrl.grid(row=row * 2 + 1, column=0, padx=12, pady=(0, 10), sticky="ew")
    ctrl.grid_columnconfigure(1, weight=1)

    val = getattr(ctx.srv, field, 1.0)
    var = tk.StringVar(value=str(val))
    ctx.vars_ref[field] = var

    entry = ctk.CTkEntry(ctrl, textvariable=var, width=90, height=30)
    entry.grid(row=0, column=0, sticky="w")

    lo = meta.min_val if meta.min_val is not None else 0.0
    hi = meta.max_val if meta.max_val is not None else max(10.0, float(val) * 2 or 10.0)
    _slider_sync = [False]

    def _clamp_float(raw: str) -> float:
        return max(lo, min(hi, float(raw)))

    def _sync_slider_from_var(*_args: object) -> None:
        if _slider_sync[0]:
            return
        try:
            _slider_sync[0] = True
            slider.set(_clamp_float(var.get()))
        except (TypeError, ValueError):
            pass
        finally:
            _slider_sync[0] = False

    def _on_slider_move(v: float) -> None:
        _slider_sync[0] = True
        var.set(f"{float(v):.4g}")
        _slider_sync[0] = False

    slider = ctk.CTkSlider(
        ctrl, from_=lo, to=hi, number_of_steps=max(int((hi - lo) * 20), 20),
        command=_on_slider_move,
        width=140, height=16,
    )
    try:
        slider.set(_clamp_float(str(val)))
    except (TypeError, ValueError):
        slider.set(lo)
    slider.grid(row=0, column=1, padx=(10, 0), sticky="ew")
    var.trace_add("write", _sync_slider_from_var)

    if ctx.responsive:
        attach_slider_visibility(ctx.responsive, slider)

    badge = ctk.CTkLabel(ctrl, text="●", text_color="#fbbf24", width=16)
    reset_btn = ctk.CTkButton(
        ctrl, text="↺", width=28, height=28,
        fg_color="transparent", hover_color=ctx.theme.get("accent_muted_bg", "#052e16"),
        text_color=ctx.accent,
    )
    badge.grid(row=0, column=2, padx=(6, 0))
    reset_btn.grid(row=0, column=3, padx=(2, 0))
    badge.grid_remove()
    reset_btn.grid_remove()

    def _reset_field() -> None:
        var.set(str(default_val := val))
        try:
            _slider_sync[0] = True
            slider.set(_clamp_float(str(default_val)))
        except (TypeError, ValueError):
            slider.set(lo)
        finally:
            _slider_sync[0] = False

    _track_modified(ctx, field, var, badge, reset_btn, val, on_reset=_reset_field)


def add_int_field(ctx: TekPanelCtx, card: ctk.CTkFrame, field: str, row: int) -> None:
    meta = get_field_meta(field)
    dual_label(card, meta, row * 2, ctx.accent, ctx.theme)

    ctrl = ctk.CTkFrame(card, fg_color="transparent")
    ctrl.grid(row=row * 2 + 1, column=0, padx=12, pady=(0, 10), sticky="ew")

    val = getattr(ctx.srv, field, 0)
    var = tk.StringVar(value=str(val))
    ctx.vars_ref[field] = var

    ctk.CTkEntry(ctrl, textvariable=var, width=120, height=30).grid(row=0, column=0, sticky="w")

    badge = ctk.CTkLabel(ctrl, text="●", text_color="#fbbf24", width=16)
    reset_btn = ctk.CTkButton(
        ctrl, text="↺", width=28, height=28,
        fg_color="transparent", hover_color=ctx.theme.get("accent_muted_bg", "#052e16"),
        text_color=ctx.accent,
    )
    badge.grid(row=0, column=1, padx=(8, 0))
    reset_btn.grid(row=0, column=2)
    badge.grid_remove()
    reset_btn.grid_remove()
    _track_modified(ctx, field, var, badge, reset_btn, val)


def add_bool_field(ctx: TekPanelCtx, card: ctk.CTkFrame, field: str, row: int, col: int = 0) -> None:
    meta = get_field_meta(field)
    val = bool(getattr(ctx.srv, field, False))
    var = tk.BooleanVar(value=val)
    ctx.vars_ref[field] = var

    frame = ctk.CTkFrame(card, fg_color="transparent")
    frame.grid(row=row, column=col, padx=12, pady=6, sticky="ew")
    frame.grid_columnconfigure(1, weight=1)

    cb = ctk.CTkCheckBox(
        frame, text="", variable=var,
        checkmark_color=ctx.accent, border_color=ctx.accent,
        width=24,
    )
    cb.grid(row=0, column=0, sticky="w")

    labels = ctk.CTkFrame(frame, fg_color="transparent")
    labels.grid(row=0, column=1, padx=(6, 0), sticky="w")
    ctk.CTkLabel(
        labels, text=meta.pt, anchor="w",
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color=ctx.theme["text_primary"],
    ).pack(anchor="w")
    ctk.CTkLabel(
        labels, text=meta.en, anchor="w",
        font=ctk.CTkFont(size=9),
        text_color=ctx.theme["text_muted"],
    ).pack(anchor="w")

    badge = ctk.CTkLabel(frame, text="●", text_color="#fbbf24", width=12)
    reset_btn = ctk.CTkButton(
        frame, text="↺", width=24, height=24,
        fg_color="transparent", hover_color=ctx.theme.get("accent_muted_bg", "#052e16"),
        text_color=ctx.accent,
    )
    badge.grid(row=0, column=2)
    reset_btn.grid(row=0, column=3, padx=(2, 0))
    badge.grid_remove()
    reset_btn.grid_remove()
    _track_modified(ctx, field, var, badge, reset_btn, val)

    # Hint disponível via catálogo; tooltip no checkbox removido (conflitava com clique)


@dataclass
class CardSpec:
    title: str
    fields: Sequence[str]
    bool_grid: bool = False


def begin_tek_section(
    sf: ctk.CTkScrollableFrame,
    srv: AsmServerConfig,
    vars_ref: dict,
    accent: str,
    section_name: str,
    title: str,
) -> TekPanelCtx:
    setup_dual_column_parent(sf)
    ctx = init_panel_context(sf, srv, vars_ref, accent, section_name, vars_ref.get("_panel_root"))
    section_title(sf, title, accent, 0)
    return ctx


def add_str_field(
    ctx: TekPanelCtx,
    card: ctk.CTkFrame,
    field: str,
    row: int,
    *,
    password: bool = False,
    wide: bool = False,
) -> None:
    meta = get_field_meta(field)
    dual_label(card, meta, row * 2, ctx.accent, ctx.theme)

    ctrl = ctk.CTkFrame(card, fg_color="transparent")
    ctrl.grid(row=row * 2 + 1, column=0, padx=12, pady=(0, 10), sticky="ew")
    ctrl.grid_columnconfigure(0, weight=1)

    val = getattr(ctx.srv, field, "")
    var = tk.StringVar(value=str(val))
    ctx.vars_ref[field] = var

    ctk.CTkEntry(
        ctrl, textvariable=var,
        show="*" if password else "",
        width=300 if wide else 200, height=30,
    ).grid(row=0, column=0, sticky="ew")

    badge = ctk.CTkLabel(ctrl, text="●", text_color="#fbbf24", width=16)
    reset_btn = ctk.CTkButton(
        ctrl, text="↺", width=28, height=28,
        fg_color="transparent", hover_color=ctx.theme.get("accent_muted_bg", "#052e16"),
        text_color=ctx.accent,
    )
    badge.grid(row=0, column=1, padx=(8, 0))
    reset_btn.grid(row=0, column=2)
    badge.grid_remove()
    reset_btn.grid_remove()
    _track_modified(ctx, field, var, badge, reset_btn, val)


def add_field_auto(ctx: TekPanelCtx, card: ctk.CTkFrame, field: str, row: int) -> None:
    meta = get_field_meta(field)
    if meta.field_type == "bool":
        add_bool_field(ctx, card, field, row, col=0)
    elif meta.field_type == "int":
        add_int_field(ctx, card, field, row)
    elif meta.field_type == "float":
        add_float_field(ctx, card, field, row)
    else:
        add_str_field(ctx, card, field, row)


def fill_card(ctx: TekPanelCtx, card: ctk.CTkFrame, spec: CardSpec) -> None:
    add_card_header(card, spec.title, ctx.accent)
    if spec.bool_grid:
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=1)
        for i, fld in enumerate(spec.fields):
            add_bool_field(ctx, card, fld, row=1 + i // 2, col=i % 2)
        return
    row = 1
    for fld in spec.fields:
        add_field_auto(ctx, card, fld, row)
        row += 1


def build_cards_layout(
    sf: ctk.CTkScrollableFrame,
    ctx: TekPanelCtx,
    cards: Sequence[CardSpec],
    start_row: int = 1,
) -> int:
    row = start_row
    i = 0
    while i < len(cards):
        for col in (0, 1):
            if i >= len(cards):
                break
            card = make_card(sf, row, col, ctx.theme)
            fill_card(ctx, card, cards[i])
            i += 1
        row += 1
    return row


def add_card_header(card: ctk.CTkFrame, title: str, accent: str) -> None:
    ctk.CTkLabel(
        card, text=title,
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=accent, anchor="w",
    ).grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")


def build_per_level_accordion(
    ctx: TekPanelCtx,
    parent: ctk.CTkScrollableFrame,
    row: int,
    col_defs: list[tuple[str, str]],
    subtitle: str,
) -> None:
    """Accordion colapsável para multiplicadores por nível (substitui grade 12×N)."""
    theme = ctx.theme
    accent = ctx.accent

    if "_pls" not in ctx.vars_ref:
        ctx.vars_ref["_pls"] = {}

    wrapper = ctk.CTkFrame(
        parent, fg_color=theme.get("card_bg", "#0d1b2a"),
        corner_radius=10, border_width=1, border_color=theme.get("separator", "#1e293b"),
    )
    wrapper.grid(row=row, column=0, columnspan=2, padx=8, pady=8, sticky="ew")
    wrapper.grid_columnconfigure(0, weight=1)

    state = [False]
    arrow_var = tk.StringVar(value="▶  Multiplicadores por nível")

    content = ctk.CTkFrame(wrapper, fg_color="#0a0f1a", corner_radius=8)
    content.grid_columnconfigure(0, weight=0)
    for ci in range(len(col_defs)):
        content.grid_columnconfigure(ci + 1, weight=1)

    ctk.CTkLabel(
        content, text=subtitle,
        font=ctk.CTkFont(size=10), text_color=theme["text_muted"],
        wraplength=700, justify="left",
    ).grid(row=0, column=0, columnspan=len(col_defs) + 1, padx=12, pady=(8, 4), sticky="w")

    ctk.CTkLabel(content, text="Stat", font=ctk.CTkFont(size=10, weight="bold"),
                 text_color=theme["text_muted"]).grid(row=1, column=0, padx=(12, 4), pady=4, sticky="w")
    for ci, (col_lbl, _) in enumerate(col_defs):
        ctk.CTkLabel(content, text=col_lbl, font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=accent).grid(row=1, column=ci + 1, padx=4, pady=4)

    sep = theme.get("separator", "#1e293b")
    ctk.CTkFrame(content, height=1, fg_color=sep).grid(
        row=2, column=0, columnspan=len(col_defs) + 1, sticky="ew", padx=8)

    for ri, (icon, stat_name) in enumerate(STAT_NAMES):
        row_bg = "#080d16" if ri % 2 == 0 else "#0a0f1a"
        row_f = ctk.CTkFrame(content, fg_color=row_bg, corner_radius=0)
        row_f.grid(row=ri + 3, column=0, columnspan=len(col_defs) + 1, sticky="ew")
        for ci in range(len(col_defs)):
            row_f.grid_columnconfigure(ci + 1, weight=1)

        ctk.CTkLabel(row_f, text=f"{icon}  {stat_name}",
                     font=ctk.CTkFont(size=11), text_color="#94a3b8",
                     anchor="w", width=120).grid(row=0, column=0, padx=(12, 8), pady=2, sticky="w")

        for ci, (_, attr) in enumerate(col_defs):
            if attr not in ctx.vars_ref["_pls"]:
                cur_list = getattr(ctx.srv, attr, None) or []
                ctx.vars_ref["_pls"][attr] = [
                    tk.StringVar(value=str(cur_list[i]) if i < len(cur_list) else "1.0")
                    for i in range(12)
                ]
            ctk.CTkEntry(
                row_f, textvariable=ctx.vars_ref["_pls"][attr][ri],
                width=72, height=24, font=ctk.CTkFont(size=11), justify="center",
            ).grid(row=0, column=ci + 1, padx=4, pady=2, sticky="ew")

    def _toggle() -> None:
        state[0] = not state[0]
        if state[0]:
            arrow_var.set("▼  Multiplicadores por nível")
            content.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 10))
        else:
            arrow_var.set("▶  Multiplicadores por nível")
            content.grid_remove()

    ctk.CTkButton(
        wrapper, textvariable=arrow_var, anchor="w",
        fg_color="transparent", hover_color=theme.get("accent_muted_bg", "#052e16"),
        text_color=accent, font=ctk.CTkFont(size=12, weight="bold"),
        height=36, corner_radius=8, command=_toggle,
    ).grid(row=0, column=0, sticky="ew", padx=4, pady=4)


def add_collapsible_help(
    parent: ctk.CTkScrollableFrame,
    items: list[tuple[str, str]],
    row: int,
) -> None:
    """Seção AJUDA colapsável (compatível com painel legado)."""
    theme = get_theme("tek")
    accent = theme["accent"]

    ctk.CTkFrame(parent, height=1, fg_color=theme["separator"]).grid(
        row=row, column=0, columnspan=2, sticky="ew", padx=8, pady=(14, 4))

    content_frame = ctk.CTkFrame(parent, fg_color=theme.get("card_bg", "#0d1b2a"), corner_radius=8)
    content_frame.grid_columnconfigure(0, weight=1)
    for i, (label, desc) in enumerate(items):
        row_f = ctk.CTkFrame(content_frame, fg_color="transparent")
        row_f.grid(row=i, column=0, sticky="ew", padx=12, pady=3)
        row_f.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(row_f, text=f"• {label}:",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=accent, width=200, anchor="nw",
                     ).grid(row=0, column=0, sticky="nw", padx=(0, 8))
        ctk.CTkLabel(row_f, text=desc,
                     font=ctk.CTkFont(size=11),
                     text_color=theme["text_secondary"],
                     wraplength=460, justify="left", anchor="nw",
                     ).grid(row=0, column=1, sticky="nw")

    state = [False]
    arrow_var = tk.StringVar(value="▶  AJUDA")

    def _toggle() -> None:
        state[0] = not state[0]
        if state[0]:
            arrow_var.set("▼  AJUDA")
            content_frame.grid(row=row + 2, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 16))
        else:
            arrow_var.set("▶  AJUDA")
            content_frame.grid_remove()

    ctk.CTkButton(
        parent, textvariable=arrow_var, anchor="w",
        fg_color="transparent", hover_color=theme.get("accent_muted_bg", "#052e16"),
        text_color=accent, font=ctk.CTkFont(size=11, weight="bold"),
        height=28, corner_radius=6, command=_toggle,
    ).grid(row=row + 1, column=0, columnspan=2, padx=4, pady=(0, 4), sticky="ew")
