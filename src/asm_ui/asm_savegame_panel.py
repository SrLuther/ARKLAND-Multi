"""Painel global de gerenciamento de saves TEK — inventário nativo em savegame."""
from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_savegame_manager import (
    SaveFileEntry,
    SaveFileKind,
    SaveInventory,
    can_load_save,
    create_manual_backup,
    delete_save_file,
    format_datetime,
    format_size,
    list_server_saves,
    load_save,
)
from ..asm_engine.asm_server_config import (
    ASM_STATUS_CRASHED,
    ASM_STATUS_RUNNING,
    ASM_STATUS_STARTING,
    ASM_STATUS_STOPPED,
    ASM_STATUS_STOPPING,
    ASM_STATUS_UPDATING,
)
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp

_STATUS_DOT = {
    ASM_STATUS_RUNNING: "🟢",
    ASM_STATUS_STARTING: "🟡",
    ASM_STATUS_STOPPING: "🟡",
    ASM_STATUS_STOPPED: "🔴",
    ASM_STATUS_CRASHED: "🔴",
    ASM_STATUS_UPDATING: "🔵",
}

_STATUS_TEXT = {
    ASM_STATUS_RUNNING: "Em execução",
    ASM_STATUS_STARTING: "Iniciando",
    ASM_STATUS_STOPPING: "Parando",
    ASM_STATUS_STOPPED: "Parado",
    ASM_STATUS_CRASHED: "Travado",
    ASM_STATUS_UPDATING: "Atualizando",
}


def build_savegame_panel(app: "ARKServerManagerApp", parent: ctk.CTkFrame) -> None:
    theme = get_theme("tek")
    accent = theme["accent"]
    bg = theme["bg"]
    card_bg = theme["card_bg"]
    sep = theme["separator"]
    t_pri = theme["text_primary"]
    t_sec = theme["text_secondary"]
    t_mut = theme["text_muted"]
    acc_mb = theme["accent_muted_bg"]
    acc_dk = theme["accent_dark"]
    hover_bg = theme["accent_hover"]
    card_bdr = theme.get("card_border", sep)
    is_light = theme.get("_is_light", False)
    ok_bg = "#dcfce7" if is_light else "#052e16"
    ok_hover = "#bbf7d0" if is_light else "#14532d"
    ok_tc = "#166534" if is_light else "#4ade80"
    warn_tc = "#b45309" if is_light else "#fbbf24"
    del_bg = "#fee2e2" if is_light else "#7f1d1d"
    del_hover = "#fecaca" if is_light else "#450a0a"
    del_tc = "#991b1b" if is_light else "#fca5a5"

    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(3, weight=1)

    state: Dict[str, object] = {
        "busy": False,
        "inventories": {},
        "expanded": {},
    }

    # ── Cabeçalho ─────────────────────────────────────────────────────────────
    hdr = ctk.CTkFrame(parent, fg_color="transparent")
    hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 8))
    hdr.grid_columnconfigure(0, weight=1)

    title_col = ctk.CTkFrame(hdr, fg_color="transparent")
    title_col.grid(row=0, column=0, sticky="w")
    ctk.CTkLabel(
        title_col, text="💾  Gerenciamento de Saves",
        font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
        text_color=t_pri,
    ).pack(anchor="w")
    ctk.CTkLabel(
        title_col,
        text="Visualize, carregue, faça backup e exclua saves nativos do ARK em cada servidor.",
        font=ctk.CTkFont(size=12),
        text_color=t_sec,
    ).pack(anchor="w", pady=(4, 0))

    btn_bar = ctk.CTkFrame(hdr, fg_color="transparent")
    btn_bar.grid(row=0, column=1, sticky="e")
    refresh_btn = ctk.CTkButton(
        btn_bar, text="🔄  Atualizar", width=120, height=36,
        fg_color=acc_mb, hover_color=acc_dk,
        text_color=accent, border_width=1, border_color=acc_dk,
    )
    refresh_btn.pack(side="left")

    # ── Ajuda ───────────────────────────────────────────────────────────────────
    help_card = ctk.CTkFrame(parent, fg_color=card_bg, corner_radius=10,
                             border_width=1, border_color=card_bdr)
    help_card.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 8))
    help_card.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        help_card, text="ℹ️  Como funcionam os saves",
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=t_sec,
    ).grid(row=0, column=0, padx=14, pady=(12, 4), sticky="w")

    help_text = (
        "• Save ativo — arquivo principal do mundo (ex.: Alps.ark). É o que o servidor usa ao iniciar.\n"
        "• Backups datados — cópias automáticas ou manuais com data no nome "
        "(ex.: Alps_01.07.2026_01.39.14.ark).\n"
        "• Anti Corruption — backup de emergência (.bak) criado pelo ARK quando detecta "
        "corrupção ao carregar o mundo.\n"
        "• New Launch — backup (.bak) criado pelo ARK ao iniciar com wipe controlado "
        "(novo lançamento / NewLaunch).\n\n"
        "⚠ Para carregar um backup como save ativo, o servidor deve estar parado ou travado. "
        "O app não para o servidor automaticamente."
    )
    ctk.CTkLabel(
        help_card, text=help_text, justify="left", anchor="w",
        font=ctk.CTkFont(size=11), text_color=t_mut, wraplength=900,
    ).grid(row=1, column=0, padx=14, pady=(0, 12), sticky="w")

    status_lbl = ctk.CTkLabel(
        parent, text="", font=ctk.CTkFont(size=11), text_color=t_mut,
    )
    status_lbl.grid(row=2, column=0, sticky="w", padx=22, pady=(0, 4))

    # ── Lista de servidores ─────────────────────────────────────────────────────
    list_scroll = ctk.CTkScrollableFrame(
        parent, fg_color="transparent",
        scrollbar_button_color=sep,
        scrollbar_button_hover_color=accent,
    )
    list_scroll.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 4))
    list_scroll.grid_columnconfigure(0, weight=1)

    log_box = ctk.CTkTextbox(
        parent, state="disabled", height=100,
        font=ctk.CTkFont(family="Consolas", size=11),
        fg_color="#04090f" if not is_light else "#f8fafc",
        text_color="#d1fae5" if not is_light else "#14532d",
        border_width=1, border_color=sep, corner_radius=6, wrap="word",
    )
    log_box.grid(row=4, column=0, sticky="ew", padx=20, pady=(4, 16))

    def _log(msg: str, color: Optional[str] = None) -> None:
        log_box.configure(state="normal")
        if color:
            log_box.insert("end", msg + "\n")
        else:
            log_box.insert("end", msg + "\n")
        log_box.see("end")
        log_box.configure(state="disabled")

    def _set_busy(busy: bool) -> None:
        state["busy"] = busy
        refresh_btn.configure(state="disabled" if busy else "normal")

    def _confirm(
        title: str,
        message: str,
        warning: str,
        on_ok: Callable[[], None],
        ok_label: str = "Confirmar",
    ) -> None:
        win = ctk.CTkToplevel(parent)
        win.title(title)
        win.geometry("500x200")
        win.configure(fg_color=card_bg)
        win.grab_set()
        win.transient(parent.winfo_toplevel())

        ctk.CTkLabel(
            win, text=message,
            font=ctk.CTkFont(size=13), text_color=t_sec, justify="center",
        ).pack(pady=(24, 6), padx=16)
        ctk.CTkLabel(
            win, text=warning,
            font=ctk.CTkFont(size=11), text_color=warn_tc, justify="center",
        ).pack(pady=(0, 16), padx=16)

        row = ctk.CTkFrame(win, fg_color="transparent")
        row.pack()
        ctk.CTkButton(
            row, text="Cancelar", width=100,
            fg_color=acc_mb, hover_color=acc_dk, text_color=accent,
            command=win.destroy,
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            row, text=ok_label, width=110,
            fg_color="#1e3a5f", hover_color="#2563eb", text_color="#7dd3fc",
            command=lambda: (win.destroy(), on_ok()),
        ).pack(side="left", padx=8)

    def _run_worker(worker: Callable[[], None], done: Callable[[], None]) -> None:
        if state["busy"]:
            return
        _set_busy(True)

        def _thread() -> None:
            try:
                worker()
            finally:
                parent.after(0, done)

        threading.Thread(target=_thread, daemon=True).start()

    def _render_file_row(
        srv_id: str,
        entry: SaveFileEntry,
        row_idx: int,
        files_frame: ctk.CTkFrame,
        can_load: bool,
        load_reason: str,
    ) -> None:
        row_bg = card_bg if row_idx % 2 == 0 else (hover_bg if not is_light else "#f1f5f9")
        row = ctk.CTkFrame(files_frame, fg_color=row_bg, corner_radius=4, height=38)
        row.grid(row=row_idx, column=0, sticky="ew", pady=1)
        row.grid_propagate(False)
        row.grid_columnconfigure(1, weight=1)

        kind_colors = {
            SaveFileKind.ACTIVE: accent,
            SaveFileKind.DATED_BACKUP: t_sec,
            SaveFileKind.ANTI_CORRUPTION: warn_tc,
            SaveFileKind.NEW_LAUNCH: "#38bdf8",
            SaveFileKind.OTHER: t_mut,
        }
        ctk.CTkLabel(
            row, text=entry.kind_label, width=120, anchor="w",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=kind_colors.get(entry.kind, t_sec),
        ).grid(row=0, column=0, padx=(8, 4), pady=6, sticky="w")

        ctk.CTkLabel(
            row, text=entry.name, anchor="w",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=t_sec,
        ).grid(row=0, column=1, padx=4, pady=6, sticky="ew")

        ctk.CTkLabel(
            row, text=format_datetime(entry.display_date), width=130, anchor="w",
            font=ctk.CTkFont(size=10), text_color=t_mut,
        ).grid(row=0, column=2, padx=4, pady=6, sticky="w")

        ctk.CTkLabel(
            row, text=format_size(entry.size_bytes), width=72, anchor="e",
            font=ctk.CTkFont(size=10), text_color=t_mut,
        ).grid(row=0, column=3, padx=4, pady=6, sticky="e")

        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.grid(row=0, column=4, padx=(4, 8), pady=4, sticky="e")

        if entry.kind != SaveFileKind.ACTIVE:
            load_enabled = can_load
            load_btn = ctk.CTkButton(
                actions, text="↩ Carregar", width=88, height=26,
                fg_color="#1e3a5f" if load_enabled else sep,
                hover_color="#2563eb" if load_enabled else sep,
                text_color="#7dd3fc" if load_enabled else t_mut,
                font=ctk.CTkFont(size=10),
                state="normal" if load_enabled else "disabled",
                command=lambda e=entry, sid=srv_id: _ask_load(sid, e),
            )
            load_btn.pack(side="left", padx=(0, 4))
            if not load_enabled and load_reason:
                _bind_tooltip(load_btn, load_reason)

            ctk.CTkButton(
                actions, text="🗑", width=30, height=26,
                fg_color=del_bg, hover_color=del_hover, text_color=del_tc,
                font=ctk.CTkFont(size=10),
                command=lambda e=entry, sid=srv_id: _ask_delete(sid, e),
            ).pack(side="left")

    def _bind_tooltip(widget: ctk.CTkBaseClass, text: str) -> None:
        tip: Dict[str, Optional[tk.Toplevel]] = {"win": None}

        def _show(_event=None) -> None:
            if tip["win"]:
                return
            tw = tk.Toplevel(widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{widget.winfo_rootx() + 10}+{widget.winfo_rooty() + 28}")
            lbl = tk.Label(
                tw, text=text, justify="left",
                background="#1e293b", foreground="#e2e8f0",
                relief="solid", borderwidth=1,
                font=("Segoe UI", 9), padx=8, pady=4, wraplength=320,
            )
            lbl.pack()
            tip["win"] = tw

        def _hide(_event=None) -> None:
            if tip["win"]:
                tip["win"].destroy()
                tip["win"] = None

        widget.bind("<Enter>", _show)
        widget.bind("<Leave>", _hide)

    def _ask_load(srv_id: str, entry: SaveFileEntry) -> None:
        srv = app.asm_config_manager.get_server(srv_id)
        if not srv:
            return
        ok, reason = can_load_save(app, srv_id)
        if not ok:
            _log(f"✖ Carregar bloqueado ({srv.name}): {reason}")
            return
        _confirm(
            "Carregar save",
            f"Restaurar como save ativo:\n{entry.name}",
            "O save ativo atual será preservado em um backup datado antes da troca.",
            lambda: _do_load(srv_id, entry.path),
            ok_label="Carregar",
        )

    def _do_load(srv_id: str, source: Path) -> None:
        srv = app.asm_config_manager.get_server(srv_id)
        if not srv:
            return
        _log(f"Carregando {source.name} em {srv.name}…")

        def worker() -> None:
            try:
                ok, reason = can_load_save(app, srv_id)
                if not ok:
                    parent.after(0, lambda: _log(f"✖ {reason}"))
                    return
                dest = load_save(srv, source)
                parent.after(0, lambda: _log(
                    f"✔ Save carregado em {srv.name}: {dest.name}", 
                ))
            except Exception as exc:
                parent.after(0, lambda e=exc: _log(f"✖ Erro ao carregar: {e}"))

        _run_worker(worker, lambda: (_set_busy(False), _refresh_all()))

    def _ask_delete(srv_id: str, entry: SaveFileEntry) -> None:
        srv = app.asm_config_manager.get_server(srv_id)
        if not srv:
            return
        _confirm(
            "Excluir arquivo",
            f"Excluir permanentemente:\n{entry.name}",
            "Esta ação não pode ser desfeita.",
            lambda: _do_delete(srv_id, entry.path),
            ok_label="Excluir",
        )

    def _do_delete(srv_id: str, path: Path) -> None:
        srv = app.asm_config_manager.get_server(srv_id)
        if not srv:
            return
        _log(f"Excluindo {path.name} ({srv.name})…")

        def worker() -> None:
            try:
                delete_save_file(path)
                parent.after(0, lambda: _log(f"✔ Arquivo excluído: {path.name}"))
            except Exception as exc:
                parent.after(0, lambda e=exc: _log(f"✖ Erro ao excluir: {e}"))

        _run_worker(worker, lambda: (_set_busy(False), _refresh_all()))

    def _do_manual_backup(srv_id: str) -> None:
        srv = app.asm_config_manager.get_server(srv_id)
        if not srv:
            return
        ok, reason = can_load_save(app, srv_id)
        if not ok:
            _log(f"✖ Backup manual bloqueado ({srv.name}): {reason}")
            return
        _log(f"Criando backup manual de {srv.name}…")

        def worker() -> None:
            try:
                dest = create_manual_backup(srv)
                parent.after(0, lambda: _log(f"✔ Backup criado: {dest.name}"))
            except Exception as exc:
                parent.after(0, lambda e=exc: _log(f"✖ Erro no backup: {e}"))

        _run_worker(worker, lambda: (_set_busy(False), _refresh_all()))

    def _render_server_card(inv: SaveInventory, row_idx: int) -> None:
        srv_id = inv.server_id
        status = app.asm_server_manager.get_status(srv_id)
        dot = _STATUS_DOT.get(status, "⚪")
        status_txt = _STATUS_TEXT.get(status, status)
        can_load, load_reason = can_load_save(app, srv_id)

        expanded_map: Dict[str, bool] = state["expanded"]  # type: ignore[assignment]
        is_exp = expanded_map.get(srv_id, row_idx == 0)

        wrapper = ctk.CTkFrame(list_scroll, fg_color=card_bg, corner_radius=10,
                               border_width=1, border_color=card_bdr)
        wrapper.grid(row=row_idx, column=0, sticky="ew", pady=4, padx=4)
        wrapper.grid_columnconfigure(0, weight=1)

        arrow_var = tk.StringVar(value=("▼ " if is_exp else "▶ ") + inv.server_name)
        header = ctk.CTkFrame(wrapper, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 2))
        header.grid_columnconfigure(1, weight=1)

        def _toggle() -> None:
            expanded_map[srv_id] = not expanded_map.get(srv_id, False)
            _refresh_all()

        ctk.CTkButton(
            header, textvariable=arrow_var, anchor="w",
            fg_color="transparent", hover_color=hover_bg,
            text_color=accent, font=ctk.CTkFont(size=13, weight="bold"),
            height=32, corner_radius=6, command=_toggle,
        ).grid(row=0, column=0, columnspan=2, sticky="ew")

        meta = ctk.CTkFrame(header, fg_color="transparent")
        meta.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 4))
        meta.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(
            meta, text=f"{dot} {status_txt}",
            font=ctk.CTkFont(size=11), text_color=t_sec,
        ).grid(row=0, column=0, padx=(0, 12), sticky="w")

        ctk.CTkLabel(
            meta, text=f"Mapa: {inv.map_basename}  ·  Ativo: {inv.active_filename}",
            font=ctk.CTkFont(size=10), text_color=t_mut,
        ).grid(row=0, column=1, padx=(0, 12), sticky="w")

        ctk.CTkLabel(
            meta, text=str(inv.savegame_dir),
            font=ctk.CTkFont(family="Consolas", size=9), text_color=t_mut,
        ).grid(row=0, column=2, sticky="w")

        backup_btn = ctk.CTkButton(
            meta, text="💾 Backup manual", width=120, height=28,
            fg_color=ok_bg, hover_color=ok_hover, text_color=ok_tc,
            font=ctk.CTkFont(size=10, weight="bold"),
            state="normal" if can_load else "disabled",
            command=lambda sid=srv_id: _do_manual_backup(sid),
        )
        backup_btn.grid(row=0, column=3, padx=(8, 0), sticky="e")
        if not can_load and load_reason:
            _bind_tooltip(backup_btn, load_reason)

        body = ctk.CTkFrame(wrapper, fg_color="transparent")
        if is_exp:
            body.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
            body.grid_columnconfigure(0, weight=1)

            if inv.error and not inv.dir_exists:
                ctk.CTkLabel(
                    body, text=inv.error,
                    font=ctk.CTkFont(size=11), text_color=warn_tc,
                ).grid(row=0, column=0, pady=12, padx=8, sticky="w")
                return

            if not inv.entries:
                ctk.CTkLabel(
                    body, text="Nenhum arquivo .ark ou .bak encontrado nesta pasta.",
                    font=ctk.CTkFont(size=11), text_color=t_mut,
                ).grid(row=0, column=0, pady=12, padx=8, sticky="w")
                return

            tbl_hdr = ctk.CTkFrame(body, fg_color=hover_bg if not is_light else "#e2e8f0",
                                   corner_radius=4, height=28)
            tbl_hdr.grid(row=0, column=0, sticky="ew", pady=(0, 2))
            tbl_hdr.grid_propagate(False)
            for col, (txt, w) in enumerate([
                ("Tipo", 120), ("Arquivo", 0), ("Data", 130), ("Tamanho", 72), ("Ações", 130),
            ]):
                ctk.CTkLabel(
                    tbl_hdr, text=txt, width=w if w else None, anchor="w",
                    font=ctk.CTkFont(size=10, weight="bold"), text_color=t_sec,
                ).grid(row=0, column=col, padx=(8 if col == 0 else 4, 0), pady=4, sticky="w")
                if w == 0:
                    tbl_hdr.grid_columnconfigure(col, weight=1)

            files_frame = ctk.CTkFrame(body, fg_color="transparent")
            files_frame.grid(row=1, column=0, sticky="ew")
            files_frame.grid_columnconfigure(0, weight=1)

            for i, entry in enumerate(inv.entries):
                _render_file_row(srv_id, entry, i, files_frame, can_load, load_reason)

    def _refresh_all() -> None:
        for w in list_scroll.winfo_children():
            w.destroy()

        servers = list(app.asm_config_manager.servers)
        if not servers:
            ctk.CTkLabel(
                list_scroll,
                text="Nenhum servidor cadastrado. Adicione um servidor na barra lateral.",
                font=ctk.CTkFont(size=13), text_color=t_mut,
            ).grid(row=0, column=0, pady=40, padx=12)
            status_lbl.configure(text="0 servidores")
            return

        inventories: List[SaveInventory] = []
        for srv in servers:
            inv = list_server_saves(srv)
            inventories.append(inv)
        state["inventories"] = {inv.server_id: inv for inv in inventories}

        for i, inv in enumerate(inventories):
            _render_server_card(inv, i)

        total_files = sum(len(inv.entries) for inv in inventories)
        status_lbl.configure(
            text=f"{len(servers)} servidor(es) · {total_files} arquivo(s) de save",
        )

    def _refresh_async() -> None:
        if state["busy"]:
            return
        _set_busy(True)
        status_lbl.configure(text="Atualizando lista…")

        def worker() -> None:
            servers = list(app.asm_config_manager.servers)
            invs = [list_server_saves(s) for s in servers]
            parent.after(0, lambda: _on_refresh_done(invs))

        threading.Thread(target=worker, daemon=True).start()

    def _on_refresh_done(invs: List[SaveInventory]) -> None:
        state["inventories"] = {inv.server_id: inv for inv in invs}
        _set_busy(False)
        _refresh_all()

    refresh_btn.configure(command=_refresh_async)
    _refresh_async()
