from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _GREEN_DARK, _GREEN_HOVER, _BLUE, _BLUE_HOVER, _CARD_BG

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig


def build_tab_backup(app: "ARKServerManagerApp", parent, srv: "ServerConfig") -> None:  # noqa: C901
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(1, weight=1)

    w = app._server_widgets[srv.id]

    _interval_opts = ["1h", "2h", "3h", "6h", "12h", "24h"]
    _interval_map  = {1: "1h", 2: "2h", 3: "3h", 6: "6h", 12: "12h", 24: "24h"}

    # ── Card: configurações ───────────────────────────────────────────
    cfg_card = ctk.CTkFrame(parent, corner_radius=10, fg_color=_CARD_BG)
    cfg_card.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
    cfg_card.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        cfg_card, text="💾  Backup Automático",
        font=ctk.CTkFont(size=14, weight="bold"),
    ).grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 4), sticky="w")

    def _lbl(parent_w, text: str, hint: str) -> ctk.CTkFrame:
        fr = ctk.CTkFrame(parent_w, fg_color="transparent")
        ctk.CTkLabel(fr, text=text, width=190, anchor="w",
                     text_color="gray65",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(fr, text=hint, width=190, anchor="w",
                     text_color="gray40",
                     font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))
        return fr

    # Habilitar
    w["backup_enabled"] = tk.BooleanVar(value=srv.backup_enabled)
    _lbl(cfg_card,
         "Habilitar backup automático",
         "Cria backups em segundo plano no intervalo definido."
         ).grid(row=1, column=0, padx=(16, 8), pady=(4, 0), sticky="w")
    ctk.CTkSwitch(
        cfg_card, text="",
        variable=w["backup_enabled"],
    ).grid(row=1, column=1, padx=(0, 16), pady=(4, 0), sticky="w")

    # Intervalo
    w["backup_interval"] = tk.StringVar(value=_interval_map.get(srv.backup_interval_hours, "6h"))
    _lbl(cfg_card,
         "Intervalo entre backups",
         "Com que frequência o backup automático será executado."
         ).grid(row=2, column=0, padx=(16, 8), pady=(4, 0), sticky="w")
    ctk.CTkOptionMenu(
        cfg_card, values=_interval_opts,
        variable=w["backup_interval"], width=110, height=32,
    ).grid(row=2, column=1, padx=(0, 16), pady=4, sticky="w")

    # Manter últimos N backups
    w["backup_keep"] = tk.StringVar(value=str(srv.backup_keep_count))
    _lbl(cfg_card,
         "Manter últimos N backups",
         "Backups mais antigos são excluídos automaticamente."
         ).grid(row=3, column=0, padx=(16, 8), pady=(4, 0), sticky="w")
    ctk.CTkEntry(cfg_card, textvariable=w["backup_keep"], width=80, height=32).grid(
        row=3, column=1, padx=(0, 16), pady=4, sticky="w")

    # O que incluir
    w["backup_inc_saves"]  = tk.BooleanVar(value=srv.backup_include_saves)
    w["backup_inc_config"] = tk.BooleanVar(value=srv.backup_include_config)
    _lbl(cfg_card,
         "O que incluir no backup",
         "Saves = dados de jogadores/mundo.  Config = arquivos .ini."
         ).grid(row=4, column=0, padx=(16, 8), pady=(4, 0), sticky="w")
    chk_row = ctk.CTkFrame(cfg_card, fg_color="transparent")
    chk_row.grid(row=4, column=1, padx=(0, 16), pady=4, sticky="w")
    ctk.CTkCheckBox(chk_row, text="Saves",  variable=w["backup_inc_saves"],  width=100).pack(side="left")
    ctk.CTkCheckBox(chk_row, text="Config", variable=w["backup_inc_config"], width=100).pack(side="left", padx=(8, 0))

    # Pasta personalizada
    w["backup_dir"] = tk.StringVar(value=srv.backup_dir)
    _lbl(cfg_card,
         "Pasta de destino",
         "Deixe vazio para usar o padrão em %APPDATA%."
         ).grid(row=5, column=0, padx=(16, 8), pady=(4, 6), sticky="w")
    dir_fr = ctk.CTkFrame(cfg_card, fg_color="transparent")
    dir_fr.grid(row=5, column=1, padx=(0, 16), pady=(4, 6), sticky="ew")
    dir_fr.grid_columnconfigure(0, weight=1)
    ctk.CTkEntry(
        dir_fr, textvariable=w["backup_dir"], height=32,
        placeholder_text="Padrão: %APPDATA%\\ARKLAND-ServerManager\\backups\\",
    ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
    ctk.CTkButton(
        dir_fr, text="📁", width=34, height=32,
        command=lambda: app._browse_dir(w["backup_dir"]),
    ).grid(row=0, column=1)

    # Botões Salvar + Backup Manual
    btn_row = ctk.CTkFrame(cfg_card, fg_color="transparent")
    btn_row.grid(row=6, column=0, columnspan=2, padx=12, pady=(4, 14), sticky="w")
    ctk.CTkButton(
        btn_row, text="💾  Salvar Configurações",
        height=36, fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=lambda: app._save_backup_config(srv.id),
    ).pack(side="left", padx=(4, 8))
    ctk.CTkButton(
        btn_row, text="📸  Fazer Backup Agora",
        height=36, fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=lambda: app._do_manual_backup(srv.id),
    ).pack(side="left")

    # ── Card: lista de backups ────────────────────────────────────────
    list_card = ctk.CTkFrame(parent, corner_radius=10, fg_color=_CARD_BG)
    list_card.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
    list_card.grid_columnconfigure(0, weight=1)
    list_card.grid_rowconfigure(1, weight=1)

    hdr2 = ctk.CTkFrame(list_card, fg_color="transparent")
    hdr2.grid(row=0, column=0, padx=16, pady=(12, 4), sticky="ew")
    hdr2.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(hdr2, text="📂  Backups Disponíveis",
                 font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w")
    ctk.CTkButton(
        hdr2, text="🔄 Atualizar", width=100, height=28,
        fg_color="#3a3a5a", hover_color="#252540",
        command=lambda: app._refresh_backup_list(srv.id),
    ).grid(row=0, column=1, sticky="e")

    scroll = ctk.CTkScrollableFrame(list_card, fg_color="transparent")
    scroll.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
    scroll.grid_columnconfigure(0, weight=1)
    w["_backup_list_frame"] = scroll

    app._refresh_backup_list(srv.id)

