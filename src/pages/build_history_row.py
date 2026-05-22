from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _CARD_BG
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..buff_manager import BuffEvent
from ..buff_manager import BUFF_STATUS_CANCELLED


def build_history_row(app: "ARKServerManagerApp", parent, row: int, event: "BuffEvent") -> None:
    is_cancelled = event.status == BUFF_STATUS_CANCELLED
    card = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=8)
    card.grid(row=row, column=0, padx=20, pady=2, sticky="ew")
    card.grid_columnconfigure(1, weight=1)

    icon = "✕" if is_cancelled else "✔"
    color = "gray45" if is_cancelled else "gray55"
    status_lbl = "Cancelado" if is_cancelled else "Finalizado"
    ctk.CTkLabel(
        card,
        text=f"{icon}  {event.name}  —  {status_lbl}  "
             f"({event.start_datetime().strftime('%d/%m/%Y')} — "
             f"{event.end_datetime().strftime('%d/%m/%Y')})",
        text_color=color, font=ctk.CTkFont(size=11),
    ).pack(padx=16, pady=8, side="left")

