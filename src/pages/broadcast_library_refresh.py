from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp

from ..ui_constants import get_theme
from .broadcast_profile_io import get_library
from .broadcast_tek_settings import get_settings


def broadcast_library_refresh(app: "ARKServerManagerApp") -> None:
    scroll = getattr(app, "_broadcast_lib_scroll", None)
    if not scroll or not scroll.winfo_exists():
        return

    for w in scroll.winfo_children():
        w.destroy()

    if not hasattr(app, "_broadcast_message_vars"):
        app._broadcast_message_vars = {}
    app._broadcast_message_vars.clear()

    theme = get_theme("tek")
    accent = theme["accent"]
    card_bg = theme["card_bg"]
    t_sec = theme["text_secondary"]
    t_mut = theme["text_muted"]
    acc_mb = theme["accent_muted_bg"]
    acc_dk = theme["accent_dark"]
    is_light = theme.get("_is_light", False)
    card_bdr = theme.get("card_border", theme["separator"])

    lib = get_library(app)
    settings = get_settings(app)
    all_msg_ids = {str(e.get("id")) for e in lib if e.get("id")}
    enabled_ids = (
        set(settings.enabled_message_ids)
        if settings.enabled_message_ids else all_msg_ids
    )

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
        row.grid_columnconfigure(2, weight=1)

        in_cycle = entry_id in enabled_ids if settings.enabled_message_ids else True
        cycle_var = tk.BooleanVar(value=in_cycle)
        app._broadcast_message_vars[entry_id] = cycle_var

        ctk.CTkCheckBox(
            row, text="", variable=cycle_var, width=24,
            command=app._broadcast_tek_save_settings_from_ui,
        ).grid(row=0, column=0, padx=(10, 4), pady=10)

        label_col = ctk.CTkFrame(row, fg_color="transparent")
        label_col.grid(row=0, column=1, sticky="w", padx=(0, 8), pady=10)

        ctk.CTkLabel(
            label_col, text=entry.get("label", ""),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=accent,
            anchor="w", width=140, wraplength=130,
        ).pack(anchor="w")

        if str(entry.get("source") or "") == "regulamento" or entry.get("category"):
            badge = str(entry.get("category") or "Regulamento")
            sec = str(entry.get("section") or "").strip()
            badge_txt = f"{badge} §{sec}" if sec else badge
            ctk.CTkLabel(
                label_col, text=badge_txt,
                font=ctk.CTkFont(size=9),
                text_color=t_mut,
                anchor="w",
            ).pack(anchor="w", pady=(2, 0))

        msg = entry.get("message", "")
        preview = msg if len(msg) <= 90 else msg[:87] + "..."
        ctk.CTkLabel(
            row, text=preview,
            font=ctk.CTkFont(size=11),
            text_color=t_sec,
            anchor="w", wraplength=420,
        ).grid(row=0, column=2, sticky="ew", padx=(0, 8), pady=10)

        btns = ctk.CTkFrame(row, fg_color="transparent")
        btns.grid(row=0, column=3, padx=(0, 10), pady=8)

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
