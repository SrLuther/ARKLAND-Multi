"""Diálogo para agendar desligamento de servidores TEK (multi-select + minutos/segundos)."""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Iterable

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import ASM_STATUS_RUNNING
from ..pages.asm_scheduled_shutdown import total_seconds_from_parts
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp

# Presets em segundos (rótulos amigáveis no botão)
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
    dlg.geometry("520x600")
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

    # ── Tempo (minutos + segundos) ─────────────────────────────────────────────
    time_card = ctk.CTkFrame(dlg, fg_color=card_bg, corner_radius=8)
    time_card.pack(fill="x", padx=20, pady=(0, 8))

    ctk.CTkLabel(
        time_card, text="Tempo até desligar",
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color=t_sec,
    ).pack(anchor="w", padx=12, pady=(10, 6))

    # Default: 5 minutos (antes o campo «personalizado» em segundos fazia
    # operadores digitarem 5/15 e o servidor cair em 5–15 segundos).
    minutes_var = tk.StringVar(value="5")
    seconds_var = tk.StringVar(value="0")
    preset_total_var = tk.IntVar(value=300)
    use_preset = tk.BooleanVar(value=True)

    row = ctk.CTkFrame(time_card, fg_color="transparent")
    row.pack(fill="x", padx=8, pady=(0, 6))

    def _apply_total_to_fields(total: int) -> None:
        total = max(1, int(total))
        mins, secs = divmod(total, 60)
        minutes_var.set(str(mins))
        seconds_var.set(str(secs))
        preset_total_var.set(total)
        use_preset.set(True)

    def _pick_preset(sec: int) -> None:
        _apply_total_to_fields(sec)

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
    custom_f.pack(fill="x", padx=12, pady=(0, 4))

    ctk.CTkLabel(
        custom_f, text="Minutos:",
        font=ctk.CTkFont(size=11), text_color=t_mut,
    ).pack(side="left", padx=(0, 6))
    minutes_entry = ctk.CTkEntry(
        custom_f, width=64, textvariable=minutes_var, placeholder_text="5",
    )
    minutes_entry.pack(side="left")

    ctk.CTkLabel(
        custom_f, text="Segundos:",
        font=ctk.CTkFont(size=11), text_color=t_mut,
    ).pack(side="left", padx=(12, 6))
    seconds_entry = ctk.CTkEntry(
        custom_f, width=64, textvariable=seconds_var, placeholder_text="0",
    )
    seconds_entry.pack(side="left")

    preview_var = tk.StringVar(value="")

    def _refresh_preview(*_a) -> None:
        use_preset.set(False)
        try:
            m = int((minutes_var.get() or "0").strip() or "0")
            s = int((seconds_var.get() or "0").strip() or "0")
        except ValueError:
            preview_var.set("Valores inválidos")
            return
        if m < 0 or s < 0 or s > 59:
            preview_var.set("Segundos devem ser 0–59")
            return
        total = total_seconds_from_parts(m, s)
        if total < 1:
            preview_var.set("Informe ao menos 1 segundo")
            return
        from ..pages.asm_scheduled_shutdown import format_remaining_human
        preview_var.set(f"Total: {format_remaining_human(total)} ({total}s)")

    minutes_var.trace_add("write", _refresh_preview)
    seconds_var.trace_add("write", _refresh_preview)
    _refresh_preview()
    use_preset.set(True)

    ctk.CTkLabel(
        time_card, textvariable=preview_var,
        font=ctk.CTkFont(size=11), text_color=t_mut,
    ).pack(anchor="w", padx=12, pady=(0, 10))

    err_var = tk.StringVar(value="")
    ctk.CTkLabel(
        dlg, textvariable=err_var,
        font=ctk.CTkFont(size=11),
        text_color="#f87171",
    ).pack(pady=(0, 4))

    btns = ctk.CTkFrame(dlg, fg_color="transparent")
    btns.pack(fill="x", padx=20, pady=(4, 16))

    def _resolve_seconds() -> int | None:
        if use_preset.get() and preset_total_var.get() >= 1:
            return int(preset_total_var.get())
        try:
            m = int((minutes_var.get() or "0").strip() or "0")
            s = int((seconds_var.get() or "0").strip() or "0")
        except ValueError:
            err_var.set("Informe minutos e segundos numéricos.")
            return None
        if m < 0 or s < 0:
            err_var.set("Tempo não pode ser negativo.")
            return None
        if s > 59:
            err_var.set("Segundos devem estar entre 0 e 59.")
            return None
        total = total_seconds_from_parts(m, s)
        if total < 1:
            err_var.set("Informe ao menos 1 segundo (ex.: 0 min + 30 s).")
            return None
        return total

    def _confirm() -> None:
        from ..pages.asm_scheduled_shutdown import schedule_shutdown_many

        seconds = _resolve_seconds()
        if seconds is None:
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
