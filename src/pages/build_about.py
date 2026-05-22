from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _GREEN, _GREEN_DARK, _GREEN_HOVER, _BLUE, _BLUE_HOVER, _CARD_BG
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..version import APP_VERSION, BUILD_DATE, CHANGELOG

APP_NAME = "ARKLAND - Server Manager"


def build_about(app: "ARKServerManagerApp", parent) -> None:
    parent.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(parent, text="Sobre & Atualizações",
                 font=ctk.CTkFont(size=24, weight="bold")).grid(
        row=0, column=0, padx=24, pady=(24, 2), sticky="w")
    ctk.CTkLabel(parent, text="Informações do aplicativo e gerenciamento de atualizações.",
                 text_color="gray60").grid(row=1, column=0, padx=24, pady=(0, 18), sticky="w")

    app._section_lbl(parent, 2, "📦  Aplicativo")
    info_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    info_card.grid(row=3, column=0, padx=20, pady=(0, 14), sticky="ew")
    info_card.grid_columnconfigure(1, weight=1)
    for rn, (lbl, val, bold) in enumerate([
        ("Nome:",         APP_NAME,          False),
        ("Versão atual:", f"v{APP_VERSION}", True),
        ("Build:",        BUILD_DATE,        False),
    ]):
        ctk.CTkLabel(info_card, text=lbl, width=160, anchor="w",
                     text_color="gray60").grid(row=rn, column=0, padx=18, pady=8)
        ctk.CTkLabel(info_card, text=val, anchor="w",
                     font=ctk.CTkFont(weight="bold" if bold else "normal"),
                     text_color=_GREEN if bold else "#d8d8e8").grid(
            row=rn, column=1, padx=(0, 18), pady=8, sticky="w")

    app._section_lbl(parent, 4, "🔄  Atualização")
    upd_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    upd_card.grid(row=5, column=0, padx=20, pady=(0, 14), sticky="ew")
    upd_card.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(upd_card, text="Status:", width=160, anchor="w",
                 text_color="gray60").grid(row=0, column=0, padx=18, pady=(18, 6))
    app._update_status_var = tk.StringVar(value="Não verificado")
    app._update_status_lbl = ctk.CTkLabel(upd_card, textvariable=app._update_status_var,
                                           font=ctk.CTkFont(weight="bold"), text_color="gray50")
    app._update_status_lbl.grid(row=0, column=1, padx=(0, 18), pady=(18, 6), sticky="w")

    ctk.CTkLabel(upd_card, text="Última verificação:", width=160, anchor="w",
                 text_color="gray60").grid(row=1, column=0, padx=18, pady=(0, 10))
    app._last_check_var = tk.StringVar(value="Nunca")
    ctk.CTkLabel(upd_card, textvariable=app._last_check_var,
                 text_color="#d8d8e8").grid(row=1, column=1, padx=(0, 18), sticky="w")

    btn_row = ctk.CTkFrame(upd_card, fg_color="transparent")
    btn_row.grid(row=2, column=0, columnspan=2, padx=18, pady=(4, 14), sticky="w")
    app._check_update_btn = ctk.CTkButton(
        btn_row, text="🔍  Verificar Atualizações", width=210, height=40,
        fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=app._check_updates_manual,
    )
    app._check_update_btn.pack(side="left", padx=(0, 10))
    app._install_update_btn = ctk.CTkButton(
        btn_row, text="⬇️  Baixar e Instalar", width=190, height=40,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER, state="disabled",
        command=app._start_download_update,
    )
    app._install_update_btn.pack(side="left")

    app._update_progress       = ctk.CTkProgressBar(upd_card, width=420, height=14)
    app._update_progress.set(0)
    app._update_progress_label = ctk.CTkLabel(upd_card, text="", text_color="gray60",
                                               font=ctk.CTkFont(size=11))

    app._section_lbl(parent, 6, "📝  Histórico de Versões")
    cl_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    cl_card.grid(row=7, column=0, padx=20, pady=(0, 24), sticky="ew")
    cl_card.grid_columnconfigure(0, weight=1)
    cl_text = ctk.CTkTextbox(cl_card, font=ctk.CTkFont(family="Courier New", size=12),
                             wrap="word", state="normal", height=200, fg_color="#161622")
    cl_text.grid(row=0, column=0, padx=12, pady=12, sticky="ew")
    tw = cl_text._textbox
    tw.tag_config("ver",  foreground="#4CAF50", font=("Courier New", 13, "bold"))
    tw.tag_config("date", foreground="#888899")
    tw.tag_config("item", foreground="#c0c0d8")
    for entry in CHANGELOG:
        tw.insert("end", f"v{entry.get('version', '?')}", "ver")
        if entry.get("date"):
            tw.insert("end", f"  ·  {entry['date']}\n", "date")
        else:
            tw.insert("end", "\n")
        for change in entry.get("changes", []):
            tw.insert("end", f"  • {change}\n", "item")
        tw.insert("end", "\n")
    cl_text.configure(state="disabled")

