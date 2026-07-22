"""
asm_save_restore.py — Backup e Restauração de Saves TEK.

Janela para gerenciar backups do mapa ARK (.ark), tribos e perfis de jogadores.
Permite criar backup manual, listar backups e restaurar um estado anterior.

Uso:
    from src.asm_ui.asm_save_restore import open_asm_save_restore
    open_asm_save_restore(app, srv)
"""
from __future__ import annotations

import os
import shutil
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import AsmServerConfig
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp


def _saves_dir(srv: AsmServerConfig) -> Path:
    return Path(srv.install_dir) / "ShooterGame" / "Saved" / "SavedArks"


from ..arkland_environment import default_backups_saves_root


def _backups_root(srv: AsmServerConfig) -> Path:
    return default_backups_saves_root() / srv.id


def _backup_size_str(path: Path) -> str:
    """Retorna tamanho total de uma pasta em string legível (ex: '47.2 MB')."""
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024:
            return f"{total:.1f} {unit}"
        total /= 1024
    return f"{total:.1f} TB"


def _list_backups(srv: AsmServerConfig) -> list[Path]:
    """Retorna lista de pastas de backup, da mais recente para a mais antiga."""
    root = _backups_root(srv)
    if not root.exists():
        return []
    entries = sorted(
        (p for p in root.iterdir() if p.is_dir()),
        reverse=True,
    )
    return entries


# ─────────────────────────────────────────────────────────────────────────────


def open_asm_save_restore(app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
    """Abre (ou foca) a janela de backup/restore para *srv*."""
    win_attr = f"_asm_save_restore_{srv.id}"
    existing: Optional[ctk.CTkToplevel] = getattr(app, win_attr, None)
    if existing and existing.winfo_exists():
        existing.lift()
        existing.focus_force()
        return

    win = _SaveRestoreWindow(app, srv)
    setattr(app, win_attr, win)
    win.protocol("WM_DELETE_WINDOW", lambda: _on_close(app, win_attr, win))
    win.after(100, win.lift)
    win.after(150, win.focus_force)


def _on_close(app: "ARKServerManagerApp", attr: str, win: ctk.CTkToplevel) -> None:
    setattr(app, attr, None)
    win.destroy()


# ─────────────────────────────────────────────────────────────────────────────


class _SaveRestoreWindow(ctk.CTkToplevel):
    """Janela de backup e restauração de saves ARK."""

    def __init__(self, app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
        super().__init__(app)
        th = get_theme("tek")
        bg      = th["bg"]
        card_bg = th["card_bg"]
        accent  = th["accent"]
        sep     = th.get("separator", "#1e293b")
        t_sec   = th.get("text_secondary", "#94a3b8")
        t_mut   = th.get("text_muted", "#475569")

        self._app   = app
        self._srv   = srv
        self._busy  = False

        # ── Janela ───────────────────────────────────────────────────────────
        self.title(f"Backup & Restore — {srv.name}")
        self.geometry("720x540")
        self.minsize(560, 400)
        self.configure(fg_color=bg)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── TopBar ───────────────────────────────────────────────────────────
        top = ctk.CTkFrame(self, fg_color=card_bg, corner_radius=0, height=44)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(1, weight=1)
        top.grid_propagate(False)

        saves_path = str(_saves_dir(srv))
        ctk.CTkLabel(
            top,
            text=f"Saves: {saves_path}",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=t_mut,
        ).grid(row=0, column=0, padx=14, pady=10, sticky="w")

        self._status_lbl = ctk.CTkLabel(
            top, text="",
            font=ctk.CTkFont(size=11), text_color=t_mut,
        )
        self._status_lbl.grid(row=0, column=1, padx=0, pady=10, sticky="e")

        self._btn_backup = ctk.CTkButton(
            top, text="💾  Backup Agora", width=130, height=30,
            fg_color="#14532d", hover_color="#166534",
            text_color=accent,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._do_backup,
        )
        self._btn_backup.grid(row=0, column=2, padx=12, pady=7, sticky="e")

        # ── Corpo ─────────────────────────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=10, pady=8)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        # Cabeçalho da lista
        hdr = ctk.CTkFrame(body, fg_color=card_bg, corner_radius=6, height=30)
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        hdr.grid_propagate(False)
        for col, (txt, w, anchor) in enumerate([
            ("Data / Nome", 320, "w"),
            ("Tamanho", 90, "e"),
            ("Ações", 180, "e"),
        ]):
            ctk.CTkLabel(
                hdr, text=txt, width=w, anchor=anchor,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=t_sec,
            ).grid(row=0, column=col, padx=(10 if col == 0 else 4, 0), pady=4, sticky=anchor)

        # Lista rolável
        self._list_frame = ctk.CTkScrollableFrame(
            body, fg_color="transparent",
            scrollbar_button_color=sep,
            scrollbar_button_hover_color=accent,
        )
        self._list_frame.grid(row=1, column=0, sticky="nsew")
        self._list_frame.grid_columnconfigure(0, weight=1)

        # Log de operações
        self._log = ctk.CTkTextbox(
            self, state="disabled",
            height=110,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#04090f",
            text_color="#d1fae5",
            border_width=1,
            border_color=sep,
            corner_radius=6,
            wrap="word",
        )
        self._log.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))

        self._reload_list()

    # ── Lista de backups ──────────────────────────────────────────────────────

    def _reload_list(self) -> None:
        th = get_theme("tek")
        card_bg = th["card_bg"]
        t_sec   = th.get("text_secondary", "#94a3b8")
        t_mut   = th.get("text_muted", "#475569")
        sep     = th.get("separator", "#1e293b")

        for w in self._list_frame.winfo_children():
            w.destroy()

        backups = _list_backups(self._srv)
        if not backups:
            ctk.CTkLabel(
                self._list_frame,
                text="Nenhum backup encontrado.",
                font=ctk.CTkFont(size=13),
                text_color=t_mut,
            ).grid(row=0, column=0, pady=40)
            return

        for i, bp in enumerate(backups):
            row_bg = card_bg if i % 2 == 0 else "#0a1520"
            row = ctk.CTkFrame(
                self._list_frame,
                fg_color=row_bg,
                corner_radius=4,
                height=40,
            )
            row.grid(row=i, column=0, sticky="ew", pady=1)
            row.grid_propagate(False)
            row.grid_columnconfigure(0, weight=1)

            # Nome
            ctk.CTkLabel(
                row, text=bp.name, anchor="w",
                font=ctk.CTkFont(family="Consolas", size=11),
                text_color=t_sec,
            ).grid(row=0, column=0, padx=(10, 4), pady=8, sticky="w")

            # Tamanho
            try:
                size_str = _backup_size_str(bp)
            except Exception:
                size_str = "—"
            ctk.CTkLabel(
                row, text=size_str, width=90, anchor="e",
                font=ctk.CTkFont(size=11),
                text_color=t_mut,
            ).grid(row=0, column=1, padx=4, pady=8, sticky="e")

            # Ações
            btn_cell = ctk.CTkFrame(row, fg_color="transparent")
            btn_cell.grid(row=0, column=2, padx=(4, 10), pady=6, sticky="e")

            ctk.CTkButton(
                btn_cell, text="↩ Restaurar", width=90, height=28,
                fg_color="#1e3a5f", hover_color="#2563eb",
                text_color="#7dd3fc",
                font=ctk.CTkFont(size=11),
                corner_radius=4,
                command=lambda p=bp: self._confirm_restore(p),
            ).pack(side="left", padx=(0, 4))

            ctk.CTkButton(
                btn_cell, text="🗑", width=32, height=28,
                fg_color="#7f1d1d", hover_color="#991b1b",
                text_color="#fca5a5",
                font=ctk.CTkFont(size=11),
                corner_radius=4,
                command=lambda p=bp: self._confirm_delete(p),
            ).pack(side="left")

    # ── Backup ────────────────────────────────────────────────────────────────

    def _do_backup(self) -> None:
        if self._busy:
            return
        self._set_busy(True)
        threading.Thread(target=self._backup_worker, daemon=True).start()

    def _backup_worker(self) -> None:
        srv = self._srv
        src = _saves_dir(srv)
        ts  = time.strftime("%Y-%m-%d_%H-%M-%S")
        dst = _backups_root(srv) / ts

        self.after(0, lambda: self._log_line(f"Iniciando backup → {dst}"))

        try:
            if not src.exists():
                raise FileNotFoundError(f"Pasta de saves não encontrada: {src}")
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copytree(str(src), str(dst / "SavedArks"), dirs_exist_ok=True)
            size = _backup_size_str(dst)
            self.after(0, lambda s=size, d=dst: self._on_backup_done(d.name, s))
        except Exception as exc:
            self.after(0, lambda e=exc: self._on_error(str(e)))

    def _on_backup_done(self, name: str, size: str) -> None:
        self._log_line(f"✔ Backup concluído: {name}  ({size})", color="#4ade80")
        self._set_busy(False)
        self._reload_list()

    # ── Restaurar ─────────────────────────────────────────────────────────────

    def _confirm_restore(self, backup_path: Path) -> None:
        win = ctk.CTkToplevel(self)
        win.title("Confirmar Restauração")
        win.geometry("460x180")
        win.configure(fg_color=get_theme("tek")["card_bg"])
        win.grab_set()

        ctk.CTkLabel(
            win,
            text=f"Restaurar backup:\n{backup_path.name}",
            font=ctk.CTkFont(size=13),
            text_color=get_theme("tek").get("text_secondary", "#94a3b8"),
            justify="center",
        ).pack(pady=(28, 6))
        ctk.CTkLabel(
            win,
            text="⚠ O servidor será parado e os saves atuais substituídos.",
            font=ctk.CTkFont(size=11),
            text_color="#fbbf24",
        ).pack(pady=(0, 18))

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack()
        ctk.CTkButton(
            btn_row, text="Cancelar", width=100,
            fg_color="#0f172a", hover_color="#1e293b",
            command=win.destroy,
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            btn_row, text="Restaurar", width=100,
            fg_color="#1e3a5f", hover_color="#2563eb",
            text_color="#7dd3fc",
            command=lambda: (win.destroy(), self._do_restore(backup_path)),
        ).pack(side="left", padx=8)

    def _do_restore(self, backup_path: Path) -> None:
        if self._busy:
            return
        self._set_busy(True)
        threading.Thread(
            target=self._restore_worker, args=(backup_path,), daemon=True
        ).start()

    def _restore_worker(self, backup_path: Path) -> None:
        srv = self._srv
        src_saves = backup_path / "SavedArks"
        dst_saves = _saves_dir(srv)

        self.after(0, lambda: self._log_line(f"Iniciando restauração de {backup_path.name}…"))

        try:
            # Para o servidor se estiver rodando
            mgr = self._app.asm_server_manager
            was_running = mgr.get_status(srv.id) not in ("stopped", "crashed")
            if was_running:
                self.after(0, lambda: self._log_line("Parando servidor…"))
                stop_event = threading.Event()
                mgr.stop(srv.id, on_done=lambda ok, msg: stop_event.set())
                stop_event.wait(timeout=60)
                time.sleep(2)

            if not src_saves.exists():
                raise FileNotFoundError(f"Pasta de saves no backup não encontrada: {src_saves}")

            # Faz backup automático dos saves atuais antes de restaurar
            if dst_saves.exists():
                ts = time.strftime("%Y-%m-%d_%H-%M-%S")
                pre_backup = _backups_root(srv) / f"{ts}_pre_restore"
                pre_backup.mkdir(parents=True, exist_ok=True)
                shutil.copytree(str(dst_saves), str(pre_backup / "SavedArks"), dirs_exist_ok=True)
                self.after(0, lambda: self._log_line(f"Saves atuais preservados em {pre_backup.name}"))

            # Copia saves do backup para o destino
            if dst_saves.exists():
                shutil.rmtree(str(dst_saves))
            shutil.copytree(str(src_saves), str(dst_saves))
            self.after(0, lambda: self._log_line("✔ Saves restaurados.", color="#4ade80"))

            # Reinicia se estava rodando
            if was_running:
                self.after(0, lambda: self._log_line("Reiniciando servidor…"))
                mgr.start(srv, on_done=lambda ok, msg: None)

            self.after(0, lambda: self._set_busy(False))
            self.after(0, self._reload_list)

        except Exception as exc:
            self.after(0, lambda e=exc: self._on_error(str(e)))

    # ── Deletar backup ────────────────────────────────────────────────────────

    def _confirm_delete(self, backup_path: Path) -> None:
        win = ctk.CTkToplevel(self)
        win.title("Confirmar Exclusão")
        win.geometry("400x160")
        win.configure(fg_color=get_theme("tek")["card_bg"])
        win.grab_set()

        ctk.CTkLabel(
            win,
            text=f"Excluir backup permanentemente?\n{backup_path.name}",
            font=ctk.CTkFont(size=12),
            text_color=get_theme("tek").get("text_secondary", "#94a3b8"),
            justify="center",
        ).pack(pady=(24, 18))

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack()
        ctk.CTkButton(
            btn_row, text="Cancelar", width=100,
            fg_color="#0f172a", hover_color="#1e293b",
            command=win.destroy,
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            btn_row, text="Excluir", width=100,
            fg_color="#7f1d1d", hover_color="#991b1b",
            text_color="#fca5a5",
            command=lambda: (win.destroy(), self._delete_backup(backup_path)),
        ).pack(side="left", padx=8)

    def _delete_backup(self, backup_path: Path) -> None:
        try:
            shutil.rmtree(str(backup_path))
            self._log_line(f"Backup excluído: {backup_path.name}")
            self._reload_list()
        except Exception as exc:
            self._on_error(str(exc))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _log_line(self, text: str, color: str = "#d1fae5") -> None:
        if not self.winfo_exists():
            return
        self._log.configure(state="normal")
        ts = time.strftime("%H:%M:%S")
        self._log.insert("end", f"[{ts}] ", ("ts",))
        self._log.insert("end", text + "\n", ("msg",))
        self._log.tag_config("ts",  foreground="#475569")
        self._log.tag_config("msg", foreground=color)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _on_error(self, msg: str) -> None:
        self._log_line(f"✘ Erro: {msg}", color="#f87171")
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        if self.winfo_exists():
            self._btn_backup.configure(state=state)
            self._status_lbl.configure(
                text="Operação em andamento…" if busy else ""
            )
