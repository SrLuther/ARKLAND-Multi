"""
Visualizador do log de inicialização do servidor ARK (ShooterGame.log).
Abre uma janela com o conteúdo do arquivo de log com auto-refresh.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional
import tkinter as tk
import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import get_theme
from ..asm_engine.asm_server_config import AsmServerConfig

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

# Instâncias abertas (uma por servidor)
_open_windows: dict[str, "AsmServerLogWindow"] = {}

# Caminho do log dentro do install_dir
_LOG_RELATIVE = Path("ShooterGame") / "Saved" / "Logs" / "ShooterGame.log"
_REFRESH_INTERVAL = 2  # segundos


class AsmServerLogWindow(ctk.CTkToplevel):
    def __init__(self, parent, srv: AsmServerConfig, app: "ARKServerManagerApp"):
        super().__init__(parent)
        th = get_theme("tek")
        self._bg  = th["bg"]
        self._cg  = th["card_bg"]
        self._sep = th["separator"]
        self._acc = th["accent"]
        self._t   = th["text_primary"]
        self._tm  = th["text_muted"]
        self._srv = srv
        self._app = app
        self._running = True
        self._last_size = 0
        self._pinned_bottom = True

        self.title(f"Log — {srv.name}")
        self.geometry("900x560")
        self.configure(fg_color=self._bg)
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self.lift)
        self.after(150, self.focus_force)

        self._build_ui()
        self._start_reader()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Toolbar
        tb = ctk.CTkFrame(self, fg_color=self._cg, corner_radius=0, height=40)
        tb.grid(row=0, column=0, sticky="ew")
        tb.grid_propagate(False)
        tb.grid_columnconfigure(3, weight=1)

        # Caminho do arquivo
        log_path = Path(self._srv.install_dir) / _LOG_RELATIVE
        ctk.CTkLabel(
            tb, text=str(log_path),
            font=ctk.CTkFont(size=10), text_color=self._tm,
        ).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        # Botão limpar display (não apaga o arquivo)
        ctk.CTkButton(
            tb, text="🗑  Limpar Display", width=130, height=26,
            fg_color="transparent", hover_color=self._sep,
            border_width=1, border_color=self._sep,
            text_color=self._tm, font=ctk.CTkFont(size=11),
            command=self._clear_display,
        ).grid(row=0, column=1, padx=6, pady=6)

        # Toggle "seguir fim"
        self._follow_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            tb, text="Seguir fim", variable=self._follow_var,
            font=ctk.CTkFont(size=11), text_color=self._tm,
            checkmark_color=self._acc, border_color=self._acc,
            width=100,
        ).grid(row=0, column=2, padx=6, pady=6)

        # Área de texto
        txt_frame = ctk.CTkFrame(self, fg_color=self._bg, corner_radius=0)
        txt_frame.grid(row=1, column=0, sticky="nsew")
        txt_frame.grid_rowconfigure(0, weight=1)
        txt_frame.grid_columnconfigure(0, weight=1)

        self._txt = tk.Text(
            txt_frame,
            bg="#030c1a", fg="#94a3b8",
            insertbackground="#94a3b8",
            font=("Consolas", 10),
            wrap="none",
            bd=0, relief="flat",
            state="disabled",
        )
        self._txt.grid(row=0, column=0, sticky="nsew")

        sb_v = tk.Scrollbar(txt_frame, orient="vertical", command=self._txt.yview)
        sb_v.grid(row=0, column=1, sticky="ns")
        sb_h = tk.Scrollbar(txt_frame, orient="horizontal", command=self._txt.xview)
        sb_h.grid(row=1, column=0, sticky="ew")
        self._txt.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)

        # Tags de cor
        self._txt.tag_config("warn",  foreground="#fbbf24")
        self._txt.tag_config("error", foreground="#f87171")
        self._txt.tag_config("ok",    foreground="#4ade80")
        self._txt.tag_config("info",  foreground="#7dd3fc")

        # Status bar
        self._status_var = tk.StringVar(value="Aguardando arquivo...")
        ctk.CTkLabel(
            self, textvariable=self._status_var,
            font=ctk.CTkFont(size=10), text_color=self._tm,
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", padx=12, pady=(2, 4))

    # ── Leitura do log ────────────────────────────────────────────────────────

    def _start_reader(self) -> None:
        t = threading.Thread(target=self._reader_loop, daemon=True)
        t.start()

    def _reader_loop(self) -> None:
        log_path = Path(self._srv.install_dir) / _LOG_RELATIVE
        while self._running:
            try:
                if not log_path.exists():
                    self.after(0, lambda: self._status_var.set(
                        f"Arquivo não encontrado: {log_path}"))
                    time.sleep(_REFRESH_INTERVAL)
                    continue

                current_size = log_path.stat().st_size
                if current_size != self._last_size:
                    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    self._last_size = current_size
                    self.after(0, lambda c=content: self._update_text(c))
                    mod_time = log_path.stat().st_mtime
                    from datetime import datetime
                    ts = datetime.fromtimestamp(mod_time).strftime("%H:%M:%S")
                    self.after(0, lambda t=ts, s=current_size: self._status_var.set(
                        f"Atualizado às {t}  •  {s // 1024} KB"))

            except Exception as exc:
                self.after(0, lambda e=str(exc): self._status_var.set(f"Erro: {e}"))

            time.sleep(_REFRESH_INTERVAL)

    def _update_text(self, content: str) -> None:
        self._txt.configure(state="normal")
        self._txt.delete("1.0", "end")
        for line in content.splitlines():
            tag = self._line_tag(line)
            self._txt.insert("end", line + "\n", tag)
        self._txt.configure(state="disabled")
        if self._follow_var.get():
            self._txt.see("end")

    @staticmethod
    def _line_tag(line: str) -> str:
        ll = line.lower()
        if "error" in ll or "fatal" in ll or "crash" in ll:
            return "error"
        if "warning" in ll or "warn" in ll:
            return "warn"
        if "success" in ll or "complete" in ll or "loaded" in ll:
            return "ok"
        if "log:" in ll or "info" in ll:
            return "info"
        return ""

    def _clear_display(self) -> None:
        self._txt.configure(state="normal")
        self._txt.delete("1.0", "end")
        self._txt.configure(state="disabled")
        self._last_size = 0  # força releitura na próxima iteração

    def _on_close(self) -> None:
        self._running = False
        _open_windows.pop(self._srv.id, None)
        self.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────

def open_asm_server_log(app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
    """Abre (ou foca) a janela de log do servidor."""
    existing = _open_windows.get(srv.id)
    if existing and existing.winfo_exists():
        existing.lift()
        existing.focus_force()
        return
    win = AsmServerLogWindow(app, srv, app)
    _open_windows[srv.id] = win
