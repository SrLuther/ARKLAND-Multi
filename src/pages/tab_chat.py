from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]
import sys

from ..ui_constants import (
    _GREEN_DARK, _GREEN_HOVER, _BLUE, _BLUE_HOVER,
    _SIDEBAR_BG, _CARD_BG, _BG,
)

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig


def build_tab_chat(app: "ARKServerManagerApp", parent, srv: "ServerConfig") -> None:  # noqa: C901
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=1)

    w = app._server_widgets[srv.id]

    sub = ctk.CTkTabview(parent, fg_color=_BG,
                         segmented_button_fg_color=_SIDEBAR_BG,
                         segmented_button_selected_color=_GREEN_DARK,
                         segmented_button_selected_hover_color=_GREEN_HOVER,
                         segmented_button_unselected_color=_SIDEBAR_BG,
                         segmented_button_unselected_hover_color=_CARD_BG)
    sub.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
    sub.add("📢 Broadcasts")
    sub.add("💬 Chat ao vivo")

    # ══════════════════════════════════════════════════════════════════════
    # Sub-aba: Broadcasts
    # ══════════════════════════════════════════════════════════════════════
    bt = sub.tab("📢 Broadcasts")
    bt.grid_columnconfigure(0, weight=1)
    bt.grid_rowconfigure(2, weight=1)

    # ── Barra de envio rápido ─────────────────────────────────────────────
    quick_bar = ctk.CTkFrame(bt, fg_color=_CARD_BG, corner_radius=8)
    quick_bar.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 3))
    quick_bar.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(quick_bar, text="📡 Envio rápido:",
                 text_color="gray55", font=ctk.CTkFont(size=12, weight="bold")
                 ).grid(row=0, column=0, padx=(12, 8), pady=8, sticky="w")

    w["bc_quick_var"] = tk.StringVar()
    ctk.CTkEntry(quick_bar, textvariable=w["bc_quick_var"], height=32,
                 placeholder_text="Mensagem de broadcast — todos os jogadores online verão",
                 font=ctk.CTkFont(size=11)
                 ).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=8)

    ctk.CTkButton(quick_bar, text="📢 Enviar", width=100, height=32,
                  fg_color=_BLUE, hover_color=_BLUE_HOVER,
                  font=ctk.CTkFont(size=11),
                  command=lambda: app._broadcast_send_quick(srv.id)
                  ).grid(row=0, column=2, padx=(0, 4), pady=8)

    ctk.CTkButton(quick_bar, text="🔧 Testar RCON", width=120, height=32,
                  fg_color="#3a3a5a", hover_color="#4a4a7a",
                  font=ctk.CTkFont(size=11),
                  command=lambda: app._broadcast_test(srv.id)
                  ).grid(row=0, column=3, padx=(0, 10), pady=8)

    # ── Formulário: adicionar novo broadcast à biblioteca ─────────────────
    add_fr = ctk.CTkFrame(bt, fg_color=_CARD_BG, corner_radius=8)
    add_fr.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 3))
    add_fr.grid_columnconfigure(1, weight=1)
    add_fr.grid_columnconfigure(2, weight=3)

    ctk.CTkLabel(add_fr, text="+ Novo:",
                 text_color="gray55", font=ctk.CTkFont(size=12, weight="bold")
                 ).grid(row=0, column=0, padx=(12, 8), pady=(8, 7), sticky="w")

    w["bc_new_label"] = tk.StringVar()
    ctk.CTkEntry(add_fr, textvariable=w["bc_new_label"], height=30,
                 placeholder_text="Rótulo (ex: Reinício em 5min)",
                 font=ctk.CTkFont(size=11), width=180
                 ).grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=(8, 7))

    w["bc_new_msg"] = tk.StringVar()
    ctk.CTkEntry(add_fr, textvariable=w["bc_new_msg"], height=30,
                 placeholder_text="Texto do broadcast...",
                 font=ctk.CTkFont(size=11)
                 ).grid(row=0, column=2, sticky="ew", padx=(0, 6), pady=(8, 7))

    ctk.CTkButton(add_fr, text="Adicionar", width=90, height=30,
                  fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  font=ctk.CTkFont(size=11),
                  command=lambda: app._broadcast_add(srv.id)
                  ).grid(row=0, column=3, padx=(0, 10), pady=(8, 7))

    # ── Lista de broadcasts salvos ────────────────────────────────────────
    list_hdr = ctk.CTkFrame(bt, fg_color="transparent")
    list_hdr.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 6))
    list_hdr.grid_columnconfigure(0, weight=1)
    list_hdr.grid_rowconfigure(1, weight=1)

    ctk.CTkLabel(list_hdr, text="Biblioteca de Broadcasts",
                 text_color="gray45", font=ctk.CTkFont(size=11, weight="bold")
                 ).grid(row=0, column=0, sticky="w", padx=2, pady=(2, 2))

    bc_scroll = ctk.CTkScrollableFrame(list_hdr, fg_color=_CARD_BG, corner_radius=8)
    bc_scroll.grid(row=1, column=0, sticky="nsew")
    bc_scroll.grid_columnconfigure(0, weight=1)
    w["bc_list_scroll"] = bc_scroll

    # Carrega broadcasts existentes
    app._broadcast_refresh_list(srv.id)

    # ══════════════════════════════════════════════════════════════════════
    # Sub-aba: Chat ao vivo
    # ══════════════════════════════════════════════════════════════════════
    ct = sub.tab("💬 Chat ao vivo")
    ct.grid_columnconfigure(0, weight=1)
    ct.grid_rowconfigure(1, weight=1)

    # Barra de controle
    ctrl = ctk.CTkFrame(ct, corner_radius=10, fg_color=_CARD_BG)
    ctrl.grid(row=0, column=0, padx=6, pady=(6, 4), sticky="ew")
    ctrl.grid_columnconfigure(3, weight=1)

    w["chat_auto_poll"] = tk.BooleanVar(value=False)
    ctk.CTkCheckBox(
        ctrl, text="Auto-atualizar",
        variable=w["chat_auto_poll"],
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        checkmark_color="white",
        command=lambda: app._chat_toggle_poll(srv.id),
    ).grid(row=0, column=0, padx=(14, 8), pady=10)

    ctk.CTkLabel(ctrl, text="Intervalo:", text_color="gray60").grid(
        row=0, column=1, padx=(0, 4), pady=10)
    w["chat_interval"] = tk.StringVar(value="5")
    ctk.CTkOptionMenu(
        ctrl, variable=w["chat_interval"],
        values=["3", "5", "10", "15", "30"], width=70,
    ).grid(row=0, column=2, padx=(0, 2), pady=10, sticky="w")
    ctk.CTkLabel(ctrl, text="seg", text_color="gray50").grid(
        row=0, column=3, padx=(0, 16), pady=10, sticky="w")

    w["chat_status_var"] = tk.StringVar(value="⬛ Inativo")
    ctk.CTkLabel(ctrl, textvariable=w["chat_status_var"],
                 text_color="gray50", font=ctk.CTkFont(size=12)).grid(
        row=0, column=4, padx=8, pady=10, sticky="w")

    ctk.CTkButton(
        ctrl, text="🔄 Buscar", width=100, height=30,
        fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=lambda: app._chat_fetch(srv.id),
    ).grid(row=0, column=5, padx=(0, 6), pady=10)
    ctk.CTkButton(
        ctrl, text="🗑 Limpar", width=90, height=30,
        fg_color="#3a3a5a", hover_color="#252540",
        command=lambda: app._chat_clear(srv.id),
    ).grid(row=0, column=6, padx=(0, 14), pady=10)

    # Exibição do chat
    w["chat_box"] = ctk.CTkTextbox(
        ct, font=ctk.CTkFont(family="Courier New", size=12),
        wrap="word", state="disabled", fg_color="#0a0a14",
    )
    w["chat_box"].grid(row=1, column=0, padx=6, pady=4, sticky="nsew")
    tw = w["chat_box"]._textbox
    tw.tag_config("ts",      foreground="#555570")
    tw.tag_config("player",  foreground="#88d4a0")
    tw.tag_config("server",  foreground="#6699ff")
    tw.tag_config("message", foreground="#d0d0e0")
    tw.tag_config("sys",     foreground="#888899")
    tw.tag_config("err",     foreground="#ff6666")
    app._chat_append(
        srv.id,
        "💬  Chat do Servidor — requer RCON conectado (aba 'Console RCON').\n"
        "Ative 'Auto-atualizar' ou clique em '🔄 Buscar' para carregar mensagens.\n",
        "sys",
    )

    # Campo de envio
    input_row = ctk.CTkFrame(ct, fg_color="transparent")
    input_row.grid(row=2, column=0, padx=6, pady=(2, 8), sticky="ew")
    input_row.grid_columnconfigure(0, weight=1)

    w["chat_input"] = tk.StringVar()
    inp = ctk.CTkEntry(
        input_row, textvariable=w["chat_input"], height=36,
        placeholder_text="Mensagem para enviar como [SERVIDOR] via ServerChat — pressione Enter para enviar...",
    )
    inp.grid(row=0, column=0, sticky="ew", padx=(0, 8))
    inp.bind("<Return>", lambda e: app._chat_send(srv.id))

    ctk.CTkButton(
        input_row, text="Enviar ▶", width=90, height=36,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=lambda: app._chat_send(srv.id),
    ).grid(row=0, column=1)

