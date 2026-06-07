"""
global_crash_monitor.py — Página global de monitoramento de crashes.

Mostra todos os crashes de todos os servidores em tempo real,
com filtro por servidor, badge de não-lido e detalhes expandíveis.
"""
import threading
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING, Any

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..crash_store import CrashEvent, CrashStore
from ..ui_constants import get_theme, _RED_DARK, _RED_HOVER

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def _build_event_card_body(card, evt: "CrashEvent") -> int:
    """Renderiza diagnóstico e call stack do card de evento. Retorna o próximo row."""
    body_row = 1
    if evt.diagnosis:
        diag_f = ctk.CTkFrame(card, fg_color="#1a2a1a", corner_radius=4)
        diag_f.grid(row=body_row, column=0, padx=8, pady=(6, 0), sticky="ew")
        diag_f.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(diag_f, text="🔍", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(8, 4), pady=6)
        ctk.CTkLabel(diag_f, text=evt.diagnosis, font=ctk.CTkFont(size=11), text_color="#80d080",
                     anchor="w", wraplength=700).grid(row=0, column=1, padx=(0, 8), pady=6, sticky="w")
        body_row += 1
    if evt.log_tail:
        ctk.CTkLabel(card, text="Call stack / log:", text_color="gray55",
                     font=ctk.CTkFont(size=10), anchor="w").grid(
            row=body_row, column=0, padx=(12, 0), pady=(6, 0), sticky="w")
        body_row += 1
        stk = ctk.CTkTextbox(card, height=min(110, max(48, len(evt.log_tail) * 15)),
                             font=ctk.CTkFont(family="Consolas", size=10),
                             fg_color="#12121e", text_color="#a0a0c0")
        for line in evt.log_tail: stk.insert("end", line + "\n")
        stk.configure(state="disabled")
        stk.grid(row=body_row, column=0, padx=8, pady=(0, 0), sticky="ew")
        body_row += 1
    return body_row


def _render_crash_event_card(frame, idx: int, evt: "CrashEvent", accent: str, on_refresh) -> None:
    """Renderiza um card de evento de crash no monitor global."""
    culprit     = evt.culprit
    has_culprit = bool(culprit)
    is_unseen   = not evt.seen
    kind_label  = {"crash": "💥 Crash", "launch_fail": "🚫 Falha ao Iniciar"}.get(evt.kind, f"💥 {evt.kind}")
    card = ctk.CTkFrame(frame, corner_radius=8,
                        fg_color="#2a1a1a" if has_culprit else "#1a2a1a" if is_unseen else "#1e1e2e",
                        border_width=1,
                        border_color="#5a2020" if has_culprit else "#2a4a2a" if is_unseen else "#3a3a55")
    card.grid(row=idx, column=0, padx=4, pady=(0, 8), sticky="ew")
    card.grid_columnconfigure(0, weight=1)
    hdr = ctk.CTkFrame(card, fg_color="#3a1515" if has_culprit else "#1e3020" if is_unseen else "#252535",
                       corner_radius=6)
    hdr.grid(row=0, column=0, padx=6, pady=(6, 0), sticky="ew")
    hdr.grid_columnconfigure(2, weight=1)
    ctk.CTkLabel(hdr, text=kind_label, font=ctk.CTkFont(size=11, weight="bold"),
                 text_color="#ffaa44").grid(row=0, column=0, padx=(10, 8), pady=6)
    ctk.CTkLabel(hdr, text=evt.server_name, font=ctk.CTkFont(size=11, weight="bold"),
                 text_color=accent).grid(row=0, column=1, padx=(0, 10), pady=6)
    ctk.CTkLabel(hdr, text=evt.ts_display(), font=ctk.CTkFont(size=12),
                 text_color="#e08080" if has_culprit else "#c0e0c0" if is_unseen else "#d0d0e0",
                 anchor="w").grid(row=0, column=2, pady=6, sticky="w")
    if is_unseen:
        ctk.CTkLabel(hdr, text="● NOVO", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#ff6666").grid(row=0, column=3, padx=(0, 8), pady=6)
    if culprit:
        ctk.CTkLabel(hdr, text=f"⚠ {culprit}", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#ffaa44").grid(row=0, column=4, padx=(0, 10), pady=6)
    body_row = _build_event_card_body(card, evt)
    act = ctk.CTkFrame(card, fg_color="transparent")
    act.grid(row=body_row, column=0, padx=8, pady=(4, 8), sticky="w")
    if is_unseen:
        eid = evt.event_id
        ctk.CTkButton(act, text="✓ Marcar visto", height=24, width=110,
                      fg_color="#2a4a2a", hover_color="#1a3a1a", font=ctk.CTkFont(size=10),
                      command=lambda e=eid: (CrashStore.instance().mark_seen(e), on_refresh()),
                      ).pack(side="left", padx=(0, 6))
    eid2 = evt.event_id
    ctk.CTkButton(act, text="🗑 Remover", height=24, width=90,
                  fg_color=_RED_DARK, hover_color=_RED_HOVER, font=ctk.CTkFont(size=10),
                  command=lambda e=eid2: (CrashStore.instance().delete(e), on_refresh()),
                  ).pack(side="left")


def _repopulate_monitor_buttons(btn_bar, events: list, unseen: int, refresh_cb, clear_cb) -> None:
    """Reconstrói os botões de ação no cabeçalho do monitor de crashes."""
    for w in btn_bar.winfo_children():
        w.destroy()
    ctk.CTkButton(
        btn_bar, text="🔄 Atualizar", height=28, width=100,
        fg_color="#3a3a5a", hover_color="#252540",
        font=ctk.CTkFont(size=11), command=refresh_cb,
    ).pack(side="left", padx=(0, 6))
    if unseen:
        ctk.CTkButton(
            btn_bar, text="✓ Marcar todos vistos", height=28, width=150,
            fg_color="#2a4a2a", hover_color="#1a3a1a", font=ctk.CTkFont(size=11),
            command=lambda: (CrashStore.instance().mark_all_seen(), refresh_cb()),
        ).pack(side="left", padx=(0, 6))
    if events:
        ctk.CTkButton(
            btn_bar, text="🗑 Limpar todos", height=28, width=120,
            fg_color=_RED_DARK, hover_color=_RED_HOVER, font=ctk.CTkFont(size=11),
            command=clear_cb,
        ).pack(side="left")


def build_global_crash_monitor(app: "ARKServerManagerApp", parent: ctk.CTkFrame) -> None:  # noqa: C901
    """Constrói a página global de crashes dentro de `parent`."""
    theme   = get_theme("tek")
    bg      = theme["bg"]
    card_bg = theme["card_bg"]
    accent  = theme["accent"]
    sep     = theme["separator"]
    t_sec   = theme["text_secondary"]
    t_mut   = theme["text_muted"]

    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(1, weight=1)

    # ── Header ────────────────────────────────────────────────────────────────
    hdr = ctk.CTkFrame(parent, fg_color=card_bg, corner_radius=0, height=60)
    hdr.grid(row=0, column=0, sticky="ew")
    hdr.grid_propagate(False)
    hdr.grid_columnconfigure(1, weight=1)

    badge_var = tk.StringVar(value="")

    ctk.CTkLabel(
        hdr, text="🔴  Monitor Global de Crashes",
        font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
        text_color="#d08080",
    ).grid(row=0, column=0, padx=20, pady=12, sticky="w")

    badge_lbl = ctk.CTkLabel(
        hdr, textvariable=badge_var,
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        text_color="#ff6666",
    )
    badge_lbl.grid(row=0, column=1, padx=8, sticky="w")

    btn_bar = ctk.CTkFrame(hdr, fg_color="transparent")
    btn_bar.grid(row=0, column=2, padx=12, pady=8, sticky="e")

    # ── Filtro por servidor ───────────────────────────────────────────────────
    filter_frame = ctk.CTkFrame(parent, fg_color=card_bg, corner_radius=0, height=40)
    filter_frame.grid(row=1, column=0, sticky="ew")
    filter_frame.grid_propagate(False)
    filter_frame.grid_columnconfigure(3, weight=1)

    ctk.CTkLabel(
        filter_frame, text="Filtrar:",
        font=ctk.CTkFont(size=11), text_color=t_sec,
    ).grid(row=0, column=0, padx=(16, 4), pady=8, sticky="w")

    _server_filter_var = tk.StringVar(value="Todos")
    server_names: list[str] = ["Todos"]

    def _get_asm_servers() -> list:
        try:
            return list(app.asm_config_manager.servers)
        except Exception:
            return []

    for s in _get_asm_servers():
        if s.name and s.name not in server_names:
            server_names.append(s.name)

    filter_combo = ctk.CTkOptionMenu(
        filter_frame, variable=_server_filter_var,
        values=server_names, width=180, height=28,
        fg_color=theme.get("accent_muted_bg", "#1a1a2e"),
        button_color=accent, button_hover_color=theme["accent_hover"],
        command=lambda _v: _refresh(),
    )
    filter_combo.grid(row=0, column=1, padx=(0, 12), pady=6, sticky="w")

    # ── Scroll area ───────────────────────────────────────────────────────────
    parent.grid_rowconfigure(2, weight=1)
    scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent", corner_radius=0)
    scroll.grid(row=2, column=0, sticky="nsew", padx=8, pady=(4, 8))
    scroll.grid_columnconfigure(0, weight=1)

    # ── Lógica de dados ───────────────────────────────────────────────────────

    def _get_server_id_for_name(name: str) -> str:
        """Retorna server_id correspondente ao nome (ou "" = todos)."""
        if name == "Todos":
            return ""
        for s in _get_asm_servers():
            if s.name == name:
                return s.id
        return ""

    def _bootstrap_from_files() -> None:
        """Popula CrashStore com crashes históricos de arquivo (roda em background)."""
        from ..server_manager import _list_crash_records
        import uuid as _uuid
        for srv in _get_asm_servers():
            if not srv.install_dir:
                continue
            try:
                recs = _list_crash_records(
                    srv.install_dir,
                    alt_save_dir=getattr(srv, "alt_save_directory_name", "") or "",
                )
                for rec in recs[:50]:
                    evt = CrashEvent(
                        event_id=str(_uuid.uuid4()),
                        server_id=srv.id,
                        server_name=srv.name or srv.id,
                        kind="crash",
                        timestamp=rec["timestamp"].isoformat(),
                        exit_code=None,
                        log_tail=rec.get("call_stack") or rec.get("log_lines", []),
                        culprit=rec.get("culprit", ""),
                        diagnosis=rec.get("diagnosis", ""),
                        seen=True,
                    )
                    CrashStore.instance().add(evt)
            except Exception:
                pass
        try:
            if parent.winfo_exists():
                parent.after(0, _refresh)
        except Exception:
            pass

    def _get_display_events() -> list[CrashEvent]:
        filter_val = _server_filter_var.get()
        sid = _get_server_id_for_name(filter_val)
        if sid:
            return CrashStore.instance().list_for_server(sid)
        return CrashStore.instance().list_all()

    def _refresh() -> None:
        for w in scroll.winfo_children():
            w.destroy()
        events = _get_display_events()
        unseen = sum(1 for e in events if not e.seen)
        badge_var.set(f"● {unseen} não visto(s)" if unseen else "")
        _repopulate_monitor_buttons(btn_bar, events, unseen, _refresh, _clear_all)
        if not events:
            ctk.CTkLabel(
                scroll,
                text="✅  Nenhum crash registrado.\n\n"
                     "Os crashes de todos os servidores aparecerão aqui em tempo real\n"
                     "quando ocorrerem durante a sessão.\n\n"
                     "Use o painel de cada servidor para ver crashes históricos de arquivo.",
                text_color="gray55",
                font=ctk.CTkFont(size=12),
                justify="left",
            ).grid(row=0, column=0, pady=40, padx=24, sticky="w")
            return

        scroll.unbind("<Configure>")
        for idx, evt in enumerate(events):
            _render_crash_event_card(scroll, idx, evt, accent, _refresh)
        try:
            c = scroll._parent_canvas
            c.configure(scrollregion=c.bbox("all"))
            scroll.bind("<Configure>", lambda _e, c=c: c.configure(scrollregion=c.bbox("all")))
        except Exception:
            pass

    def _clear_all() -> None:
        filter_val = _server_filter_var.get()
        sid = _get_server_id_for_name(filter_val)
        label = filter_val if filter_val != "Todos" else "todos os servidores"
        if not messagebox.askyesno(
            "Limpar crashes",
            f"Apagar todos os eventos de crash de {label} do histórico?\n"
            "(Os arquivos físicos não serão removidos.)",
            parent=app,
        ):
            return
        if sid:
            CrashStore.instance().delete_for_server(sid)
        else:
            CrashStore.instance().clear_all()
        _refresh()

    # ── Callback em tempo real ─────────────────────────────────────────────────
    def _on_new_crash(evt: CrashEvent) -> None:
        try:
            if parent.winfo_exists():
                parent.after(0, _refresh)
        except Exception:
            pass

    CrashStore.instance().register_callback(_on_new_crash)

    # Bootstrapa crashes históricos de arquivo em background
    threading.Thread(target=_bootstrap_from_files, daemon=True).start()

    # Build inicial (eventos já no store)
    _refresh()
