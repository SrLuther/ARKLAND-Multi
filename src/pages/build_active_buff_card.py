from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _GREEN
from ..ui_constants import _RED_DARK, _RED_HOVER
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..buff_manager import BuffEvent
from ..buff_manager import BUFF_TYPE_LABELS


def build_active_buff_card(
    app: "ARKServerManagerApp",
    parent,
    row: int,
    event: "BuffEvent",
    *,
    activating: bool = False,
    deactivating: bool = False,
) -> None:
    card = ctk.CTkFrame(parent, fg_color="#1a2a1a", corner_radius=12)
    card.grid(row=row, column=0, padx=20, pady=(0, 8), sticky="ew")
    card.grid_columnconfigure(0, weight=1)
    card.grid_columnconfigure(1, weight=0)

    top = ctk.CTkFrame(card, fg_color="transparent")
    top.grid(row=0, column=0, padx=16, pady=(14, 4), sticky="ew")
    top.grid_columnconfigure(1, weight=1)

    if activating:
        status_txt, status_color = "🟡  ATIVANDO…", "#ffaa44"
    elif deactivating:
        status_txt, status_color = "🟡  ENCERRANDO…", "#ffaa44"
    else:
        status_txt, status_color = "🟢  EVENTO ATIVO", _GREEN
    ctk.CTkLabel(
        top, text=status_txt,
        font=ctk.CTkFont(size=11, weight="bold"), text_color=status_color,
    ).grid(row=0, column=0, sticky="w")
    ctk.CTkLabel(
        top,
        text=f"Fim: {event.end_datetime().strftime('%d/%m/%Y  %H:%M')}",
        text_color="gray60", font=ctk.CTkFont(size=11),
    ).grid(row=0, column=2, sticky="e")

    ctk.CTkLabel(
        card, text=event.name,
        font=ctk.CTkFont(size=18, weight="bold"), text_color="#e8e8ff",
    ).grid(row=1, column=0, padx=16, pady=(0, 4), sticky="w")

    types_str = "  ·  ".join(BUFF_TYPE_LABELS.get(t, t) for t in event.types)
    ctk.CTkLabel(
        card, text=types_str,
        text_color="#ffaa44", font=ctk.CTkFont(size=12),
    ).grid(row=2, column=0, padx=16, pady=(0, 4), sticky="w")

    ctk.CTkLabel(
        card, text=event.rates.summary(),
        text_color="gray60", font=ctk.CTkFont(size=11),
        wraplength=700, justify="left",
    ).grid(row=3, column=0, padx=16, pady=(0, 4), sticky="w")

    if activating:
        ctk.CTkLabel(
            card,
            text="Reiniciando o servidor e aplicando rates nos INIs…",
            text_color="gray55", font=ctk.CTkFont(size=11),
        ).grid(row=4, column=0, padx=16, pady=(0, 14), sticky="w")
        return

    if deactivating:
        ctk.CTkLabel(
            card,
            text="Restaurando configurações do backup e reiniciando o servidor…",
            text_color="gray55", font=ctk.CTkFont(size=11),
        ).grid(row=4, column=0, padx=16, pady=(0, 14), sticky="w")
        return

    bottom = ctk.CTkFrame(card, fg_color="transparent")
    bottom.grid(row=4, column=0, padx=16, pady=(0, 14), sticky="ew")
    bottom.grid_columnconfigure(0, weight=1)

    countdown_lbl = ctk.CTkLabel(
        bottom, text="",
        text_color="#88d4a0", font=ctk.CTkFont(size=11),
    )
    countdown_lbl.grid(row=0, column=0, sticky="w")
    app._buff_countdown_labels.append((countdown_lbl, event.end_datetime(), "⏱ Encerra em: "))

    ctk.CTkButton(
        bottom, text="⏹  Encerrar Evento", width=140, height=30,
        fg_color=_RED_DARK, hover_color=_RED_HOVER,
        font=ctk.CTkFont(size=11),
        command=lambda eid=event.id: app._stop_buff(eid),
    ).grid(row=0, column=1, sticky="e")
