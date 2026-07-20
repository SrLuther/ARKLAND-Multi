"""Evento sazonal ARK (ActiveEvent) — aplicação global em vários servidores."""
from __future__ import annotations

import logging
import tkinter as tk
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]
from tkinter import messagebox

from ..buff_server_bridge import BuffServerEntry, buff_server_kind, list_buff_servers
from ..global_active_event_scheduler import (
    ARK_EVENT_STATUS_SCHEDULED,
    format_brasilia_datetime,
    parse_brasilia_datetime,
)
from ..buff_manager import now_brasilia
from ..ui_constants import (
    _ARK_EVENT_ID_TO_LABEL,
    _ARK_EVENT_LABEL_TO_ID,
    _ARK_OFFICIAL_EVENTS,
    _BLUE,
    _BLUE_HOVER,
    _CARD_BG,
    _GREEN_DARK,
    _GREEN_HOVER,
    normalize_active_event,
)

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

_log = logging.getLogger("arkland")


@dataclass
class ApplyActiveEventResult:
    server_id: str
    server_name: str
    ok: bool
    message: str


def event_id_from_combo_label(label: str) -> str:
    raw = (label or "").strip()
    return normalize_active_event(_ARK_EVENT_LABEL_TO_ID.get(raw, raw))


def _sync_open_panel_active_event(app: Any, server_id: str, event_id: str) -> None:
    """Atualiza o combo do painel TEK/legado aberto para não apagar o evento no próximo start."""
    label = _ARK_EVENT_ID_TO_LABEL.get(event_id, event_id) or "(nenhum evento)"

    # Painel TEK (AsmServerConfig)
    tek_vars = getattr(app, "_asm_panel_vars", {}).get(server_id, {})
    tek_var = tek_vars.get("active_event") if isinstance(tek_vars, dict) else None
    if tek_var is not None:
        try:
            tek_var.set(label)
        except Exception:
            pass

    # Painel legado (widgets por servidor)
    leg_widgets = getattr(app, "_server_widgets", {}).get(server_id, {})
    leg_var = leg_widgets.get("active_event") if isinstance(leg_widgets, dict) else None
    if leg_var is not None:
        try:
            leg_var.set(label)
        except Exception:
            pass


def apply_active_event_to_server(app: Any, entry: BuffServerEntry, event_id: str) -> ApplyActiveEventResult:
    """Define ``active_event`` no perfil e grava GameUserSettings.ini."""
    event_id = normalize_active_event(event_id)
    kind = buff_server_kind(app, entry.id)
    if kind is None:
        return ApplyActiveEventResult(entry.id, entry.name, False, "servidor não encontrado")

    try:
        if kind == "tek":
            asm_cm = getattr(app, "asm_config_manager", None)
            if asm_cm is None:
                return ApplyActiveEventResult(entry.id, entry.name, False, "ASM indisponível")
            srv = asm_cm.get_server(entry.id)
            if srv is None:
                return ApplyActiveEventResult(entry.id, entry.name, False, "perfil TEK ausente")
            srv.active_event = event_id
            asm_cm.update_server(srv)
            if srv.install_dir:
                from ..asm_engine.asm_ini_manager import mirror_ini_to_user_config_folder, write_ini

                write_ini(srv)
                mirror_ini_to_user_config_folder(srv)
            asm_cm.save()
            _sync_open_panel_active_event(app, entry.id, event_id)
            label = _ARK_EVENT_ID_TO_LABEL.get(event_id, event_id) or "(nenhum)"
            return ApplyActiveEventResult(
                entry.id, entry.name, True, f"ActiveEvent → {label or 'removido'}",
            )

        srv = app.config_manager.get_server(entry.id)
        if srv is None:
            return ApplyActiveEventResult(entry.id, entry.name, False, "perfil legado ausente")
        srv.active_event = event_id
        app.config_manager.update_server(srv)
        sm = getattr(app, "server_manager", None)
        if sm is not None:
            sm.update_server_config(srv)
        if srv.install_dir:
            from ..ark_ini import ArkIniManager

            ArkIniManager(srv.install_dir).save_game_user_settings(srv)
        app.config_manager.save()
        _sync_open_panel_active_event(app, entry.id, event_id)
        label = _ARK_EVENT_ID_TO_LABEL.get(event_id, event_id) or "(nenhum)"
        return ApplyActiveEventResult(
            entry.id, entry.name, True, f"ActiveEvent → {label or 'removido'}",
        )
    except Exception as exc:
        _log.warning("apply_active_event %s: %s", entry.id, exc)
        return ApplyActiveEventResult(entry.id, entry.name, False, str(exc))


def apply_active_event_to_servers(
    app: Any,
    server_ids: list[str],
    event_id: str,
) -> list[ApplyActiveEventResult]:
    by_id = {e.id: e for e in list_buff_servers(app)}
    results: list[ApplyActiveEventResult] = []
    for sid in server_ids:
        entry = by_id.get(sid)
        if entry is None:
            results.append(ApplyActiveEventResult(sid, sid, False, "servidor não encontrado"))
            continue
        results.append(apply_active_event_to_server(app, entry, event_id))
    return results


def restart_server_after_active_event(app: Any, server_id: str) -> None:
    kind = buff_server_kind(app, server_id)
    if kind == "tek":
        asm_cm = getattr(app, "asm_config_manager", None)
        srv = asm_cm.get_server(server_id) if asm_cm else None
        if srv is not None and hasattr(app, "_asm_restart_server"):
            app._asm_restart_server(srv)
        return
    if hasattr(app, "server_manager"):
        app.server_manager.restart_server(server_id)


def _selected_server_ids(app: Any) -> list[str]:
    vars_map: dict[str, tk.BooleanVar] = getattr(app, "_global_event_server_vars", {}) or {}
    return [sid for sid, var in vars_map.items() if var.get()]


def _set_all_server_checks(app: Any, value: bool) -> None:
    for var in (getattr(app, "_global_event_server_vars", {}) or {}).values():
        var.set(value)


def refresh_global_event_server_checks(app: Any) -> None:
    """Reconstrói checkboxes de servidores (lista TEK + legado)."""
    host = getattr(app, "_global_event_servers_host", None)
    if host is None:
        return

    for w in host.winfo_children():
        w.destroy()

    entries = list_buff_servers(app)
    app._global_event_server_vars = {}

    if not entries:
        ctk.CTkLabel(
            host, text="Nenhum servidor cadastrado.",
            text_color="gray50", font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=4, pady=4)
        return

    cols = 2
    grid = ctk.CTkFrame(host, fg_color="transparent")
    grid.pack(fill="x", expand=True)
    for col in range(cols):
        grid.grid_columnconfigure(col, weight=1)

    for i, entry in enumerate(entries):
        var = tk.BooleanVar(value=True)
        app._global_event_server_vars[entry.id] = var
        ctk.CTkCheckBox(
            grid,
            text=entry.label,
            variable=var,
            font=ctk.CTkFont(size=11),
            checkbox_width=18,
            checkbox_height=18,
        ).grid(row=i // cols, column=i % cols, padx=8, pady=3, sticky="w")


def _on_apply_active_event(app: Any, *, restart: bool) -> None:
    event_id = event_id_from_combo_label(
        getattr(app, "_global_active_event_var", tk.StringVar()).get()
    )
    server_ids = _selected_server_ids(app)
    if not server_ids:
        messagebox.showwarning("Eventos Globais", "Selecione ao menos um servidor.", parent=app)
        return

    if not messagebox.askyesno(
        "Eventos Globais",
        f"Aplicar evento ARK em {len(server_ids)} servidor(es)?\n\n"
        f"Valor: {_ARK_EVENT_ID_TO_LABEL.get(event_id, event_id) or '(nenhum — remove ActiveEvent)'}\n\n"
        + ("Os servidores selecionados serão reiniciados." if restart else "Reinicie os servidores para o efeito no jogo."),
        parent=app,
    ):
        return

    results = apply_active_event_to_servers(app, server_ids, event_id)
    ok_ids = [r.server_id for r in results if r.ok]
    failed = [r for r in results if not r.ok]

    if restart and ok_ids:
        for sid in ok_ids:
            restart_server_after_active_event(app, sid)

    lines = [f"{'✓' if r.ok else '✗'} {r.server_name}: {r.message}" for r in results]
    summary = "\n".join(lines[:20])
    if len(lines) > 20:
        summary += f"\n… e mais {len(lines) - 20}"

    if failed:
        messagebox.showwarning(
            "Eventos Globais — concluído com avisos",
            summary,
            parent=app,
        )
    else:
        extra = "\n\nReinício enfileirado." if restart else "\n\nReinicie os servidores para aplicar no jogo."
        messagebox.showinfo("Eventos Globais", summary + extra, parent=app)

    if hasattr(app, "_asm_refresh_dashboard"):
        app._asm_refresh_dashboard()


def _on_schedule_active_event(app: Any) -> None:
    scheduler = getattr(app, "_global_ark_event_scheduler", None)
    if scheduler is None:
        messagebox.showerror(
            "Eventos Globais",
            "Scheduler não inicializado. Reinicie o aplicativo.",
            parent=app,
        )
        return

    event_id = event_id_from_combo_label(
        getattr(app, "_global_active_event_var", tk.StringVar()).get()
    )
    if not event_id:
        messagebox.showwarning(
            "Eventos Globais",
            "Selecione um evento (não use “nenhum evento” para agendar).",
            parent=app,
        )
        return

    server_ids = _selected_server_ids(app)
    if not server_ids:
        messagebox.showwarning("Eventos Globais", "Selecione ao menos um servidor.", parent=app)
        return

    raw_dt = getattr(app, "_global_active_event_datetime_var", tk.StringVar()).get().strip()
    try:
        when = parse_brasilia_datetime(raw_dt)
    except ValueError as exc:
        messagebox.showerror("Eventos Globais", str(exc), parent=app)
        return

    label = _ARK_EVENT_ID_TO_LABEL.get(event_id, event_id)
    if not messagebox.askyesno(
        "Eventos Globais",
        f"Agendar evento em {len(server_ids)} servidor(es)?\n\n"
        f"Evento: {label}\n"
        f"Início: {format_brasilia_datetime(when)}\n\n"
        "O app avisará via broadcast 10, 5, 3, 2 e 1 min antes, "
        "reiniciará os mapas na hora e notificará a cada 10 min por 1 h.",
        parent=app,
    ):
        return

    _ev, err = scheduler.schedule_event(event_id, when, server_ids)
    if err:
        messagebox.showerror("Eventos Globais", err, parent=app)
        return
    messagebox.showinfo("Eventos Globais", "Evento agendado com sucesso.", parent=app)
    refresh_scheduled_ark_events_list(app)


def refresh_scheduled_ark_events_list(app: Any) -> None:
    host = getattr(app, "_global_ark_scheduled_host", None)
    if host is None:
        return

    for w in host.winfo_children():
        w.destroy()

    scheduler = getattr(app, "_global_ark_event_scheduler", None)
    events = scheduler.list_events() if scheduler else []
    pending = [e for e in events if e.status in (
        ARK_EVENT_STATUS_SCHEDULED, "applying", "notifying",
    )]
    recent = [e for e in reversed(events) if e.status in ("completed", "failed", "cancelled")][:5]

    if not pending and not recent:
        ctk.CTkLabel(
            host, text="Nenhum evento agendado.",
            text_color="gray50", font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=4, pady=4)
        return

    for ev in pending:
        row = ctk.CTkFrame(host, fg_color="#1a1f2e", corner_radius=8)
        row.pack(fill="x", pady=3, padx=2)
        when_str = format_brasilia_datetime(ev.scheduled_datetime())
        status_pt = {
            ARK_EVENT_STATUS_SCHEDULED: "agendado",
            "applying": "aplicando…",
            "notifying": "ativo (avisos)",
        }.get(ev.status, ev.status)
        ctk.CTkLabel(
            row,
            text=f"{ev.display_event()} — {when_str} — {len(ev.server_ids)} mapa(s) — {status_pt}",
            font=ctk.CTkFont(size=11),
            anchor="w",
        ).pack(side="left", padx=12, pady=8)

        if ev.status == ARK_EVENT_STATUS_SCHEDULED:
            ctk.CTkButton(
                row, text="Cancelar", width=80, height=28,
                fg_color="#7f1d1d", hover_color="#991b1b",
                command=lambda eid=ev.id: _cancel_scheduled_event(app, eid),
            ).pack(side="right", padx=8, pady=6)

    if recent:
        ctk.CTkLabel(
            host, text="Recentes",
            text_color="gray55", font=ctk.CTkFont(size=10, weight="bold"),
        ).pack(anchor="w", padx=4, pady=(8, 2))
        for ev in recent:
            when_str = format_brasilia_datetime(ev.scheduled_datetime())
            extra = f" — {ev.error_message}" if ev.error_message else ""
            ctk.CTkLabel(
                host,
                text=f"{ev.display_event()} — {when_str} — {ev.status}{extra}",
                text_color="gray50", font=ctk.CTkFont(size=10),
                anchor="w",
            ).pack(anchor="w", padx=8, pady=1)


def _cancel_scheduled_event(app: Any, event_id: str) -> None:
    scheduler = getattr(app, "_global_ark_event_scheduler", None)
    if not scheduler:
        return
    err = scheduler.cancel_event(event_id)
    if err:
        messagebox.showwarning("Eventos Globais", err, parent=app)
    else:
        refresh_scheduled_ark_events_list(app)


def build_global_active_event_section(app: "ARKServerManagerApp", parent) -> None:
    """Card ActiveEvent (aba «Evento ARK oficial» em Eventos Globais)."""
    card = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=10)
    card.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 8))
    card.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        card,
        text="Evento ARK oficial (dinos coloridos)",
        font=ctk.CTkFont(size=14, weight="bold"),
        text_color="#88d4a0",
    ).grid(row=0, column=0, columnspan=3, padx=16, pady=(14, 2), sticky="w")

    ctk.CTkLabel(
        card,
        text=(
            "Define -ActiveEvent= na linha de comando ASE (Páscoa, Halloween…). "
            "Agende data/hora para avisos RCON, restart automático e 1 h de broadcasts. "
            "Após reiniciar, rode DestroyWildDinos para respawnar dinos coloridos."
        ),
        text_color="gray55",
        font=ctk.CTkFont(size=11),
        wraplength=720,
        justify="left",
    ).grid(row=1, column=0, columnspan=3, padx=16, pady=(0, 10), sticky="w")

    ctk.CTkLabel(
        card, text="Evento:", text_color="gray60", font=ctk.CTkFont(size=12),
    ).grid(row=2, column=0, padx=(16, 8), pady=6, sticky="w")

    labels = [label for _, label in _ARK_OFFICIAL_EVENTS]
    app._global_active_event_var = tk.StringVar(value=labels[0])
    ctk.CTkComboBox(
        card,
        variable=app._global_active_event_var,
        values=labels,
        state="readonly",
        width=380,
    ).grid(row=2, column=1, padx=(0, 8), pady=6, sticky="w")

    ctk.CTkLabel(
        card, text="Agendar para:", text_color="gray60", font=ctk.CTkFont(size=12),
    ).grid(row=3, column=0, padx=(16, 8), pady=6, sticky="w")

    dt_default = (now_brasilia().replace(minute=0, second=0, microsecond=0)).strftime("%d/%m/%Y %H:%M")
    app._global_active_event_datetime_var = tk.StringVar(value=dt_default)
    ctk.CTkEntry(
        card,
        textvariable=app._global_active_event_datetime_var,
        width=180,
        placeholder_text="dd/mm/aaaa HH:MM",
    ).grid(row=3, column=1, padx=(0, 8), pady=6, sticky="w")
    ctk.CTkLabel(
        card,
        text="(horário de Brasília)",
        text_color="gray50",
        font=ctk.CTkFont(size=10),
    ).grid(row=3, column=2, padx=(0, 16), pady=6, sticky="w")

    ctk.CTkLabel(
        card, text="Servidores:", text_color="gray60", font=ctk.CTkFont(size=12),
    ).grid(row=4, column=0, padx=(16, 8), pady=(4, 0), sticky="nw")

    servers_outer = ctk.CTkFrame(card, fg_color="transparent")
    servers_outer.grid(row=4, column=1, columnspan=2, padx=(0, 16), pady=(4, 0), sticky="ew")
    servers_outer.grid_columnconfigure(0, weight=1)

    sel_row = ctk.CTkFrame(servers_outer, fg_color="transparent")
    sel_row.pack(fill="x", pady=(0, 4))
    ctk.CTkButton(
        sel_row, text="Marcar todos", width=100, height=28,
        fg_color="transparent", border_width=1, border_color="gray40",
        command=lambda: _set_all_server_checks(app, True),
    ).pack(side="left", padx=(0, 6))
    ctk.CTkButton(
        sel_row, text="Desmarcar", width=100, height=28,
        fg_color="transparent", border_width=1, border_color="gray40",
        command=lambda: _set_all_server_checks(app, False),
    ).pack(side="left")

    scroll = ctk.CTkScrollableFrame(servers_outer, fg_color="#1a1f2e", height=100, corner_radius=8)
    scroll.pack(fill="x", expand=True)
    app._global_event_servers_host = scroll
    refresh_global_event_server_checks(app)

    ctk.CTkLabel(
        card, text="Agendados:", text_color="gray60", font=ctk.CTkFont(size=12),
    ).grid(row=5, column=0, padx=(16, 8), pady=(8, 0), sticky="nw")

    sched_host = ctk.CTkFrame(card, fg_color="transparent")
    sched_host.grid(row=5, column=1, columnspan=2, padx=(0, 16), pady=(8, 0), sticky="ew")
    sched_host.grid_columnconfigure(0, weight=1)
    app._global_ark_scheduled_host = sched_host
    refresh_scheduled_ark_events_list(app)

    btn_row = ctk.CTkFrame(card, fg_color="transparent")
    btn_row.grid(row=6, column=0, columnspan=3, padx=16, pady=(12, 4), sticky="e")
    ctk.CTkButton(
        btn_row, text="Agendar evento", width=140, height=34,
        fg_color="#7c3aed", hover_color="#6d28d9",
        font=ctk.CTkFont(size=12, weight="bold"),
        command=lambda: _on_schedule_active_event(app),
    ).pack(side="left", padx=(0, 8))
    ctk.CTkButton(
        btn_row, text="Aplicar", width=120, height=34,
        fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=lambda: _on_apply_active_event(app, restart=False),
    ).pack(side="left", padx=(0, 8))
    ctk.CTkButton(
        btn_row, text="Aplicar e reiniciar", width=160, height=34,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        font=ctk.CTkFont(size=12, weight="bold"),
        command=lambda: _on_apply_active_event(app, restart=True),
    ).pack(side="left")

    help_f = ctk.CTkFrame(card, fg_color="#1a1f2e", corner_radius=8)
    help_f.grid(row=7, column=0, columnspan=3, padx=16, pady=(0, 14), sticky="ew")
    ctk.CTkLabel(
        help_f,
        text=(
            "Quando usar cada botão:\n"
            "• Agendar evento — escolhe data/hora futura; o TEK avisa no jogo (10/5/3/2/1 min), "
            "reinicia sozinho na hora e notifica por 1 h. Use para Páscoa/Halloween em horário marcado.\n"
            "• Aplicar — grava o evento no perfil/INI agora, sem reiniciar. O efeito só entra no próximo restart "
            "(ex.: restart das 3h ou manual depois).\n"
            "• Aplicar e reiniciar — grava e reinicia na hora os mapas marcados.\n\n"
            "Como verificar: no log do start deve aparecer «ActiveEvent CLI: -ActiveEvent=Easter» "
            "(ou vday, FearEvolved…). Em RunServer.cmd do mapa, procure -ActiveEvent= (com hífen). "
            "Depois do restart, DestroyWildDinos para skins novas."
        ),
        text_color="gray55",
        font=ctk.CTkFont(size=10),
        justify="left",
        anchor="w",
        wraplength=700,
    ).pack(padx=12, pady=10, anchor="w")
