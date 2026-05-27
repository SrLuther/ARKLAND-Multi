from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _GREEN_DARK, _GREEN_HOVER, _BLUE, _BLUE_HOVER, _CARD_BG

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig

_HISTORY_LIMIT = 100   # máximo de comandos no histórico por servidor


def build_tab_rcon(app: "ARKServerManagerApp", parent, srv: "ServerConfig") -> None:
    # Linhas: 0=conn_bar, 1=log, 2=shortcuts_bar, 3=broadcast_row, 4=input_row
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(1, weight=1)

    w   = app._server_widgets[srv.id]
    sid = srv.id

    # Estado de histórico local (por servidor)
    w["_rcon_history"]  = []   # list[str]
    w["_rcon_hist_idx"] = [-1] # [-1] = nenhum item selecionado

    # ── Barra de Conexão ────────────────────────────────────────────────────
    conn_bar = ctk.CTkFrame(parent, corner_radius=10, fg_color=_CARD_BG)
    conn_bar.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="ew")
    conn_bar.grid_columnconfigure(1, weight=1)

    _host = srv.server_ip or "127.0.0.1"
    ctk.CTkLabel(
        conn_bar,
        text=f"🖥  {_host}:{srv.rcon_port}",
        text_color="gray55",
        font=ctk.CTkFont(size=11),
    ).grid(row=0, column=0, padx=(14, 14), pady=10, sticky="w")

    w["rcon_status_var"] = tk.StringVar(value="⬛ Desconectado")
    ctk.CTkLabel(conn_bar, textvariable=w["rcon_status_var"],
                 text_color="gray50", font=ctk.CTkFont(size=12)).grid(
        row=0, column=1, padx=8, pady=10, sticky="w")

    # Checkbox auto-conectar (mantém RCON vivo automaticamente)
    w["rcon_auto_chk_var"] = tk.BooleanVar(value=True)
    def _on_auto_chk(sid_: str = sid) -> None:
        enabled = w["rcon_auto_chk_var"].get()
        app._rcon_auto_enabled[sid_] = enabled
        if enabled:
            app._rcon_schedule_auto_connect(sid_, delay_ms=5_000)
        else:
            app._rcon_cancel_auto_job(sid_)
    ctk.CTkCheckBox(
        conn_bar, text="Auto-reconectar",
        variable=w["rcon_auto_chk_var"],
        command=_on_auto_chk,
        font=ctk.CTkFont(size=11),
        text_color="gray60",
    ).grid(row=0, column=2, padx=(0, 12), pady=10)

    w["rcon_connect_btn"] = ctk.CTkButton(
        conn_bar, text="🔌 Conectar", width=120, height=30,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=lambda: app._rcon_connect(sid),
    )
    w["rcon_connect_btn"].grid(row=0, column=3, padx=(0, 14), pady=10)

    # ── Log Output ──────────────────────────────────────────────────────────
    w["rcon_output"] = ctk.CTkTextbox(
        parent, font=ctk.CTkFont(family="Courier New", size=12),
        wrap="word", state="disabled", fg_color="#0a0a14",
    )
    w["rcon_output"].grid(row=1, column=0, padx=12, pady=4, sticky="nsew")
    tw = w["rcon_output"]._textbox
    tw.tag_config("cmd",  foreground="#88d4a0", font=("Courier New", 12, "bold"))
    tw.tag_config("resp", foreground="#d0d0e0")
    tw.tag_config("err",  foreground="#ff6666", font=("Courier New", 12, "bold"))
    tw.tag_config("sys",  foreground="#888899", font=("Courier New", 11, "italic"))
    tw.tag_config("ts",   foreground="#555566")

    # ── Barra de Atalhos + Limpar Log ───────────────────────────────────────
    shortcuts_frame = ctk.CTkFrame(parent, corner_radius=8, fg_color=_CARD_BG)
    shortcuts_frame.grid(row=2, column=0, padx=12, pady=(2, 2), sticky="ew")

    common_cmds = [
        ("💾 SaveWorld",        "SaveWorld"),
        ("👥 ListPlayers",      "ListPlayers"),
        ("💬 GetChat",          "GetChat"),
        ("🦕 DestroyWildDinos", "DestroyWildDinos"),
        ("⚠ DoExit",            "DoExit"),
    ]
    for ci, (lbl, cmd) in enumerate(common_cmds):
        ctk.CTkButton(
            shortcuts_frame, text=lbl, width=140, height=28,
            fg_color="#2a2a44", hover_color="#3a3a5a",
            font=ctk.CTkFont(size=11),
            command=lambda c=cmd, s=sid: app._rcon_exec(s, c),
        ).grid(row=0, column=ci, padx=4, pady=6)

    # Botão Limpar Log (alinhado à direita na shortcuts bar)
    shortcuts_frame.grid_columnconfigure(len(common_cmds), weight=1)
    def _clear_log(s: str = sid) -> None:
        box = app._server_widgets.get(s, {}).get("rcon_output")
        if box:
            box.configure(state="normal")
            box._textbox.delete("1.0", "end")
            box.configure(state="disabled")
    ctk.CTkButton(
        shortcuts_frame, text="🗑 Limpar", width=80, height=28,
        fg_color="#3a2a2a", hover_color="#5a3a3a",
        font=ctk.CTkFont(size=11),
        command=_clear_log,
    ).grid(row=0, column=len(common_cmds) + 1, padx=(0, 8), pady=6, sticky="e")

    # ── Linha de Broadcast ──────────────────────────────────────────────────
    bc_row = ctk.CTkFrame(parent, corner_radius=8, fg_color=_CARD_BG)
    bc_row.grid(row=3, column=0, padx=12, pady=(2, 2), sticky="ew")
    bc_row.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(bc_row, text="📢 Broadcast:", text_color="gray60",
                 font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(12, 8), pady=8)

    w["rcon_broadcast_var"] = tk.StringVar()
    bc_entry = ctk.CTkEntry(
        bc_row, textvariable=w["rcon_broadcast_var"], height=30,
        placeholder_text="Mensagem para todos os jogadores online...",
    )
    bc_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=8)

    def _do_broadcast(s: str = sid) -> None:
        msg = w["rcon_broadcast_var"].get().strip()
        if not msg:
            return
        w["rcon_broadcast_var"].set("")
        app._rcon_exec(s, f"Broadcast {msg}")
    bc_entry.bind("<Return>", lambda e: _do_broadcast())
    ctk.CTkButton(
        bc_row, text="Enviar 📢", width=100, height=30,
        fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=_do_broadcast,
    ).grid(row=0, column=2, padx=(0, 12), pady=8)

    # ── Linha de Input de Comando ───────────────────────────────────────────
    input_row = ctk.CTkFrame(parent, fg_color="transparent")
    input_row.grid(row=4, column=0, padx=12, pady=(2, 12), sticky="ew")
    input_row.grid_columnconfigure(0, weight=1)

    w["rcon_input"] = tk.StringVar()
    input_entry = ctk.CTkEntry(
        input_row, textvariable=w["rcon_input"], height=36,
        placeholder_text="Comando RCON (↑↓ = histórico)...",
    )
    input_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

    def _send(s: str = sid) -> None:
        cmd = w["rcon_input"].get().strip()
        if not cmd:
            return
        # Registra no histórico (sem duplicatas consecutivas)
        hist = w["_rcon_history"]
        if not hist or hist[-1] != cmd:
            hist.append(cmd)
            if len(hist) > _HISTORY_LIMIT:
                hist.pop(0)
        w["_rcon_hist_idx"][0] = -1  # reset do cursor no histórico
        app._rcon_send(s)

    input_entry.bind("<Return>",  lambda e: _send())

    def _hist_up(event: tk.Event) -> str:
        hist = w["_rcon_history"]
        if not hist:
            return "break"
        idx = w["_rcon_hist_idx"][0]
        if idx == -1:
            idx = len(hist) - 1
        elif idx > 0:
            idx -= 1
        w["_rcon_hist_idx"][0] = idx
        w["rcon_input"].set(hist[idx])
        input_entry.icursor("end")
        return "break"

    def _hist_down(event: tk.Event) -> str:
        hist = w["_rcon_history"]
        idx  = w["_rcon_hist_idx"][0]
        if idx == -1 or not hist:
            return "break"
        if idx < len(hist) - 1:
            idx += 1
            w["_rcon_hist_idx"][0] = idx
            w["rcon_input"].set(hist[idx])
        else:
            w["_rcon_hist_idx"][0] = -1
            w["rcon_input"].set("")
        input_entry.icursor("end")
        return "break"

    input_entry.bind("<Up>",   _hist_up)
    input_entry.bind("<Down>", _hist_down)

    ctk.CTkButton(
        input_row, text="Enviar ▶", width=90, height=36,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=lambda s=sid: _send(s),
    ).grid(row=0, column=1)

