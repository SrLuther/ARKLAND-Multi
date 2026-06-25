"""Diálogo para agendar desligamento de servidor TEK."""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp

_PRESETS = (5, 10, 15, 30)


def open_shutdown_schedule_dialog(app: "ARKServerManagerApp", server_id: str) -> None:
    srv = app.asm_config_manager.get_server(server_id)
    if not srv:
        return

    theme = get_theme("tek")
    bg = theme["bg"]
    card_bg = theme["card_bg"]
    accent = theme["accent"]
    sep = theme["separator"]
    t_sec = theme["text_secondary"]
    t_mut = theme["text_muted"]
    acc_mb = theme["accent_muted_bg"]
    acc_dk = theme["accent_dark"]
    hover = theme["accent_hover"]

    dlg = ctk.CTkToplevel(app)
    dlg.title("TEK — Agendar desligamento")
    dlg.geometry("420x320")
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.configure(fg_color=bg)
    dlg.after(100, dlg.lift)
    dlg.after(150, dlg.focus_force)

    ctk.CTkLabel(
        dlg, text="Agendar desligamento",
        font=ctk.CTkFont(size=16, weight="bold"),
        text_color=accent,
    ).pack(pady=(18, 2))

    ctk.CTkLabel(
        dlg, text=srv.name,
        font=ctk.CTkFont(size=12),
        text_color=t_sec,
    ).pack(pady=(0, 10))

    ctk.CTkLabel(
        dlg,
        text="Avisos RCON serão enviados aos jogadores em 5, 3 e 1 minuto(s)\n"
             "antes do desligamento (conforme o tempo escolhido).",
        font=ctk.CTkFont(size=11),
        text_color=t_mut,
        justify="center",
    ).pack(padx=24, pady=(0, 12))

    preset_var = tk.IntVar(value=5)
    custom_var = tk.StringVar(value="")

    presets_f = ctk.CTkFrame(dlg, fg_color=card_bg, corner_radius=8)
    presets_f.pack(fill="x", padx=24, pady=(0, 10))

    ctk.CTkLabel(
        presets_f, text="Tempo até desligar",
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color=t_sec,
    ).pack(anchor="w", padx=12, pady=(10, 6))

    row = ctk.CTkFrame(presets_f, fg_color="transparent")
    row.pack(fill="x", padx=8, pady=(0, 8))

    def _pick_preset(m: int) -> None:
        preset_var.set(m)
        custom_var.set("")

    for m in _PRESETS:
        ctk.CTkButton(
            row, text=f"{m} min", width=72, height=30,
            fg_color=acc_mb, hover_color=hover,
            text_color=accent, border_width=1, border_color=acc_dk,
            corner_radius=6,
            font=ctk.CTkFont(size=11),
            command=lambda mm=m: _pick_preset(mm),
        ).pack(side="left", padx=4)

    custom_f = ctk.CTkFrame(presets_f, fg_color="transparent")
    custom_f.pack(fill="x", padx=12, pady=(0, 12))

    ctk.CTkLabel(
        custom_f, text="Personalizado (min):",
        font=ctk.CTkFont(size=11), text_color=t_mut,
    ).pack(side="left", padx=(0, 8))

    custom_entry = ctk.CTkEntry(custom_f, width=80, textvariable=custom_var, placeholder_text="ex: 7")
    custom_entry.pack(side="left")

    def _on_custom_change(*_) -> None:
        if custom_var.get().strip():
            preset_var.set(0)

    custom_var.trace_add("write", _on_custom_change)

    err_var = tk.StringVar(value="")

    ctk.CTkLabel(
        dlg, textvariable=err_var,
        font=ctk.CTkFont(size=11),
        text_color="#f87171",
    ).pack(pady=(0, 4))

    btns = ctk.CTkFrame(dlg, fg_color="transparent")
    btns.pack(fill="x", padx=24, pady=(8, 18))

    def _confirm() -> None:
        from ..pages.asm_scheduled_shutdown import schedule_shutdown

        raw = custom_var.get().strip()
        if raw:
            try:
                minutes = int(raw)
            except ValueError:
                err_var.set("Minutos inválidos.")
                return
        else:
            minutes = preset_var.get()
            if minutes < 1:
                err_var.set("Escolha um tempo ou informe minutos.")
                return

        err = schedule_shutdown(app, server_id, minutes)
        if err:
            err_var.set(err)
            return
        dlg.destroy()

    ctk.CTkButton(
        btns, text="Cancelar", width=100, height=34,
        fg_color=sep, hover_color="#263347",
        text_color=t_sec, corner_radius=7,
        command=dlg.destroy,
    ).pack(side="right", padx=(8, 0))

    ctk.CTkButton(
        btns, text="Agendar", width=120, height=34,
        fg_color="#7f1d1d", hover_color="#450a0a",
        text_color="#fca5a5", corner_radius=7,
        font=ctk.CTkFont(weight="bold"),
        command=_confirm,
    ).pack(side="right")
