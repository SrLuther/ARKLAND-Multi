from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp

from ..ui_constants import get_theme
from .broadcast_profile_io import get_library


def broadcast_library_refresh(app: "ARKServerManagerApp") -> None:
    scroll = getattr(app, "_broadcast_lib_scroll", None)
    if not scroll or not scroll.winfo_exists():
        return

    for w in scroll.winfo_children():
        w.destroy()

    theme = get_theme("tek")
    accent = theme["accent"]
    card_bg = theme["card_bg"]
    t_sec = theme["text_secondary"]
    t_mut = theme["text_muted"]
    acc_mb = theme["accent_muted_bg"]
    acc_dk = theme["accent_dark"]
    sep = theme["separator"]
    is_light = theme.get("_is_light", False)
    card_bdr = theme.get("card_border", sep)

    lib = get_library(app)
    if not lib:
        ctk.CTkLabel(
            scroll,
            text="Nenhuma mensagem cadastrada.\nAdicione acima ou importe um arquivo .arkbroadcast",
            text_color=t_mut,
            font=ctk.CTkFont(size=13),
            justify="center",
        ).pack(pady=40)
        return

    for entry in lib:
        entry_id = str(entry.get("id", ""))
        row = ctk.CTkFrame(scroll, fg_color=card_bg, corner_radius=8,
                           border_width=1, border_color=card_bdr)
        row.pack(fill="x", padx=4, pady=4)
        row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            row, text=entry.get("label", ""),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=accent,
            anchor="w", width=160, wraplength=150,
        ).grid(row=0, column=0, sticky="w", padx=(12, 8), pady=10)

        msg = entry.get("message", "")
        preview = msg if len(msg) <= 100 else msg[:97] + "..."
        ctk.CTkLabel(
            row, text=preview,
            font=ctk.CTkFont(size=11),
            text_color=t_sec,
            anchor="w", wraplength=480,
        ).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=10)

        btns = ctk.CTkFrame(row, fg_color="transparent")
        btns.grid(row=0, column=2, padx=(0, 10), pady=8)

        send_bg = "#dcfce7" if is_light else "#052e16"
        send_tc = "#166534" if is_light else "#4ade80"

        ctk.CTkButton(
            btns, text="📢 Enviar", width=88, height=28,
            fg_color=send_bg, hover_color=acc_dk,
            text_color=send_tc,
            font=ctk.CTkFont(size=10),
            command=lambda eid=entry_id: app._broadcast_tek_send_one(eid),
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            btns, text="✏", width=30, height=28,
            fg_color=acc_mb, hover_color=acc_dk,
            text_color=accent,
            font=ctk.CTkFont(size=11),
            command=lambda eid=entry_id: app._broadcast_library_edit(eid),
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            btns, text="🗑", width=30, height=28,
            fg_color="#fee2e2" if is_light else "#7f1d1d",
            hover_color="#fecaca" if is_light else "#450a0a",
            text_color="#991b1b" if is_light else "#fca5a5",
            font=ctk.CTkFont(size=11),
            command=lambda eid=entry_id: app._broadcast_library_remove(eid),
        ).pack(side="left")
