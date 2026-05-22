from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _RED_DARK, _RED_HOVER, _CARD_BG
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..buff_manager import BuffEvent
from ..buff_manager import BUFF_TYPE_LABELS


def build_scheduled_buff_row(app: "ARKServerManagerApp", parent, row: int, event: "BuffEvent") -> None:
    card = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=10)
    card.grid(row=row, column=0, padx=20, pady=3, sticky="ew")
    card.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        card,
        text=f"🕐  {event.start_datetime().strftime('%d/%m/%Y  %H:%M')}  →  "
             f"{event.end_datetime().strftime('%d/%m/%Y  %H:%M')}",
        text_color="gray55", font=ctk.CTkFont(size=11),
    ).grid(row=0, column=0, padx=(16, 8), pady=(10, 2), sticky="w")

    ctk.CTkLabel(
        card, text=event.name,
        font=ctk.CTkFont(size=13, weight="bold"),
    ).grid(row=1, column=0, padx=(16, 8), pady=(0, 2), sticky="w")

    types_str = "  ·  ".join(BUFF_TYPE_LABELS.get(t, t) for t in event.types)
    ctk.CTkLabel(card, text=types_str, text_color="#ffaa44",
                 font=ctk.CTkFont(size=11)).grid(
        row=2, column=0, padx=(16, 8), pady=(0, 2), sticky="w")

    countdown_lbl = ctk.CTkLabel(
        card, text="",
        text_color="#aaaaff", font=ctk.CTkFont(size=11),
    )
    countdown_lbl.grid(row=3, column=0, padx=(16, 8), pady=(0, 10), sticky="w")
    app._buff_countdown_labels.append((countdown_lbl, event.start_datetime(), "⏳ Inicia em: "))

    ctk.CTkButton(
        card, text="✕  Cancelar", width=110, height=30,
        fg_color=_RED_DARK, hover_color=_RED_HOVER,
        font=ctk.CTkFont(size=11),
        command=lambda eid=event.id: app._cancel_buff(eid),
    ).grid(row=0, column=2, rowspan=4, padx=16, pady=10)

