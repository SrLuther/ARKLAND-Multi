from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING, Optional
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _GREEN_DARK, _GREEN_HOVER, _CARD_BG
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..buff_manager import BuffPreset
from ..buff_manager import BUFF_TYPE_LABELS


def build_preset_chip(app: "ARKServerManagerApp", parent, row: int, col: int, preset: "BuffPreset", srv_id: "Optional[str]") -> None:
    card = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=10)
    card.grid(row=row, column=col, padx=6, pady=4, sticky="ew")
    card.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        card, text=preset.name,
        font=ctk.CTkFont(size=13, weight="bold"),
    ).grid(row=0, column=0, padx=12, pady=(10, 2), sticky="w")

    types_str = "  ·  ".join(BUFF_TYPE_LABELS.get(t, t) for t in preset.types)
    ctk.CTkLabel(card, text=types_str, text_color="#ffaa44",
                 font=ctk.CTkFont(size=11)).grid(
        row=1, column=0, padx=12, pady=(0, 8), sticky="w")

    if srv_id:
        ctk.CTkButton(
            card, text="⚡  Usar", height=28, width=80,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            font=ctk.CTkFont(size=11),
            command=lambda p=preset, sid=srv_id: app._open_create_buff_dialog(
                preset=p, server_id=sid),
        ).grid(row=2, column=0, padx=12, pady=(0, 10), sticky="w")

