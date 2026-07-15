"""Diálogo para agendar desligamento de servidores TEK (multi-select + segundos)."""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Iterable

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import ASM_STATUS_RUNNING
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp

# Presets em segundos
_PRESETS_SEC = (30, 60, 120, 300, 600, 900)


def open_shutdown_schedule_dialog(
    app: "ARKServerManagerApp",
    server_id: str | None = None,
    preselected: Iterable[str] | None = None,
) -> None:
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
    card_bdr = theme.get("card_border", sep)

    servers = list(app.asm_config_manager.servers)
    if not servers:
        app._toast("Nenhum servidor TEK configurado.", kind="warning")
        return

    pre_set = set(preselected or [])
    if server_id:
        pre_set.add(server_id)
    if not pre_set:
        # Sem pré-seleção: marca os online
        for srv in servers:
            inst = app.asm_server_manager.get_instance(srv.id)
            if inst and inst.status == ASM_STATUS_RUNNING:
                pre_set.add(srv.id)

    dlg = ctk.CTkToplevel(app)
    dlg.title("TEK — Agendar desligamento")
    dlg.geometry("520x560")
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.configure(fg_color=bg)
    dlg.after(100, dlg.lift)
    dlg.after(150, dlg.focus_force)

    ctk.CTkLabel(
        dlg, text="Agendar desligamento",
        font=ctk.CTkFont(size=16, weight="bold"),
        text_color=accent,
    ).pack(pady=(16, 2))

    ctk.CTkLabel(
        dlg,
        text="Avisos RCON em intervalos sensatos (ex.: 60s, 30s, 10s, 5s…)\n"
             "conforme o tempo restante — sem spam a cada segundo.",
        font=ctk.CTkFont(size=11),
        text_color=t_mut,
        justify="center",
    ).pack(padx=20, pady=(0, 10))

    # ── Servidores ────────────────────────────────────────────────────────────
    srv_card = ctk.CTkFrame(
        dlg, fg_color=card_bg, corner_radius=8,
        border_width=1, border_color=card_bdr,
    )
    srv_card.pack(fill="both", expand=True, padx=20, pady=(0, 10))

    srv_hdr = ctk.CTkFrame(srv_card, fg_color="transparent")
    srv_hdr.pack(fill="x", padx=12, pady=(10, 4))

    ctk.CTkLabel(
        srv_hdr, text="Servidores",
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=t_sec,
    ).pack(side="left")

    server_vars: dict[str, tk.BooleanVar] = {}
    mark_all_var = tk.BooleanVar(value=False)

    def _sync_mark_all() -> None:
        vals = list(server_vars.values())
        mark_all_var.set(bool(vals) and all(v.get() for v in vals))

    def _toggle_all() -> None:
        val = mark_all_var.get()
        for var in server_vars.values():
            var.set(val)

    ctk.CTkCheckBox(
        srv_hdr, text="Marcar todos",
        variable=mark_all_var,
        font=ctk.CTkFont(size=11),
        command=_toggle_all,
    ).pack(side="right")

    srv_scroll = ctk.CTkScrollableFrame(srv_card, fg_color="transparent", height=180)
    srv_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 10))

    for srv in servers:
        inst = app.asm_server_manager.get_instance(srv.id)
        online = bool(inst and inst.status == ASM_STATUS_RUNNING)
        dot = "🟢" if online else "⚫"
        var = tk.BooleanVar(value=srv.id in pre_set and online)
        server_vars[srv.id] = var

        def _on_toggle(*_a, _sid=srv.id) -> None:
            _sync_mark_all()

        row = ctk.CTkFrame(srv_scroll, fg_color="transparent")
        row.pack(fill="x", pady=2)
        cb = ctk.CTkCheckBox(
            row,
            text=f"{dot}  {srv.name}" + ("" if online else "  (offline)"),
            variable=var,
            font=ctk.CTkFont(size=11),
            state="normal" if online else "disabled",
            command=_on_toggle,
        )
        cb.pack(anchor="w", padx=4)

    _sync_mark_all()

    # ── Tempo (segundos) ──────────────────────────────────────────────────────
    time_card = ctk.CTkFrame(dlg, fg_color=card_bg, corner_radius=8)
    time_card.pack(fill="x", padx=20, pady=(0, 8))

    ctk.CTkLabel(
        time_card, text="Tempo até desligar (segundos)",
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color=t_sec,
    ).pack(anchor="w", padx=12, pady=(10, 6))

    preset_var = tk.IntVar(value=60)
    custom_var = tk.StringVar(value="")

    row = ctk.CTkFrame(time_card, fg_color="transparent")
    row.pack(fill="x", padx=8, pady=(0, 6))

    def _pick_preset(sec: int) -> None:
        preset_var.set(sec)
        custom_var.set("")

    for sec in _PRESETS_SEC:
        label = f"{sec}s" if sec < 60 else f"{sec // 60}m"
        ctk.CTkButton(
            row, text=label, width=56, height=28,
            fg_color=acc_mb, hover_color=hover,
            text_color=accent, border_width=1, border_color=acc_dk,
            corner_radius=6,
            font=ctk.CTkFont(size=11),
            command=lambda s=sec: _pick_preset(s),
        ).pack(side="left", padx=3)

    custom_f = ctk.CTkFrame(time_card, fg_color="transparent")
    custom_f.pack(fill="x", padx=12, pady=(0, 12))

    ctk.CTkLabel(
        custom_f, text="Personalizado (s):",
        font=ctk.CTkFont(size=11), text_color=t_mut,
    ).pack(side="left", padx=(0, 8))

    custom_entry = ctk.CTkEntry(
        custom_f, width=100, textvariable=custom_var, placeholder_text="ex: 90",
    )
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
    btns.pack(fill="x", padx=20, pady=(4, 16))

    def _confirm() -> None:
        from ..pages.asm_scheduled_shutdown import schedule_shutdown_many

        raw = custom_var.get().strip()
        if raw:
            try:
                seconds = int(raw)
            except ValueError:
                err_var.set("Segundos inválidos.")
                return
        else:
            seconds = int(preset_var.get())
            if seconds < 1:
                err_var.set("Escolha um tempo ou informe os segundos.")
                return

        selected = [sid for sid, var in server_vars.items() if var.get()]
        if not selected:
            err_var.set("Marque ao menos um servidor online.")
            return

        err = schedule_shutdown_many(app, selected, seconds)
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
