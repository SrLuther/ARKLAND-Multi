"""
asm_file_manager.py — Gerenciador de Arquivos do Servidor TEK.

Explorador de arquivos integrado para navegar pelo install_dir do servidor,
com editor simples para arquivos de texto e atalhos para paths críticos do ARK.

Uso:
    from src.asm_ui.asm_file_manager import open_asm_file_manager
    open_asm_file_manager(app, srv)
"""
from __future__ import annotations

import os
import subprocess
import tkinter as tk
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import AsmServerConfig
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp


# Atalhos rápidos para paths críticos do ARK
_SHORTCUTS: dict[str, str] = {
    "⚙ GUS.ini":   "ShooterGame/Saved/Config/WindowsServer/GameUserSettings.ini",
    "🎮 Game.ini":  "ShooterGame/Saved/Config/WindowsServer/Game.ini",
    "📋 Logs":      "ShooterGame/Saved/Logs",
    "🔌 Plugins":   "ShooterGame/Binaries/Win64/ArkApi/Plugins",
    "💾 Saves":     "ShooterGame/Saved/SavedArks",
    "🧩 Mods":      "ShooterGame/Content/Mods",
}

# Extensões editáveis inline
_EDITABLE_EXTS = {".ini", ".json", ".txt", ".log", ".cfg", ".yaml", ".yml", ".xml", ".bat", ".sh"}

# Ícones por extensão/tipo
_ICONS: dict[str, str] = {
    "dir":   "📁",
    ".ini":  "⚙",
    ".json": "{}",
    ".txt":  "📄",
    ".log":  "📋",
    ".ark":  "💾",
    ".bak":  "🔁",
    ".dll":  "🔌",
    ".exe":  "▶",
    ".bat":  "⚡",
    ".zip":  "📦",
    ".7z":   "📦",
}


def _file_icon(path: Path) -> str:
    if path.is_dir():
        return _ICONS["dir"]
    return _ICONS.get(path.suffix.lower(), "📄")


def _size_str(path: Path) -> str:
    try:
        b = path.stat().st_size
        for unit in ("B", "KB", "MB", "GB"):
            if b < 1024:
                return f"{b:.0f} {unit}"
            b /= 1024
        return f"{b:.1f} TB"
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────


def open_asm_file_manager(
    app: "ARKServerManagerApp",
    srv: AsmServerConfig,
    start_path: Optional[str] = None,
) -> None:
    """Abre (ou foca) o gerenciador de arquivos para *srv*."""
    win_attr = f"_asm_file_mgr_{srv.id}"
    existing: Optional[ctk.CTkToplevel] = getattr(app, win_attr, None)
    if existing and existing.winfo_exists():
        existing.lift()
        existing.focus_force()
        if start_path:
            existing._navigate(Path(start_path))  # type: ignore[attr-defined]
        return

    win = _FileManagerWindow(app, srv, start_path=start_path)
    setattr(app, win_attr, win)
    win.protocol("WM_DELETE_WINDOW", lambda: _on_close(app, win_attr, win))
    win.after(100, win.lift)
    win.after(150, win.focus_force)


def _on_close(app: "ARKServerManagerApp", attr: str, win: ctk.CTkToplevel) -> None:
    setattr(app, attr, None)
    win.destroy()


# ─────────────────────────────────────────────────────────────────────────────


class _FileManagerWindow(ctk.CTkToplevel):
    """Explorador de arquivos do servidor ARK."""

    def __init__(
        self,
        app: "ARKServerManagerApp",
        srv: AsmServerConfig,
        start_path: Optional[str] = None,
    ) -> None:
        super().__init__(app)
        th = get_theme("tek")
        bg      = th["bg"]
        card_bg = th["card_bg"]
        accent  = th["accent"]
        sep     = th.get("separator", "#1e293b")
        t_sec   = th.get("text_secondary", "#94a3b8")
        t_mut   = th.get("text_muted", "#475569")

        self._app     = app
        self._srv     = srv
        self._root    = Path(srv.install_dir)
        self._current = Path(start_path) if start_path else self._root

        self.title(f"Arquivos — {srv.name}")
        self.geometry("860x560")
        self.minsize(640, 400)
        self.configure(fg_color=bg)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Atalhos rápidos ───────────────────────────────────────────────────
        shortcuts_bar = ctk.CTkFrame(self, fg_color=card_bg, corner_radius=0, height=44)
        shortcuts_bar.grid(row=0, column=0, sticky="ew")
        shortcuts_bar.grid_propagate(False)

        ctk.CTkLabel(
            shortcuts_bar, text="Atalhos:",
            font=ctk.CTkFont(size=10), text_color=t_mut,
        ).pack(side="left", padx=(12, 6), pady=12)

        for label, rel_path in _SHORTCUTS.items():
            abs_path = self._root / rel_path
            ctk.CTkButton(
                shortcuts_bar, text=label,
                width=max(70, len(label) * 9), height=28,
                fg_color="#0f172a", hover_color="#1e293b",
                border_width=1, border_color=sep,
                text_color=t_sec,
                font=ctk.CTkFont(size=10),
                corner_radius=4,
                command=lambda p=abs_path: self._navigate(p),
            ).pack(side="left", padx=(0, 3))

        # Ações lado direito
        right = ctk.CTkFrame(shortcuts_bar, fg_color="transparent")
        right.pack(side="right", padx=12)

        ctk.CTkButton(
            right, text="↺", width=32, height=28,
            fg_color="#0f172a", hover_color="#1e293b",
            border_width=1, border_color=sep,
            text_color=t_sec, font=ctk.CTkFont(size=12),
            corner_radius=4,
            command=self._refresh,
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            right, text="📂 Abrir no Explorer", width=130, height=28,
            fg_color="#0f172a", hover_color="#1e293b",
            border_width=1, border_color=sep,
            text_color=t_sec, font=ctk.CTkFont(size=10),
            corner_radius=4,
            command=self._open_in_explorer,
        ).pack(side="left")

        # ── Corpo: breadcrumb + lista ─────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=10, pady=8)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        # Breadcrumb
        self._breadcrumb_frame = ctk.CTkFrame(body, fg_color="transparent", height=30)
        self._breadcrumb_frame.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        # Lista de arquivos
        self._list_scroll = ctk.CTkScrollableFrame(
            body, fg_color="transparent",
            scrollbar_button_color=sep,
            scrollbar_button_hover_color=accent,
        )
        self._list_scroll.grid(row=1, column=0, sticky="nsew")
        self._list_scroll.grid_columnconfigure(0, weight=1)

        self._navigate(self._current)

    # ── Navegação ─────────────────────────────────────────────────────────────

    def _navigate(self, path: Path) -> None:
        """Navega para *path* (arquivo ou pasta)."""
        if path.is_file():
            self._open_file(path)
            return
        if not path.exists():
            self._current = self._root
        else:
            self._current = path
        self._refresh()

    def _refresh(self) -> None:
        self._render_breadcrumb()
        self._render_listing()

    def _render_breadcrumb(self) -> None:
        th = get_theme("tek")
        t_sec = th.get("text_secondary", "#94a3b8")
        t_mut = th.get("text_muted", "#475569")
        sep   = th.get("separator", "#1e293b")

        for w in self._breadcrumb_frame.winfo_children():
            w.destroy()

        # Calcula partes relativas ao root
        try:
            rel = self._current.relative_to(self._root)
            parts = [self._root] + [self._root / Path(*rel.parts[:i + 1]) for i in range(len(rel.parts))]
            labels = [self._root.name] + list(rel.parts)
        except ValueError:
            parts = [self._root]
            labels = [self._root.name]

        for i, (lbl, pth) in enumerate(zip(labels, parts)):
            ctk.CTkButton(
                self._breadcrumb_frame, text=lbl,
                height=24, font=ctk.CTkFont(size=11),
                fg_color="transparent", hover_color="#1e293b",
                text_color=t_sec if i < len(labels) - 1 else "#f1f5f9",
                corner_radius=4,
                command=lambda p=pth: self._navigate(p),
            ).pack(side="left")
            if i < len(labels) - 1:
                ctk.CTkLabel(
                    self._breadcrumb_frame, text="›",
                    font=ctk.CTkFont(size=12), text_color=t_mut,
                ).pack(side="left")

    def _render_listing(self) -> None:
        th = get_theme("tek")
        card_bg = th["card_bg"]
        t_sec   = th.get("text_secondary", "#94a3b8")
        t_mut   = th.get("text_muted", "#475569")
        sep     = th.get("separator", "#1e293b")

        for w in self._list_scroll.winfo_children():
            w.destroy()

        if not self._current.exists():
            ctk.CTkLabel(
                self._list_scroll,
                text=f"Pasta não encontrada:\n{self._current}",
                font=ctk.CTkFont(size=12), text_color=t_mut,
            ).grid(row=0, column=0, pady=30)
            return

        # Botão subir (..)
        if self._current != self._root and self._current.parent != self._current:
            up_row = ctk.CTkFrame(self._list_scroll, fg_color="transparent", height=34)
            up_row.grid(row=0, column=0, sticky="ew", pady=1)
            up_row.grid_columnconfigure(1, weight=1)
            up_row.grid_propagate(False)
            ctk.CTkButton(
                up_row, text="📁  ..", anchor="w",
                height=34, fg_color="transparent", hover_color="#1e293b",
                text_color=t_sec, font=ctk.CTkFont(size=12),
                corner_radius=4,
                command=lambda: self._navigate(self._current.parent),
            ).grid(row=0, column=0, sticky="ew", padx=4)

        try:
            entries = sorted(
                self._current.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except PermissionError:
            ctk.CTkLabel(
                self._list_scroll,
                text="Acesso negado.", font=ctk.CTkFont(size=12), text_color=t_mut,
            ).grid(row=0, column=0, pady=20)
            return

        offset = 1 if (self._current != self._root) else 0
        for i, entry in enumerate(entries):
            row_bg = card_bg if i % 2 == 0 else "#0a1520"
            row = ctk.CTkFrame(
                self._list_scroll, fg_color=row_bg, corner_radius=4, height=34,
            )
            row.grid(row=i + offset, column=0, sticky="ew", pady=1)
            row.grid_columnconfigure(1, weight=1)
            row.grid_propagate(False)

            icon = _file_icon(entry)
            ctk.CTkLabel(row, text=icon, width=28, font=ctk.CTkFont(size=13)).grid(
                row=0, column=0, padx=(8, 4), pady=6)

            # Nome — clicável
            ctk.CTkButton(
                row, text=entry.name, anchor="w",
                height=28, fg_color="transparent", hover_color="#1e293b",
                text_color=t_sec if entry.is_dir() else "#e2e8f0",
                font=ctk.CTkFont(
                    family="Segoe UI", size=11,
                    weight="bold" if entry.is_dir() else "normal",
                ),
                corner_radius=4,
                command=lambda p=entry: self._navigate(p),
            ).grid(row=0, column=1, sticky="ew", padx=(0, 4))

            # Tamanho (só para arquivos)
            if not entry.is_dir():
                ctk.CTkLabel(
                    row, text=_size_str(entry), width=72, anchor="e",
                    font=ctk.CTkFont(family="Consolas", size=10), text_color=t_mut,
                ).grid(row=0, column=2, padx=(0, 8))

            # Botões de ação para arquivos editáveis
            if entry.is_file():
                btn_cell = ctk.CTkFrame(row, fg_color="transparent")
                btn_cell.grid(row=0, column=3, padx=(0, 8))
                ctk.CTkButton(
                    btn_cell, text="✏", width=28, height=24,
                    fg_color="transparent", hover_color="#1e293b",
                    text_color=t_mut, font=ctk.CTkFont(size=11),
                    corner_radius=4,
                    command=lambda p=entry: self._open_file(p),
                ).pack(side="left", padx=(0, 2))
                ctk.CTkButton(
                    btn_cell, text="📋", width=28, height=24,
                    fg_color="transparent", hover_color="#1e293b",
                    text_color=t_mut, font=ctk.CTkFont(size=11),
                    corner_radius=4,
                    command=lambda p=entry: self._copy_path(p),
                ).pack(side="left")

    # ── Editor de arquivo ─────────────────────────────────────────────────────

    def _open_file(self, path: Path) -> None:
        """Abre arquivo em editor inline ou externo."""
        if path.suffix.lower() not in _EDITABLE_EXTS:
            # Abre com programa padrão do OS
            try:
                os.startfile(str(path))
            except Exception:
                subprocess.Popen(["explorer", str(path)])
            return

        self._open_editor_window(path)

    def _open_editor_window(self, path: Path) -> None:
        th = get_theme("tek")
        bg  = th["bg"]
        sep = th.get("separator", "#1e293b")
        accent = th["accent"]

        win = ctk.CTkToplevel(self)
        win.title(f"Editar — {path.name}")
        win.geometry("800x560")
        win.configure(fg_color=bg)
        win.grid_columnconfigure(0, weight=1)
        win.grid_rowconfigure(0, weight=1)

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            content = f"# Erro ao ler o arquivo: {exc}"

        editor = ctk.CTkTextbox(
            win,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#04090f",
            text_color="#e2e8f0",
            border_width=1,
            border_color=sep,
            corner_radius=6,
            wrap="none",
        )
        editor.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 6))
        editor.insert("1.0", content)

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(
            btn_row,
            text=str(path),
            font=ctk.CTkFont(family="Consolas", size=9),
            text_color=th.get("text_muted", "#475569"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            btn_row, text="💾  Salvar", width=90, height=30,
            fg_color="#14532d", hover_color="#166534",
            text_color=accent,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: self._save_file(path, editor, win),
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            btn_row, text="Cancelar", width=80, height=30,
            fg_color="#0f172a", hover_color="#1e293b",
            border_width=1, border_color=sep,
            font=ctk.CTkFont(size=11),
            command=win.destroy,
        ).pack(side="right")

        editor.bind("<Control-s>", lambda _: self._save_file(path, editor, win))

    def _save_file(
        self, path: Path, editor: ctk.CTkTextbox, win: ctk.CTkToplevel
    ) -> None:
        content = editor.get("1.0", "end-1c")
        try:
            path.write_text(content, encoding="utf-8")
            win.title(f"Editar — {path.name}  ✔ Salvo")
        except Exception as exc:
            win.title(f"Editar — {path.name}  ✘ Erro: {exc}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _open_in_explorer(self) -> None:
        path = self._current if self._current.is_dir() else self._current.parent
        subprocess.Popen(["explorer", str(path)])

    def _copy_path(self, path: Path) -> None:
        self.clipboard_clear()
        self.clipboard_append(str(path))
