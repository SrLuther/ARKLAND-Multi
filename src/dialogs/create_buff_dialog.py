from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Dict, List, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]
from tkinter import messagebox

from ..buff_manager import (
    BuffPreset, BuffEvent, BuffRates,
    BUFF_TYPE_XP, BUFF_TYPE_DOMA, BUFF_TYPE_BREEDING, BUFF_TYPE_FARM,
    BUFF_TYPE_LABELS, BUFF_RATE_FIELDS, QUICK_PRESETS,
    BUFF_STATUS_SCHEDULED, now_brasilia,
    BUFF_RECURRENCE_NONE, BUFF_RECURRENCE_DAILY,
    BUFF_RECURRENCE_WEEKLY, BUFF_RECURRENCE_WEEKEND,
    BUFF_RECURRENCE_LABELS,
)
from ..ui_constants import _GREEN_DARK, _GREEN_HOVER, _CARD_BG, _BLUE, _BLUE_HOVER
from ..buff_server_bridge import list_buff_servers
from datetime import datetime, timedelta
import uuid

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def open_create_buff_dialog(
    app: "ARKServerManagerApp",
    preset: Optional[BuffPreset] = None,
    server_id: Optional[str] = None,
    event: Optional[BuffEvent] = None,  # preenchido para editar buff agendado
) -> None:
    entries = list_buff_servers(app)
    if not entries:
        messagebox.showwarning(
            "Sem Servidores",
            "Adicione ao menos um servidor (TEK ou legado) antes de criar um evento sazonal.",
            parent=app,
        )
        return

    servers = entries  # BuffServerEntry list — usa .id e .label

    is_editing = event is not None
    dlg_title  = "✏️  Editar Evento" if is_editing else "⚡  Novo Evento Sazonal"

    dlg = ctk.CTkToplevel(app)
    dlg.title("Editar Evento" if is_editing else "Novo Evento Sazonal")
    dlg.geometry("820x820")
    dlg.resizable(True, True)
    dlg.grab_set()
    dlg.grid_columnconfigure(0, weight=1)
    dlg.grid_rowconfigure(1, weight=1)

    ctk.CTkLabel(
        dlg, text=dlg_title,
        font=ctk.CTkFont(size=18, weight="bold"),
    ).grid(row=0, column=0, padx=20, pady=(18, 4), sticky="w")

    body = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
    body.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
    body.grid_columnconfigure(0, weight=1)

    r = 0

    # ── Nome ─────────────────────────────────────────────────────────
    name_row = ctk.CTkFrame(body, fg_color="transparent")
    name_row.grid(row=r, column=0, sticky="ew", padx=16, pady=(8, 4))
    name_row.grid_columnconfigure(1, weight=1)
    r += 1

    ctk.CTkLabel(name_row, text="Nome do Evento:", width=110, anchor="w").grid(
        row=0, column=0, sticky="w")

    # Valor inicial: evento em edição > preset (cópia) > vazio
    _init_name = ""
    if event:
        _init_name = event.name
    elif preset:
        _init_name = preset.name + " (cópia)"
    name_var = tk.StringVar(value=_init_name)
    ctk.CTkEntry(name_row, textvariable=name_var, height=36).grid(
        row=0, column=1, sticky="ew", padx=(8, 0))

    # ── Servidores (multi-seleção) ───────────────────────────────────
    ctk.CTkLabel(
        body, text="SERVIDORES",
        font=ctk.CTkFont(size=11, weight="bold"), text_color="#88d4a0",
    ).grid(row=r, column=0, padx=18, pady=(10, 4), sticky="w")
    r += 1

    srv_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    srv_card.grid(row=r, column=0, padx=16, pady=(0, 6), sticky="ew")
    r += 1

    srv_vars: Dict[str, tk.BooleanVar] = {}
    # Determina quais servidores pré-selecionar
    _presel_ids: set = set()
    if event:
        _presel_ids = {event.server_id}
    elif server_id:
        _presel_ids = {server_id}
    else:
        sel_name = app._buffs_server_var.get() if app._buffs_server_var else ""
        from ..buff_server_bridge import resolve_buff_server_id
        resolved = resolve_buff_server_id(app, sel_name)
        if resolved:
            _presel_ids = {resolved}
        elif servers:
            _presel_ids = {servers[0].id}

    for ci, srv in enumerate(servers):
        var = tk.BooleanVar(value=(srv.id in _presel_ids))
        srv_vars[srv.id] = var
        ctk.CTkCheckBox(
            srv_card, text=srv.label, variable=var,
            font=ctk.CTkFont(size=12),
        ).grid(row=ci // 3, column=ci % 3, padx=16, pady=8, sticky="w")

    # ── Tipos ────────────────────────────────────────────────────────
    ctk.CTkLabel(
        body, text="TIPOS DE EVENTO",
        font=ctk.CTkFont(size=11, weight="bold"), text_color="#88d4a0",
    ).grid(row=r, column=0, padx=18, pady=(12, 4), sticky="w")
    r += 1

    types_frame = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    types_frame.grid(row=r, column=0, padx=16, pady=(0, 6), sticky="ew")
    r += 1

    type_vars: Dict[str, tk.BooleanVar] = {}
    _init_types = event.types if event else (preset.types if preset else [])
    for ci, btype in enumerate([BUFF_TYPE_XP, BUFF_TYPE_DOMA, BUFF_TYPE_BREEDING, BUFF_TYPE_FARM]):
        var = tk.BooleanVar(value=(btype in _init_types) if _init_types else True)
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

    # Fonte de rates: evento em edição > preset > vazio
    _init_rates = event.rates if event else (preset.rates if preset else None)
    fr = 0
    for btype, fields in BUFF_RATE_FIELDS.items():
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
            if _init_rates:
                v = getattr(_init_rates, fname, None)
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

    _fmt = "%d/%m/%Y %H:%M"
    _now_str = now_brasilia().strftime("%d/%m/%Y %H:00")

    # Valores iniciais: evento em edição ou agora
    if event:
        _start_init = event.start_datetime().strftime(_fmt)
        _end_init   = event.end_datetime().strftime(_fmt)
    else:
        _start_init = _end_init = _now_str

    ctk.CTkLabel(sched_card, text="Início:", text_color="gray60").grid(
        row=0, column=0, padx=(16, 4), pady=(14, 4), sticky="w")
    start_var = tk.StringVar(value=_start_init)
    ctk.CTkEntry(sched_card, textvariable=start_var, width=160,
                 placeholder_text="DD/MM/AAAA HH:MM").grid(
        row=0, column=1, padx=(0, 24), pady=(14, 4), sticky="w")

    ctk.CTkLabel(sched_card, text="Fim:", text_color="gray60").grid(
        row=0, column=2, padx=(0, 4), pady=(14, 4), sticky="w")
    end_var = tk.StringVar(value=_end_init)
    ctk.CTkEntry(sched_card, textvariable=end_var, width=160,
                 placeholder_text="DD/MM/AAAA HH:MM").grid(
        row=0, column=3, padx=(0, 16), pady=(14, 4), sticky="w")

    # ── Duração rápida ───────────────────────────────────────────────
    quick_dur_frame = ctk.CTkFrame(sched_card, fg_color="transparent")
    quick_dur_frame.grid(row=1, column=0, columnspan=6, padx=12, pady=(0, 4), sticky="w")

    ctk.CTkLabel(quick_dur_frame, text="Duração rápida:",
                 text_color="gray55", font=ctk.CTkFont(size=11)).pack(side="left", padx=(4, 8))

    def _apply_duration(hours: float, label: str = "") -> None:
        """Define end_dt = start_dt + horas. Se start inválido, usa agora."""
        raw = start_var.get().strip()
        try:
            base = datetime.strptime(raw, _fmt)
        except ValueError:
            base = now_brasilia().replace(minute=0, second=0, microsecond=0)
            start_var.set(base.strftime(_fmt))
        end_var.set((base + timedelta(hours=hours)).strftime(_fmt))

    def _apply_weekend() -> None:
        """Define início na sexta 20h e fim no domingo 23h59."""
        now_dt = now_brasilia()
        days_to_fri = (4 - now_dt.weekday()) % 7
        if days_to_fri == 0 and now_dt.hour >= 20:
            days_to_fri = 7
        fri = now_dt + timedelta(days=days_to_fri)
        fri_start = fri.replace(hour=20, minute=0, second=0, microsecond=0)
        sun_end   = fri_start + timedelta(hours=51, minutes=59)  # dom 23h59
        start_var.set(fri_start.strftime(_fmt))
        end_var.set(sun_end.strftime(_fmt))

    for _lbl, _h in (("1h", 1), ("2h", 2), ("4h", 4), ("8h", 8), ("24h", 24), ("48h", 48)):
        ctk.CTkButton(
            quick_dur_frame, text=_lbl, width=48, height=26,
            fg_color="#2a2a44", hover_color="#1e2a3a",
            font=ctk.CTkFont(size=11),
            command=lambda h=_h: _apply_duration(h),
        ).pack(side="left", padx=3)

    ctk.CTkButton(
        quick_dur_frame, text="🎮 Fim de Semana", width=130, height=26,
        fg_color="#2a2a44", hover_color="#1e2a3a",
        font=ctk.CTkFont(size=11),
        command=_apply_weekend,
    ).pack(side="left", padx=(8, 3))

    # ── Recorrência ──────────────────────────────────────────────────
    rec_frame = ctk.CTkFrame(sched_card, fg_color="transparent")
    rec_frame.grid(row=2, column=0, columnspan=6, padx=12, pady=(2, 8), sticky="w")

    ctk.CTkLabel(rec_frame, text="Repetir:",
                 text_color="gray55", font=ctk.CTkFont(size=11)).pack(side="left", padx=(4, 8))

    _rec_options = list(BUFF_RECURRENCE_LABELS.values())
    _rec_keys    = list(BUFF_RECURRENCE_LABELS.keys())
    _init_rec_label = BUFF_RECURRENCE_LABELS.get(
        event.recurrence if event else None, "Sem repetição"
    )
    recurrence_var = tk.StringVar(value=_init_rec_label)
    ctk.CTkComboBox(
        rec_frame, variable=recurrence_var, values=_rec_options,
        state="readonly", width=180,
    ).pack(side="left")

    ctk.CTkLabel(sched_card,
                 text="Formato: DD/MM/AAAA HH:MM  —  Máx. 30 dias",
                 text_color="gray45", font=ctk.CTkFont(size=10)).grid(
        row=3, column=0, columnspan=6, padx=16, pady=(0, 10), sticky="w")

    # ── Preview de rates ─────────────────────────────────────────────
    preview_var = tk.StringVar(value="—")
    preview_lbl = ctk.CTkLabel(
        body, textvariable=preview_var,
        text_color="#88aaff", font=ctk.CTkFont(size=11),
        wraplength=740, justify="left",
    )
    preview_lbl.grid(row=r, column=0, padx=18, pady=(0, 4), sticky="w")
    r += 1

    def _update_preview(*_) -> None:
        try:
            preview_var.set("📊  " + _collect_rates().summary())
        except Exception:
            pass

    # Vincula atualização do preview a qualquer mudança nos rate_vars
    for _sv in rate_vars.values():
        _sv.trace_add("write", _update_preview)
    _update_preview()

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

    def _get_recurrence() -> Optional[str]:
        label = recurrence_var.get()
        for k, v in BUFF_RECURRENCE_LABELS.items():
            if v == label:
                return k
        return None

    def _do_schedule() -> None:
        name = name_var.get().strip()
        selected_types = [t for t, v in type_vars.items() if v.get()]
        selected_srvs  = [s for s in servers if srv_vars.get(s.id, tk.BooleanVar()).get()]

        if not selected_srvs:
            err_var.set("Selecione ao menos um servidor.")
            return

        start_iso = _parse_dt(start_var.get())
        end_iso   = _parse_dt(end_var.get())
        if not start_iso or not end_iso:
            err_var.set("Data/hora inválida. Use DD/MM/AAAA HH:MM.")
            return

        if not app._buff_manager:
            err_var.set("BuffManager não inicializado.")
            return

        rates      = _collect_rates()
        recurrence = _get_recurrence()

        # Salva preset se solicitado
        if save_preset_var.get():
            pname = preset_name_var.get().strip() or name
            app._buff_manager.save_preset(BuffPreset(
                id=str(uuid.uuid4()),
                name=pname,
                types=selected_types,
                rates=rates,
            ))

        # Cria (ou atualiza) um evento por servidor selecionado
        errors: List[str] = []
        for srv in selected_srvs:
            if is_editing and len(selected_srvs) == 1 and event.server_id == srv.id:  # type: ignore[union-attr]
                # Edição: atualiza o evento existente
                updated = BuffEvent(
                    id=event.id,  # type: ignore[union-attr]
                    name=name,
                    server_id=srv.id,
                    types=selected_types,
                    rates=rates,
                    start_dt=start_iso,
                    end_dt=end_iso,
                    status=BUFF_STATUS_SCHEDULED,
                    recurrence=recurrence,
                )
                err = app._buff_manager.update_event(updated)
            else:
                new_event = BuffEvent(
                    id=str(uuid.uuid4()),
                    name=name,
                    server_id=srv.id,
                    types=selected_types,
                    rates=rates,
                    start_dt=start_iso,
                    end_dt=end_iso,
                    status=BUFF_STATUS_SCHEDULED,
                    recurrence=recurrence,
                )
                err = app._buff_manager.add_event(new_event)
            if err:
                errors.append(f"{srv.name}: {err}")

        if errors:
            err_var.set("\n".join(errors))
            return

        dlg.destroy()

    _btn_label = "💾  Salvar Alterações" if is_editing else "⚡  Agendar Evento"
    ctk.CTkButton(btn_row, text="Cancelar", width=120, height=40,
                  fg_color="#2a2a44", hover_color="#1e2a3a",
                  command=dlg.destroy).pack(side="left", padx=(0, 12))
    ctk.CTkButton(btn_row, text=_btn_label, width=200, height=40,
                  fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  font=ctk.CTkFont(size=13, weight="bold"),
                  command=_do_schedule).pack(side="left")

