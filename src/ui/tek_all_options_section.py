"""Visão «Todas as opções» — lista filtrável agrupada por seção TEK."""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import AsmServerConfig
from .server_field_labels import FIELD_LABELS, get_field_meta
from .server_field_widgets import (
    CardSpec,
    add_field_auto,
    add_card_header,
    begin_tek_section,
    make_card,
    run_ui_tasks_chunked,
    section_title,
    setup_dual_column_parent,
)
from .tek_section_fields import FLAT_VIEW_SECTIONS, SECTION_FIELDS


def build_all_options_section(
    sf: ctk.CTkScrollableFrame,
    srv: AsmServerConfig,
    vars_ref: dict,
    accent: str,
    *,
    on_goto_section: Optional[Callable[[str], None]] = None,
    on_done=None,
    is_cancelled=None,
    on_progress=None,
    on_error=None,
    on_cancelled=None,
) -> None:
    """Lista scrollável com campos escalares agrupados por seção + filtro."""
    setup_dual_column_parent(sf)
    ctx = begin_tek_section(sf, srv, vars_ref, accent, "Todas as opções", "Todas as opções")
    section_title(sf, "Todas as opções", accent, 0)

    hint = ctk.CTkLabel(
        sf,
        text="Lista completa dos campos editáveis. Use o filtro ou «Buscar configuração» na barra lateral.",
        font=ctk.CTkFont(size=10),
        text_color=ctx.theme.get("text_muted", "#64748b"),
        anchor="w",
        wraplength=560,
    )
    hint.grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 6), sticky="w")

    filter_var = tk.StringVar(value="")
    filter_row = ctk.CTkFrame(sf, fg_color="transparent")
    filter_row.grid(row=2, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")
    filter_row.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(filter_row, text="Filtrar:", font=ctk.CTkFont(size=11)).grid(
        row=0, column=0, padx=(4, 6), sticky="w",
    )
    filter_entry = ctk.CTkEntry(
        filter_row, textvariable=filter_var, placeholder_text="Nome, rótulo ou palavra-chave…",
        height=30,
    )
    filter_entry.grid(row=0, column=1, sticky="ew")

    cards_host = ctk.CTkFrame(sf, fg_color="transparent")
    cards_host.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
    cards_host.grid_columnconfigure(0, weight=1)
    cards_host.grid_columnconfigure(1, weight=1)

    section_cards: dict[str, ctk.CTkFrame] = {}
    field_rows: dict[str, tuple[ctk.CTkFrame, str]] = {}

    def _scalar_fields(section: str) -> list[str]:
        out: list[str] = []
        for key in SECTION_FIELDS.get(section, []):
            meta = FIELD_LABELS.get(key)
            if meta is None:
                continue
            if meta.field_type in ("raw", "list"):
                continue
            if key.endswith("_raw") or key.endswith("_multipliers") or key.endswith("_ids"):
                continue
            if key.startswith("per_level_"):
                continue
            out.append(key)
        return out

    card_specs: list[tuple[str, CardSpec]] = []
    for sec in FLAT_VIEW_SECTIONS:
        fields = _scalar_fields(sec)
        if not fields:
            continue
        card_specs.append((sec, CardSpec(sec, fields, bool_grid=False)))

    def _build_card(idx: int, sec: str, spec: CardSpec) -> None:
        row = 1 + idx // 2
        col = idx % 2
        card = make_card(cards_host, row, col, ctx.theme)
        if len(spec.fields) > 6:
            card.grid(columnspan=2, sticky="ew")
        section_cards[sec] = card
        add_card_header(card, spec.title, accent)
        if on_goto_section:
            link = ctk.CTkButton(
                card, text="Abrir seção →", width=100, height=22,
                fg_color="transparent", hover_color=ctx.theme.get("accent_muted_bg", "#1e293b"),
                text_color=accent, font=ctk.CTkFont(size=10),
                command=lambda s=sec: on_goto_section(s),
            )
            link.grid(row=0, column=1, padx=8, pady=4, sticky="e")
        for i, fld in enumerate(spec.fields, start=1):
            add_field_auto(ctx, card, fld, i)
            field_rows[fld] = (card, sec)

    def _apply_filter(*_args: object) -> None:
        q = filter_var.get().strip().lower()
        for sec, card in section_cards.items():
            visible = False
            for fld in SECTION_FIELDS.get(sec, []):
                row_info = field_rows.get(fld)
                if row_info is None:
                    continue
                meta = get_field_meta(fld)
                blob = meta.search_text
                match = not q or q in blob or q in meta.pt.lower() or q in sec.lower()
                # hide individual field widgets — walk card children is fragile; hide whole card
                if match:
                    visible = True
                    break
            if visible or not q:
                card.grid()
            else:
                card.grid_remove()

    filter_var.trace_add("write", _apply_filter)

    tasks = [
        lambda i=i, s=s, sp=sp: _build_card(i, s, sp)
        for i, (s, sp) in enumerate(card_specs)
    ]

    def _finish() -> None:
        _apply_filter()
        if on_done:
            on_done()

    run_ui_tasks_chunked(
        cards_host,
        tasks,
        on_done=_finish,
        is_cancelled=is_cancelled,
        on_progress=on_progress,
        on_error=on_error,
        on_cancelled=on_cancelled,
        chunk_size=1,
    )
