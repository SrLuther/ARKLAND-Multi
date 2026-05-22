from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _GREEN
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..buff_manager import BuffEvent
from ..buff_manager import BUFF_TYPE_LABELS


def build_active_buff_card(app: "ARKServerManagerApp", parent, row: int, event: "BuffEvent") -> None:
    card = ctk.CTkFrame(parent, fg_color="#1a2a1a", corner_radius=12)
    card.grid(row=row, column=0, padx=20, pady=(0, 8), sticky="ew")
    card.grid_columnconfigure(0, weight=1)

    top = ctk.CTkFrame(card, fg_color="transparent")
    top.grid(row=0, column=0, padx=16, pady=(14, 4), sticky="ew")
    top.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        top, text="🟢  BUFF ATIVO",
        font=ctk.CTkFont(size=11, weight="bold"), text_color=_GREEN,
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

    countdown_lbl = ctk.CTkLabel(
        card, text="",
        text_color="#88d4a0", font=ctk.CTkFont(size=11),
    )
    countdown_lbl.grid(row=4, column=0, padx=16, pady=(0, 14), sticky="w")
    app._buff_countdown_labels.append((countdown_lbl, event.end_datetime(), "⏱ Encerra em: "))

