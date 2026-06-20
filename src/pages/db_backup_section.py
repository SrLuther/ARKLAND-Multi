"""Seção de backup automático no painel Banco de Dados."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Callable

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..db_backup_manager import DbBackupManager

if TYPE_CHECKING:
    from ..app_tek import ARKTEKApp


def build_db_backup_section(
    app: "ARKTEKApp",
    parent: ctk.CTkFrame,
    *,
    theme: dict,
    get_connection: Callable[[], dict],
    grid_row: int,
    bare: bool = False,
) -> None:
    """Painel de backup/restore do MariaDB com retenção e compactação."""
    card_bg = theme["card_bg"]
    accent = theme["accent"]
    t_sec = theme["text_secondary"]
    t_mut = theme["text_muted"]
    sep_col = theme["separator"]

    cfg = app.config_manager.config.db_backup
    if not hasattr(app, "_db_backup_manager"):
        app._db_backup_manager = DbBackupManager(on_log=app._global_log)

    if bare:
        card = parent
        card.grid(row=grid_row, column=0, sticky="ew")
        content_row = 0
    else:
        card = ctk.CTkFrame(parent, fg_color=card_bg, corner_radius=8)
        card.grid(row=grid_row, column=0, sticky="ew", padx=12, pady=(0, 8))

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            hdr, text="💾  Backup Automático do Banco",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=accent,
        ).grid(row=0, column=0, sticky="w")
        content_row = 1

    card.grid_columnconfigure(0, weight=1)

    opts = ctk.CTkFrame(card, fg_color="transparent")
    opts.grid(row=content_row, column=0, sticky="ew", padx=14 if not bare else 8, pady=(0, 6))
    opts.grid_columnconfigure(1, weight=1)

    app._db_bk_enabled_var = tk.BooleanVar(value=cfg.enabled)
    app._db_bk_dir_var = tk.StringVar(value=cfg.backup_dir)
    app._db_bk_interval_var = tk.StringVar(value=str(cfg.interval_hours))
    app._db_bk_limit_var = tk.BooleanVar(value=cfg.limit_backup_count)
    app._db_bk_max_var = tk.StringVar(value=str(cfg.max_backup_count))
    app._db_bk_shop_var = tk.BooleanVar(value=cfg.include_arkshop)
    app._db_bk_perm_var = tk.BooleanVar(value=cfg.include_permissions)

    ctk.CTkCheckBox(
        opts, text="Ativar backup automático",
        variable=app._db_bk_enabled_var,
        font=ctk.CTkFont(size=11), text_color=t_sec,
        fg_color=accent, command=lambda: _save_db_backup_cfg(app),
    ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

    ctk.CTkLabel(opts, text="Pasta de destino:", text_color=t_mut,
                 font=ctk.CTkFont(size=11)).grid(row=1, column=0, sticky="w", padx=(0, 8))
    dir_row = ctk.CTkFrame(opts, fg_color="transparent")
    dir_row.grid(row=1, column=1, columnspan=2, sticky="ew")
    dir_row.grid_columnconfigure(0, weight=1)
    ctk.CTkEntry(
        dir_row, textvariable=app._db_bk_dir_var, height=28,
        placeholder_text="Padrão: %APPDATA%\\ARKLAND-ServerManager\\backups\\database",
        font=ctk.CTkFont(size=11),
    ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
    ctk.CTkButton(
        dir_row, text="📁", width=32, height=28,
        command=lambda: _browse(app, app._db_bk_dir_var),
    ).grid(row=0, column=1)

    ctk.CTkLabel(opts, text="Intervalo (horas):", text_color=t_mut,
                 font=ctk.CTkFont(size=11)).grid(row=2, column=0, sticky="w", pady=(6, 0))
    ctk.CTkEntry(
        opts, textvariable=app._db_bk_interval_var, width=70, height=28,
        font=ctk.CTkFont(size=11),
    ).grid(row=2, column=1, sticky="w", pady=(6, 0))

    ctk.CTkCheckBox(
        opts, text="Manter apenas os",
        variable=app._db_bk_limit_var,
        font=ctk.CTkFont(size=11), text_color=t_sec,
        fg_color=accent, command=lambda: _save_db_backup_cfg(app),
    ).grid(row=3, column=0, sticky="w", pady=(8, 0))
    keep_row = ctk.CTkFrame(opts, fg_color="transparent")
    keep_row.grid(row=3, column=1, columnspan=2, sticky="w", pady=(8, 0))
    ctk.CTkEntry(keep_row, textvariable=app._db_bk_max_var, width=50, height=28).pack(side="left")
    ctk.CTkLabel(keep_row, text=" backups mais recentes (ZIP compactado)",
                 text_color=t_mut, font=ctk.CTkFont(size=11)).pack(side="left", padx=6)

    db_row = ctk.CTkFrame(opts, fg_color="transparent")
    db_row.grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))
    ctk.CTkLabel(db_row, text="Incluir bancos:", text_color=t_mut,
                 font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 8))
    ctk.CTkCheckBox(
        db_row, text="arkland_shop", variable=app._db_bk_shop_var,
        font=ctk.CTkFont(size=11), text_color=t_sec, fg_color=accent,
        command=lambda: _save_db_backup_cfg(app),
    ).pack(side="left", padx=(0, 10))
    ctk.CTkCheckBox(
        db_row, text="ark_permission", variable=app._db_bk_perm_var,
        font=ctk.CTkFont(size=11), text_color=t_sec, fg_color=accent,
        command=lambda: _save_db_backup_cfg(app),
    ).pack(side="left")

    btn_row = ctk.CTkFrame(card, fg_color="transparent")
    btn_row.grid(row=content_row + 1, column=0, sticky="ew", padx=14 if not bare else 8, pady=(4, 6))
    _status_var = tk.StringVar(value="")
    ctk.CTkLabel(btn_row, textvariable=_status_var, text_color=t_mut,
                 font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 12))

    def _set_status(msg: str) -> None:
        parent.after(0, lambda m=msg: _status_var.set(m))

    def _run_backup() -> None:
        _save_db_backup_cfg(app)
        conn = get_connection()
        if not conn.get("host") or not conn.get("user"):
            messagebox.showwarning("Backup", "Configure host e usuário na barra de conexão.", parent=parent)
            return
        _set_status("Backup em andamento...")
        bm: DbBackupManager = app._db_backup_manager

        def _worker():
            path = bm.create_backup(
                app.config_manager.config.db_backup,
                host=conn["host"],
                port=int(conn.get("port") or 3306),
                user=conn["user"],
                password=conn.get("password") or "",
            )
            parent.after(0, lambda: _on_backup_done(path))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_backup_done(path: str | None) -> None:
        if path:
            _set_status(f"Último backup: {path}")
        else:
            _set_status("Backup falhou — veja o log.")
        _reload_list()

    ctk.CTkButton(
        btn_row, text="▶ Backup agora", width=120, height=28,
        fg_color="#14532d", text_color="#86efac",
        font=ctk.CTkFont(size=11), command=_run_backup,
    ).pack(side="left", padx=(0, 6))
    ctk.CTkButton(
        btn_row, text="💾 Salvar config", width=110, height=28,
        fg_color=theme.get("accent_muted_bg", "#164e63"), text_color=accent,
        font=ctk.CTkFont(size=11),
        command=lambda: (_save_db_backup_cfg(app), _set_status("Configuração salva.")),
    ).pack(side="left")

    list_frame = ctk.CTkFrame(card, fg_color="transparent")
    list_frame.grid(row=content_row + 2, column=0, sticky="ew", padx=14 if not bare else 8, pady=(0, 6))
    list_frame.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        list_frame, text="Backups disponíveis",
        font=ctk.CTkFont(size=11, weight="bold"), text_color=t_sec,
    ).grid(row=0, column=0, sticky="w", pady=(0, 4))

    list_box = ctk.CTkScrollableFrame(
        list_frame, height=72, fg_color=theme.get("input_bg", "#1e293b"),
        border_color=sep_col, border_width=1,
    )
    list_box.grid(row=1, column=0, sticky="ew")
    list_box.grid_columnconfigure(0, weight=1)

    def _reload_list() -> None:
        for w in list_box.winfo_children():
            w.destroy()
        entries = app._db_backup_manager.list_backups(app.config_manager.config.db_backup)
        if not entries:
            ctk.CTkLabel(list_box, text="Nenhum backup encontrado.",
                         text_color=t_mut, font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w", padx=8, pady=6)
            return
        for i, entry in enumerate(entries):
            row_f = ctk.CTkFrame(list_box, fg_color="transparent")
            row_f.grid(row=i, column=0, sticky="ew", pady=1)
            row_f.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                row_f, text=entry.label, anchor="w",
                font=ctk.CTkFont(family="Consolas", size=10), text_color=t_sec,
            ).grid(row=0, column=0, sticky="ew", padx=(8, 4))
            ctk.CTkButton(
                row_f, text="Restaurar", width=72, height=24,
                fg_color="#1e3a5f", text_color="#93c5fd",
                font=ctk.CTkFont(size=10),
                command=lambda p=str(entry.path): _confirm_restore(p),
            ).grid(row=0, column=1, padx=2)
            ctk.CTkButton(
                row_f, text="Excluir", width=60, height=24,
                fg_color="#5c1a1a", text_color="#fca5a5",
                font=ctk.CTkFont(size=10),
                command=lambda p=str(entry.path): _confirm_delete(p),
            ).grid(row=0, column=2, padx=(2, 8))

    def _confirm_restore(path: str) -> None:
        if not messagebox.askyesno(
            "Restaurar backup",
            "Isso substituirá os dados atuais dos bancos no dump.\n\nContinuar?",
            parent=parent,
        ):
            return
        conn = get_connection()
        _set_status("Restaurando...")
        bm: DbBackupManager = app._db_backup_manager

        def _worker():
            ok = bm.restore_backup(
                path,
                host=conn["host"],
                port=int(conn.get("port") or 3306),
                user=conn["user"],
                password=conn.get("password") or "",
            )
            parent.after(0, lambda: _set_status("Restauração concluída." if ok else "Restauração falhou."))

        threading.Thread(target=_worker, daemon=True).start()

    def _confirm_delete(path: str) -> None:
        if messagebox.askyesno("Excluir backup", "Remover este arquivo de backup?", parent=parent):
            app._db_backup_manager.delete_backup(path)
            _reload_list()

    _reload_list()


def _browse(app: "ARKTEKApp", var: tk.StringVar) -> None:
    path = filedialog.askdirectory(parent=app)
    if path:
        var.set(path)


def _save_db_backup_cfg(app: "ARKTEKApp") -> None:
    cfg = app.config_manager.config.db_backup
    cfg.enabled = getattr(app, "_db_bk_enabled_var", tk.BooleanVar()).get()
    cfg.backup_dir = getattr(app, "_db_bk_dir_var", tk.StringVar()).get().strip()
    try:
        cfg.interval_hours = max(1, int(getattr(app, "_db_bk_interval_var", tk.StringVar(value="6")).get()))
    except ValueError:
        cfg.interval_hours = 6
    cfg.limit_backup_count = getattr(app, "_db_bk_limit_var", tk.BooleanVar(value=True)).get()
    try:
        cfg.max_backup_count = max(1, int(getattr(app, "_db_bk_max_var", tk.StringVar(value="10")).get()))
    except ValueError:
        cfg.max_backup_count = 10
    cfg.include_arkshop = getattr(app, "_db_bk_shop_var", tk.BooleanVar(value=True)).get()
    cfg.include_permissions = getattr(app, "_db_bk_perm_var", tk.BooleanVar(value=True)).get()
    app.config_manager.save()
