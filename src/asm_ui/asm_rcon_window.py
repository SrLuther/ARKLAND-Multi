"""
asm_rcon_window.py — Console RCON TEK para servidores ARK.

Janela de terminal interativo que conecta ao servidor via RCON e permite
enviar comandos, visualizar respostas e usar atalhos rápidos.

Uso:
    from src.asm_ui.asm_rcon_window import open_asm_rcon_window
    open_asm_rcon_window(app, srv)
"""
from __future__ import annotations

import threading
import time
import tkinter as tk
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..rcon_client import RconClient, RconError
from ..asm_engine.asm_server_config import AsmServerConfig
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp


# Atalhos rápidos — (label, comando)
_QUICK_CMDS = [
    ("ListPlayers",   "listplayers"),
    ("SaveWorld",     "saveworld"),
    ("DestroyWildDinos", "destroywilddinos"),
    ("Broadcast",     "broadcast "),        # abre com cursor no campo
    ("DoExit",        "doexit"),
    ("Cheat GCM",     "cheat gcm"),
    ("Cheat GFI",     "cheat gfi "),
]


def open_asm_rcon_window(app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
    """Abre (ou foca) a janela RCON para *srv*.

    Se já houver uma janela aberta para este servidor, ela é trazida para frente.
    """
    win_attr = f"_asm_rcon_win_{srv.id}"
    existing: Optional[ctk.CTkToplevel] = getattr(app, win_attr, None)
    if existing and existing.winfo_exists():
        existing.lift()
        existing.focus_force()
        return

    win = _RconWindow(app, srv)
    setattr(app, win_attr, win)
    win.protocol("WM_DELETE_WINDOW", lambda: _on_close(app, win_attr, win))
    win.after(100, win.lift)
    win.after(150, win.focus_force)


def _on_close(app: "ARKServerManagerApp", attr: str, win: ctk.CTkToplevel) -> None:
    win._disconnect()  # type: ignore[attr-defined]
    setattr(app, attr, None)
    win.destroy()


# ─────────────────────────────────────────────────────────────────────────────


class _RconWindow(ctk.CTkToplevel):
    """Janela de console RCON."""

    _HISTORY_MAX = 200     # linhas máximas no log
    _CMD_HISTORY_MAX = 100 # histórico de comandos navegável

    def __init__(self, app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
        super().__init__(app)
        th = get_theme("tek")
        bg       = th["bg"]
        card_bg  = th["card_bg"]
        accent   = th["accent"]
        sep      = th.get("separator", "#1e293b")
        t_sec    = th.get("text_secondary", "#94a3b8")
        t_mut    = th.get("text_muted", "#475569")

        self._app    = app
        self._srv    = srv
        self._client: Optional[RconClient] = None
        self._lock   = threading.Lock()
        self._cmd_hist: list[str] = []
        self._hist_idx: int = -1
        self._ping_after_id: Optional[str] = None

        # ── Layout da janela ──────────────────────────────────────────────────
        self.title(f"RCON — {srv.name}")
        self.geometry("820x560")
        self.minsize(600, 400)
        self.configure(fg_color=bg)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Barra de status / conexão ─────────────────────────────────────────
        top_bar = ctk.CTkFrame(self, fg_color=card_bg, corner_radius=0, height=44)
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.grid_columnconfigure(2, weight=1)
        top_bar.grid_propagate(False)

        self._dot = ctk.CTkLabel(top_bar, text="●", font=ctk.CTkFont(size=16),
                                 text_color="#ef4444", width=24)
        self._dot.grid(row=0, column=0, padx=(12, 4), pady=10)

        self._status_lbl = ctk.CTkLabel(
            top_bar, text="Desconectado",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=t_sec,
        )
        self._status_lbl.grid(row=0, column=1, padx=(0, 16), pady=10)

        conn_info = f"{srv.server_ip or '127.0.0.1'}:{srv.rcon_port}"
        ctk.CTkLabel(
            top_bar, text=conn_info,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=t_mut,
        ).grid(row=0, column=2, padx=0, pady=10, sticky="w")

        btn_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        btn_frame.grid(row=0, column=3, padx=12, pady=6, sticky="e")

        self._btn_connect = ctk.CTkButton(
            btn_frame, text="Conectar", width=90, height=30,
            fg_color="#14532d", hover_color="#166534",
            font=ctk.CTkFont(size=11),
            command=self._connect,
        )
        self._btn_connect.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_frame, text="Limpar", width=72, height=30,
            fg_color="#0f172a", hover_color="#1e293b",
            border_width=1, border_color=sep,
            font=ctk.CTkFont(size=11),
            command=self._clear_log,
        ).pack(side="left")

        # ── Área principal ────────────────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew", padx=10, pady=(8, 0))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Log de saída
        self._log = ctk.CTkTextbox(
            body,
            state="disabled",
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#04090f",
            text_color="#d1fae5",
            border_width=1,
            border_color=sep,
            corner_radius=8,
            wrap="word",
        )
        self._log.grid(row=0, column=0, sticky="nsew", pady=(0, 8))

        # ── Atalhos rápidos ───────────────────────────────────────────────────
        quick_row = ctk.CTkFrame(body, fg_color="transparent")
        quick_row.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        ctk.CTkLabel(quick_row, text="Atalhos:",
                     font=ctk.CTkFont(size=10), text_color=t_mut).pack(side="left", padx=(0, 6))

        for label, cmd in _QUICK_CMDS:
            ctk.CTkButton(
                quick_row, text=label,
                width=max(70, len(label) * 8), height=26,
                fg_color="#0f172a", hover_color="#1e293b",
                border_width=1, border_color=sep,
                text_color=t_sec,
                font=ctk.CTkFont(size=10),
                corner_radius=4,
                command=lambda c=cmd: self._fill_input(c),
            ).pack(side="left", padx=(0, 3))

        # ── Campo de entrada ──────────────────────────────────────────────────
        input_row = ctk.CTkFrame(body, fg_color="transparent")
        input_row.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        input_row.grid_columnconfigure(0, weight=1)

        self._input_var = tk.StringVar()
        self._input = ctk.CTkEntry(
            input_row,
            textvariable=self._input_var,
            placeholder_text="Digite um comando RCON e pressione Enter…",
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#04090f",
            border_color=sep,
            text_color="#d1fae5",
            height=36,
            corner_radius=8,
        )
        self._input.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            input_row, text="Enviar", width=80, height=36,
            fg_color="#14532d", hover_color="#166534",
            text_color=accent,
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=8,
            command=self._send,
        ).grid(row=0, column=1)

        # Atalhos de teclado
        self._input.bind("<Return>", lambda _: self._send())
        self._input.bind("<Up>",     lambda _: self._hist_prev())
        self._input.bind("<Down>",   lambda _: self._hist_next())
        self.bind("<Escape>",        lambda _: self._disconnect())

        # Auto-conecta se RCON habilitado
        if srv.rcon_enabled and srv.admin_password:
            self.after(200, self._connect)
        else:
            self._log_line("[AVISO] RCON desabilitado ou senha não configurada.", color="#fbbf24")

    # ── Conexão ───────────────────────────────────────────────────────────────

    def _connect(self) -> None:
        self._set_status("Conectando…", "#f59e0b")
        self._btn_connect.configure(state="disabled")
        threading.Thread(target=self._connect_worker, daemon=True).start()

    def _connect_worker(self) -> None:
        srv = self._srv
        host = srv.server_ip or "127.0.0.1"
        try:
            client = RconClient(host, srv.rcon_port, srv.admin_password)
            client.connect()
            with self._lock:
                self._client = client
            self.after(0, lambda: self._on_connected(host))
            self._schedule_ping()
        except Exception as exc:
            self.after(0, lambda e=exc: self._on_connect_error(str(e)))

    def _on_connected(self, host: str) -> None:
        self._set_status(f"Conectado a {host}:{self._srv.rcon_port}", "#22c55e")
        self._btn_connect.configure(state="normal", text="Reconectar")
        self._log_line(f"✔ Conectado a {host}:{self._srv.rcon_port}", color="#4ade80")
        self._input.focus()

    def _on_connect_error(self, msg: str) -> None:
        self._set_status("Falha na conexão", "#ef4444")
        self._btn_connect.configure(state="normal", text="Tentar Novamente")
        self._log_line(f"✘ Falha: {msg}", color="#f87171")

    def _disconnect(self) -> None:
        self._cancel_ping()
        with self._lock:
            c = self._client
            self._client = None
        if c:
            try:
                c.disconnect()
            except Exception:
                pass
        if self.winfo_exists():
            self._set_status("Desconectado", "#ef4444")
            self._btn_connect.configure(state="normal", text="Conectar")

    # ── Envio de comandos ─────────────────────────────────────────────────────

    def _send(self) -> None:
        cmd = self._input_var.get().strip()
        if not cmd:
            return
        self._input_var.set("")
        self._hist_idx = -1

        # Adiciona ao histórico
        if not self._cmd_hist or self._cmd_hist[0] != cmd:
            self._cmd_hist.insert(0, cmd)
            if len(self._cmd_hist) > self._CMD_HISTORY_MAX:
                self._cmd_hist.pop()

        self._log_line(f"> {cmd}", color="#86efac")

        with self._lock:
            client = self._client

        if client is None:
            self._log_line("[ERRO] Não conectado. Use o botão Conectar.", color="#f87171")
            return

        threading.Thread(target=self._send_worker, args=(client, cmd), daemon=True).start()

    def _send_worker(self, client: RconClient, cmd: str) -> None:
        ok, resp = client.send_command_safe(cmd)
        resp = resp.strip() if resp else ""
        if ok:
            self.after(0, lambda r=resp: self._log_line(r or "(sem resposta)", color="#d1fae5"))
        else:
            self.after(0, lambda r=resp: self._log_line(f"[ERRO] {r}", color="#f87171"))
            # Marca como desconectado
            self.after(0, lambda: self._set_status("Conexão perdida", "#ef4444"))
            with self._lock:
                self._client = None

    # ── Log ───────────────────────────────────────────────────────────────────

    def _log_line(self, text: str, color: str = "#d1fae5") -> None:
        """Adiciona linha colorida ao log (deve ser chamado na thread principal)."""
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

    def _clear_log(self) -> None:
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    # ── Status bar ────────────────────────────────────────────────────────────

    def _set_status(self, text: str, color: str) -> None:
        if self.winfo_exists():
            self._dot.configure(text_color=color)
            self._status_lbl.configure(text=text)

    # ── Histórico de comandos ─────────────────────────────────────────────────

    def _hist_prev(self) -> None:
        if not self._cmd_hist:
            return
        self._hist_idx = min(self._hist_idx + 1, len(self._cmd_hist) - 1)
        self._input_var.set(self._cmd_hist[self._hist_idx])
        self._input.icursor("end")

    def _hist_next(self) -> None:
        if self._hist_idx <= 0:
            self._hist_idx = -1
            self._input_var.set("")
        else:
            self._hist_idx -= 1
            self._input_var.set(self._cmd_hist[self._hist_idx])
        self._input.icursor("end")

    # ── Input helper ─────────────────────────────────────────────────────────

    def _fill_input(self, cmd: str) -> None:
        """Preenche o campo de input com *cmd* (cursor no final)."""
        self._input_var.set(cmd)
        self._input.focus()
        self._input.icursor("end")

    # ── Keep-alive ping ───────────────────────────────────────────────────────

    def _schedule_ping(self) -> None:
        if self.winfo_exists():
            self._ping_after_id = self.after(30_000, self._ping_tick)

    def _cancel_ping(self) -> None:
        if self._ping_after_id:
            try:
                self.after_cancel(self._ping_after_id)
            except Exception:
                pass
            self._ping_after_id = None

    def _ping_tick(self) -> None:
        with self._lock:
            client = self._client
        if client:
            threading.Thread(target=self._ping_worker, args=(client,), daemon=True).start()
        self._schedule_ping()

    def _ping_worker(self, client: RconClient) -> None:
        alive = client.ping()
        if not alive:
            self.after(0, lambda: self._set_status("Conexão perdida (ping)", "#ef4444"))
            with self._lock:
                self._client = None
