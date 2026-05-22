from __future__ import annotations

import threading
import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import (
    _GREEN, _GREEN_DARK, _GREEN_HOVER,
    _RED_DARK, _RED_HOVER,
    _BLUE, _BLUE_HOVER,
    _CARD_BG, _BG,
)

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def open_remote_control(app: "ARKServerManagerApp", inst: dict) -> None:  # noqa: C901

    """Abre janela de controle remoto para uma máquina."""
    host  = inst.get("host", "")
    port  = inst.get("port", 32440)
    token = inst.get("token", "")
    name  = inst.get("name", "Remoto")

    win = tk.Toplevel(app)
    win.title(f"🖥️  {name}  —  {host}:{port}")
    win.geometry("860x600")
    win.configure(bg=_BG)

    client = RemoteClient(host, port, token, timeout=6.0)
    _stop_polling = threading.Event()

    # ── Header ──────────────────────────────────────────────────────────
    hdr = ctk.CTkFrame(win, corner_radius=0, fg_color=_CARD_BG, height=50)
    hdr.pack(fill="x", side="top")
    hdr.pack_propagate(False)
    ctk.CTkLabel(hdr, text=f"🖥️  {name}",
                 font=ctk.CTkFont(size=16, weight="bold")).pack(
        side="left", padx=16, pady=10)
    conn_var = tk.StringVar(value="🟡 Conectando...")
    ctk.CTkLabel(hdr, textvariable=conn_var,
                 font=ctk.CTkFont(size=11), text_color="gray60").pack(
        side="left", padx=8)
    version_var = tk.StringVar(value="")
    ctk.CTkLabel(hdr, textvariable=version_var,
                 font=ctk.CTkFont(size=10), text_color="gray50").pack(
        side="left", padx=4)

    # ── Body: painel esquerdo (servers) + direito (logs) ─────────────────
    body = ctk.CTkFrame(win, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=12, pady=12)
    body.grid_columnconfigure(0, weight=1)
    body.grid_columnconfigure(1, weight=1)
    body.grid_rowconfigure(0, weight=1)

    # Servers panel
    srv_outer = ctk.CTkFrame(body, corner_radius=10, fg_color=_CARD_BG)
    srv_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    srv_outer.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(srv_outer, text="Servidores",
                 font=ctk.CTkFont(size=13, weight="bold")).grid(
        row=0, column=0, padx=14, pady=(10, 4), sticky="w")
    srv_scroll = ctk.CTkScrollableFrame(srv_outer, fg_color="transparent")
    srv_scroll.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 8))
    srv_scroll.grid_columnconfigure(0, weight=1)
    srv_outer.grid_rowconfigure(1, weight=1)

    # Log panel
    log_outer = ctk.CTkFrame(body, corner_radius=10, fg_color=_CARD_BG)
    log_outer.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
    log_outer.grid_columnconfigure(0, weight=1)
    log_outer.grid_rowconfigure(1, weight=1)

    log_hdr = ctk.CTkFrame(log_outer, fg_color="transparent")
    log_hdr.grid(row=0, column=0, padx=14, pady=(10, 4), sticky="ew")
    log_hdr.grid_columnconfigure(0, weight=1)
    app._remote_log_title_var = tk.StringVar(value="Log — selecione um servidor")
    ctk.CTkLabel(log_hdr, textvariable=app._remote_log_title_var,
                 font=ctk.CTkFont(size=13, weight="bold")).grid(
        row=0, column=0, sticky="w")

    log_txt = tk.Text(
        log_outer, bg="#0d0d14", fg="#c8dff8",
        font=("Consolas", 9), relief="flat", wrap="word",
        state="disabled",
    )
    log_txt.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 8))
    log_sb = ctk.CTkScrollbar(log_outer, command=log_txt.yview)
    log_sb.grid(row=1, column=1, sticky="ns", pady=(0, 8))
    log_txt.configure(yscrollcommand=log_sb.set)

    # RCON input
    rcon_fr = ctk.CTkFrame(log_outer, fg_color="transparent")
    rcon_fr.grid(row=2, column=0, columnspan=2, padx=6, pady=(0, 8), sticky="ew")
    rcon_fr.grid_columnconfigure(0, weight=1)
    rcon_var = tk.StringVar()
    rcon_entry = ctk.CTkEntry(rcon_fr, textvariable=rcon_var, height=28,
                               placeholder_text="Comando RCON...")
    rcon_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
    _selected_srv_id: list = [None]  # mutable container

    def _send_rcon(event=None) -> None:
        cmd  = rcon_var.get().strip()
        sid  = _selected_srv_id[0]
        if not cmd or not sid:
            return
        rcon_var.set("")

        def _do() -> None:
            res = client.send_rcon(sid, cmd)
            resp = res.get("response") or res.get("error") or "—"
            win.after(0, lambda: _append_log(f"[RCON] > {cmd}\n{resp}"))
        threading.Thread(target=_do, daemon=True).start()

    rcon_entry.bind("<Return>", _send_rcon)
    ctk.CTkButton(rcon_fr, text="↵", width=28, height=28,
                  command=_send_rcon).grid(row=0, column=1)

    def _append_log(text: str) -> None:
        log_txt.configure(state="normal")
        log_txt.insert("end", text + "\n")
        log_txt.configure(state="disabled")
        log_txt.see("end")

    def _load_logs(sid: str, sname: str) -> None:
        _selected_srv_id[0] = sid
        app._remote_log_title_var.set(f"Log — {sname}")
        log_txt.configure(state="normal")
        log_txt.delete("1.0", "end")
        log_txt.configure(state="disabled")

        def _do() -> None:
            res = client.get_server_logs(sid, 200)
            lines = res.get("logs", [])
            win.after(0, lambda: _append_log("\n".join(lines)))
        threading.Thread(target=_do, daemon=True).start()

    # Server cards builder
    _srv_widgets: dict = {}

    def _rebuild_servers(servers: list) -> None:
        existing_ids = {w["id"] for w in _srv_widgets.values()} if _srv_widgets else set()
        new_ids      = {s["id"] for s in servers}

        # Remove cards que sumiram
        for sid in list(_srv_widgets.keys()):
            if sid not in new_ids:
                _srv_widgets[sid]["frame"].destroy()
                del _srv_widgets[sid]

        _STATUS_COLORS_R = {
            "stopped": "#ff6666", "starting": "#ffaa44",
            "running": _GREEN,    "stopping": "#ffaa44",
            "crashed": "#ff3333", "updating": "#ffaa44",
        }
        _STATUS_LABELS_R = {
            "stopped": "⬛ PARADO",  "starting": "🟡 INICIANDO",
            "running": "🟢 RODANDO", "stopping": "🟡 PARANDO",
            "crashed": "🔴 TRAVADO", "updating": "🟡 ATUALIZANDO",
        }

        for i, srv in enumerate(servers):
            sid     = srv["id"]
            sname   = srv.get("name", "?")
            status  = srv.get("status", "stopped")
            uptime  = srv.get("uptime", "—")

            if sid not in _srv_widgets:
                # Cria novo card
                c = ctk.CTkFrame(srv_scroll, corner_radius=8, fg_color="#151520")
                c.grid(row=i, column=0, sticky="ew", padx=4, pady=3)
                c.grid_columnconfigure(0, weight=1)

                ctk.CTkLabel(c, text=sname,
                             font=ctk.CTkFont(size=12, weight="bold")).grid(
                    row=0, column=0, padx=10, pady=(8, 0), sticky="w")
                sv = tk.StringVar(value=_STATUS_LABELS_R.get(status, status))
                sl = ctk.CTkLabel(c, textvariable=sv,
                                  font=ctk.CTkFont(size=11),
                                  text_color=_STATUS_COLORS_R.get(status, "gray"))
                sl.grid(row=1, column=0, padx=10, pady=(0, 4), sticky="w")
                uv = tk.StringVar(value=f"Uptime: {uptime}")
                ctk.CTkLabel(c, textvariable=uv, text_color="gray55",
                             font=ctk.CTkFont(size=10)).grid(
                    row=2, column=0, padx=10, pady=(0, 4), sticky="w")

                btns = ctk.CTkFrame(c, fg_color="transparent")
                btns.grid(row=3, column=0, padx=8, pady=(0, 8), sticky="w")

                def _mk_start(s=sid): return lambda: _remote_action(s, "start")
                def _mk_stop(s=sid): return lambda: _remote_action(s, "stop")
                def _mk_restart(s=sid): return lambda: _remote_action(s, "restart")
                def _mk_log(s=sid, n=sname): return lambda: _load_logs(s, n)

                ctk.CTkButton(btns, text="▶", width=32, height=28,
                              fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                              command=_mk_start()).pack(side="left", padx=2)
                ctk.CTkButton(btns, text="⏹", width=32, height=28,
                              fg_color=_RED_DARK, hover_color=_RED_HOVER,
                              command=_mk_stop()).pack(side="left", padx=2)
                ctk.CTkButton(btns, text="🔄", width=32, height=28,
                              fg_color=_BLUE, hover_color=_BLUE_HOVER,
                              command=_mk_restart()).pack(side="left", padx=2)
                ctk.CTkButton(btns, text="📋", width=32, height=28,
                              fg_color="#2a2a44", hover_color="#3a3a54",
                              command=_mk_log()).pack(side="left", padx=2)

                _srv_widgets[sid] = {
                    "id": sid, "frame": c,
                    "status_var": sv, "status_lbl": sl,
                    "uptime_var": uv,
                }
            else:
                # Atualiza existente
                w = _srv_widgets[sid]
                lbl = _STATUS_LABELS_R.get(status, status)
                col = _STATUS_COLORS_R.get(status, "gray")
                w["status_var"].set(lbl)
                w["status_lbl"].configure(text_color=col)
                w["uptime_var"].set(f"Uptime: {uptime}")

    def _remote_action(sid: str, action: str) -> None:
        def _do() -> None:
            if action == "start":
                client.start_server(sid)
            elif action == "stop":
                client.stop_server(sid)
            elif action == "restart":
                client.restart_server(sid)
        threading.Thread(target=_do, daemon=True).start()

    # ── Polling ──────────────────────────────────────────────────────────
    def _poll() -> None:
        res = client.get_info()
        if "error" in res:
            win.after(0, lambda: conn_var.set(f"🔴 Erro: {res['error']}"))
        else:
            v     = res.get("version", "")
            srvs  = res.get("servers", [])
            win.after(0, lambda: conn_var.set("🟢 Conectado"))
            win.after(0, lambda: version_var.set(f"v{v}" if v else ""))
            win.after(0, lambda: _rebuild_servers(srvs))
        if not _stop_polling.is_set():
            win.after(3000, lambda: threading.Thread(
                target=_poll, daemon=True).start())

    def _on_close() -> None:
        _stop_polling.set()
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", _on_close)
    threading.Thread(target=_poll, daemon=True).start()

