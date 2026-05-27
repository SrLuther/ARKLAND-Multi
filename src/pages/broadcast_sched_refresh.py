"""Reconstrói a lista visual de broadcasts automáticos por intervalo."""
from __future__ import annotations

import time
import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk

from ..ui_constants import (
    _RED_DARK, _RED_HOVER, _BLUE, _BLUE_HOVER,
    _GREEN_DARK, _GREEN_HOVER, _CARD_BG,
)

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

_ROW_ON  = "#1e2235"
_ROW_OFF = "#181820"


def broadcast_sched_refresh(app: "ARKServerManagerApp", server_id: str) -> None:
    """Destrói e reconstrói todas as linhas da lista de auto-broadcasts."""
    w = app._server_widgets.get(server_id, {})
    scroll = w.get("bcs_list_scroll")
    if scroll is None or not scroll.winfo_exists():
        return

    # Limpa lista anterior
    for child in scroll.winfo_children():
        child.destroy()

    srv = app.config_manager.get_server(server_id)
    bcs = getattr(srv, "auto_broadcasts", []) if srv else []
    running = app._bc_sched_running.get(server_id, False)

    # Atualiza rótulo de status no header
    status_var: tk.StringVar | None = w.get("bcs_status_var")
    if status_var:
        if running:
            status_var.set("🟢 Ativo")
        else:
            status_var.set("⬛ Inativo")

    if not bcs:
        ctk.CTkLabel(
            scroll,
            text="Nenhum broadcast agendado.\nUse o formulário acima para adicionar.",
            text_color="gray40",
            font=ctk.CTkFont(size=11),
            justify="center",
        ).pack(pady=30)
        return

    now = time.time()

    # Cabeçalho das colunas
    hdr = ctk.CTkFrame(scroll, fg_color="transparent")
    hdr.pack(fill="x", padx=6, pady=(4, 2))
    hdr.columnconfigure(2, weight=1)
    _hcols = [
        ("",            30),
        ("Rótulo",     140),
        ("Mensagem",     0),
        ("Intervalo",   88),
        ("Próximo",    110),
        ("",            72),
    ]
    for col, (txt, w_) in enumerate(_hcols):
        kw = {"width": w_} if w_ else {}
        ctk.CTkLabel(
            hdr, text=txt,
            text_color="gray45",
            font=ctk.CTkFont(size=10, weight="bold"),
            anchor="w", **kw,
        ).grid(row=0, column=col, sticky="w", padx=(4, 2))

    for bc in bcs:
        bc_id    = bc.get("id", "")
        enabled  = bc.get("enabled", True)
        label    = bc.get("label", "—")
        msg      = bc.get("message", "")
        interval = int(bc.get("interval_min", 30))
        last     = float(bc.get("last_sent", 0.0))

        row_bg = _ROW_ON if enabled else _ROW_OFF
        row = ctk.CTkFrame(scroll, fg_color=row_bg, corner_radius=6)
        row.pack(fill="x", padx=6, pady=2)
        row.columnconfigure(2, weight=1)

        # ── Coluna 0: Checkbox ativado ────────────────────────────────
        var = tk.BooleanVar(value=enabled)
        ctk.CTkCheckBox(
            row, text="", variable=var, width=30,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            checkmark_color="white",
            command=lambda v=var, bid=bc_id, sid=server_id:
                app._bc_sched_toggle(sid, bid, v.get()),
        ).grid(row=0, column=0, padx=(8, 2), pady=8)

        # ── Coluna 1: Rótulo ──────────────────────────────────────────
        ctk.CTkLabel(
            row, text=label, width=140, anchor="w", wraplength=136,
            text_color="#a0a8d0" if enabled else "#505060",
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=1, sticky="w", padx=(2, 6), pady=8)

        # ── Coluna 2: Mensagem (truncada) ─────────────────────────────
        disp = msg if len(msg) <= 65 else msg[:62] + "…"
        ctk.CTkLabel(
            row, text=disp, anchor="w",
            text_color="gray55" if enabled else "gray35",
            font=ctk.CTkFont(size=11),
            wraplength=320,
        ).grid(row=0, column=2, sticky="ew", padx=(0, 6), pady=8)

        # ── Coluna 3: Intervalo ───────────────────────────────────────
        ctk.CTkLabel(
            row, text=f"⏱ {interval} min", width=88,
            text_color="#8888cc" if enabled else "#444455",
            font=ctk.CTkFont(size=10, weight="bold"),
        ).grid(row=0, column=3, padx=(0, 6), pady=8)

        # ── Coluna 4: Próximo envio ───────────────────────────────────
        if last == 0.0:
            next_txt   = "nunca enviado"
            next_color = "gray40"
        else:
            next_in = (last + interval * 60) - now
            if next_in <= 0:
                next_txt   = "⚡ aguardando tick"
                next_color = "#88cc88"
            else:
                mins = int(next_in // 60)
                secs = int(next_in % 60)
                next_txt   = f"em {mins}m {secs:02d}s"
                next_color = "#8899bb" if enabled else "gray35"

        ctk.CTkLabel(
            row, text=next_txt, width=110, anchor="w",
            text_color=next_color, font=ctk.CTkFont(size=10),
        ).grid(row=0, column=4, padx=(0, 6), pady=8)

        # ── Coluna 5: Botões ──────────────────────────────────────────
        btn_fr = ctk.CTkFrame(row, fg_color="transparent")
        btn_fr.grid(row=0, column=5, padx=(4, 8), pady=4)

        ctk.CTkButton(
            btn_fr, text="📢", width=30, height=26,
            fg_color=_BLUE, hover_color=_BLUE_HOVER,
            font=ctk.CTkFont(size=11),
            command=lambda bid=bc_id, sid=server_id:
                app._bc_sched_send_now(sid, bid),
        ).pack(side="left", padx=(0, 3))

        ctk.CTkButton(
            btn_fr, text="🗑", width=30, height=26,
            fg_color=_RED_DARK, hover_color=_RED_HOVER,
            font=ctk.CTkFont(size=11),
            command=lambda bid=bc_id, sid=server_id:
                app._bc_sched_delete(sid, bid),
        ).pack(side="left")
