from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]
from tkinter import messagebox

from ..buff_manager import (
    BuffPreset, BuffEvent, BuffRates,
    BUFF_TYPE_XP, BUFF_TYPE_DOMA, BUFF_TYPE_BREEDING, BUFF_TYPE_FARM,
    BUFF_TYPE_LABELS, BUFF_RATE_FIELDS, QUICK_PRESETS,
    BUFF_STATUS_SCHEDULED,
)
from ..ui_constants import _GREEN_DARK, _GREEN_HOVER, _CARD_BG
import datetime
import uuid

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def open_create_buff_dialog(
    app: "ARKServerManagerApp",
    preset: Optional[BuffPreset] = None,
    server_id: Optional[str] = None,
) -> None:
    servers = app.config_manager.servers
    if not servers:
        messagebox.showwarning(
            "Sem Servidores",
            "Adicione ao menos um servidor antes de criar um BUFF.",
            parent=app,
        )
        return

    dlg = ctk.CTkToplevel(app)
    dlg.title("Criar BUFF")
    dlg.geometry("780x740")
    dlg.resizable(True, True)
    dlg.grab_set()
    dlg.grid_columnconfigure(0, weight=1)
    dlg.grid_rowconfigure(1, weight=1)

    ctk.CTkLabel(
        dlg, text="⚡  Criar Novo BUFF",
        font=ctk.CTkFont(size=18, weight="bold"),
    ).grid(row=0, column=0, padx=20, pady=(18, 4), sticky="w")

    body = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
    body.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
    body.grid_columnconfigure(0, weight=1)

    r = 0

    # ── Nome + Servidor ──────────────────────────────────────────────
    top_row = ctk.CTkFrame(body, fg_color="transparent")
    top_row.grid(row=r, column=0, sticky="ew", padx=16, pady=(8, 4))
    top_row.grid_columnconfigure(1, weight=1)
    top_row.grid_columnconfigure(3, weight=1)
    r += 1

    ctk.CTkLabel(top_row, text="Nome do BUFF:", width=110, anchor="w").grid(
        row=0, column=0, sticky="w")
    name_var = tk.StringVar(value=preset.name + " (cópia)" if preset else "")
    ctk.CTkEntry(top_row, textvariable=name_var, height=36).grid(
        row=0, column=1, sticky="ew", padx=(8, 16))

    ctk.CTkLabel(top_row, text="Servidor:", width=80, anchor="w").grid(
        row=0, column=2, sticky="w")
    srv_var = tk.StringVar()
    srv_names = [s.name for s in servers]
    if server_id:
        presel = next((s.name for s in servers if s.id == server_id), srv_names[0])
    else:
        presel = app._buffs_server_var.get() if app._buffs_server_var else srv_names[0]
    srv_var.set(presel)
    ctk.CTkComboBox(
        top_row, variable=srv_var, values=srv_names,
        state="readonly", width=220,
    ).grid(row=0, column=3, sticky="w", padx=(8, 0))

    # ── Tipos ────────────────────────────────────────────────────────
    ctk.CTkLabel(
        body, text="TIPOS DE BUFF",
        font=ctk.CTkFont(size=11, weight="bold"), text_color="#88d4a0",
    ).grid(row=r, column=0, padx=18, pady=(12, 4), sticky="w")
    r += 1

    types_frame = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    types_frame.grid(row=r, column=0, padx=16, pady=(0, 6), sticky="ew")
    r += 1

    type_vars: Dict[str, tk.BooleanVar] = {}
    preset_types = preset.types if preset else []
    for ci, btype in enumerate([BUFF_TYPE_XP, BUFF_TYPE_DOMA, BUFF_TYPE_BREEDING, BUFF_TYPE_FARM]):
        var = tk.BooleanVar(value=(btype in preset_types) if preset_types else True)
        type_vars[btype] = var
        ctk.CTkCheckBox(
            types_frame,
            text=BUFF_TYPE_LABELS[btype],
            variable=var,
            font=ctk.CTkFont(size=13),
        ).grid(row=0, column=ci, padx=20, pady=14, sticky="w")

    # ── Preset rápido ────────────────────────────────────────────────
    ctk.CTkLabel(
        body, text="PRESET RÁPIDO",
        font=ctk.CTkFont(size=11, weight="bold"), text_color="#88d4a0",
    ).grid(row=r, column=0, padx=18, pady=(10, 4), sticky="w")
    r += 1

    quick_frame = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    quick_frame.grid(row=r, column=0, padx=16, pady=(0, 6), sticky="ew")
    r += 1

    rate_vars: Dict[str, tk.StringVar] = {}

    def _fill_quick(mult: int) -> None:
        vals = QUICK_PRESETS.get(mult, {})
        for btype, fields in vals.items():
            if type_vars[btype].get():
                for fname, fval in fields.items():
                    if fname in rate_vars:
                        rate_vars[fname].set(str(fval))

    ctk.CTkLabel(quick_frame, text="Aplicar multiplicador a todos os tipos selecionados:",
                 text_color="gray60", font=ctk.CTkFont(size=11)).grid(
        row=0, column=0, columnspan=5, padx=16, pady=(12, 4), sticky="w")
    for ci, mult in enumerate((5, 10, 15)):
        ctk.CTkButton(
            quick_frame, text=f"{mult}x", width=72, height=34,
            fg_color="#2a2a44", hover_color="#1e2a3a",
            command=lambda m=mult: _fill_quick(m),
        ).grid(row=1, column=ci, padx=(16 if ci == 0 else 8, 0), pady=(4, 14))

    # Preset salvo
    presets_list = app._buff_manager.get_presets() if app._buff_manager else []
    if presets_list:
        ctk.CTkLabel(quick_frame, text="Usar preset salvo:",
                     text_color="gray60", font=ctk.CTkFont(size=11)).grid(
            row=1, column=3, padx=(24, 4), pady=(4, 14))

        def _apply_preset_combo(pname: str) -> None:
            found = next((p for p in presets_list if p.name == pname), None)
            if not found:
                return
            for t in [BUFF_TYPE_XP, BUFF_TYPE_DOMA, BUFF_TYPE_BREEDING, BUFF_TYPE_FARM]:
                type_vars[t].set(t in found.types)
            for fname in rate_vars:
                val = getattr(found.rates, fname, None)
                rate_vars[fname].set(str(val) if val is not None else "")

        ctk.CTkComboBox(
            quick_frame,
            values=[p.name for p in presets_list],
            state="readonly", width=200,
            command=_apply_preset_combo,
        ).grid(row=1, column=4, padx=(0, 16), pady=(4, 14))

    # ── Campos de rate por tipo ───────────────────────────────────────
    ctk.CTkLabel(
        body, text="MULTIPLICADORES",
        font=ctk.CTkFont(size=11, weight="bold"), text_color="#88d4a0",
    ).grid(row=r, column=0, padx=18, pady=(10, 4), sticky="w")
    r += 1

    rates_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    rates_card.grid(row=r, column=0, padx=16, pady=(0, 6), sticky="ew")
    rates_card.grid_columnconfigure((1, 3, 5, 7), weight=1)
    r += 1

    preset_rates = preset.rates if preset else None
    fr = 0
    for btype, fields in BUFF_RATE_FIELDS.items():
        # Separador de tipo
        ctk.CTkLabel(
            rates_card,
            text=BUFF_TYPE_LABELS[btype],
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#ffaa44",
        ).grid(row=fr, column=0, columnspan=8, padx=16, pady=(12, 4), sticky="w")
        fr += 1

        col = 0
        for fname, label, is_inv in fields:
            hint = " ↓" if is_inv else ""
            ctk.CTkLabel(
                rates_card, text=f"{label}{hint}:",
                text_color="gray60", font=ctk.CTkFont(size=11),
                anchor="e", width=110,
            ).grid(row=fr, column=col, padx=(16 if col == 0 else 4, 4),
                   pady=6, sticky="e")
            col += 1

            init_val = ""
            if preset_rates:
                v = getattr(preset_rates, fname, None)
                if v is not None:
                    init_val = str(v)
            sv = tk.StringVar(value=init_val)
            rate_vars[fname] = sv
            ctk.CTkEntry(
                rates_card, textvariable=sv, width=80, height=32,
                placeholder_text="1.0",
            ).grid(row=fr, column=col, padx=(0, 16), pady=6, sticky="w")
            col += 1

            if col >= 8:
                col = 0
                fr += 1

        if col > 0:
            fr += 1

    # ── Agendamento ──────────────────────────────────────────────────
    ctk.CTkLabel(
        body, text="AGENDAMENTO",
        font=ctk.CTkFont(size=11, weight="bold"), text_color="#88d4a0",
    ).grid(row=r, column=0, padx=18, pady=(10, 4), sticky="w")
    r += 1

    sched_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    sched_card.grid(row=r, column=0, padx=16, pady=(0, 6), sticky="ew")
    r += 1

    now_str = now_brasilia().strftime("%d/%m/%Y %H:00")
    ctk.CTkLabel(sched_card, text="Início:", text_color="gray60").grid(
        row=0, column=0, padx=(16, 4), pady=14, sticky="w")
    start_var = tk.StringVar(value=now_str)
    ctk.CTkEntry(sched_card, textvariable=start_var, width=160,
                 placeholder_text="DD/MM/AAAA HH:MM").grid(
        row=0, column=1, padx=(0, 24), pady=14, sticky="w")

    ctk.CTkLabel(sched_card, text="Fim:", text_color="gray60").grid(
        row=0, column=2, padx=(0, 4), pady=14, sticky="w")
    end_var = tk.StringVar(value=now_str)
    ctk.CTkEntry(sched_card, textvariable=end_var, width=160,
                 placeholder_text="DD/MM/AAAA HH:MM").grid(
        row=0, column=3, padx=(0, 16), pady=14, sticky="w")

    ctk.CTkLabel(sched_card,
                 text="Formato: DD/MM/AAAA HH:MM  —  Máx. 30 dias",
                 text_color="gray45", font=ctk.CTkFont(size=10)).grid(
        row=1, column=0, columnspan=4, padx=16, pady=(0, 10), sticky="w")

    # ── Salvar como preset ───────────────────────────────────────────
    save_preset_var = tk.BooleanVar(value=False)
    preset_name_var = tk.StringVar()
    sp_frame = ctk.CTkFrame(body, fg_color="transparent")
    sp_frame.grid(row=r, column=0, padx=16, pady=(4, 4), sticky="ew")
    r += 1

    ctk.CTkCheckBox(sp_frame, text="Salvar como Preset", variable=save_preset_var).pack(
        side="left", padx=(0, 12))
    ctk.CTkEntry(sp_frame, textvariable=preset_name_var, width=220,
                 placeholder_text="Nome do Preset").pack(side="left")

    # ── Status / erro ─────────────────────────────────────────────────
    err_var = tk.StringVar()
    err_lbl = ctk.CTkLabel(body, textvariable=err_var,
                           text_color="#ff6666", font=ctk.CTkFont(size=11),
                           wraplength=700, justify="left")
    err_lbl.grid(row=r, column=0, padx=18, pady=(4, 0), sticky="w")
    r += 1

    # ── Botões ────────────────────────────────────────────────────────
    btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_row.grid(row=2, column=0, pady=(8, 16), padx=16, sticky="e")

    def _parse_dt(s: str) -> Optional[str]:
        """Converte DD/MM/AAAA HH:MM para ISO 8601."""
        s = s.strip()
        for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
            try:
                return datetime.strptime(s, fmt).isoformat()
            except ValueError:
                pass
        return None

    def _collect_rates() -> BuffRates:
        kwargs: Dict[str, float] = {}
        for fname, sv in rate_vars.items():
            raw = sv.get().strip()
            if raw:
                try:
                    kwargs[fname] = float(raw.replace(",", "."))
                except ValueError:
                    pass
        return BuffRates(**kwargs)

    def _do_schedule() -> None:
        name = name_var.get().strip()
        selected_types = [t for t, v in type_vars.items() if v.get()]

        start_iso = _parse_dt(start_var.get())
        end_iso   = _parse_dt(end_var.get())
        if not start_iso or not end_iso:
            err_var.set("Data/hora inválida. Use DD/MM/AAAA HH:MM.")
            return

        srv_name = srv_var.get()
        sel_srv = next((s for s in servers if s.name == srv_name), None)
        if not sel_srv:
            err_var.set("Servidor não encontrado.")
            return

        rates = _collect_rates()

        event = BuffEvent(
            id=str(uuid.uuid4()),
            name=name,
            server_id=sel_srv.id,
            types=selected_types,
            rates=rates,
            start_dt=start_iso,
            end_dt=end_iso,
            status=BUFF_STATUS_SCHEDULED,
        )

        if not app._buff_manager:
            err_var.set("BuffManager não inicializado.")
            return

        # Salva preset se solicitado
        if save_preset_var.get():
            pname = preset_name_var.get().strip() or name
            app._buff_manager.save_preset(BuffPreset(
                id=str(uuid.uuid4()),
                name=pname,
                types=selected_types,
                rates=rates,
            ))

        err = app._buff_manager.add_event(event)
        if err:
            err_var.set(err)
            return

        dlg.destroy()

    ctk.CTkButton(btn_row, text="Cancelar", width=120, height=40,
                  fg_color="#2a2a44", hover_color="#1e2a3a",
                  command=dlg.destroy).pack(side="left", padx=(0, 12))
    ctk.CTkButton(btn_row, text="⚡  Agendar BUFF", width=180, height=40,
                  fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  font=ctk.CTkFont(size=13, weight="bold"),
                  command=_do_schedule).pack(side="left")

